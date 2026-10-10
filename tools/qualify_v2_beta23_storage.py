"""Deadline-bounded SRAM/WORK hardware regression with exact live restoration."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from serial.tools.list_ports import comports
from beta4_migration import Link, s19
from rtc_boards import SERIALS
from qualify_v2_spi_install import load_image, write
from qualify_v2_spi_storage import memory_request, workspace_request

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--board', choices=tuple(SERIALS), required=True)
    p.add_argument('--port', required=True)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--deadline-utc', required=True)
    a = p.parse_args(); deadline = datetime.fromisoformat(a.deadline_utc.replace('Z','+00:00')).timestamp()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    build = a.build; client = build/'hardware-client'
    cm = json.loads((client/'build.json').read_text()); ct = json.loads((client/'test-results.json').read_text())
    meta = json.loads((build/'build.json').read_text())
    assert ct['passed'] and ct['sha256']==cm['sha256']==sha((client/'client.bin').read_bytes())
    assert ct['resident_artifacts']==meta['artifacts'], 'Client model not bound to beta23'
    wm = json.loads((build/'workspace/build.json').read_text()); assert wm['api']==0x5003
    assert sha((build/'workspace/workspace.bin').read_bytes())==wm['sha256']
    out = a.root/'storage-workflow'; out.mkdir(exist_ok=False)
    original = None; mutated = False; checks = []
    report = dict(passed=False, board=a.board, checks=checks, clock_set=False, trim_changed=False,
                  flash_written=False, deadline_utc=a.deadline_utc, restored=False)
    with (out/'serial.jsonl').open('x') as log:
        link = Link(a.port,log)
        try:
            time.sleep(.3); first=link.command('',b'> ')
            if any(x in first for x in (b'CLOCK>',b'BM>',b'WORK>',b'SRAM>',b'EDU>')): link.command('Q')
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            flash=b''.join(link.dump(addr,addr+4095) for addr in range(0x8000,0x10000,4096))
            expected_flash=a.root/'prior/b3.bin' if (a.root/'prior/b3.bin').exists() else a.root/'reset-notice-check/b3.bin'
            assert flash==expected_flash.read_bytes(), 'B3 changed since qualification'
            load_image(link,client/'client.s19')
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                data=link.command(text,prompt)
                if label: (out/(label+'.txt')).write_bytes(data)
                return data
            def driver(op,address=0,privileged=False):
                write(link,0x3E20,bytes((1,3,0xA5 if privileged else 0)))
                write(link,0x3E00,memory_request(op,address))
                cmd('G 2003'); result=link.dump(0x3E10,0x3E38)
                assert result[8:10]==b'\0\x40' and result[0x23]==result[0x24]
                assert link.dump(0x66AE,0x66AE)==b'\x01'
            def array(label):
                parts=[]
                for i in range(16):
                    driver(1,i*8192); parts.append(link.dump(0x4000,0x5FFF))
                    print(a.board,label,i+1,'/16',flush=True)
                body=b''.join(parts); (out/(label+'.bin')).write_bytes(body); return body
            def load_work():
                load_image(link,client/'client.s19'); assert b'Done' in cmd('R 2 WORK L')
                assert link.dump(0x5006,0x5009)==b'WK\x01\x02'
            def work(req,expected=0,bank=3):
                write(link,0x3E21,bytes((bank,))); write(link,0x3E40,req)
                cmd('G 2006'); result=link.dump(0x3E60,0x3E7F); state=link.dump(0x3E30,0x3E38)
                assert state[3]==state[4] and state[8]==expected,(expected,state.hex())
                return result
            original=array('live-before')
            expected_sram=a.root/'sram-prior/array-0.bin' if (a.root/'sram-prior/array-0.bin').exists() else a.root/'sram-final/array-0.bin'
            assert original==expected_sram.read_bytes(), 'Live SRAM differs; stop before mutation'
            assert deadline-time.time()>300, 'Too close to deadline for mutation and full restoration'
            load_work(); mutated=True
            work(workspace_request(6,key=b'FORMAT!!'))
            for units in (1,2,3,4):
                r=work(workspace_request(5,units=units,key=b'RESIZE!!'))
                assert r[21]==units and int.from_bytes(r[18:21],'little')==0x1FFE0-units*0x4000
            _,h=0,work(workspace_request(1,size=512))[4:12]
            pattern=bytes(range(64)); write(link,0x2600,pattern)
            for bank in range(4):
                work(workspace_request(4,h,count=64),bank=bank)
                work(workspace_request(3,h,count=64,buffer=0x2700),bank=bank)
                assert link.dump(0x2700,0x273F)==pattern
            work(workspace_request(3,h,owner=1,count=1),expected=0x4B)
            work(workspace_request(3,h,count=1,offset=512),expected=0x44)
            work(workspace_request(5,units=1,key=b'RESIZE!!'))
            low=work(workspace_request(1,size=256))[4:12]
            work(workspace_request(5,units=4,key=b'RESIZE!!'),expected=0x4A)
            work(workspace_request(2,low)); work(workspace_request(5,units=4,key=b'RESIZE!!'))
            work(workspace_request(2,h)); work(workspace_request(3,h,count=1),expected=0x4B)
            checks.append('All four program-region sizes; all-bank claim read/write, owner/bounds checks, overlap refusal and release/stale handle')
            program=bytes.fromhex('EE 00 27 4C 67 7E'); write(link,0x2600,program); write(link,0x2700,b'\0')
            assert b'SRAM 1.2' in cmd('R SRAM',b'SRAM> ',label='sram-start')
            assert b'SRAM: 00' in cmd('S B23TEST 2600 2605 2600',b'SRAM> ',label='save')
            assert b'B23TEST' in cmd('T',b'SRAM> ',label='table')
            assert b'SRAM: 00' in cmd('R B23TEST',b'SRAM> ',label='restore')
            cmd('Q'); assert link.dump(0x2600,0x2605)==program
            cmd('R SRAM',b'SRAM> '); cmd('G B23TEST',label='run')
            assert link.dump(0x2700,0x2700)==b'\x01'
            cmd('R SRAM',b'SRAM> ')
            assert b'SRAM: 00' in cmd('D B23TEST',b'SRAM> ',label='delete')
            assert b'B23TEST' not in cmd('T',b'SRAM> ',label='deleted-table')
            assert b'SRAM: 00' in cmd('C',b'SRAM> ',label='reclaim'); cmd('Q')
            checks.append('Named SRAM save/table/restore/run/delete/tombstone/reclaim, original load address and actual execution')
            load_work(); h=work(workspace_request(1,size=256))[4:12]
            assert b'Done' in cmd('R 2 WORK L'); work(workspace_request(3,h,count=1))
            start=cmd('J3',b'Enter default [3s]: '); link.send(b'\r'); start+=link.until(b'\r\nB3> ')
            (out/'handle-cold-reset.txt').write_bytes(start); assert b'STR8-N 2.0b23' in start
            load_work(); work(workspace_request(3,h,count=1),expected=0x4B)
            new=work(workspace_request(1,size=256))[4:12]; assert new!=h
            checks.append('HOLD/library reload preserves handle; actual J3 invalidates old epoch and issues a new handle')
            report['exercised']=True
        except Exception as e:
            report['error']=repr(e)
        finally:
            try:
                if mutated and original is not None:
                    prompt=link.command('',b'> ')
                    if any(x in prompt for x in (b'CLOCK>',b'BM>',b'WORK>',b'SRAM>',b'EDU>')): link.command('Q')
                    load_image(link,client/'client.s19')
                    changed=array('test-before-restore'); touched=[]
                    for i in range(16):
                        part=original[i*8192:(i+1)*8192]
                        if changed[i*8192:(i+1)*8192]==part: continue
                        path=out/f'restore-block-{i:02d}.s19'; path.write_bytes(s19(dict(enumerate(part,0x4000)),0x4000))
                        load_image(link,path); driver(2,i*8192,True); driver(1,i*8192)
                        assert link.dump(0x4000,0x5FFF)==part; touched.append(i)
                        print(a.board,'restored block',i,flush=True)
                    final=array('live-restored'); assert final==original
                    report.update(restored=True,restored_blocks=touched,sram_sha256=sha(final))
                    start=cmd('J3',b'Enter default [3s]: '); link.send(b'\r'); start+=link.until(b'\r\nB3> ')
                    (out/'restored-cold-reset.txt').write_bytes(start)
                report['passed']=bool(report.get('exercised') and report['restored'] and 'error' not in report)
            except Exception as e:
                report['restoration_error']=repr(e)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n'); link.serial.close()
    print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
