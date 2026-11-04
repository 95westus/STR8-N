"""Build DBG guards/cleanup once; reuse ASM tables, AP adapter and SF provider."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches
from storage_compact import compact
OUT=ROOT/'BUILD/dbg-base1-g2-r1';BASE=ROOT/'BUILD/dbg-base1-g1-r5';AP=ROOT/'BUILD/devtools-AP02-g1-r2';SF=ROOT/'BUILD/asm-flash-source-g2-r4'
def db(b):return ''.join(' DB '+','.join(f'${v:02X}' for v in b[i:i+16])+'\n' for i in range(0,len(b),16))
def run():
 f=json.loads((REPO/'F_FREEZE.json').read_text());assert all(sha((REPO/n).read_bytes())==h for n,h in f['sources'].items());assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
 resume='--resume-pack' in sys.argv
 OUT.mkdir(exist_ok=resume);stage=OUT/'source'
 if not resume:shutil.copytree(REPO/'monitors/devtools/base1/debugger',stage)
 logs=json.loads((OUT/'build-log.json').read_text()) if resume else []
 (stage/'generated.inc').write_text('AS_OP_TABLE EQU $5F00\nAS_OP_END EQU $63F8\nAS_LENGTHS EQU $63F8\n',encoding='ascii')
 for name in ('debugger.asm','disasm.inc','step-flow.inc'):
  s=(REPO/'monitors/devtools/base1/debugger'/name).read_text();s=re.sub(r'^\s*XDEF\b[^\n]*','; local map symbols',s,flags=re.M);s=re.sub(r'^(\w+) (DB|DW)\b',r'\1: \2',s,flags=re.M);s,_=conservative_branches(s,'DG2_'+re.sub(r'\W','_',name)+'_')
  if resume:assert (stage/name).read_text()==s
  else:(stage/name).write_text(s)
 def link(stem,origin,end):
  for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj']):
   assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
  sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)};m=cells(stage/(stem+'.s19'));assert set(m)==set(range(origin,sy[end]));return bytes(m[a] for a in range(origin,sy[end])),sy
 if resume:code=(OUT/'DBG-code.bin').read_bytes();sy=json.loads((OUT/'symbols.json').read_text());assert len(code)==sy['DEBUG_END']-0x4000
 else:code,sy=link('debugger',0x4000,'DEBUG_END')
 assert sy['DEBUG_END']<0x5f00 and sy['DBG_ENTRY']==0x4010
 base=(BASE/'DBG-BASE1-RAM.bin').read_bytes();assert sha(base)=='f55b7edddbf5ed783734e6247aa073d367dffdbe3ad3fc54f465c482a4306e12';tables=base[0x5d00:];assert len(tables)==1288 and sha(tables)=='1a58fd4b4659be39067f2eb9c3886598d66e67cbdfc910da67cfb01bd2427796'
 packet=bytearray(0x6208);packet[:13]=bytes.fromhex('A9008D7A70A9108D7B704C')+sy['DBG_ENTRY'].to_bytes(2,'little');packet[0x3e00:0x3e00+len(code)]=code;packet[0x5d00:]=tables;(OUT/'DBG-RAM.bin').write_bytes(packet);(OUT/'DBG-code.bin').write_bytes(code);(OUT/'symbols.json').write_text(json.dumps(sy,indent=2))
 raw=bytearray(packet[0x3e00:]);entry=raw.index(bytes.fromhex('6C7A70'));assert raw.count(bytes.fromhex('6C7A70'))==1;raw[entry:entry+3]=bytes.fromhex('4C4967');packed=compact(bytes(raw));(OUT/'DBG-expanded.bin').write_bytes(raw)
 oldsy=json.loads((BASE/'symbols.json').read_text());s=(AP/'DBG-AP02/image.asm').read_text();s=s[:s.index('DT_PACKED:\n')]
 for name in ('DBG_PRINT','DBG_READ_LINE','DBG_SPACES','DBG_HEX_WORD'):
  old=f' JSR ${oldsy[name]:04X}';new=f' JSR ${sy[name]:04X}';assert old in s;s=s.replace(old,new)
 crc=binascii.crc_hqx(raw,65535)
 for addr,value in ((0x670d,crc&255),(0x670e,crc>>8)):
  s,n=re.subn(r' LDA #\$[0-9A-Fa-f]{2}\n STA \$'+f'{addr:04X}'+r'\n',f' LDA #${value:02X}\n STA ${addr:04X}\n',s);assert n==1
 s+='DT_PACKED:\n'+db(packed)+'DT_PACKED_END:\nDT_END:\n ENDMOD\n END\n';s,_=conservative_branches(s,'DG2_AP_');(stage/'app.asm').write_text(s);rom,rs=link('app',0xc020,'DT_END');assert len(rom)+32<=0x1800
 image=bytearray((SF/'DBG-FLASH.bin').read_bytes());provider=(SF/'FLASH-SOURCE-7000.bin').read_bytes();assert image[0x1800:]==provider;image[32:0x1800]=rom.ljust(0x1800-32,b'\xff');image[28:30]=binascii.crc_hqx(image[:28],65535).to_bytes(2,'little');image[30:32]=binascii.crc_hqx(image[32:],65535).to_bytes(2,'little');assert image[0x1800:]==provider;(OUT/'DBG-FLASH.bin').write_bytes(image)
 report=dict(status='BUILT_NOT_LIVE',generation=2,F_changed=False,MON_changed=False,ASM_changed=False,SF_provider_changed=False,F_sha256=f['sha256'],code_bytes=len(code),code_end=f'{sy["DEBUG_END"]:04X}',packet_bytes=len(packet),user_RAM='0200-3FFF',state='7000-744F',public_N_calls=['7E6D PUTC','7E7C HEX','7E7F NL','7E82 nibble','7E85 caps','7E88 board'],paired_table_sha256=sha(tables),SF_provider_sha256=sha(provider),app_loader_end=f'{rs["DT_END"]:04X}',free_before_SF_provider=0xd800-rs['DT_END'],CPU_simulations=0,core_builds=1,artifacts={n:dict(bytes=len((OUT/n).read_bytes()),sha256=sha((OUT/n).read_bytes())) for n in ('DBG-RAM.bin','DBG-code.bin','DBG-expanded.bin','DBG-FLASH.bin')})
 (OUT/'manifest.json').write_text(json.dumps(report,indent=2));(OUT/'builder-as-executed.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(report,indent=2))
if __name__=='__main__':run()
