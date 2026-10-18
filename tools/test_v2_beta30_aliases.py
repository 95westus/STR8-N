"""Execute native aliases and strict token boundaries in the CPU model."""
import json
from test_v2_beta30 import fixture,cmd,OUT,META,X,sha,S,k,snapshot

def main():
 checks=[]
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 cpu,m=fixture();original=snapshot(m)
 for line,title,prompt in [(b'maint',b'BANK MAINT 2.4',b'BM> '),(b'  sRaM  ',b'SRAM 1.4',b'SRAM> '),(b'work\t',b'WORK 1.4',b'WORK> '),(b'edu',b'EDU 1.4',b'EDU> ')]:
  text=cmd(cpu,m,line+b'\r');assert title in text and text.endswith(prompt),(line,text[-500:])
  assert cmd(cpu,m,b'Q\r').endswith(b'B3> ')
  assert snapshot(m)==original and not m.events
 passed('all four bare names launch from monitor; case folding, whitespace and Q preserve storage')
 text=cmd(cpu,m,b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r')
 assert all(t in text for t in [b'BANK MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4',b'BATCH done']) and text.endswith(b'B3> '),text[-1200:]
 assert snapshot(m)==original and not m.events
 (OUT/'batch-alias-example.txt').write_bytes(text)
 passed('one batch launches all four bare aliases and returns to monitor at each Q')
 text=cmd(cpu,m,b'BATCH R MAINT;Q; WORK ;Q;EDU;Q\r');assert b'BATCH done' in text and text.endswith(b'B3> '),text[-1000:]
 assert snapshot(m)==original and not m.events
 passed('bare and R-prefixed launches mix in a list with trimmed segment whitespace')
 text=cmd(cpu,m,b'BATCH MAINT;NAME TEST;YES;Q\r');assert text.endswith(b'Type YES: '),text[-600:]
 assert snapshot(m)==original and not m.events
 text=cmd(cpu,m,b'\x1b');assert b'BATCH canceled' in text and text.endswith(b'BM> '),text[-600:]
 cmd(cpu,m,b'Q\r');assert snapshot(m)==original and not m.events
 passed('bare MAINT keeps real confirmation; queued YES is not consumed and Esc cancels remaining commands')
 text=cmd(cpu,m,b'BATCH EDU;BOGUS;Q;VERSION\r');assert b'BATCH stopped: command failed' in text and text.endswith(b'EDU> ') and b'Running:' not in text,text[-700:]
 cmd(cpu,m,b'Q\r')
 text=cmd(cpu,m,b'BATCH MAINTX;VERSION\r');assert b'BATCH stopped' in text and b'Running:' not in text and b'BANK MAINT' not in text,text
 passed('utility errors and invalid alias suffixes discard remaining commands')
 text=cmd(cpu,m,b'?\r');assert b'MAINT SRAM WORK EDU (R optional)' in text and b'BATCH cmd;cmd' in text,text
 passed('monitor help lists bare aliases and retains BATCH syntax')
 # Execute the actual matcher over bounded monitor inputs. Check every RAM
 # byte outside its documented scratch and the line buffer for corruption.
 savedpc=cpu.pc;savedport=m.ram[0x7FEC];m[0x7FEC]=(savedport&0x11)|0xEC
 positives=[(n,b'R '+n) for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']]
 positives +=[(b' '*35+b'MAINT',b'R MAINT'),(b'EDU'+b' '*37,b'R EDU')]
 negatives=[b'',b' ',b'MAIN',b'MAINTX',b'SRAMX',b'WORKER',b'EDUC',b'MAINT Q',b'SRAM 1',b'WORK ?',b'EDU OFF',b'R MAINT',b'BATCH SRAM;Q',b'M 0200 AA',b'F 0200 0201 FF',b'S 1 8000 2000 2001 TEST',b'G 2000',b'J3',b'VERSION']
 for raw,want in positives+[(n,n) for n in negatives]:
  m.ram[0x7C00:0x7C29]=b'\xA5'*41;m.ram[0x7C00:0x7C00+len(raw)+1]=raw+b'\0'
  before=bytes(m.ram);sp=cpu.sp;cpu.stPushWord(0x01FF);cpu.pc=S['B30_ALIAS']
  for _ in range(10000):
   if cpu.pc==0x0200:break
   cpu.step()
  else:raise AssertionError(('matcher timeout',raw))
  assert cpu.sp==sp
  got=bytes(m.ram[0x7C00:0x7C29]).split(b'\0')[0];assert got==want,(raw,got,want)
  allowed=set(range(0x100,0x200))|set(range(0x7C00,0x7C29))|{0x7EEE,0x7EEF,0x7EEC}
  changed={i for i,(a,b) in enumerate(zip(before,m.ram)) if a!=b};assert changed<=allowed,(raw,changed-allowed)
 assert snapshot(m)==original and not m.events
 passed('real matcher rejects prefixes/arguments and preserves legacy monitor commands; 40-byte bounds and scratch verified')
 r=dict(passed=True,checks=checks,build_sha256=sha((OUT/'build.json').read_bytes()),artifacts=META['artifacts'],board_access=False,boards_flashed=False)
 (OUT/'beta30-alias-test-results.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
