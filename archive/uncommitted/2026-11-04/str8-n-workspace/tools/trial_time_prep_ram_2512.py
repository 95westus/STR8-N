"""2512-only TIME retry/guarded PREP CPU-RAM qualification, zero NVM writes."""
import binascii,json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
import time_prep_ram_packets as packets
from serial_test_coordination import drift_pending

t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-TIME-PREP-RAM-20261101-r1'

def frame(sec=0xD9,minute=0x59,hour=0x18,month=0x11,date=1,year=0x26,recheck=None,error9=0,error1=0,control=0x80,trim=0x0C):
    return bytes((sec,minute,hour,0x2F,date,month,year,control,trim,sec if recheck is None else recheck,error9,error1))

def run(continuation=False):
    global OUT
    prior_folder=OUT;prior=None
    if continuation:
        prior=json.loads((prior_folder/'report.json').read_text())
        assert len(prior['checks'])==19 and prior['error'].startswith('IndexError(')
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['port_released']
        OUT=Q/'2512-TIME-PREP-RAM-20261101-r2'
    ins.window(480);OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    bad=frame(month=0x1A);good=frame(sec=0x80,minute=0,hour=0x19,control=0x84,trim=0x8F)
    cases=[('old-invalid-first-refuses','old',[bad,good,good],4,1),('new-invalid-then-valid','new',[bad,good,good],0,2),
        ('new-persistent-invalid-refuses','new',[bad]*3,4,3),('new-rollover-resample','new',[frame(recheck=0x80),good,good],0,2),
        ('new-persistent-incoherent-refuses','new',[frame(recheck=0x80)]*3,7,3),('new-NACK-refuses','new',[frame(error9=2)]*3,2,1),
        ('new-invalid-leap-day-refuses','new',[frame(month=2,date=0x29,year=0x25)]*3,4,3),
        ('new-valid-leap-day','new',[frame(month=2,date=0x29,year=0x24)]*3,0,1),
        ('new-12h-noon','new',[frame(hour=0x72)]*3,0,1)]
    probes=[('old-pending-flags-refuse','old',{},0,0,0),('new-pending-flags-prepared','new',{},1,1,1),
        ('new-enabled-CB-owner-refused','new',{0xE:0x18},0,0,0),('new-PCR-owner-refused','new',{0xC:0x10},0,0,0),
        ('new-ACR-owner-refused','new',{0xB:2},0,0,0),('new-DDR-owner-refused','new',{2:1},0,0,0),
        ('new-stuck-pending-refused','new',{0x11:0},0,1,0),('new-unrelated-owner-retained','new',{0xD:0x1A,0xE:2,0xB:1,2:0x80},1,1,1)]
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,metadata_writes=0,SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,
        owner_RAM_restored=False,owner_ZP_restored=False,CPU_simulations=0,fixture_note='CPU-RAM transport/register fixtures; separate completely unpatched live MR_SAMPLE and physical SRAM probe')
    if continuation:
        r['checks']=prior['checks'].copy();r['carried_checks']=dict(report=str(prior_folder/'report.json'),sha256=t.sha((prior_folder/'report.json').read_bytes()),reason='Host match-object slice assertion; no firmware change or repeated accepted fixture cases')
    s=None;ram=zp=prefix=None;borrowed=False;marker=None;banks={}
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt').write_bytes(b);return b
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:assert s.context==t.MON;cmd('Q',(t.REC,))
    def load(label,body):
        if drift_pending():raise InterruptedError('RTC priority between RAM cases')
        (OUT/(label+'.bin')).write_bytes(body);rec();s.load(body,t.sha(body),t.MON)
    def check(n):r['checks'].append(n);save();print('PASS2512 RAM '+n,flush=True)
    save()
    with t.serial_lease('2512-TIME-and-cold-SRAM-RAM-only',timeout=60):
      ins.window(480);marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.REC,t.MON),seconds=12);mon();assert b'g0000000E / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(time_prep_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
            for bank in (2,3):
                banks[bank]=(prior_folder/f'B{bank}-before.bin').read_bytes() if continuation else s.client.flash(bank)
                assert t.sha(banks[bank])==marker['current_physical_bank_sha256'][f'B{bank}'];(OUT/f'B{bank}-before.bin').write_bytes(banks[bank])
            for label,which,frames,error,count in ([] if continuation else cases):
                load(label,packets.time_packet(which,frames));answer=s.dump(0x1A00,0x1A3F);(OUT/(label+'-answer.bin')).write_bytes(answer)
                assert answer[0]==error and answer[2]==count,(label,answer.hex())
                assert answer[0x1B]==(error==0),(label,'MR_VALID')
                if label=='new-invalid-then-valid':assert answer[0x37:0x39]==bytes((0x84,0x8F)),'Control/trim must come from accepted retry'
                check(label)
            for label,which,fixture,carry,reads,clock in ([] if continuation else probes):
                load(label,packets.sram_packet(which,fixture=fixture));answer=s.dump(0x1A00,0x1A1F);(OUT/(label+'-answer.bin')).write_bytes(answer)
                assert (answer[0]&1,answer[1],answer[2])==(carry,reads,clock),(label,answer.hex())
                assert answer[0x10]==0xA5 and answer[0x12]==fixture.get(2,0)
                assert all(answer[0x10+k]==fixture.get(k,0) for k in (0xB,0xC,0xE))
                expected_ifr=fixture.get(0xD,0x18)&(0xE7 if reads and fixture.get(0x11,1) else 0xFF)
                assert answer[0x1D]==expected_ifr
                check(label)
            if not continuation:
                load('physical-SRAM-probe',packets.sram_packet('new'));answer=s.dump(0x1A00,0x1A94);(OUT/'physical-SRAM-probe-answer.bin').write_bytes(answer)
                assert answer[0]&1 and answer[0x10:0x14]==b'SS\x01\x08'
                assert binascii.crc_hqx(answer[0x10:0x4E],65535)==0 and answer[0x4E:0x50]==bytes((0,0xA5))
                assert answer[0x80:0x84]==answer[0x90:0x94],'DDR/ACR/PCR/IER must be exact'
                check('physical-SPI-primary-read-and-control-preservation')
            load('live-new-MON-and-STATUS',packets.live_packet());face=cmd('VERSION');assert b'g0000000F / RAM' in face and b'SSRAM: PROGRAM payload 63488 bytes' in face and b'SSRAM: WORKSPACE 65504 bytes' in face
            if not continuation:check('live-relocated-MON-STATUS-capacity')
            samples=[];start=time.monotonic()
            while time.monotonic()-start<65:
                face=cmd('TIME');m=re.search(rb'RTCC: (20\d\d-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2}) trim \$([0-9A-F]{2}) ctrl \$([0-9A-F]{2})',face)
                assert m and b'RTCC error' not in face,face
                assert m.group(3,4)==(b'0C',b'80');samples.append(m[1].decode());time.sleep(.137+len(samples)%9*.031)
                if drift_pending():raise InterruptedError('RTC priority during live reads')
            r['live_TIME_samples']=len(samples);r['live_TIME_first_last']=[samples[0],samples[-1]];check('live-TIME-full-minute-no-error-fresh-control-trim')
            cmd('!M 6A20 00');off=cmd('VERSION');assert b'EDU OFF' in off and b'SSRAM: --*' in off and b'RTCC: --*' in off
            cmd('!M 6A20 01');assert b'SSRAM: PROGRAM payload' in cmd('VERSION');check('EDU-OFF-skips-devices-ON-reopens')
            rec();s.service(reader)
            for bank in (2,3):
                after=s.client.flash(bank);assert after==banks[bank];(OUT/f'B{bank}-after.bin').write_bytes(after)
            r['B2_B3_unchanged']=True;check('all-images-settings-history-and-golden-F-unchanged')
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
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(time_prep_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_TIME_PREP_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==22 and r.get('B2_B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored'];save();assert r['passed'];print('PASS2512 TIME/PREP RAM; REC>; COM4 released',flush=True)

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--live-continuation',action='store_true');v=a.parse_args();run(v.live_continuation)
