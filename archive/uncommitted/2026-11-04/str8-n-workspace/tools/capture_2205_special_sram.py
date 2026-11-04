"""Read-only full SPI companion to the permanent2205 b35 special image."""
import binascii,json,re,time
from pathlib import Path
import install_named_edu_2512 as guard
from capture_2205_special_permanent import ARCHIVE,F_HASH
from inventory_boards_readonly import durable,sha
from installer.engine.legacy_transport import Link,s19
from installer.common import save
from serial_test_coordination import serial_lease,drift_pending

ROOT=Path(__file__).resolve().parents[1];OUT=ARCHIVE/'SPI-companion-r3';MON=b'\r\nB3> ';PB=b'PB> '

def packet(flash):
 folder=ROOT/'BUILD/SRAM-reader-current-r2';pb=bytearray((folder/'SRAM-READ-ONLY-CURRENT-RAM.bin').read_bytes());assert sha(pb)=='12b4836319b6bf77e6031079c18f856df94bb52779a837c5f05be164040b9126'
 assert sha(flash)==F_HASH and pb[0x34]==pb[0x3e]==0xc9
 crc=binascii.crc_hqx(flash,65535);pb[0x35]=crc&255;pb[0x3f]=crc>>8
 pos=0x4a2-0x200;pb[pos:pos+2]=binascii.crc_hqx(pb[:pos],65535).to_bytes(2,'big');assert binascii.crc_hqx(pb,65535)==0
 provider=(ROOT/'release/str8nf-v0.2.0/monitors/candidates/program-sp1-g00000002-wide-r5/STR8N-PROGRAM-SP1-6B00.bin').read_bytes();assert len(provider)==3328 and sha(provider)=='865294b6572e7dc403deb87ed2920ef6e46f9791db2f62c8f07cfc1b6758c4be'
 a=bytearray(b'\xff'*0x1c00);a[:len(pb)]=pb;a[0xf00:]=provider
 code=bytearray(bytes.fromhex('78 D8 A9 80 8D 04 1E'))
 # Legacy D deliberately refuses I/O. Read only inert direction/control
 # registers in RAM and refuse before any GPIO write or provider replacement.
 for i,(address,mask) in enumerate(((0x7fc2,0x2f),(0x7fcb,0x1e),(0x7fcc,0xf0),(0x7fce,0x18))):
  code+=bytes((0xad,address&255,address>>8,0x8d,i,0x1e,0x29,mask,0xf0,3,0x4c,0x67,0x7e))
 code+=bytes.fromhex('A9 00 8D 04 1E A2 00');loop=0x1000+len(code)
 for p in range(13):code+=bytes((0xbd,0,0x11+p,0x9d,0,0x6b+p))
 code+=bytes((0xe8,0xd0,(loop-(0x1000+len(code)+3))&255))
 for i,v in enumerate(pb[:3]):code+=bytes((0xa9,v,0x8d,i,2))
 code+=bytes.fromhex('A9 01 8D CC 69 4C 00 02');assert len(code)<256
 a[0xe00:0xe00+len(code)]=code;a[:3]=bytes.fromhex('4C 00 10')
 return bytes(a)

def run():
 assert json.loads((ARCHIVE/'live-board/report.json').read_text())['passed']
 print('2205 read-only SPI companion waiting for RTC window540s',flush=True)
 while True:
  try:guard.window(540);break
  except AssertionError:time.sleep(1)
 r=dict(board='2205',passed=False,flash_writes=0,SPI_writes=0,RTC_setting_writes=0,resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,owner_RAM_restored=False,owner_ZP_restored=False)
 mp=ROOT/'output/qualification/device-operations/2205.json';link=None;borrowed=False;context=None
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);save(mp,m)
 def checkpoint():save(OUT/'report.json',r)
 with serial_lease('2205-SPECIAL-readonly-full-SPI-escrow',timeout=600):
  guard.window(540);OUT.mkdir();m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot']
  from serial.tools.list_ports import comports
  assert any(p.device=='COM3' and p.serial_number=='A10MPUPNA' for p in comports())
  durable(OUT/'marker-before.json',mp.read_bytes());durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    link=Link('COM3',log);link.send(b'\r');link.until(MON,seconds=10);context=MON
    def dump(a,z):return b''.join(link.dump(i,min(i+511,z),MON) for i in range(a,z+1,512))
    ram=dump(0x200,0x66ff);zp=dump(0,0xdf);upper=dump(0x6500,0x77ff);vectors=dump(0x7e00,0x7e8f)
    for n,v in [('owner-ram.bin',ram),('owner-zp.bin',zp),('upper-RAM-6500-77FF.bin',upper),('legacy-vectors.bin',vectors)]:durable(OUT/n,v)
    b3=dump(0x8000,0xffff);assert b3==(ARCHIVE/'live-board/b3.bin').read_bytes()
    def load(address,body,entry=None):
     nonlocal context
     assert context==MON and 0x200<=address and address+len(body)<=0x6500
     text=s19(dict(enumerate(body,address)),address if entry is None else entry)
     link.command('L',b'S19');context=None
     for row in text.splitlines():link.send(row+b'\r\n');time.sleep(.04)
     face=link.until(MON);context=MON
     assert b'Entry' in face and not any(x in face for x in (b'Bad',b'Protected',b'Wrap',b'Error'))
     assert dump(address,address+len(body)-1)==body
    image=packet(b3[-4096:]);durable(OUT/'read-only-RAM-transport.bin',image)
    if drift_pending():raise InterruptedError('RTC priority before helper load')
    mark(special_2205_SPI_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    load(0x200,image);link.send(b'G 0200\r');context=None
    try:link.until(PB,seconds=15);context=PB
    except TimeoutError:
     link.until(MON,seconds=3);context=MON
     r['RAM_guard_result']=dump(0x1e00,0x1e04).hex();checkpoint()
     raise AssertionError('RAM read-only guard/helper refused; no SPI write or flash operation')
    data=bytearray()
    for a in range(0,0x20000,64):
     if drift_pending():raise InterruptedError('RTC priority during read; restore borrowed RAM, no SRAM/flash writes')
     link.send(b'R'+a.to_bytes(3,'big').hex().upper().encode()+b'\r');face=link.until(PB)
     match=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(match)==1,face
     frame=bytes.fromhex(match[0].decode());assert int.from_bytes(frame[:3],'big')==a and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
     data.extend(frame[3:-2])
     if (a+64)%32768==0:print(f'2205 SPI backup {a+64}/131072',flush=True)
    durable(OUT/'SPI-SRAM-FULL-128KiB.bin',data)
    import sys;sys.path.insert(0,str(ROOT/'release/str8nf-v0.2.0/tools'));from program_format import inspect
    layout=inspect(bytes(data));save(OUT/'PROGRAM-WORK-layout.json',layout);r.update(full_SPI_sha256=sha(data),format=layout['format'],PROGRAM_boundary=layout['boundary'],full_SPI_backed_up=True)
   except BaseException as e:r['error']=repr(e);checkpoint();raise
   finally:
    try:
     if borrowed:
      if context==PB:link.send(b'Q');link.until(MON);context=MON
      assert context==MON,'Unknown legacy state; no blind restoration upload'
      # Restore original upper RAM/cache/session/ZP through a small copying
      # bridge, then restore all lower owner RAM with load-only S19.
      load(0x2000,upper+zp)
      code=bytearray(bytes.fromhex('78 D8 A2 00'))
      for p in range(19):code+=bytes((0xbd,0,0x20+p,0x9d,0,0x65+p))
      code+=bytes((0xe8,0xd0,(0x3804-(0x3800+len(code)+3))&255))
      code+=bytes.fromhex('A2 00');at=0x3800+len(code);code+=bytes.fromhex('BD 00 33 95 00 E8 E0 E0 D0')+bytes(((at-(at+10))&255,))+bytes.fromhex('4C 67 7E')
      load(0x3800,bytes(code));link.command('G 3800',MON)
      load(0x200,ram[:0x6300])
      assert dump(0x200,0x66ff)==ram and dump(0,0xdf)==zp and dump(0x6500,0x77ff)==upper and dump(0x7e00,0x7e8f)==vectors
      assert dump(0x8000,0xffff)==b3
      r.update(owner_RAM_restored=True,owner_ZP_restored=True,upper_cache_session_restored=True,vectors_exact=True,B3_exact=True)
    finally:
     if link:link.serial.close();r['port_released']=True
     if borrowed:
      ok=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(special_2205_SPI_worker_active=False,application_ram_restored=ok,application_RAM_restore_pending=not ok,block_snapshot=not ok,final_prompt='B3>' if ok else 'RESTORATION REQUIRED',last_special_SPI_backup=str(OUT/'report.json'))
     checkpoint()
 r['passed']=bool(r.get('full_SPI_backed_up') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('B3_exact'));checkpoint();assert r['passed']
 print('PASS2205 full SPI companion; original RAM/ZP/cache/vectors restored; COM3 free',flush=True)

if __name__=='__main__':run()
