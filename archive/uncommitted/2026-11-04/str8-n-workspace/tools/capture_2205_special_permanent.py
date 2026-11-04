"""Permanent2205 b35 reference image; native double-read, no RAM uploads."""
import json,subprocess,time
from pathlib import Path
import install_named_edu_2512 as guard
from inventory_boards_readonly import durable,describe,sha
from installer.engine.legacy_transport import Link,slot_valid
from installer.common import save
from installer.engine.runtime import clean_journal
from serial_test_coordination import serial_lease,drift_pending

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'local-archives/STR8-N-b35-2205-SPECIAL-20261102'
OUT=ARCHIVE/'live-board';MON=b'\r\nB3> '
F_HASH='aff5874806721137ec7677beb2e80c0db7c3f563f8027967db4b898554a34028'

def run():
 ARCHIVE.mkdir(parents=True,exist_ok=True);(ARCHIVE/'.gitignore').write_text('*\n')
 print('2205 SPECIAL native double-read waiting for RTC window300s',flush=True)
 while True:
  try:guard.window(300);break
  except AssertionError:time.sleep(1)
 OUT.mkdir();r=dict(board='2205',passed=False,permanent_local_special_image=True,flash_writes=0,RAM_uploads=0,SPI_accesses=0,RTC_accesses=0,resets=0,power_cuts=0)
 mp=ROOT/'output/qualification/device-operations/2205.json';link=None
 with serial_lease('2205-b35-SPECIAL-permanent-native-backup',timeout=30):
  guard.window(300);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m.get('physical_reset_pending')
  assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
  from serial.tools.list_ports import comports
  ports=[p for p in comports() if p.serial_number=='A10MPUPNA'];assert len(ports)==1 and ports[0].device=='COM3'
  durable(OUT/'marker-before.json',mp.read_bytes());durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    link=Link('COM3',log);link.send(b'\r');durable(OUT/'initial-console.txt',link.until(MON,seconds=10))
    def dump(a,z,prompt=MON):return b''.join(link.dump(i,min(i+511,z),prompt) for i in range(a,z+1,512))
    original={n:dump(a,z) for n,a,z in [('owner-ram',0x200,0x66ff),('owner-zp',0,0xdf),('provider-cache',0x6b00,0x77ff),('runtime-vectors',0x7e00,0x7e8f)]}
    for n,v in original.items():durable(OUT/(n+'-before.bin'),v)
    durable(OUT/'legacy-control-state.bin',dump(0x7d00,0x7dff))
    banks={}
    try:
     for repeat in (False,True):
      for b in (3,0,1,2):
       if drift_pending():raise InterruptedError('RTC priority at bank boundary; original firmware unchanged')
       prompt=f'\r\nB{b}> '.encode();link.command(f'B{b}',prompt);body=dump(0x8000,0xffff,prompt)
       if b==3:
        assert sha(body[-4096:])==F_HASH,'Legacy F differs from admitted2205 b35 reference; inspect before mutation'
        for offset,page,generation in ((0x2000,0xa0,0x28),(0x3000,0xb0,0x2f)):assert slot_valid(body[offset:offset+4096],page) and int.from_bytes(body[offset+8:offset+12],'little')==generation
       durable(OUT/(f'b{b}-repeat.bin' if repeat else f'b{b}.bin'),body)
       if repeat:assert body==banks[b]
       else:banks[b]=body
       print('PASS2205 bank'+str(b)+(' repeat' if repeat else ' original'),flush=True)
    finally:link.command('B3',MON)
    for n,a,z in [('owner-ram',0x200,0x66ff),('owner-zp',0,0xdf),('provider-cache',0x6b00,0x77ff),('runtime-vectors',0x7e00,0x7e8f)]:
     v=dump(a,z);durable(OUT/(n+'-after.bin'),v);assert v==original[n]
    joined=b''.join(banks[b] for b in range(4));durable(ARCHIVE/'2205-b35-SPECIAL-FULL-FLASH-128KiB.bin',joined)
    for name,v in [('2205-b35-SPECIAL-F-4096.bin',banks[3][-4096:]),('2205-b35-SPECIAL-MON-A-g28.bin',banks[3][0x2000:0x3000]),('2205-b35-SPECIAL-MON-B-g2F.bin',banks[3][0x3000:0x4000]),('2205-b35-SPECIAL-WDC-B0.bin',banks[0]),('2205-b35-SPECIAL-legacy-CD-8192.bin',banks[3][0x4000:0x6000])]:durable(ARCHIVE/name,v)
    seq,off,row,valid=clean_journal([banks[b] for b in range(4)])
    counts=[max(int.from_bytes(v[24+3*i:27+3*i],'little') for _,_,v in valid) for i in range(32)]
    r.update(passed=True,bank_sha256={f'B{b}':sha(v) for b,v in banks.items()},full_flash_sha256=sha(joined),source_F_sha256=F_HASH,description=describe([banks[b] for b in range(4)]),legacy_journal=dict(sequence=seq,address=f'{off+0x8000:04X}',records=len(valid),counts=counts,config_hex=row[8:24].hex()),owner_RAM_unchanged=True,owner_ZP_unchanged=True,provider_cache_unchanged=True,vectors_unchanged=True,final_prompt='B3>')
   except BaseException as e:r['error']=repr(e);raise
   finally:
    if link:link.serial.close();r['port_released']=True
    save(OUT/'report.json',r)
  if r['passed']:
   m=json.loads(mp.read_text());m.update(last_permanent_b35_SPECIAL_backup=str(OUT/'report.json'),current_physical_bank_sha256=r['bank_sha256'],current_F_sha256=F_HASH,current_fixed_F_sha256=F_HASH);save(mp,m)
 if r['passed']:
  durable(ARCHIVE/'KEEP-LOCAL.txt',b'PERMANENT SPECIAL2205 b35 reference; private owner archive, never publish.\nFull-flash bank orderB0/B1/B2/B3, each32768 bytes. Original WDC image included privately.\nNative double reads match; owner RAM/ZP/cache/vectors unchanged.\nOriginal WC history/settings retained in full. Never restore old wear counts blindly.\nSPI SRAM and RTC evidence are separate companion captures before conversion.\nNo original firmware is replaced until preservation and conversion scope are reviewed.\n')
  files={str(p.relative_to(ARCHIVE)):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in ARCHIVE.rglob('*') if p.is_file()};save(ARCHIVE/'archive-manifest.json',dict(permanent=True,special=True,local_only=True,board='2205',files=files))
  rel=ARCHIVE.relative_to(ROOT).as_posix();assert not subprocess.run(['git','ls-files','--',rel],capture_output=True,text=True,check=True).stdout.strip()
  assert subprocess.run(['git','check-ignore',rel+'/2205-b35-SPECIAL-FULL-FLASH-128KiB.bin'],capture_output=True).returncode==0
 print('PASS2205 SPECIAL archive complete; exact native double reads; original RAM/cache retained; COM3 released',flush=True)

if __name__=='__main__':run()
