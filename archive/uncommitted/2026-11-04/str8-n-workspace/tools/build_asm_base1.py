"""Build the paired RAM ASM/source modules once, without F or simulation."""
import json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches
SRC=REPO/'monitors/devtools/base1/assembler';OUT=ROOT/'BUILD/asm-base1-g1-r6'

def run():
 freeze=json.loads((REPO/'F_FREEZE.json').read_text());assert all(sha((REPO/n).read_bytes())==h for n,h in freeze['sources'].items());assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
 OUT.mkdir();stage=OUT/'source';shutil.copytree(SRC,stage);shutil.copyfile(REPO/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
 logs=[];artifacts=[]
 def link(name,origin,end):
  for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W',name+'.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']):
   assert command[0];p=subprocess.run(command,cwd=stage,capture_output=True,text=True);logs.append(dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
  sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(name+'.map')).read_text(),re.M)};m=cells(stage/(name+'.s19'));assert set(m)==set(range(origin,sy[end]));body=bytes(m[a] for a in range(origin,sy[end]));(OUT/(name+'.bin')).write_bytes(body);(OUT/(name+'-symbols.json')).write_text(json.dumps(sy,indent=2));artifacts.append(dict(module=name,origin=origin,end=sy[end],bytes=len(body),sha256=sha(body)));return sy,body
 for name in ('asm-app.asm','source.asm'):
  text=re.sub(r'^\s*XDEF\b[^\n]*','; local module end exported through its generated map',(stage/name).read_text(),flags=re.M)
  text,info=conservative_branches(text,prefix='BASE1_'+re.sub(r'\W','_',name)+'_');(stage/name).write_text(text)
 if '--resume-asm' in sys.argv:
  prior=ROOT/'BUILD/asm-base1-g1-r3';assert (stage/'asm-app.asm').read_bytes()==(prior/'source/asm-app.asm').read_bytes() and (stage/'layout.inc').read_bytes()==(prior/'source/layout.inc').read_bytes()
  sy=json.loads((prior/'asm-app-symbols.json').read_text());asm=(prior/'asm-app.bin').read_bytes();assert len(asm)==sy['APP_END']-0x4000
  (OUT/'asm-app.bin').write_bytes(asm);(OUT/'asm-app-symbols.json').write_text(json.dumps(sy,indent=2));artifacts.append(dict(module='asm-app',origin=0x4000,end=sy['APP_END'],bytes=len(asm),sha256=sha(asm),reused_from=str(prior)))
 else:sy,asm=link('asm-app',0x4000,'APP_END')
 assert sy['APP_END']<=0x5d00
 (stage/'asm-equ.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in sy.items() if not n.startswith(('_','BM_LONG_','BASE1_','NS_'))))
 ns,source=link('source',0x5d00,'NS_END');assert ns['NS_END']<=0x6500 and [ns[n] for n in ('NS_INIT','NS_EDIT','NS_DISPATCH')]==[0x5d08,0x5d12,0x5d1b]
 packet=bytearray(b'\x00'*(ns['NS_END']-0x200));packet[:3]=bytes((0x4c,sy['APP_START']&255,sy['APP_START']>>8));packet[0x3e00:0x3e00+len(asm)]=asm;packet[0x5b00:]=source;(OUT/'ASM-BASE1-RAM.bin').write_bytes(packet)
 record=dict(component='BASE1 resident ASM RAM1',status='BUILT_NOT_LIVE',generation=1,artifact_sha256=sha(packet),packet_bytes=len(packet),modules=artifacts,output='0200-1FFF',source='2000-37FF',symbols='3800-3FFF',state='6500-66FF',PROGRAM_provider='6B00-77FF, admitted existingg3',source_storage='AS/1 PROGRAM implemented, not positively tested; FLASH explicitly refused',F_changed=False,firmware_builds=0,CPU_simulations=0)
 (OUT/'manifest.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))

if __name__=='__main__':run()
