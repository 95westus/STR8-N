"""Build DBG RAM1 using exact opcode tables from the paired ASM link."""
import json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches
SRC=REPO/'monitors/devtools/base1/debugger';OUT=ROOT/'BUILD/dbg-base1-g1-r4';ASM=ROOT/'BUILD/asm-base1-g1-r5'

def run():
 OUT.mkdir();stage=OUT/'source';shutil.copytree(SRC,stage)
 sy=json.loads((ASM/'asm-app-symbols.json').read_text());asm=(ASM/'asm-app.bin').read_bytes();am=json.loads((ASM/'manifest.json').read_text());assert sha(asm)==am['modules'][0]['sha256']
 tables=asm[sy['OP_TABLE']-0x4000:sy['OP_END']-0x4000]+asm[sy['MODE_LENGTHS']-0x4000:sy['MODE_LENGTHS']-0x4000+16]
 assert len(tables)==1288
 (stage/'generated.inc').write_text(f'AS_OP_TABLE EQU $5F00\nAS_OP_END EQU ${0x5F00+len(tables)-16:04X}\nAS_LENGTHS EQU ${0x5F00+len(tables)-16:04X}\n')
 for name in ('debugger.asm','disasm.inc','step-flow.inc'):
  text=(stage/name).read_text();text=re.sub(r'^\s*XDEF\b[^\n]*','; map exports local entry symbols',text,flags=re.M)
  # Legacy debugger uses bare label DB/EQU forms; normalize DB labels for the
  # existing branch-size pass without changing emitted instructions/data.
  text=re.sub(r'^(\w+) (DB|DW)\b',r'\1: \2',text,flags=re.M)
  text,info=conservative_branches(text,prefix='DB_BASE1_'+re.sub(r'\W','_',name)+'_');(stage/name).write_text(text)
 logs=[]
 for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','debugger.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c4000','-hm19','-j','-o','debugger.s19','debugger.obj']):
  assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
 sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'debugger.map').read_text(),re.M)};m=cells(stage/'debugger.s19');assert set(m)==set(range(0x4000,sy['DEBUG_END'])) and sy['DEBUG_END']<=0x6000
 code=bytes(m[a] for a in range(0x4000,sy['DEBUG_END']));packet=bytearray(0x5F00+len(tables)-0x200)
 packet[:13]=bytes.fromhex('A9008D7A70A9108D7B704C')+sy['DBG_ENTRY'].to_bytes(2,'little')
 packet[0x3e00:0x3e00+len(code)]=code;packet[0x5d00:]=tables;assert len(packet)<=0x6300;(OUT/'DBG-BASE1-RAM.bin').write_bytes(packet);(OUT/'symbols.json').write_text(json.dumps(sy,indent=2))
 record=dict(component='BASE1 DBG RAM1',generation=1,status='BUILT_NOT_LIVE',artifact_sha256=sha(packet),packet_bytes=len(packet),code_first='4000',code_end=f'{sy["DEBUG_END"]:04X}',table_first='5F00',table_end=f'{0x5F00+len(tables):04X}',user_RAM='0200-3FFF',state='7000-744F, provider cache borrowed',hooks=['7E02-7E03 emulation BRK pointer','7E67-7E69 public HOLD JMP'],paired_ASM=am['artifact_sha256'],F_changed=False,CPU_simulations=0,firmware_builds=0)
 (OUT/'manifest.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))

if __name__=='__main__':run()
