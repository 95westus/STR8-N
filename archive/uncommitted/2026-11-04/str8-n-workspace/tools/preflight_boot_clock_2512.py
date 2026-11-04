"""Read-only2512 BOOT/CLOCK scope inventory; borrowed owner RAM restored exactly."""
import json,re
from pathlib import Path
import install_startup_traditional_2512 as ins

t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-BOOT-CLOCK-preflight-20261101-r1'

def run():
    ins.base.window(240)
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    mp=Q/'device-operations/2512.json';reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,flash_writes=0,journal_appends=0,EEPROM_writes=0,RTC_SET=0,
        trim_writes=0,PF_ACK=0,SPI_data_writes=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;ram=zp=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**fields):m=json.loads(mp.read_text());m.update(fields);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        else:
            if s.context in (d.FT,t.CLOCK):cmd('Q',(t.MON,))
            if s.context==t.MON:cmd('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with t.serial_lease('2512-BOOT-CLOCK-readonly-scope-inventory',timeout=30):
      ins.base.window(240);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['block_snapshot'] and not marker['application_RAM_restore_pending']
      assert not marker['physical_reset_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['monitor_generation']=='00000010'
      t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
            if s.context==t.REC:cmd('B',(t.MON,))
            assert b'STR8-N MON B  gen 00000010' in cmd('VERSION')
            ram,zp=s.owner();(OUT/'owner-ram.bin').write_bytes(ram);(OUT/'owner-zp.bin').write_bytes(zp)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp));save()
            # Fresh scratch admission, without a whole-bank capture.
            cmd('B0',(b'B0> ',));face=cmd('D 9000 9FFF')
            cells={}
            for line in face.decode('ascii').splitlines():
                match=re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
                if match:cells.update((int(match[1],16)+i,v) for i,v in enumerate(bytes.fromhex(match[2])))
            assert set(cells)==set(range(0x9000,0xA000))
            scratch=bytes(cells[a] for a in range(0x9000,0xA000));(OUT/'B0-9000-original.bin').write_bytes(scratch)
            r['B0_9_blank']=scratch==b'\xff'*4096;cmd('B3',(t.MON,))
            metadata=s.dump(0x9C00,0x9FFF);(OUT/'B3-metadata-9C00.bin').write_bytes(metadata)
            mark(boot_clock_preflight_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            cmd('R FLASH',(d.FT,));cmd('BOOT');cmd('Q',(t.MON,))
            cmd('R CLOCK',(t.CLOCK,))
            for command in ('TIME','STATUS','TRIM','OFFSET','BATTERY','EUI','STATS','HISTORY'):
                face=cmd(command)
                assert not any(text in face for text in (b'Invalid command',b'Services unavailable',b'REFUSED')),(command,face)
            # Managed SCAN has read all four EEPROM rows into J_CACHE. Quiet Q
            # only rebinds the MON; it does not overwrite this system buffer.
            cmd('Q',(t.MON,));cache=s.dump(0x6B00,0x6B7F)
            (OUT/'EEPROM-00-7F-original.bin').write_bytes(cache)
            r.update(queries_completed=True,EEPROM_raw_sha256=t.sha(cache),metadata_sha256=t.sha(metadata));save()
        except BaseException as error:r['error']=repr(error);save();raise
        finally:
          try:
            if borrowed:
                rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            elif ram is not None:
                rec();r.update(owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_not_borrowed=True)
          finally:
            if s:s.link.close();r['COM4_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(boot_clock_preflight_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                    final_prompt='REC>',last_BOOT_CLOCK_preflight=str(OUT/'report.json'))
            save()
    r['passed']=bool(r.get('queries_completed') and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS2512 BOOT/CLOCK read-only inventory; owner restored;REC>;COM4 free',flush=True)

if __name__=='__main__':run()
