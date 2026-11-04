"""Execute the paired onboard REPORT code; serial ABI is captured in memory."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/asm-report'

sys.path.insert(0,str(ROOT/'BUILD/v1.30/local/test-deps'))
def run(cpu_name='65c02',cancel_after=None,source=None):
 if cpu_name=='65c02':
  from py65.devices.mpu65c02 import MPU
 else:
  sys.path.insert(0,str(ROOT/'BUILD/test-deps-816'))
  from py65816.devices.mpu65c816 import MPU
 memory=[0]*65536;cpu=MPU(memory=memory,pc=0x1000)
 sy=json.loads((OUT/'asm-app-symbols.json').read_text());rp=json.loads((OUT/'report-symbols.json').read_text())
 for name,address in [('asm-app',0x4000),('source',0x5d00),('report',0x6800)]:
  body=(OUT/(name+'.bin')).read_bytes();memory[address:address+len(body)]=body
 lines=source or (ROOT/'examples/source-cycle/report-demo.asm').read_text().splitlines()
 packed=b''.join((10*(i+1)).to_bytes(2,'little')+bytes((len(line),0))+line.encode() for i,line in enumerate(lines))
 memory[0x2000:0x2000+len(packed)]=packed
 memory[0x6500:0x6502]=(0x2000+len(packed)).to_bytes(2,'little')
 output=[];polls=0;cancel_enabled=False
 def call(address,stop_at=0x1000):
  nonlocal polls
  cpu.sp=255;cpu.stPushWord(0x0fff);cpu.pc=address
  for _ in range(30000000):
   if cpu.pc==stop_at:return
   if cpu.pc in (0x7e6d,0x7e7c,0x7e7f,0x7e76):
    if cpu.pc==0x7e6d:output.append(chr(cpu.a))
    elif cpu.pc==0x7e7c:output.append(f'{cpu.a:02X}')
    elif cpu.pc==0x7e7f:output.append('\r\n')
    else:
     polls+=1;cpu.p=(cpu.p|1) if cancel_enabled and cancel_after and polls>=cancel_after else (cpu.p&254)
    cpu.pc=(cpu.stPopWord()+1)&65535
   else:cpu.step()
  raise AssertionError(('CPU timeout',hex(cpu.pc),''.join(output)[-300:]))
 call(sy['ASM_ASSEMBLE']);assert memory[sy['ERROR']]==0
 original=bytes(memory[0x200:0x200+memory[0x6502]+256*memory[0x6503]])
 polls=0;cancel_enabled=True
 packed_before=memory[0x2000:0x2000+len(packed)]
 call(rp['RP_REPORT']);text=''.join(output)
 if not cancel_after:
  memory[sy['LINE']:sy['LINE']+7]=list(b'REPORT\0')
  cpu.x=0
  call(sy['DX_DISPATCH'],stop_at=sy['SHELL'])
  assert cpu.sp==255,('REPORT command leaked stack',cpu.sp)
 assert memory[0x2000:0x2000+len(packed)]==packed_before, ([(hex(0x2000+i),a,b) for i,(a,b) in enumerate(zip(packed,memory[0x2000:])) if a!=b][:15],text[-1000:],hex(cpu.pc))
 if cancel_after:
  assert memory[sy['ERROR']]==13 and memory[rp['RP_MODE']]==0
 else:
  assert memory[sy['ERROR']]==0,text[-300:]
  assert bytes(memory[0x200:0x200+len(original)])==original
 return text,memory,sy

def main():
 from py65.devices.mpu65c02 import MPU
 memory=[0]*65536
 packet=(OUT/'ASM-REPORT-RAM.bin').read_bytes()
 memory[0x200:0x200+len(packet)]=packet
 cpu=MPU(memory=memory,pc=0x200)
 sy=json.loads((OUT/'asm-app-symbols.json').read_text())
 for _ in range(20000):
  if cpu.pc==sy['APP_START']:break
  cpu.step()
 else:raise AssertionError('Bootstrap did not reach ASM')
 reporter=(OUT/'report.bin').read_bytes()
 assert bytes(memory[0x6800:0x6800+len(reporter)])==reporter
 for cpu in ('65c02','65c816-e'):
  text,m,sy=run(cpu)
  for expected in ('SOURCE / OBJECT LISTING','SYMBOL TABLE','SYMBOL CROSS REFERENCE','SUM: R110 D160','SUM.LOOP: D180 R210','UNUSED: D320','ASSEMBLY COMPLETE  ORIGIN $0200  OBJECT BYTES 55'):
   assert expected in text,(expected,text)
  (OUT/(cpu+'-sample-report.txt')).write_bytes(text.encode('ascii'))
  (OUT/'report-demo.bin').write_bytes(bytes(m[0x200:0x237]))
  # Semantic xrefs exclude quoted strings and comments, distinguish scopes,
  # and combine repeated uses on a line. Definitions retain their identity
  # when their value references a different symbol.
  fixture=['BASE = $0200','ALIAS = BASE+BASE','ORG BASE','first: LDA #ALIAS-BASE-BASE','BRA .loop','.loop: NOP','second: BRA .loop','.loop: NOP','TEXT "BASE .loop" ; BASE','END']
  text,_,_=run(cpu,source=fixture)
  assert 'ALIAS: D20 R40' in text,text
  assert 'BASE: D10 R20 R30 R40' in text,text
  assert 'FIRST.LOOP: R50 D60' in text and 'SECOND.LOOP: R70 D80' in text,text
  print('PASS',cpu,'listing, values, definitions, semantic xrefs, object/source preservation')
 for point in (40,110,200):run(cancel_after=point)
 print('PASS cancellation and report mode cleanup')
if __name__=='__main__':main()





