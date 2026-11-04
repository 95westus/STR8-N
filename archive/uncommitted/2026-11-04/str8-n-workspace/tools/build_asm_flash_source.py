"""Link only the SF/1 source increment; reuse accepted ASM/DBG/decoder bytes."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches
from storage_compact import compact
OUT=ROOT/'BUILD/asm-flash-source-g2-r4';OLD=ROOT/'BUILD/devtools-AP02-g1-r2';BASE=ROOT/'BUILD/asm-base1-g1-r6';SRC=REPO/'monitors/devtools/base1/assembler'
def db(body):return ''.join(' DB '+','.join(f'${v:02X}' for v in body[i:i+16])+'\n' for i in range(0,len(body),16))
def run():
 f=json.loads((REPO/'F_FREEZE.json').read_text());assert all(sha((REPO/n).read_bytes())==h for n,h in f['sources'].items());assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
 OUT.mkdir();stage=OUT/'source';shutil.copytree(SRC,stage);logs=[]
 amap=json.loads((BASE/'asm-app-symbols.json').read_text());core=(BASE/'asm-app.bin').read_bytes();assert sha(core)=='046541a30212784f6506a5ee663ac70c3d1bb44b504335f2652bb19868154f18'
 (stage/'asm-equ.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in amap.items() if not n.startswith(('_','BM_LONG_','BASE1_','NS_'))),encoding='ascii')
 (stage/'flash-bindings.inc').write_text('V2_ADDR EQU $E2\nV2_COUNT EQU $EA\nV2_BYTES EQU $7C80\nV2_SELECTED EQU $F3\nV2_FLASH_PTR EQU $E4\nV2_FLASH_DATA EQU $F0\n',encoding='ascii')
 def link(stem,text,origin,end):
  text=re.sub(r'^\s*XDEF\b[^\n]*','; local map symbols',text,flags=re.M);text,_=conservative_branches(text,'SF_'+re.sub(r'\W','_',stem)+'_');(stage/(stem+'.asm')).write_text(text,encoding='utf-8')
  for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj']):
   assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
  sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)};m=cells(stage/(stem+'.s19'));assert set(m)==set(range(origin,sy[end]));body=bytes(m[a] for a in range(origin,sy[end]));(OUT/(stem+'.bin')).write_bytes(body);(OUT/(stem+'-symbols.json')).write_text(json.dumps(sy,indent=2));return body,sy
 ns,nsy=link('source',(SRC/'source.asm').read_text(),0x5d00,'NS_END');assert nsy['NS_END']<=0x6500 and [nsy[n] for n in ('NS_INIT','NS_EDIT','NS_DISPATCH')]==[0x5d08,0x5d12,0x5d1b]
 (stage/'ns-equ.inc').write_text(''.join(f'{n} EQU ${nsy[n]:04X}\n' for n in ('NS_CRC_BYTE','NS_YES_WORD')),encoding='ascii')
 sf,fsy=link('flash-provider',(SRC/'flash-provider.asm').read_text(),0x7000,'NF_END');assert len(sf)<=2046
 sf=sf.ljust(2046,b'\xff');sf+=binascii.crc_hqx(sf,65535).to_bytes(2,'big');assert binascii.crc_hqx(sf,65535)==0;(OUT/'FLASH-SOURCE-7000.bin').write_bytes(sf)
 raw=core.ljust(0x1d00,b'\0')+ns;assert len(raw)==nsy['NS_END']-0x4000;(OUT/'ASM-expanded.bin').write_bytes(raw)
 packet=bytearray(nsy['NS_END']-0x200);packet[:3]=bytes((0x4c,amap['APP_START']&255,amap['APP_START']>>8));packet[0x3e00:]=raw;(OUT/'ASM-RAM.bin').write_bytes(packet)
 packed=compact(raw);text=(OLD/'ASM-AP02/image.asm').read_text();text=text[:text.index('DT_PACKED:\n')];crc=binascii.crc_hqx(raw,65535);end=nsy['NS_END']
 for address,value in ((0x6709,end&255),(0x670a,end>>8),(0x670d,crc&255),(0x670e,crc>>8)):
  text,count=re.subn(r' LDA #\$[0-9A-Fa-f]{2}\n STA \$'+f'{address:04X}'+r'\n',f' LDA #${value:02X}\n STA ${address:04X}\n',text);assert count==1
 text+='DT_PACKED:\n'+db(packed)+'DT_PACKED_END:\nDT_END:\n ENDMOD\n END\n'
 body,sy=link('ASM-AP02',text,0xa020,'DT_END');assert len(body)+32<=8192
 image=bytearray((OLD/'ASM-FLASH.bin').read_bytes());image[32:]=body.ljust(8192-32,b'\xff');image[8:10]=(len(body)+32).to_bytes(2,'little');image[28:30]=binascii.crc_hqx(image[:28],65535).to_bytes(2,'little');image[30:32]=binascii.crc_hqx(body,65535).to_bytes(2,'little');(OUT/'ASM-FLASH.bin').write_bytes(image)
 dbg=bytearray((OLD/'DBG-FLASH.bin').read_bytes());assert dbg[0x1800:]==b'\xff'*2048;dbg[0x1800:]=sf;dbg[8:10]=(8192).to_bytes(2,'little');dbg[28:30]=binascii.crc_hqx(dbg[:28],65535).to_bytes(2,'little');dbg[30:32]=binascii.crc_hqx(dbg[32:],65535).to_bytes(2,'little');(OUT/'DBG-FLASH.bin').write_bytes(dbg)
 report=dict(status='BUILT_NOT_LIVE',F_changed=False,MON_changed=False,E_changed=False,CPU_simulations=0,ASM_core_reused_sha256=sha(core),DBG_core_reused_sha256=sha((OLD/'DBG-expanded.bin').read_bytes()),source_bytes=len(ns),source_end=f'{end:04X}',flash_provider_linked_bytes=fsy['NF_END']-0x7000,provider_RAM='7000-77FF',provider_ROM='B0:D800-DFFF',source_format='SF/1 carrying AS/1; exact extent YES, blank-only append; commit last; no erase',ASM_APP_used_bytes=len(body)+32,ASM_APP_free_bytes=8192-len(body)-32,DBG_APP_used_bytes=8192,profile_reserved_bytes=106496,artifacts={n:dict(bytes=len((OUT/n).read_bytes()),sha256=sha((OUT/n).read_bytes())) for n in ('ASM-FLASH.bin','DBG-FLASH.bin','ASM-RAM.bin','ASM-expanded.bin','FLASH-SOURCE-7000.bin')},F_sha256=f['sha256'])
 (OUT/'manifest.json').write_text(json.dumps(report,indent=2));(OUT/'builder-as-executed.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(report,indent=2))
if __name__=='__main__':run()
