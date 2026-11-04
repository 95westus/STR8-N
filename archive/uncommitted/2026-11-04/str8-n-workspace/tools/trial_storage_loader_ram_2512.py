"""New NL1/5+NB1/2 loader in RAM must refuse old storage before executing it."""
import json,re
from pathlib import Path
import install_named_edu_2512 as ins
from time_prep_ram_packets import Code
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-storage-loader-RAM-20261101-r1'
BUILD=t.ROOT/'BUILD/storage-installed-auto-r2'


def frame():
    nl=(BUILD/'NATIVE-LOADER-7000.bin').read_bytes();a=bytearray(b'\xff'*0x1800)
    a[:3]=bytes.fromhex('4C 00 10');a[0x100:0x500]=nl
    c=Code(0x1000);c.emit(0x78,0xD8,0xA2,0);c.label('copy')
    for i in range(4):c.absolute(0xBD,0x300+i*256);c.absolute(0x9D,0x7000+i*256)
    c.emit(0xE8);c.branch(0xD0,'copy')
    for i,v in enumerate(b'D 1000\0'):c.emit(0xA9,v);c.absolute(0x8D,0x6AD0+i)
    for addr,v in ((0x6AF3,6),(0x6AF4,0),(0x6AF5,0),(0x6AF6,5),(0x6AF7,3),(0x6AF8,2),(0x6AF9,0),(0x7DF9,0xB7)):
        c.emit(0xA9,v);c.absolute(0x8D,addr)
    c.emit(0xA9,3);c.absolute(0x4C,0x7008)
    b=c.done();a[0xE00:0xE00+len(b)]=b;return bytes(a)


def run():
    ins.window(180);body=frame();OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'loader-fixture.bin').write_bytes(body)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_appends=0,SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,CPU_simulations=0)
    s=None;ram=zp=prefix=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):return s.command(line,tokens)
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context is None:s.link.send(b'\x03\r');s.until((t.MON,t.REC),seconds=12)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    save()
    with t.serial_lease('2512-storage-loader-RAM-only',timeout=30):
      ins.window(180);marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored'] and not drift_pending()
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(storage_loader_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
            mon();rec();log.flush();start=(OUT/'serial.jsonl').stat().st_size
            s.load(body,t.sha(body),t.MON);log.flush()
            with (OUT/'serial.jsonl').open('rb') as capture:
                capture.seek(start);events=[json.loads(line) for line in capture if line.strip()]
            face=b''.join(bytes.fromhex(e['hex']) for e in events if e.get('direction')=='RX');(OUT/'received.txt').write_bytes(face)
            assert b'REFUSED: native' in face and b'BATCH stopped' in face and b'1000:' not in face,face[-1000:]
            assert s.dump(0x7DF9,0x7DF9)==b'\0'
            r['checks'].append('real-NL-CRC-admission-old-SW-capability-refusal-and-queue-stop');save()
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if borrowed:
                rec();s.service(reader)
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(storage_loader_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_storage_loader_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==1 and r['owner_RAM_restored'] and r['owner_ZP_restored'];save();assert r['passed']
    print('PASS2512 new storage loader refuses unqualified old module; owner restored; REC>; COM4 free',flush=True)


if __name__=='__main__':run()
