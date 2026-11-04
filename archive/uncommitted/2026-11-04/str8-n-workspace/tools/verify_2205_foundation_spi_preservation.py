"""Post-rollout full SPI read: no SPI, flash, journal or RTC data writes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import devtools_2512_session as ds
import standardize_ss2_64k as spi
from install_2205_foundation_profile import Session,t,SCOPE,CONVERSION,MP
from serial_test_coordination import serial_lease
from inventory_boards_readonly import durable
from installer.common import save

OUT=ROOT/'output/qualification/2205-foundation-SPI-preservation-20261102-r1'
BEFORE=ROOT/'local-archives/STR8-N-b35-2205-SPECIAL-20261102/SPI-companion-r3/SPI-SRAM-FULL-128KiB.bin'

class Escrow(ds.Session):
    def __init__(self,out,r):
        self.out=out;self.r=r;self.s=None;self.mp=MP;self.high=None;self.cache_first=0x6b00

def run():
    assert json.loads((ROOT/'output/qualification/2205-foundation-default-reset-20261102-r1/report.json').read_text())['passed']
    before=BEFORE.read_bytes();assert t.sha(before)=='9b86f827d007513b127e1a6d252e7ccd4492ba5babc83170be3ff315284de400'
    spi.wait_window(420)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
    r=dict(board='2205',passed=False,SPI_writes=0,flash_writes=0,journal_writes=0,RTC_setting_writes=0,resets=0,power_cuts=0)
    x=Escrow(OUT,r);x.save();borrowed=False
    with serial_lease('2205-Foundation-full-SPI-preservation-readonly',timeout=600):
      ds.ins.window(420);m=json.loads(MP.read_text())
      assert m['foundation_physical_boot_qualified'] and m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
      assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
      durable(OUT/'marker-before.json',MP.read_bytes())
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          s=x.s=Session(OUT,log);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15)
          borrowed=True;x.mark(foundation_SPI_verify_worker_active=True,application_RAM_restore_pending=True,application_ram_restored=False)
          x.mon();assert b'Board: 2205' in x.cmd('VERSION')
          x.wb();x.cmd('TABLE P');x.cmd('WORK');x.mon()
          x.high=s.dump(0x6b00,0x77ff);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
          durable(OUT/'Foundation-provider-cache-before.bin',x.high)
          after=spi.capture(x,'after',spi.reader_packet())
          assert after==before,'SPI changed from permanent SPECIAL archive'
          from program_format import inspect
          layout=inspect(after);save(OUT/'layout-after.json',layout)
          assert layout['format']=='SS2' and layout['boundary']=='08000' and len(layout['records'])==2
          assert all(v['payload_CRC_valid'] for v in layout['records'])
          r.update(whole_SPI_exact=True,SPI_sha256=t.sha(after),PROGRAM_boundary='08000',old_CLK_records_preserved=True)
        except BaseException as e:r['error']=repr(e);x.save();raise
        finally:
          try:
            if borrowed:
              x.mon()
              if x.high is not None:
                x.restore_high();assert x.hooks()==x.oldhooks
              x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
              try:
                for bank in range(4):assert s.client.flash(bank)==(SCOPE/'compact'/f'B{bank}-expected.bin').read_bytes()
                r['all_four_banks_exact']=True
              finally:
                r.update(s.client.restore_owner((CONVERSION/'owner-ram.bin').read_bytes(),(CONVERSION/'owner-zp.bin').read_bytes()));s.context=t.REC
          finally:
            if x.s:x.s.link.close();r['port_released']=True
            restored=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored'))
            if borrowed:x.mark(foundation_SPI_verify_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_foundation_SPI_preservation=str(OUT/'report.json'))
            x.save()
    r['passed']=all(r.get(k) for k in ('whole_SPI_exact','all_four_banks_exact','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
    x.save();assert r['passed'];print('PASS2205 full128KiB SPI unchanged; original SS2/32K and both CLK records retained; owner RAM/ZP restored',flush=True)

if __name__=='__main__':run()
