"""Qualify saved-EDU cold/warm entry and help in CPU RAM on2512 only."""
import binascii,json,re,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from trial_edu_settings_ram import record
from serial_test_coordination import drift_pending

t=d.t;Q=t.ROOT/'output/qualification'
BUILD=t.ROOT/'BUILD/mon-gE-settings-RAM-integration-r1'
HELPER=t.ROOT/'BUILD/edu-settings-g1-ram-r1'
OUT=Q/'2512-EDU-startup-RAM-20261101-r2'


def packet(core,sy,helper,helptext,rows,kind='valid',warm=None):
    # Only the initial JMP is redirected to a CPU-RAM setup stub; the stub
    # restores it before entering the exact linked cold/warm entry.
    a=bytearray(b'\xff'*0x5200);a[:len(core)]=core
    image=bytearray(b'\xff'*1024)
    image[0x290:0x290+len(helper)]=helper
    image[0x380:0x380+len(helptext)]=helptext
    if kind=='bad-id':image[0x290]^=1
    image[-2:]=binascii.crc_hqx(image[:-2],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(image,65535)==0
    if kind=='bad-crc':image[0x80]^=1
    if kind=='missing':image[:]=b'\xff'*1024
    # Transport only through53FF. Stage the sealed image at4000 and copy it
    # to7000 before MON starts; raw L's admitted25344-byte limit is unchanged.
    a[0x3E00:0x4200]=image
    a[0x4E00:0x5200]=b''.join(rows).ljust(1024,b'\xff')
    stub=bytearray(bytes.fromhex('78 D8 9C F9 7D A2 00')) # no active BATCH
    loop=len(stub)
    for page in range(4):stub.extend((0xBD,0,0x40+page,0x9D,0,0x70+page))
    stub.extend((0xE8,0xD0,(loop-len(stub)-3)&255))
    for i,b in enumerate(core[:3]):stub.extend((0xA9,b,0x8D,i,2))
    if warm is not None:stub.extend((0xA9,warm,0x8D,0x20,0x6A,0x9C,0x23,0x6A))
    entry=sy['M_START'] if warm is None else sy['M_WARM_ENTRY']
    stub.extend((0x4C,entry&255,entry>>8));assert len(stub)<256
    a[0x1600:0x1600+len(stub)]=stub
    a[:3]=bytes.fromhex('4C 00 18')
    assert len(a)<=0x6300
    return bytes(a)


def run():
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    assert time.time()+360<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp(),'RTC window; no port opened'
    mf=json.loads((BUILD/'manifest.json').read_text())
    name=next(n for n,v in mf['artifacts'].items() if v['variant']=='RAM')
    core=(BUILD/name).read_bytes();assert t.sha(core)==mf['artifacts'][name]['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==v for n,v in mf['source_sha256'].items())
    bindings=(BUILD/'RAM/foundation.inc').read_text()
    assert 'MON_SETTINGS_IMAGE_PAGE EQU $0070' in bindings and 'MON_SETTINGS_BASE EQU $7290' in bindings
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(BUILD/'RAM/mona.map').read_text(),re.M)}
    hm=json.loads((HELPER/'manifest.json').read_text());helper=(HELPER/'EDU-SETTINGS-RAM.bin').read_bytes()
    assert t.sha(helper)==hm['artifacts']['EDU-SETTINGS-RAM.bin']['sha256']
    helptext=(HELPER/'MON-SHARED-HELP.bin').read_bytes()
    cases=[('cold-default-ON',[], 'valid',None,1,True),
           ('cold-saved-OFF',[record(1,0)],'valid',None,0,True),
           ('cold-newest-ON',[record(1,0),record(2,1)],'valid',None,1,True),
           ('cold-conflict-retains-default',[record(3,0),record(3,1)],'valid',None,1,True),
           ('corrupt-container-refused',[record(1,0)],'bad-crc',None,1,False),
           ('wrong-helper-ID-refused',[record(1,0)],'bad-id',None,1,False),
           ('missing-helper-fallback',[record(1,0)],'missing',None,1,False),
           ('warm-retains-session-OFF',[record(2,1)],'valid',0,0,True),
           ('warm-retains-session-ON',[record(2,0)],'valid',1,1,True)]
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,metadata_writes=0,
       SRAM_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,
       owner_RAM_restored=False,owner_ZP_restored=False,build=str(BUILD),core_sha256=t.sha(core),
       fixture='CPU RAM5000-53FF only; sealed helper/help7000-73FF; no real metadata record',
       ROM_installation_qualified=False,confirmed_save_qualified=False)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json';s=None;ram=zp=prefix=old3=None;borrowed=False;marker=None;oldedu=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context is None:s.link.send(b'\r');s.until((t.MON,t.REC),seconds=10)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with t.serial_lease('2512-saved-EDU-startup-help-RAM-only',timeout=60):
      if drift_pending():raise InterruptedError('RTC priority; no port opened')
      marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000D / MON B' in s.command('VERSION')
            oldedu=s.dump(0x6A20,0x6A20)[0];assert s.dump(0x7DF9,0x7DF9)!=b'\xb7','Active BATCH; stop'
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(edu_startup_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            opaque.durable_file(OUT/'B3-before.bin',old3)
            for label,rows,kind,warm,expected,shared in cases:
                if drift_pending():raise InterruptedError('RTC priority between cases')
                rec();body=packet(core,sy,helper,helptext,rows,kind,warm);(OUT/(label+'.bin')).write_bytes(body)
                s.load(body,t.sha(body),t.MON)
                assert s.dump(0x200,0x202)==core[:3],'Setup must restore exact initial JMP'
                state=s.dump(0x6A20,0x6A23);assert state[0]==expected and state[3]==0,(label,state)
                face=s.command('?');(OUT/(label+'-help.txt')).write_bytes(face)
                assert (b'M1-3 W APPS APP CLOCK FLASH MAINT' in face)==shared
                assert b'VERSION TIME B0..3 D M/!M G L Q' in face
                version=s.command('VERSION');(OUT/(label+'-VERSION.txt')).write_bytes(version)
                assert b'g0000000E / RAM' in version and b'CPU: 65C02' in version
                assert (b'EDU ON' if expected else b'EDU OFF') in version
                assert s.dump(0x6A20,0x6A23)[0]==expected,'VERSION must preserve session override'
                r['checks'].append(label);save();print('PASS2512 EDU startup '+label,flush=True)
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
                mon();assert b'g0000000D / MON B' in s.command('VERSION')
                if oldedu!=1:s.command(f'!M 6A20 {oldedu:02X}')
                assert s.dump(0x6A20,0x6A20)[0]==oldedu
                rec();r['EDU_session_restored']=True
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('EDU_session_restored',False)
                mark(edu_startup_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                     block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_EDU_startup_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==len(cases) and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    save();assert r['passed'];print('PASS2512 EDU startup/help RAM integration; ROM unchanged; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
