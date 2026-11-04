"""One physical2512 reset, then RAM-only cold STATUS/TIME acceptance."""
import json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
import time_prep_ram_packets as packets

t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-TIME-PREP-cold-RAM-20261101-r1'

def packet():
    a=bytearray(packets.live_packet());entry=bytes(a[:3]);_,sy=packets.core('new')
    c=packets.Code(0x1F00);c.emit(0x78,0xD8)
    for n,address in enumerate((0x7FCD,0x7FCE,0x7FCC,0x7FCB,0x7FC2)):
        c.absolute(0xAD,address);c.absolute(0x8D,0x1A80+n)
    for n,v in enumerate(entry):c.imm(0xA9,v);c.absolute(0x8D,0x200+n)
    c.absolute(0x4C,sy['M_START']);stub=c.done();assert len(stub)<128
    assert a[0x1D00:0x1D80]==b'\xff'*128
    a[:3]=bytes.fromhex('4C 00 1F');a[0x1D00:0x1D00+len(stub)]=stub
    return bytes(a)

def run(reported_reset=False):
    global OUT
    if reported_reset:
        prior=json.loads((OUT/'report.json').read_text());assert prior['error'].startswith('TimeoutError(') and prior['port_released'] and prior['resets']==0
        OUT=Q/'2512-TIME-PREP-cold-RAM-20261101-r2'
    ins.window(480);authority=Q/'2512-TIME-PREP-RAM-20261101-r2';proof=json.loads((authority/'report.json').read_text());assert proof['passed']
    ram=(authority/'owner-ram.bin').read_bytes();zp=(authority/'owner-zp.bin').read_bytes();assert t.sha(ram)==proof['RAM_sha256'] and t.sha(zp)==proof['ZP_sha256']
    body=packet();OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'candidate.bin').write_bytes(body)
    (OUT/'owner-ram.bin').write_bytes(ram);(OUT/'owner-zp.bin').write_bytes(zp)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,metadata_writes=0,SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
        owner_RAM_restored=False,owner_ZP_restored=False,old_native_errors=[])
    s=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:03d}-{re.sub("[^A-Za-z0-9]","_",line)[:36]}.txt').write_bytes(b);return b
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:cmd('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with t.serial_lease('2512-TIME-PREP-cold-start-RAM-only',timeout=60):
      ins.window(480);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert marker['current_owner_RAM_sha256']==t.sha(ram) and marker['current_owner_ZP_sha256']==t.sha(zp)
      mark(physical_reset_pending=True)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512')
            if reported_reset:
                r['owner_reported_physical_reset']=True
                try:face=s.until((t.MON,t.REC),seconds=3)
                except TimeoutError:
                    face=bytes(s.link.pending);s.link.pending.clear();s.link.send(b'\r');face+=s.until((t.MON,t.REC),seconds=12)
                (OUT/'initial-after-reported-reset.txt').write_bytes(face)
                r['startup_banner_captured']=b'g0000000E / MON B' in face
                if s.context==t.REC:cmd('B',(t.MON,));r['explicit_B_entry']=True
                face=cmd('VERSION')
            else:
                print('ARMED2512 physical RESET: old gE startup, then RAM-only corrected STATUS/TIME',flush=True)
                face=s.until((t.MON,),seconds=180)
                r['startup_banner_captured']=True
            (OUT/'old-cold-startup.txt').write_bytes(face)
            assert b'g0000000E / MON B' in face and b'EDU ON' in face
            r['resets']=1;r['old_cold_SSRAM_unavailable']=b'SSRAM: --*' in face
            mark(time_prep_cold_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            for n in range(12):
                face=cmd('TIME')
                if b'RTCC error' in face:
                    raw=s.dump(0x6A90,0x6ABF);(OUT/'old-TIME-error-state.bin').write_bytes(raw);r['old_native_errors'].append(dict(reply=face.decode(),state_hex=raw.hex()));break
                time.sleep(.137+n%9*.031)
            rec();s.load(body,t.sha(body),t.MON)
            face=cmd('VERSION');assert b'g0000000F / RAM' in face and b'EDU ON' in face
            assert b'SSRAM: PROGRAM payload 63488 bytes' in face and b'SSRAM: WORKSPACE 65504 bytes' in face,face
            gpio=s.dump(0x1A80,0x1A84);r['VIA_before_candidate']=dict(zip(['IFR','IER','PCR','ACR','DDRB'],gpio))
            if r['old_cold_SSRAM_unavailable']:assert gpio[0]&0x18 and not gpio[1]&0x18
            r['cold_capacity_without_manual_PREP']=True;save();print('PASS2512 cold RAM capacity;VIA before',gpio.hex(' '),flush=True)
            for n in range(24):
                face=cmd('TIME');m=re.search(rb'RTCC: (20\d\d-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2}) trim \$([0-9A-F]{2}) ctrl \$([0-9A-F]{2})',face)
                assert m and b'RTCC error' not in face and m.group(3,4)==(b'0C',b'80'),face
                time.sleep(.137+n%9*.031)
            r['cold_TIME_samples']=24
            rec();s.service(reader)
            for bank in (2,3):
                actual=s.client.flash(bank);assert actual==(authority/f'B{bank}-before.bin').read_bytes();(OUT/f'B{bank}-after.bin').write_bytes(actual)
            r['B2_B3_unchanged']=True
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if borrowed:
                rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
            if borrowed:mark(time_prep_cold_RAM_worker_active=False,physical_reset_pending=not restored,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_TIME_PREP_cold_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=bool(r.get('cold_capacity_without_manual_PREP') and r.get('B2_B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed'];print('PASS2512 physical cold-start RAM trial; REC>; COM4 released',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--reported-reset',action='store_true');a=p.parse_args();run(a.reported_reset)
