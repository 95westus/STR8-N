"""2512-only RAM preparation; no flash/SPI/RTC writes and no live YES."""
import json,re
from pathlib import Path
import install_named_edu_2512 as ins
from storage_auto_ram_packets import cases,frame
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-storage-installed-AUTO-RAM-20261101-r1'
WB=t.WB;CONFIRM=b'Flash STORE; no erase; type YES: '


def run():
    ins.window(300);tests=cases();frames={'AUTO-boundaries':frame(tests),
        'AUTO-wide-refusal':frame(command=b'STORE 0 AUTO 4E00 66FF XWIDE'),
        'AUTO-small-NO':frame(command=b'STORE 0 AUTO 1000 1007 XNO')}
    p=t.ROOT/'BUILD/wb2-gE-storage-batch-r1';wm=json.loads((p/'manifest.json').read_text())
    wb=(p/wm['artifact']['filename']).read_bytes();assert t.sha(wb)==wm['artifact']['sha256']
    frames['WB-gE']=wb
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    for n,b in frames.items():(OUT/(n+'.bin')).write_bytes(b)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_appends=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,CPU_simulations=0,owner_RAM_restored=False,owner_ZP_restored=False,
        limits='RAM candidate helpers/NO previews, old native-loader compatibility refusal; no positive installed path or large data write claim')
    s=None;ram=zp=prefix=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:38]}.txt').write_bytes(b);return b
    def mon():
        if s.context is None:s.link.send(b'\x03\r');s.until((t.MON,t.REC,WB,CONFIRM),seconds=12)
        if s.context==CONFIRM:cmd('NO',(t.MON,))
        if s.context==WB:cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def load(name,prompt):
        if drift_pending():raise InterruptedError('RTC priority between cases')
        rec();log.flush();start=(OUT/'serial.jsonl').stat().st_size
        s.load(frames[name],t.sha(frames[name]),prompt);log.flush()
        with (OUT/'serial.jsonl').open('rb') as capture:
            capture.seek(start);events=[json.loads(line) for line in capture if line.strip()]
        face=b''.join(bytes.fromhex(e['hex']) for e in events if e.get('direction')=='RX')
        (OUT/(name+'-received.txt')).write_bytes(face)
        return face
    def check(name):r['checks'].append(name);save();print('PASS2512 storage prep '+name,flush=True)
    save()
    with t.serial_lease('2512-storage-installed-AUTO-RAM',timeout=30):
      ins.window(300);marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(storage_install_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
            load('AUTO-boundaries',t.MON);answer=s.dump(0x1A00,0x1A00+len(tests)*4-1);(OUT/'AUTO-boundaries-answer.bin').write_bytes(answer)
            for i,test in enumerate(tests):
                assert answer[i*4]&1==test['carry'],test
                assert int.from_bytes(answer[i*4+1:i*4+3],'little')==test['next'],test
            check('19-AREA-record-overlap-and-carry-boundaries-on-real-CPU')
            face=load('AUTO-wide-refusal',t.MON);assert b'REFUSED: AREA/' in face and CONFIRM not in face,face[-600:]
            check('full-AUTO-scan-refuses6400-byte-source-in4K-AREA')
            load('AUTO-small-NO',CONFIRM);face=cmd('NO',(t.MON,));assert b'Canceled; flash unchanged.' in face,face
            check('full-AUTO-finds-blank-AREA-while-skipping-opaque-outside-live-NO')
            mon();cmd('MAINT LOAD',(WB,));cmd('Q',(t.MON,));load('WB-gE',WB)
            assert b'AREA' in cmd('AREA 0 9000 9FFF')
            cmd('Q',(t.MON,));assert s.dump(0x6A29,0x6A2E)==bytes.fromhex('01 00 00 90 00 A0')
            check('new-WB-AREA-snapshot-survives-Q-outside-source-RAM')
            load('WB-gE',WB)
            for manager in ('SRAM','WORK'):
                face=cmd('BATCH R '+manager+';T;Q;D 1000')
                assert b'REFUSED: native loader' in face and b'BATCH stopped' in face and b'1000:' not in face,face[-600:]
            check('new-WB-refuses-old-loader-and-stops-both-manager-queues')
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
                mark(storage_install_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_storage_install_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==5 and r['owner_RAM_restored'] and r['owner_ZP_restored'];save();assert r['passed']
    print('PASS2512 storage RAM preparation; owner restored; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
