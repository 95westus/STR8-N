"""Backup/model-bound flash/SRAM copies; restore all original data before cutoff."""
import argparse
from datetime import datetime
import hashlib,json,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,journal,s19
from rtc_boards import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request,workspace_request

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True)
    p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--deadline-utc',required=True)
    p.add_argument('--resume-source',action='store_true');p.add_argument('--attempt',default='')
    a=p.parse_args();build=a.build;deadline=datetime.fromisoformat(a.deadline_utc.replace('Z','+00:00')).timestamp()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    meta=json.loads((build/'build.json').read_text());model=json.loads((build/'flash-roundtrip-model.json').read_text())
    assert model['passed'] and model['artifacts']==meta['artifacts'] and meta['version']=='2.0b23'
    prior=json.loads((a.root/'prior/manifest.json').read_text());assert prior['repeat_verified'] and prior['board']==a.board
    banks=[(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert sha(b)==prior['banks'][i]['sha256'] and b==(a.root/f'prior/b{i}-repeat.bin').read_bytes()
    regions=[(3,0,'str8n-rtc-component-8000-8fff.bin',4096),(3,0x1000,'str8n-journal-9000-9fff.bin',3072),
             (3,0x2000,'str8n-v2-recovery-slot-a0.bin',4096),(3,0x3000,'str8n-v2-recovery-slot-b0.bin',4096),
             (3,0x6000,'str8n-v2-recovery-e000-efff.bin',4096),(3,0x7000,'str8n-v2-recovery-f000-ffff.bin',4096),
             (2,0x4800,'boot-status/asset.bin',2560),(2,0x6000,'local-display/asset.bin',1536)]
    for bank,offset,name,length in regions:
        assert banks[bank][offset:offset+length]==(build/name).read_bytes()[:length],f'{a.board} differs from frozen beta23: {name}'
    assert banks[2][:4096]==b'\xff'*4096,'B2:8 is occupied; refuse test'
    original=(a.root/'sram-prior/array-0.bin').read_bytes();assert original==(a.root/'sram-prior/array-1.bin').read_bytes()
    assert json.loads((a.root/'sram-prior/report.json').read_text())['repeat_verified'] and len(original)==131072
    before_journal=journal(banks[3]);assert before_journal
    old_counts=[int.from_bytes(before_journal[24+3*i:27+3*i],'little') for i in range(32)]
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    out=a.root/('flash-roundtrip'+a.attempt);out.mkdir(exist_ok=False);checks=[];flash_mutated=False;sram_mutated=False
    report=dict(passed=False,board=a.board,checks=checks,clock_set=False,trim_changed=False,
                firmware_replaced=False,flash_restored=False,sram_restored=False,model_sha256=sha((build/'flash-roundtrip-model.json').read_bytes()))
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            stop=time.monotonic()+.4
            while time.monotonic()<stop:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ')
            if any(x in initial for x in (b'BM>',b'CLOCK>',b'EDU>',b'WORK>',b'SRAM>')):link.command('Q',b'> ')
            link.command('B3');assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            def cmd(text,prompt=b'> ',label=None):
                data=link.command(text,prompt)
                if re.search(rb'\r\nB[012]> $',data):data+=link.command('B3')
                if label:(out/(label+'.txt')).write_bytes(data)
                return data
            def monitor():
                prompt=link.command('',b'> ')
                if any(x in prompt for x in (b'BM>',b'CLOCK>',b'EDU>',b'WORK>',b'SRAM>')):link.command('Q',b'> ')
                link.command('B3')
            def bank_image(bank):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                link.command('B3');return data
            program=bytes.fromhex(model['program_hex'])
            resumed_bank=bytearray(banks[2]);resumed_bank[:24+len(program)]=b'SR\x01\x3f'+(0x2600).to_bytes(2,'little')+len(program).to_bytes(2,'little')+b'B23FLASH'.ljust(16,b'\0')+program
            for i in range(4):assert bank_image(i)==(resumed_bank if a.resume_source and i==2 else banks[i]),f'B{i} changed since backup'
            if a.resume_source:
                flash_mutated=True;sram_mutated=True;report['resumed_after_auto_prompt_mismatch']=True
                write(link,0x2700,b'\0')
            else:
                assert deadline-time.time()>300,'Too close to cutoff to start mutable test'
                client=build/'hardware-client/client.s19';load_image(link,client)
                assert b'Done' in cmd('R 2 WORK L')
                write(link,0x3E21,b'\x03');write(link,0x3E40,workspace_request(6,key=b'FORMAT!!'))
                sram_mutated=True;cmd('G 2006');assert link.dump(0x3E38,0x3E38)==b'\0'
                write(link,0x2600,program);write(link,0x2700,b'\0')
                flash_mutated=True;assert b'SAVE B02:8000' in cmd('S 2 AUTO 2600 2605 B23FLASH',label='auto-save')
            write(link,0x2600,bytes(6));assert b'Done' in cmd('R 2 B23FLASH L',label='restore-only')
            assert link.dump(0x2600,0x2605)==program
            cmd('R 2 B23FLASH',label='flash-run');assert link.dump(0x2700,0x2700)==b'\x01'
            assert b'BANK MAINT 1.8' in cmd('R MAINT',b'BM> ',label='maint-start')
            cmd('X 2 B23FLASH S CANCEL',b'Copy program; source retained. Y to confirm: ')
            assert b'CANCELED' in cmd('N',b'BM> ',label='copy-cancel')
            cmd('X 2 B23FLASH S B23COPY',b'Copy program; source retained. Y to confirm: ')
            assert b'Copied and verified' in cmd('Y',b'BM> ',label='flash-to-sram')
            prompt=cmd('X S B23COPY 2 B23RETURN',b'Copy program; source retained. Y to confirm: ')
            assert re.search(rb'Destination B02:80[0-9A-F]{2}',prompt),prompt
            assert b'Copied and verified' in cmd('Y',b'BM> ',label='sram-to-auto-flash')
            cmd('Q');write(link,0x2700,b'\0');cmd('R 2 B23RETURN',label='returned-run');assert link.dump(0x2700,0x2700)==b'\x01'
            table=cmd('T 2',label='flash-table');assert b'B23FLASH' in table and b'B23RETURN' in table
            cmd('R SRAM',b'SRAM> ');assert b'B23COPY' in cmd('T',b'SRAM> ',label='sram-table');cmd('Q')
            start=cmd('J3',b'Enter default [3s]: ');link.send(b'\r');start+=link.until(b'\r\nB3> ')
            (out/'retained-cold-start.txt').write_bytes(start);assert b'STR8-N 2.0b23' in start
            write(link,0x2700,b'\0');cmd('R 2 B23FLASH',label='flash-after-j3');assert link.dump(0x2700,0x2700)==b'\x01'
            cmd('R SRAM',b'SRAM> ');assert b'B23COPY' in cmd('T',b'SRAM> ',label='sram-after-j3')
            assert b'SRAM: 00' in cmd('D B23COPY',b'SRAM> ',label='sram-delete')
            assert b'B23COPY' not in cmd('T',b'SRAM> ');cmd('Q')
            checks.extend(['Native AUTO flash save/restore/run/table','MAINT cancel and verified flash-SRAM-AUTO-flash copies retain sources',
                           'Returned payload executes identically; flash/SRAM records survive J3; explicit SRAM deletion'])
            report['exercised']=True
        except Exception as e:report['error']=repr(e)
        finally:
            try:
                monitor()
                if flash_mutated:
                    current=bank_image(2);assert current[4096:]==banks[2][4096:],'Unplanned flash-sector change; do not overwrite'
                    cmd('R MAINT',b'BM> ');cmd('R 2 8000-8FFF',b'BM> ');cmd('F 0000-0FFF FF',b'BM> ')
                    # MAINT buffer is $5000-$5FFF; verify original bytes before rewrite.
                    display=cmd('D 0000-0FFF',b'BM> ');cells={}
                    for line in display.decode('ascii').splitlines():
                        match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
                        if match:cells.update((int(match[1],16)+i,v) for i,v in enumerate(bytes.fromhex(match[2])))
                    assert set(cells)==set(range(4096)) and bytes(cells[i] for i in range(4096))==banks[2][:4096]
                    cmd('W 2 8000',b'WRITE? TYPE Y> ');assert b'VERIFIED' in cmd('Y',b'BM> ',label='original-sector-restored');cmd('Q')
                if sram_mutated:
                    load_image(link,build/'hardware-client/client.s19')
                    def transfer(op,address,privileged=False):
                        write(link,0x3E20,bytes((1,3,0xA5 if privileged else 0)));write(link,0x3E00,memory_request(op,address))
                        cmd('G 2003');r=link.dump(0x3E10,0x3E38);assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    changed=[]
                    for i in range(16):
                        transfer(1,i*8192);data=link.dump(0x4000,0x5FFF);part=original[i*8192:(i+1)*8192]
                        if data!=part:
                            path=out/f'restore-sram-{i:02d}.s19';path.write_bytes(s19(dict(enumerate(part,0x4000)),0x4000))
                            load_image(link,path);transfer(2,i*8192,True);transfer(1,i*8192)
                            assert link.dump(0x4000,0x5FFF)==part;changed.append(i)
                        print(a.board,'verified/restored SRAM',i+1,'/16',flush=True)
                    report.update(sram_restored=True,restored_sram_blocks=changed,sram_sha256=sha(original))
                    start=cmd('J3',b'Enter default [3s]: ');link.send(b'\r');start+=link.until(b'\r\nB3> ')
                    (out/'original-state-cold-start.txt').write_bytes(start)
                final=[]
                for i in range(4):
                    data=bank_image(i);(out/f'b{i}.bin').write_bytes(data);final.append(data)
                    if i!=3:assert data==banks[i],f'B{i} differs after cleanup'
                    else:assert data[:0x4000]==banks[i][:0x4000] and data[0x5000:]==banks[i][0x5000:]
                latest=journal(final[3]);assert latest
                counts=[int.from_bytes(latest[24+3*i:27+3*i],'little') for i in range(32)]
                expected=old_counts[:];expected[16]+=1 if flash_mutated else 0
                assert counts==expected and latest[8:24]==before_journal[8:24]
                assert int.from_bytes(latest[4:8],'little')==int.from_bytes(before_journal[4:8],'little')+(1 if flash_mutated else 0)
                report.update(flash_restored=True,final_flash_hashes=[sha(b) for b in final],
                              erase_count_delta={'B2:8':1 if flash_mutated else 0},original_saved_config_preserved=True)
                report['passed']=bool(report.get('exercised') and report['flash_restored'] and report['sram_restored'] and 'error' not in report)
            except Exception as e:report['restoration_error']=repr(e)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()
    print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
