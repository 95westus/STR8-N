"""Exercise the actual console S19 state machine on2512; RAM writes only."""
import json,sys,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from trial_s19_ram import READY,row
from serial_test_coordination import drift_pending

t=d.t;sys.path.insert(0,str(t.REPO/'tools'))
from console_core import Session,checked_s19,s19_image
Q=t.ROOT/'output/qualification';OUT=Q/'2512-console-S19-20261101-r1'


def run():
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    assert time.time()+180<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp(),'RTC window; no port opened'
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json';s=None;ram=zp=prefix=old3=None;marker=None;borrowed=False
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,WORKSPACE_writes=0,
       RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,
       core_sha256=t.sha((t.REPO/'tools/console_core.py').read_bytes()),GUI_sha256=t.sha((t.REPO/'tools/nf_console.py').read_bytes()))
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context is None:s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC
    def transfer(path,body,digest,cancel=False):
        mon();ready=s.command('S19',(READY,));s.context=None
        class Port:
            @property
            def in_waiting(self):return s.link.serial.in_waiting
            def write(self,data):s.link.send(data);return len(data)
            def read(self,n):return s.link.read(n)
            def close(self):raise AssertionError('Outer serial owner closes the port')
        events=[];console=Session(lambda *e:events.append(e));console.attach(Port());console.receive(ready)
        console.start_s19(path,body,digest)
        if cancel:console.cancel()
        deadline=time.monotonic()+35
        while console.busy and time.monotonic()<deadline:console.tick();time.sleep(.002)
        assert not console.busy and console.prompt=='mon',events
        result=[e[1] for e in events if e[0]=='transfer'][-1]
        assert result['cancelled']==cancel and result['board_accepted']==(not cancel),result
        assert not result['board_readback_verified']
        t.save(OUT/('cancel-events.json' if cancel else 'normal-events.json'),[
            [e[0],e[1].hex() if e[0] in ('rx','tx') else e[1],*e[2:]] for e in events])
        s.context=t.MON;return result
    save()
    with t.serial_lease('2512-console-S19-RAM-transfer',timeout=60):
      if drift_pending():raise InterruptedError('RTC priority before port open')
      marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000D / MON B' in s.command('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(console_S19_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            opaque.durable_file(OUT/'B3-before.bin',old3)
            body=checked_s19(row(0,0,b'Console RAM qualification')+row(1,0x3500,bytes(range(64)))+
                             row(1,0x66F0,bytes(range(0xA0,0xB0)))+row(9,0x3500))
            path=OUT/'console-example.s19';path.write_bytes(body);path,body,digest=s19_image(path)
            if drift_pending():raise InterruptedError('RTC priority before transfer')
            r['cancel']=transfer(path,body,digest,cancel=True);r['checks'].append('console-initial-S19-Ctrl-C');save()
            print('PASS2512 console S19 initial cancellation',flush=True)
            r['normal']=transfer(path,body,digest)
            assert s.dump(0x3500,0x353F)==bytes(range(64)) and s.dump(0x66F0,0x66FF)==bytes(range(0xA0,0xB0))
            r['normal']['board_readback_verified']=True
            r['checks'].append('console-S19-accepted-no-autorun-and-independent-RAM-readback');save()
            print('PASS2512 console S19 accepted; independent low/high RAM readback',flush=True)
            rec();s.service(reader);after=s.client.flash(3);assert after==old3
            opaque.durable_file(OUT/'B3-after.bin',after);r['B3_unchanged']=True
        except BaseException as error:r['error']=repr(error);save();raise
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
                mark(console_S19_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                   block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_console_S19_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==2 and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    save();assert r['passed'];print('PASS2512 console S19; owner RAM/ZP restored; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
