"""Known B0 monitor return; restore fresh owner escrow, no NVM writes."""
import json
import install_2512_native_utilities as d
t=d.t
BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1'
CASE=BASE/'native-RAM-recovery';PRE=BASE/'preflight-resume2'
def run():
 CASE.mkdir(exist_ok=False)
 report=dict(board='2512',passed=False,flash_writes=0,SRAM_writes=0,RTC_writes=0)
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 with t.serial_lease('2512-batch-wide-owner-recovery',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   s=d.Session(CASE,log,'2512')
   try:
    s.link.send(b'\r');s.until(tuple(f'B{b}> '.encode() for b in range(4)),seconds=12)
    s.command('B3',(t.MON,));s.command('Q',(t.REC,));t.transport.recovery_usb(s.link);s.service(reader)
    report.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01')
    report['passed']=True
   finally:
    s.link.close();report['COM4_released']=True;t.save(CASE/'report.json',report)
    m=json.loads(t.MARK.read_text());m.update(batch_wide_worker_active=False,application_RAM_restore_pending=not report['passed'],block_snapshot=not report['passed'],application_ram_restored=report['passed']);t.save(t.MARK,m)
 print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
