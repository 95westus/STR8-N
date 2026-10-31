"""Review-only storage measurement; no build, model or device access.

Prototype token format: 80..FF = 1..128 literal bytes, 00..7F = a
3..130-byte overlapping match followed by a little-endian 16-bit distance.
This is a storage feasibility experiment, not an implemented RP loader.
"""
import argparse,hashlib,json
from collections import defaultdict,deque
from pathlib import Path

def encode(data):
 out=bytearray();literal=bytearray();positions=defaultdict(lambda:deque(maxlen=64));i=0
 def flush():
  if literal:out.append(0x80+len(literal)-1);out.extend(literal);literal.clear()
 while i<len(data):
  best=0;distance=0;key=data[i:i+3]
  if len(key)==3:
   for j in reversed(positions[key]):
    if i-j>65535:break
    n=3
    while n<130 and i+n<len(data) and data[j+n]==data[i+n]:n+=1
    if n>best:best=n;distance=i-j
    if best==130:break
  count=best if best>=3 else 1
  if best>=3:
   flush();out.append(best-3);out.extend(distance.to_bytes(2,'little'))
  else:
   literal.append(data[i])
   if len(literal)==128:flush()
  for j in range(i,i+count):
   if j+3<=len(data):positions[data[j:j+3]].append(j)
  i+=count
 flush();return bytes(out)

def decode(packed,expected):
 out=bytearray();i=0
 while i<len(packed):
  token=packed[i];i+=1
  if token&128:
   n=(token&127)+1
   if i+n>len(packed):raise ValueError('Truncated literal')
   out.extend(packed[i:i+n]);i+=n
  else:
   if i+2>len(packed):raise ValueError('Truncated match')
   distance=int.from_bytes(packed[i:i+2],'little');i+=2
   if not 1<=distance<=len(out):raise ValueError('Match outside produced output')
   for unused in range(token+3):out.append(out[-distance])
  if len(out)>expected:raise ValueError('Output bound exceeded')
 if len(out)!=expected:raise ValueError('Wrong output length')
 return bytes(out)

def measure(paths):
 rows=[]
 for p in paths:
  body=p.read_bytes();packed=encode(body);assert decode(packed,len(body))==body
  rows.append(dict(input=p.name,source_sha256=hashlib.sha256(body).hexdigest(),expanded_bytes=len(body),packed_bytes=len(packed),RP_header_and_seal_bytes=34,sectors_if_adopted=(len(packed)+34+4095)//4096,roundtrip_exact=True))
 return dict(status='FEASIBILITY_ONLY_NOT_RP_IMPLEMENTED_OR_EXECUTION_QUALIFIED',CPU_simulations=0,firmware_builds=0,device_access=False,encoding='prototype literal/match LZ;128 literals,130 match,16-bit distance',images=rows,limits=['Legacy MAINT still requires BASE1 binding/guard adaptation.','A bounded 65C02/816-compatible decoder and versioned RP format are not implemented.','Future port size and loader size require measurement before allocation changes.','No bank/sector is allocated or declared free by this experiment.'])
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('images',nargs='+',type=Path);a.add_argument('--out',type=Path);args=a.parse_args();r=measure(args.images);text=json.dumps(r,indent=2)+'\n'
 if args.out:args.out.write_text(text,encoding='utf-8',newline='\n')
 print(text)
