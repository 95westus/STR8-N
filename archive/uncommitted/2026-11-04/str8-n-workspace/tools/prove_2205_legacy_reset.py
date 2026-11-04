"""Passive, unchanged-b35 RESET path proof before authorized2205 flashing."""
import json,time
from pathlib import Path
import capture_2205_special_sram as spi
from inventory_boards_readonly import durable,sha
from installer.engine.legacy_transport import Link,s19
from installer.common import save
from serial_test_coordination import serial_lease

ROOT=spi.ROOT;ARCHIVE=spi.ARCHIVE;OUT=ROOT/'output/qualification/2205-b35-reset-path-20261102-r1'
MP=ROOT/'output/qualification/device-operations/2205.json';MON=spi.MON

def dump(link,a,z):return b''.join(link.dump(i,min(i+511,z),MON) for i in range(a,z+1,512))
def load(link,address,body):
 assert 0x200<=address and address+len(body)<=0x6500
 text=s19(dict(enumerate(body,address)),address);link.command('L',b'S19')
 for row in text.splitlines():link.send(row+b'\r\n');time.sleep(.04)
 face=link.until(MON);assert b'Entry' in face and not any(x in face for x in (b'Bad',b'Protected',b'Wrap',b'Error'))
 assert dump(link,address,address+len(body)-1)==body

def restore(link,ram,zp,upper):
 assert len(ram)==0x6500 and len(zp)==0xe0 and len(upper)==0x1300
 load(link,0x2000,upper+zp);code=bytearray(bytes.fromhex('78 D8 A2 00'))
 for p in range(19):code+=bytes((0xbd,0,0x20+p,0x9d,0,0x65+p))
 code+=bytes((0xe8,0xd0,(0x3804-(0x3800+len(code)+3))&255));code+=bytes.fromhex('A2 00 BD 00 33 95 00 E8 E0 E0 D0 F6 4C 67 7E')
 load(link,0x3800,bytes(code));link.command('G 3800',MON);load(link,0x200,ram[:0x6300])
 assert dump(link,0x200,0x66ff)==ram and dump(link,0,0xdf)==zp
 # The cold firmware may legitimately reinitialize non-owner runtime fields;
 # original upper cache is restored before further migration work.
 assert dump(link,0x6500,0x77ff)==upper

def run():
 backup=json.loads((spi.OUT/'report.json').read_text());assert backup['passed'] and backup['owner_RAM_restored'] and backup['B3_exact']
 print('2205 unchanged-board RESET receiver waiting for RTC window180s',flush=True)
 while True:
  try:spi.guard.window(180);break
  except AssertionError:time.sleep(1)
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');r=dict(board='2205',passed=False,phase='preflight',flash_writes=0,SPI_writes=0,RTC_setting_writes=0,physical_resets=0,power_cuts=0,owner_RAM_restored=False)
 def mark(**kw):m=json.loads(MP.read_text());m.update(kw);save(MP,m)
 def checkpoint():save(OUT/'report.json',r)
 link=None;checkpoint()
 with (OUT/'serial.jsonl').open('x') as log:
  try:
   with serial_lease('2205-unchanged-b35-reset-path-arming',timeout=600):
    spi.guard.window(180);m=json.loads(MP.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot']
    from serial.tools.list_ports import comports
    assert any(p.device=='COM3' and p.serial_number=='A10MPUPNA' for p in comports())
    link=Link('COM3',log);link.send(b'\r');link.until(MON,seconds=10)
    original=dump(link,0x8000,0xffff);assert original==(ARCHIVE/'live-board/b3.bin').read_bytes()
    ram=dump(link,0x200,0x66ff);zp=dump(link,0,0xdf);upper=dump(link,0x6500,0x77ff);vectors=dump(link,0x7e00,0x7e8f)
    for n,v in [('owner-ram.bin',ram),('owner-zp.bin',zp),('legacy-upper-RAM.bin',upper),('legacy-vectors.bin',vectors)]:durable(OUT/n,v)
    durable(OUT/'marker-before.json',MP.read_bytes());link.serial.reset_input_buffer();link.pending.clear()
    mark(physical_reset_pending=True,foundation_preflight_reset_waiting=True)
    r['phase']='waiting-for-physical-reset';checkpoint()
   print('ARMED2205 unchanged-board RESET; passive COM3; no flashing; fleet lease released',flush=True)
   end=time.monotonic()+12*3600;tail=bytearray()
   while time.monotonic()<end:
    tail.extend(link.read(max(1,link.serial.in_waiting)))
    if len(tail)>32768:del tail[:-32768]
    if b'MONITOR A gen' in tail and b'MONITOR B gen' in tail and tail.endswith(b'B3> '):break
   else:raise TimeoutError('No unchanged-board b35 B3 RESET startup captured')
   durable(OUT/'physical-reset-startup.txt',tail);assert b'00000028' in tail and b'0000002F' in tail and b'2.0b35' in tail
   r.update(physical_resets=1,phase='legacy-B3-reset-startup-captured');checkpoint()
   with serial_lease('2205-unchanged-b35-reset-path-verification',timeout=600):
    mark(physical_reset_pending=False,foundation_preflight_reset_waiting=False,foundation_preflight_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    link.pending.clear();after=dump(link,0x8000,0xffff);durable(OUT/'B3-after-reset.bin',after)
    r['B3_exact']=after==original;r['scope_refresh_required']=after!=original
    cold=dump(link,0x7e00,0x7e8f);durable(OUT/'cold-b35-vectors.bin',cold)
    if dump(link,0x200,0x66ff)!=ram or dump(link,0,0xdf)!=zp or dump(link,0x6500,0x77ff)!=upper:restore(link,ram,zp,upper)
    r.update(owner_RAM_restored=True,owner_ZP_restored=True,original_upper_cache_restored=True,physical_B3_reset_path_verified=True)
    r['passed']=r['B3_exact'];r['phase']='unchanged-board-reset-path-verified' if r['passed'] else 'metadata-drift-review-required';checkpoint()
    mark(foundation_preflight_worker_active=False,physical_reset_pending=False,application_ram_restored=True,application_RAM_restore_pending=False,block_snapshot=not r['passed'],last_legacy_reset_proof=str(OUT/'report.json'),final_prompt='B3>')
  except BaseException as e:r['error']=repr(e);checkpoint();raise
  finally:
   if link:link.serial.close();r['port_released']=True
   checkpoint()
 assert r['passed'];print('PASS2205 physical RESET enters original b35 B3; flash exact; owner restored; COM3 free',flush=True)

if __name__=='__main__':run()
