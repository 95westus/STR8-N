"""2512 only, real SRAM/WORK queries and synthetic BATCH entry, zero NVM writes."""
import json,re
from pathlib import Path
import install_named_edu_2512 as ins
from storage_batch_ram_packet import packet
from serial_test_coordination import drift_pending

t=ins.t;d=ins.d;Q=ins.Q;BUILD=t.ROOT/'BUILD/storage-batch-g4-r1'
OUT=Q/'2512-storage-BATCH-RAM-20261101-r1'
SRAM=b'SRAM> ';WORK=b'WORK> '


def run(continuation=False):
    global OUT
    prior_folder=OUT;prior=None
    if continuation:
        prior=json.loads((prior_folder/'report.json').read_text())
        assert prior['checks']==['SRAM-table-Q-MON-continuation']
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['port_released']
        face=(prior_folder/'WORK-capacity-Q-MON-continuation-received.txt').read_bytes()
        assert b'Programs: 64 KiB; workspace: 65504 bytes' in face
        assert b'BATCH done' in face and b'1000:' in face and b'BATCH stopped' not in face
        assert prior['error'].startswith('AssertionError(')
        OUT=Q/'2512-storage-BATCH-RAM-20261101-r2'
    ins.window(300)
    body=(BUILD/'SRAM-WORK-BATCH-2000.bin').read_bytes()
    mf=json.loads((BUILD/'manifest.json').read_text());assert t.sha(body)==mf['sha256']
    kernel=(t.ROOT/'BUILD/named-edu-g3-r8/COMPACT-DECODE-6800.bin').read_bytes()
    cases=[('SRAM-table-Q-MON-continuation',3,b'T;Q;D 1000',t.MON),
           ('WORK-capacity-Q-MON-continuation',4,b'?;Q;D 1000',t.MON),
           ('WORK-overlong-stops-before-tail',4,b'ABCDEFGHIJKLMNOP;Q;D 1000',WORK),
           ('SRAM-missing-stops-before-tail',3,b'R NOG4;Q;D 1000',SRAM)]
    if continuation:cases=cases[2:]
    frames={name:packet(body,kernel,route,queue) for name,route,queue,_ in cases}
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    for name,b in frames.items():(OUT/(name+'.bin')).write_bytes(b)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_data_writes=0,
        WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,CPU_simulations=0,
        owner_RAM_restored=False,owner_ZP_restored=False,
        limitation='Synthetic RAM BATCH entry; normal WB frontdoor and flash bootstrap not yet qualified')
    if continuation:
        r['checks']=['SRAM-table-Q-MON-continuation','WORK-capacity-Q-MON-continuation']
        r['carried_report']=dict(path=str(prior_folder/'report.json'),sha256=t.sha((prior_folder/'report.json').read_bytes()),
            reason='WORK reports reservation in KiB, not STATUS payload bytes; accepted trace retained, no firmware changes or repeated positive cases')
    s=None;ram=zp=prefix=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:35]}.txt').write_bytes(b);return b
    def mon():
        if s.context in (SRAM,WORK):cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context is None:
            s.link.send(b'\x03\r');s.until((t.MON,t.REC,SRAM,WORK),seconds=12)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    save()
    with t.serial_lease('2512-storage-BATCH-RAM-only',timeout=30):
      if drift_pending():raise InterruptedError('RTC priority; no port opened')
      marker=json.loads(mp.read_text())
      assert not marker['block_snapshot'] and marker['application_ram_restored']
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(storage_batch_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500)
            assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
            (OUT/'owner-ram.bin').write_bytes(ram)
            for name,route,queue,prompt in cases:
                if drift_pending():raise InterruptedError('RTC priority between cases')
                rec();log.flush();start=(OUT/'serial.jsonl').stat().st_size
                s.load(frames[name],t.sha(frames[name]),prompt if prompt==t.MON else b'BATCH stopped\r\n')
                if prompt!=t.MON:s.until((prompt,),seconds=12)
                log.flush()
                with (OUT/'serial.jsonl').open('rb') as capture:
                    capture.seek(start)
                    events=[json.loads(line) for line in capture if line.strip()]
                face=b''.join(bytes.fromhex(e['hex']) for e in events if e.get('direction')=='RX')
                (OUT/(name+'-received.txt')).write_bytes(face)
                if prompt==t.MON:
                    assert b'BATCH done' in face and b'1000:' in face and b'BATCH stopped' not in face,face[-1000:]
                    assert (b'CLK' in face) if route==3 else (b'Programs: 64 KiB; workspace: 65504 bytes' in face),face[-1000:]
                    assert s.context==t.MON
                    assert s.dump(0x6AF4,0x6AF4)==bytes((len(queue),))
                    assert s.dump(0x7DF9,0x7DF9)==b'\0'
                else:
                    assert b'BATCH stopped' in face and b'1000:' not in face,face[-1000:]
                    cmd('Q',(t.MON,))
                    assert s.dump(0x7DF9,0x7DF9)==b'\0'
                r['checks'].append(name);save();print('PASS2512 '+name,flush=True)
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
                mark(storage_batch_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                    final_prompt='REC>',last_storage_BATCH_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==4 and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();assert r['passed'];print('PASS2512 storage BATCH RAM; REC>; COM4 released',flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--continuation',action='store_true');run(p.parse_args().continuation)
