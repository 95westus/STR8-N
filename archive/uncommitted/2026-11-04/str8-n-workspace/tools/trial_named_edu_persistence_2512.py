"""Two approved ED/1 appends and two separately armed physical reset checks."""
import argparse,json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
import nf_opaque as opaque

t=ins.t;d=ins.d;Q=ins.Q;SCOPE=ins.SCOPE;BM=ins.BM;EY=ins.EY


def expected(mode):
    a=bytearray((SCOPE/'B3-target.bin').read_bytes())
    if mode=='OFF':a[0x1DA0:0x1DC0]=b'\xff'*32
    return bytes(a)


def run(mode,reset=False,reported_reset=False):
    p=ins.approved();ins.window(240 if reset and not reported_reset else 90)
    copies=Q/'2512-named-transfer-positive-20261101-r1';assert json.loads((copies/'report.json').read_text())['passed']
    base=Q/f'2512-EDU-{mode}-saved-20261101-r1';folder=base/('reset-reported-check' if reported_reset else 'reset-check') if reset else base
    if reset:assert json.loads((base/'report.json').read_text())['passed']
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',mode=mode,reset_check=reset,passed=False,F_writes=0,erases=0,journal_writes=0,
        ED_appends=0,resets=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,SRAM_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;ram=zp=prefix=None;borrowed=False;marker=None
    if reset:ram=(base/'owner-ram.bin').read_bytes();zp=(base/'owner-zp.bin').read_bytes()
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(folder/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(face);return face
    def mon():
        if s.context==EY:cmd('NO',(BM,))
        if s.context==BM:cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    save()
    with t.serial_lease('2512-approved-EDU-'+mode+('-reset' if reset else '-save'),timeout=60):
      ins.window(240 if reset and not reported_reset else 90);marker=json.loads(mp.read_text());assert marker['monitor_generation']=='0000000E'
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,'2512')
            if reset:
                if reported_reset:
                    r['owner_reported_physical_reset']=True
                    try:face=s.until((t.MON,t.REC),seconds=3)
                    except TimeoutError:
                        face=bytes(s.link.pending);s.link.pending.clear();s.link.send(b'\r');face+=s.until((t.MON,t.REC),seconds=12)
                    (folder/'initial-after-reported-reset.txt').write_bytes(face)
                    r['startup_banner_captured']=b'g0000000E / MON B' in face and b'EDU '+mode.encode() in face
                    if s.context==t.REC:cmd('B',(t.MON,));r['explicit_B_entry']=True
                    identity=cmd('VERSION');assert b'g0000000E / MON B' in identity and b'EDU '+mode.encode() in identity
                else:
                    print('ARMED2512 physical RESET for saved EDU '+mode+'; no USB power cut',flush=True)
                    face=s.until((t.MON,),seconds=180);(folder/'startup.txt').write_bytes(face)
                    assert b'g0000000E / MON B' in face and b'EDU '+mode.encode() in face,face
                r['resets']=1;assert s.dump(0x6A20,0x6A20)==bytes([mode=='ON'])
                mark(named_edu_persistence_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            else:
                s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon();assert b'g0000000E / MON B' in cmd('VERSION')
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                opaque.durable_file(folder/'owner-prefix.bin',prefix);opaque.durable_file(folder/'owner-zp.bin',zp)
                mark(named_edu_persistence_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
                rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                ram=prefix+memory[len(reader):];opaque.durable_file(folder/'owner-ram.bin',ram)
                before=s.client.flash(3)
                want=bytearray(expected(mode));off=0x1D80 if mode=='OFF' else 0x1DA0;want[off:off+32]=b'\xff'*32
                assert before==want
                mon();cmd('R MAINT',(BM,));cmd('EDU SAVE '+mode,(EY,));r['ED_appends']=1;save()
                assert b'EDU '+mode.encode() in cmd('YES',(BM,))
                face=cmd('EDU SAVE '+mode);assert b'Save EDU mode?' not in face
                cmd('Q',(t.MON,));assert s.dump(0x6A20,0x6A20)==bytes([mode=='ON'])
            rec();s.service(reader);actual=s.client.flash(3);assert actual==expected(mode)
            opaque.durable_file(folder/'B3-after.bin',actual);r['NVM_verified']=True
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
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];kw=dict(named_edu_persistence_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=True,final_prompt='REC>',last_EDU_persistence_trial=str(folder/'report.json'))
                if r.get('NVM_verified'):
                    hs=marker['current_physical_bank_sha256'].copy();hs['B3']=t.sha(expected(mode))
                    kw.update(current_physical_bank_sha256=hs,saved_EDU=mode,physical_reset_pending=not reset,
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                mark(**kw)
            save()
    r['passed']=bool(r.get('NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS2512 EDU '+mode+(' cold reset' if reset else ' save/no-op')+'; REC>; COM4 released',flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=['OFF','ON'],required=True);a.add_argument('--reset',action='store_true');a.add_argument('--reported-reset',action='store_true');v=a.parse_args();assert not v.reported_reset or v.reset;run(v.mode,v.reset,v.reported_reset)
