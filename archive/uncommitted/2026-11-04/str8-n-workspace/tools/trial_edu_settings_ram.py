"""Run the new settings reader against RAM fixtures; never save board metadata."""
import argparse,binascii,json
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t


def record(sequence,mode,*,commit=0,reserved=False):
    a=bytearray(b'\xff'*32);a[:4]=b'ED\x01\0';a[4:8]=sequence.to_bytes(4,'little');a[8]=mode
    if reserved:a[9]=0
    a[28:30]=binascii.crc_hqx(a[:28],65535).to_bytes(2,'little');a[31]=commit
    return bytes(a)


def packet(helper,rows):
    code=bytearray(bytes.fromhex('78 D8 A2 00'));loop=len(code)
    code.extend(bytes.fromhex('BD 00 03 9D 90 72 E8 E0'));code.append(len(helper));code.append(0x90);code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('20 98 72 8D 40 03 08 68 8D 41 03 A2 07'))
    loop=len(code);code.extend(bytes.fromhex('BD 00 67 9D 42 03 CA 10'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('4C 67 7E'));assert len(code)<256 and len(helper)<=240
    data=bytes(code).ljust(256,b'\xff')+helper
    data=data.ljust(0x4E00,b'\xff')+b''.join(rows).ljust(1024,b'\xff')
    assert len(data)==0x5200;return data


def run(out):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/edu-settings-g1-ram-r1';mf=json.loads((build/'manifest.json').read_text())
    helper=(build/'EDU-SETTINGS-RAM.bin').read_bytes();assert t.sha(helper)==mf['artifacts']['EDU-SETTINGS-RAM.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/'output/qualification/device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
           power_cuts=0,resets=0,owner_RAM_restored=False,owner_ZP_restored=False,table='synthetic CPU RAM5000-53FF, never flash9C00')
    s=None;marker=None;borrowed=False;ram=zp=prefix=old3=None;origin=None;edu=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC
    cases=[('no-record-default-ON',[],1,1),('saved-OFF',[record(1,0)],0,1),
           ('newest-ON',[record(2,1),record(1,0)],1,1),
           ('uncommitted-and-reserved-ignored',[record(1,0),record(9,1,commit=255),record(10,1,reserved=True)],0,1),
           ('equal-newest-conflict-refused',[record(3,0),record(3,1)],0x41,0),
           ('newer-resolves-old-conflict',[record(3,0),record(3,1),record(4,1)],1,1),
           ('zero-sequence-and-mode2-ignored',[record(0,0),record(2,2)],1,1)]
    save()
    with t.serial_lease('2512-saved-EDU-reader-RAM-fixtures',timeout=600):
      if drift_pending():raise InterruptedError('RTC priority before any board access')
      marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context;mon()
            edu=s.dump(0x6A20,0x6A20)[0];prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(edu_settings_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);(folder/'B3-before.bin').write_bytes(old3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            for name,rows,value,carry in cases:
                if drift_pending():raise InterruptedError('RTC priority')
                rec();body=packet(helper,rows);(folder/(name+'.bin')).write_bytes(body)
                s.load(body,t.sha(body),t.MON);answer=s.dump(0x340,0x349)
                assert answer[0]==value and answer[1]&1==carry,(name,answer)
                r['checks'].append(name);save();print('PASS2512 EDU '+name,flush=True)
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          try:
            if borrowed:
                if s.context is None:s.until((t.MON,t.REC),seconds=5)
                rec();s.service(reader)
                if old3 is not None:r['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:s.command(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(edu_settings_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                     block_snapshot=marker['block_snapshot'] if restored else True,last_EDU_settings_RAM_trial=str(folder/'report.json'))
            save()
    r['passed']=len(r['checks'])==len(cases) and not r.get('error') and not r.get('yielded_to_collection') and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+'2512 saved EDU reader; RAM restored; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
