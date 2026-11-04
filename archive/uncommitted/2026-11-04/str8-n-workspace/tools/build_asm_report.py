"""Build paired RAM-only onboard REPORT prototype; never accesses a port."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells
from mona_branches import conservative_branches
OUT=ROOT/'BUILD/asm-report';SRC=REPO/'monitors/devtools/base1/assembler'
def build():
 OUT.mkdir(exist_ok=True);stage=OUT/'source';stage.mkdir(exist_ok=True)
 for name in ('layout.inc','state.inc','source-equ.inc','source.asm'):
  shutil.copyfile(SRC/name,stage/name)
 shutil.copyfile(REPO/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
 def link(name,text,origin,end):
  text=re.sub(r'^\s*XDEF\b[^\n]*','; map exports',text,flags=re.M)
  text,_=conservative_branches(text,'RPT_'+name.replace('-','_')+'_')
  (stage/(name+'.asm')).write_text(text)
  for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W',name+'.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']):
   p=subprocess.run(command,cwd=stage,capture_output=True,text=True)
   if p.returncode:raise RuntimeError(p.stdout+p.stderr)
  sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(name+'.map')).read_text(),re.M)}
  m=cells(stage/(name+'.s19'));body=bytes(m[a] for a in range(origin,sy[end]))
  (OUT/(name+'.bin')).write_bytes(body);(OUT/(name+'-symbols.json')).write_text(json.dumps(sy,indent=2))
  return sy,body
 core=(SRC/'asm-app.asm').read_text()
 core=core.replace(' JSR NS_DISPATCH\n',' JSR NS_DISPATCH\n JSR $6809\n',1)
 # Hook actual semantic references and definitions, not lexical guesses.
 start=core.index('EXPR_SYMBOL:');end=core.index('EXPR_PRIMARY_RETURN:',start)
 core=core[:start]+core[start:end].replace('JSR FIND_SYMBOL','JSR $6803')+core[end:]
 start=core.index('DX_LINE_PASS:');end=core.index('DX_BYTE:',start)
 block=core[start:end].replace('JSR DECIMAL_OUT','JSR $680C').replace('DX_ROW:\n','DX_ROW:\n JSR $680F\n')
 core=core[:start]+block+core[end:]
 core=core.replace('JSR DEFINE_SYMBOL','JSR $6806').replace('JMP DEFINE_SYMBOL','JMP $6806')
 core=core.replace('BCS DX_SYM_RETURN','BCS DX_CANCEL')
 sy,body=link('asm-app',core,0x4000,'APP_END');assert sy['APP_END']<=0x5d00,hex(sy['APP_END'])
 (stage/'asm-equ.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in sy.items() if not n.startswith(('_','BM_LONG_','RPT_','NS_'))))
 ns,source=link('source',(SRC/'source.asm').read_text(),0x5d00,'NS_END');assert ns['NS_END']<=0x6500
 rs,report=link('report',(ROOT/'prototypes/asm-report/report.asm').read_text(),0x6800,'RP_END');assert rs['RP_END']<0x7800
 # REC uploads below $6500. A RAM bootstrap copies the companion into its
 # execution window before entering ASM; no flash/provider operation is used.
 packet=bytearray(ns['NS_END']-0x200)
 boot=bytearray.fromhex('78 D8 A2 00')
 for page in range((len(report)+255)//256):
  boot+=bytes((0xbd,0,0x30+page,0x9d,0,0x68+page))
 boot+=bytes((0xe8,0xd0,(-len(boot)+1)&255,0x4c,sy['APP_START']&255,sy['APP_START']>>8))
 packet[:len(boot)]=boot
 packet[0x2e00:0x2e00+len(report)]=report
 packet[0x3e00:0x3e00+len(body)]=body
 packet[0x5b00:0x5b00+len(source)]=source
 (OUT/'ASM-REPORT-RAM.bin').write_bytes(packet)
 (OUT/'manifest.json').write_text(json.dumps(dict(status='CPU_MODEL_CANDIDATE_NOT_INSTALLED',
  entry=0x200,command='REPORT',companion_window='6800-6CFF',
  source_window='2000-37FF',symbol_capacity=102,storage_commands_supported=False,
  files={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in
         ('asm-app.bin','source.bin','report.bin','ASM-REPORT-RAM.bin')}),indent=2)+'\n')
 print(json.dumps(dict(core_end=hex(sy['APP_END']),report_bytes=len(report),report_end=hex(rs['RP_END']),status='RAM_ONLY_NOT_INSTALLED')))
if __name__=='__main__':build()



