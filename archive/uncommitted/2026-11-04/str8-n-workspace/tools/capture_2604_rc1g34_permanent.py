"""2604-only native read capture into the permanent ignored rc1g34 archive."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'release/str8nf-v0.2.0/migration-host')]
from inventory_boards_readonly import durable,describe,sha
from installer.engine.legacy_transport import Link
from installer.common import save
from serial_test_coordination import serial_lease,drift_pending
import install_named_edu_2512 as guard
from nf_migrate import classify_journal
OUT=ROOT/'local-archives/STR8-N-rc1-g0034-2604-20261102/live-board'
MON=b'\r\nB3> '

def run():
 print('2604 native read-only permanent capture waiting for RTC window240s',flush=True)
 while True:
  try:guard.window(240);break
  except AssertionError:time.sleep(1)
 OUT.mkdir();report=dict(board='2604',passed=False,flash_writes=0,RAM_uploads=0,SPI_accesses=0,RTC_accesses=0,resets=0,power_cuts=0,started_utc=guard.t.utc())
 mp=ROOT/'output/qualification/device-operations/2604.json'
 with serial_lease('2604-rc1g34-native-read-only-permanent-capture',timeout=30):
  guard.window(240);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  durable(OUT/'marker-before.json',mp.read_bytes());durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
  from serial.tools.list_ports import comports
  ports=[p for p in comports() if p.serial_number=='A10MQGVHA'];assert len(ports)==1 and ports[0].device=='COM5'
  link=None
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    link=Link('COM5',log);link.send(b'\r');initial=link.until(MON,seconds=10);durable(OUT/'initial-console.txt',initial)
    assert b'SEND BIN' not in initial and b'type YES' not in initial
    def dump(first,last,prompt=MON):return b''.join(link.dump(a,min(a+511,last),prompt) for a in range(first,last+1,512))
    ram=dump(0x200,0x66ff);zp=dump(0,0xdf);cache=dump(0x6b00,0x77ff);hooks=dump(0x7e00,0x7e8f)
    for name,body in [('owner-ram.bin',ram),('owner-zp.bin',zp),('provider-cache-before.bin',cache),('vectors-before.bin',hooks)]:durable(OUT/name,body)
    banks={}
    try:
     for repeat in (False,True):
      for bank in (3,0,1,2):
       if drift_pending():raise InterruptedError('RTC priority at bank boundary; no helper or writes')
       prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);body=dump(0x8000,0xffff,prompt)
       if bank==3:
        assert sha(body[-4096:])=='78ee949e20545cbe0e10030185dd5629b65c584af526c16e2c75c9fa103ceaec','Unadmitted current F'
        for offset in (0x2000,0x3000):assert int.from_bytes(body[offset+8:offset+12],'little')==0x34
       durable(OUT/(f'b{bank}-repeat.bin' if repeat else f'b{bank}.bin'),body)
       if repeat:assert body==banks[bank]
       else:banks[bank]=body
       print(f'PASS2604 bank{bank} '+('repeat' if repeat else 'original')+' '+sha(body),flush=True)
    finally:link.command('B3',MON)
    after=dump(0x200,0x66ff);low=dump(0,0xdf);high=dump(0x6b00,0x77ff);vectors=dump(0x7e00,0x7e8f)
    for name,body in [('owner-ram-repeat.bin',after),('owner-zp-repeat.bin',low),('provider-cache-after.bin',high),('vectors-after.bin',vectors)]:durable(OUT/name,body)
    assert ram==after and zp==low and cache==high and hooks==vectors,'Read-only preservation mismatch'
    combined=b''.join(banks[n] for n in range(4));durable(OUT/'full-flash-128KiB.bin',combined)
    capture=dict(schema=1,board='2604',cpu='65c02',board_model='W65C02SXB',usb_serial='A10MQGVHA',source_kind='rc1-monitor-s19',method='independent-double-read',owner_original_before_helpers=True,source_F_sha256=sha(banks[3][-4096:]),raw_L_supported=False,loader='native MON RAM S19 followed by explicit G',permanent_local_archive=True)
    durable(OUT/'capture.json',(json.dumps(capture,indent=2)+'\n').encode())
    report.update(passed=True,bank_sha256={f'B{n}':sha(banks[n]) for n in range(4)},full_flash_sha256=sha(combined),source_F_sha256=sha(banks[3][-4096:]),description=describe([banks[n] for n in range(4)]),journal=classify_journal(banks[3]),owner_RAM_unchanged=True,owner_ZP_unchanged=True,provider_cache_unchanged=True,vectors_unchanged=True,final_prompt='B3>')
   except BaseException as error:report['error']=repr(error);raise
   finally:
    if link:link.serial.close();report['port_released']=True
    report['finished_utc']=guard.t.utc();save(OUT/'report.json',report)
  if report['passed']:
   current=json.loads(mp.read_text());current.update(last_permanent_rc1g34_backup=str(OUT/'report.json'),current_physical_bank_sha256=report['bank_sha256'],prior_stale_fixed_F_sha256=current.get('current_fixed_F_sha256'),current_fixed_F_sha256=report['source_F_sha256'],current_F_sha256=report['source_F_sha256'])
   save(mp,current)
 manifest={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in OUT.iterdir() if p.is_file()};save(OUT/'backup-manifest.json',dict(permanent=True,local_only=True,files=manifest))
 print(json.dumps(dict(passed=True,permanent_capture=str(OUT),journal=report['journal'],owner_RAM_ZP_cache_vectors_unchanged=True,port_released=True),indent=2))

if __name__=='__main__':run()
