"""Offline host staging, bounds, feedback, identity and image-contract checks."""
import argparse,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import rtc_phase_align as p
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build',type=Path,default=p.BUILD)
args=parser.parse_args()
p.IMAGE,p.SY,p.PROOF=p.load_image(args.build)
class Link:
 def __init__(self,reply=b'B3> '):self.lines=[];self.reply=reply
 def command(self,line,prompt):self.lines.append(line);return self.reply
body=bytes(range(33));link=Link()
with patch.object(p.f,'dump_ram',return_value=body):p.stage(link,0x2000,body)
assert len(link.lines)==5 and all(len(x.split()[2:])<=8 for x in link.lines)
for message in (b'Long line',b'REFUSED',b'Protected',b'Bad range'):
 link=Link(message)
 try:p.stage(link,0x2000,body)
 except ValueError:pass
 else:raise AssertionError(message)
 assert len(link.lines)==1
r=p.Reference([{'origin_bounds':[100,100.04]},{'origin_bounds':[100.01,100.03]}])
assert abs(r.origin-100.02)<1e-7
for samples in ([{'origin_bounds':[100,100.01]},{'origin_bounds':[100.02,100.03]}],[{'origin_bounds':[100,100.3]}]):
 try:p.Reference(samples)
 except ValueError:pass
 else:raise AssertionError('Unusable NIST reference accepted')
print('PASS eight-byte staging, rejection before continuation, NIST bounds and disagreement checks')

class SRecordLink:
 phase_board='2604'
 def __init__(self):self.lines=[];self.sent=[]
 def command(self,line,prompt):self.lines.append(line);assert line=='L';return b'S19'
 def send(self,data):self.sent.append(data)
 def until(self,*args,**kw):return b'B3> '
l=SRecordLink()
with patch.object(p.f,'dump_ram',return_value=body),patch.object(p.time,'sleep'):p.stage(l,0x2000,body)
assert l.lines==['L'] and all(x.startswith(b'S') for x in l.sent)
import tempfile
from installer.engine.legacy_transport import read_s19
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'ram.s19';path.write_bytes(b''.join(l.sent));cells,entry=read_s19(path)
 assert entry==0x2000 and bytes(cells[a] for a in sorted(cells))==body
for initial in (.7,.3,-.15):
 for overhead in (.06,.14,.19):
  error=initial;bias=0
  for n in range(5):
   if abs(error)+.035<=.1:break
   add=1 if error-bias<=.005 else 0;hold=error+add-bias
   assert .005<hold<1.05
   after=error+add-hold-overhead
   bias=error+add-hold-after;error=after
  assert abs(error)+.035<=.1
print('PASS 2604 uses only checked S-record transport; bounded feedback converges with stop/restart delay')

for address,body2 in ((0x1fff,b'1'),(0x2000+len(p.IMAGE)-1,b'12')):
 l=Link()
 try:p.stage(l,address,body2)
 except ValueError:pass
 else:raise AssertionError('Out-of-window RAM staging accepted')
 assert not l.lines
print('PASS phase staging cannot write outside its borrowed RAM block')

state={'baselines':{'2205':{'EUI':'5410ecb664af','time':1}},'baseline_history':[]}
p.f.rebase(state,'2205',{'board':'2205','time':2},'receipt','test')
assert state['baselines']['2205']['EUI']=='5410ecb664af' and state['baselines']['2205']['time']==2 and state['baseline_history'][0]['previous']['time']==1
p.f.rebase(state,'2205',{'board':'2205','time':3},'receipt','test')
assert state['baselines']['2205']['EUI']=='5410ecb664af'
state['baselines']['2205'].pop('EUI')
p.f.rebase(state,'2205',{'board':'2205','time':4},'receipt','test')
assert state['baselines']['2205']['EUI']=='5410ecb664af'
print('PASS repeated drift rebaselining preserves pinned EUI and old baselines')

import copy,json
from rtc_phase_contract import load_image
with tempfile.TemporaryDirectory() as folder:
 build=Path(folder)
 def put(image=p.IMAGE,symbols=p.SY,proof=p.PROOF):
  (build/'phase.bin').write_bytes(image)
  (build/'symbols.json').write_text(json.dumps(symbols))
  (build/'proof.json').write_text(json.dumps(proof))
 def rejected():
  try:load_image(build)
  except ValueError:pass
  else:raise AssertionError('Unqualified phase artifacts accepted')
 put();assert load_image(build)[0]==p.IMAGE
 image=bytearray(p.IMAGE);image[0]^=1;put(image=bytes(image));rejected()
 symbols=dict(p.SY);symbols['TICKS']+=1;put(symbols=symbols);rejected()
 for change in ('failed','missing','duplicate','wrong-image','wrong-cpu'):
  proof=copy.deepcopy(p.PROOF)
  if change=='failed':proof['checks'][0]['passed']=False
  elif change=='missing':proof['checks'].pop()
  elif change=='duplicate':proof['checks'][0]=dict(proof['checks'][1])
  elif change=='wrong-image':proof['image_sha256']='0'*64
  else:proof['checks'][0]['CPU']='65C816 native'
  put(proof=proof);rejected()
print('PASS altered images, symbol maps, failed/missing/duplicate model cases and wrong CPUs are refused')
