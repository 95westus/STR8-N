"""Execute the qualified phase image in both CPU/I2C models; no board access."""
import argparse,sys,json,hashlib
from pathlib import Path
from rtc_phase_contract import DEFAULT_BUILD, ROOT, verify_image
from rtc_phase_bus_model import BusMemory
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build',type=Path,default=DEFAULT_BUILD)
parser.add_argument('--deps-02',type=Path,default=ROOT/'BUILD/v1.30/local/test-deps')
parser.add_argument('--deps-816',type=Path,default=ROOT/'BUILD/test-deps-816')
args=parser.parse_args()
sys.path[:0]=[str(args.deps_02),str(args.deps_816)]
from py65816.devices.mpu65c816 import MPU as MPU816
from py65.devices.mpu65c02 import MPU as MPU02
out=args.build;image=(out/'phase.bin').read_bytes();sy=json.loads((out/'symbols.json').read_text());verify_image(image,sy);checks=[]
for kind,MPU in [('65C02',MPU02),('65C816 emulation',MPU816)]:
 for case in ('observe','calibrate','pause','advance','advance-59','bad-key','zero','over-limit','PF','alarm','trim','absent','stuck-scl','stuck-sda','stopped'):
  m=BusMemory(present=case!='absent',stuck='scl' if case=='stuck-scl' else 'sda' if case=='stuck-sda' else None)
  m.ram[0x2000:0x2000+len(image)]=image
  m.regs[7:9]=bytes([0x80,0x0c]);m.ram[sy['EXPECTED']:sy['EXPECTED']+2]=m.regs[7:9]
  m.ram[sy['KEY']:sy['KEY']+2]=b'PH';m.ram[sy['TICKS']:sy['TICKS']+2]=(2).to_bytes(2,'little')
  if case in ('advance','advance-59'):m.ram[sy['ADJUST']]=1
  if case=='advance-59':m.regs[0]=0xd9
  if case=='bad-key':m.ram[sy['KEY']]=0
  if case=='zero':m.ram[sy['TICKS']:sy['TICKS']+2]=b'\0\0'
  if case=='over-limit':m.ram[sy['TICKS']:sy['TICKS']+2]=b'\0\x40'
  if case=='PF':m.regs[3]|=0x10
  if case=='alarm':m.regs[7]|=0x10
  if case=='trim':m.regs[8]=0
  if case=='stopped':m.regs[0]&=0x7f;m.regs[3]&=~0x20
  before=bytes(m.regs);entry=sy['OBSERVE'] if case=='observe' else sy['CALIBRATE'] if case=='calibrate' else sy['PAUSE_CLOCK']
  c=MPU(memory=m,pc=entry);c.pc=entry;c.sp=0xff;c.p=0x34;output=bytearray();queue=bytearray(b'rq' if case=='observe' else b'r')
  for steps in range(2_000_000):
   if c.pc==0x7e67:break
   if c.pc==0x7e70:c.a=queue.pop(0);c.pc=(c.stPopWord()+1)&65535
   elif c.pc==0x7e6d:output.append(c.a&255);c.pc=(c.stPopWord()+1)&65535
   else:c.step()
  else:raise AssertionError((kind,case,'unbounded',hex(c.pc)))
  pos=output.index(64);output=output[pos:pos+19]
  assert output[0]==64 and len(output)==19,(case,output)
  success=case in ('observe','calibrate','pause','advance')
  assert (output[1]==0)==success,(kind,case,output[1])
  expected=bytearray(before)
  if case=='advance':expected[0]=0xd9
  assert bytes(m.regs)==bytes(expected),(kind,case,'RTC state differs')
  assert all(a in (0xde,0xdf) for a in m.accesses),(case,'non-RTC address')
  assert all(a==0 for a,v in m.writes),(case,'write outside RTCSEC')
  if case in ('pause','advance'):assert m.writes==[(0,before[0]&127),(0,expected[0])],m.writes
  else:assert not m.writes,(case,m.writes)
  assert m.ddr==m.initial_ddr and m.latch&m.ddr==m.initial_latch&m.ddr
  checks.append(dict(CPU=kind,case=case,passed=True,steps=steps,writes=m.writes))
proof=dict(passed=True,image_sha256=hashlib.sha256(image).hexdigest(),checks=checks)
(out/'proof.json').write_text(json.dumps(proof,indent=2))
print('PASS',len(checks),'CPU/I2C cases; writes confined to RTCSEC; GPIO/trim/PF preserved')
