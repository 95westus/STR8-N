"""Read-only three-board cleanup inventory; no flash/SPI/RTC-setting writes."""
import json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import devtools_2512_session as ds
from inventory_boards_readonly import durable
from installer.common import save
from serial_test_coordination import serial_lease,drift_pending
t=ds.t;Q=ds.Q
IDS={'2512':('COM4','A10MQFLCA',b'CPU: 65C02'),'2604':('COM5','A10MQGVHA',b'CPU: 65C02'),'2609':('COM8','A10MPQXCA',b'CPU: 65C816 emulation')}
BASE=Q/'unified-cleanup-inventory-20261102-r1'


class BoardSession(t.Session):
    def __init__(self,out,log,board):
        self.folder=out;self.context=None;self.counter=0;self.client=None
        port,usb,_=IDS[board];self.link=t.transport.RecoveryLink(port,log,usb_serial=usb)


class Escrow(ds.Session):
    def __init__(self,out,report,board):
        self.out=out;self.r=report;self.s=None;self.borrowed=False
        self.ram=self.zp=self.high=None;self.cache_first=0x6b00
        self.mp=Q/f'device-operations/{board}.json'


def run(board):
    assert board in IDS
    while True:
        try:ds.ins.window(240);break
        except AssertionError:time.sleep(1)
    BASE.mkdir(exist_ok=True);(BASE/'.gitignore').write_text('*\n')
    out=BASE/board;out.mkdir()
    durable(out/'driver-as-executed.py',Path(__file__).read_bytes())
    r=dict(board=board,passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,resets=0,power_cuts=0)
    x=Escrow(out,r,board);reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    with serial_lease(board+'-unified-cleanup-readonly-inventory',timeout=30):
      ds.ins.window(240);m=json.loads(x.mp.read_text());x.original=m
      assert m['application_ram_restored'] and not m['block_snapshot'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
      assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
      durable(out/'marker-before.json',x.mp.read_bytes())
      with (out/'serial.jsonl').open('x') as log:
        try:
          s=x.s=BoardSession(out,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);x.mon()
          face=x.cmd('VERSION');assert IDS[board][2] in face and b'STR8-N MON B  gen 00000010' in face
          x.cmd('APPS');x.cmd('T 0-3')
          prefix=s.dump(0x200,0x1ff+len(reader));x.zp=s.dump(0,0xdf);x.high=s.dump(0x6b00,0x77ff);x.oldhooks=x.hooks()
          assert x.oldhooks==bytes.fromhex('577E4C937E')
          for name,body in [('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)]:durable(out/name,body)
          x.borrowed=True;x.mark(cleanup_inventory_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
          x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
          x.ram=prefix+memory[len(reader):];durable(out/'owner-ram.bin',x.ram)
          assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3']
          x.mon();x.cmd('MAINT LOAD',(t.WB,));x.cmd('SRAM');x.cmd('TABLE P');x.cmd('WORK')
          data=bytearray()
          for address in range(0,0x800,64):
            if drift_pending():raise InterruptedError('RTC priority before next read')
            face=x.cmd(f'SRAM READ 0 {address:04X}');match=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){63}[0-9A-F]{2})',face)
            assert match,face;data.extend(bytes.fromhex(match[1].decode()))
          durable(out/'SPI-metadata-00000-007FF.bin',data)
          # Host inspection gets only metadata. No payload CRC claim from padded bytes.
          from program_format import inspect
          padded=bytes(data)+bytes(0x20000-len(data));layout=inspect(padded)
          for record in layout['records']:
            record.pop('payload_sha256',None);record.pop('payload_CRC_valid',None)
          for record in layout['latest'].values():
            record.pop('payload_sha256',None);record.pop('payload_CRC_valid',None)
          layout.pop('sha256');layout['payloads_read']=False
          save(out/'PROGRAM-metadata-layout.json',layout)
          r['layout']=layout;r['SPI_metadata_sha256']=t.sha(data)
          x.cmd('Q',(t.MON,));r['inventory_complete']=True
        except BaseException as error:r['error']=repr(error);x.save();raise
        finally:
          try:
            if x.borrowed:
              x.mon();assert x.hooks()==x.oldhooks;x.restore_high();x.rec();s.service(reader)
              try:assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3'];r['B3_exact']=True
              finally:r.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
          finally:
            if x.s:x.s.link.close();r['port_released']=True
            if x.borrowed:
              restored=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored'))
              x.mark(cleanup_inventory_worker_active=False,application_RAM_restore_pending=not restored,
                application_ram_restored=restored,block_snapshot=not restored,final_prompt='REC>',last_unified_cleanup_inventory=str(out/'report.json'))
            x.save()
    r['passed']=bool(r.get('inventory_complete') and r.get('B3_exact') and r.get('provider_cache_restored') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored'));x.save()
    assert r['passed'];print(json.dumps(dict(board=board,passed=True,format=r['layout']['format'],boundary=r['layout']['boundary'],records=r['layout']['records'],owner_restored=True,port_released=True),indent=2))


if __name__=='__main__':run(sys.argv[1])
