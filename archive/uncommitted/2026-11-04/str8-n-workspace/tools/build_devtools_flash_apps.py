"""Package accepted RAM tools as AP/02 assets; reuse cores and admitted decoder.

Only small launch adapters and the R alias dispatcher are assembled. No F or
MON build, CPU simulation, or device access occurs here.
"""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches
from storage_compact import compact
OUT=ROOT/'BUILD/devtools-AP02-g1-r2'

def db(body):return ''.join(' DB '+','.join(f'${v:02X}' for v in body[i:i+16])+'\n' for i in range(0,len(body),16))
def run():
 freeze=json.loads((REPO/'F_FREEZE.json').read_text());assert all(sha((REPO/n).read_bytes())==h for n,h in freeze['sources'].items());assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
 resume='--resume-services' in sys.argv
 OUT.mkdir(exist_ok=resume);logs=json.loads((OUT/'build-log.json').read_text()) if resume else [];art={}
 def assemble(stem,source,origin,end):
  stage=OUT/stem;stage.mkdir(exist_ok=resume);source=re.sub(r'^\s*XDEF\b[^\n]*','; map symbols',source,flags=re.M)
  source,_=conservative_branches(source,'DT_'+re.sub(r'\W','_',stem)+'_')
  reuse=resume and stem!='services'
  if reuse:assert (stage/'image.asm').read_text()==source
  else:(stage/'image.asm').write_text(source)
  for cmd in ([] if reuse else ([shutil.which('wdc02as'),'-G','-L','-S','-W','image.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o','image.s19','image.obj'])):
   assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
  sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'image.map').read_text(),re.M)};m=cells(stage/'image.s19');assert set(m)==set(range(origin,sy[end]));body=bytes(m[a] for a in range(origin,sy[end]));(OUT/(stem+'.bin')).write_bytes(body);(OUT/(stem+'-symbols.json')).write_text(json.dumps(sy,indent=2));return body,sy
 decoder=(ROOT/'BUILD/named-edu-g3-r8/COMPACT-DECODE-6800.bin').read_bytes();assert len(decoder)==289
 # Fixed RAM return bridge: the admitted decoder returns in B3; reselect B0
 # before RTS reaches the owner AP image. Its private F CRC bindings are pinned.
 bridge=''' MODULE DT_ADAPTER
 CODE
DT_DECODE:
 JSR $6800
 LDA #0
 JSR $7848
 RTS
'''
 provider='''DT_PROVIDER:
 LDA #2
 JSR $7848
 STZ $E0
 STZ $E2
 LDA #$9F
 STA $E1
 LDA #$6B
 STA $E3
 LDX #13
 LDY #0
DT_COPY:
 LDA ($E0),Y
 STA ($E2),Y
 INY
 BNE DT_COPY
 INC $E1
 INC $E3
 DEX
 BNE DT_COPY
 LDA #3
 JSR $7848
 JSR $F8D4
 STZ $E0
 LDA #$6B
 STA $E1
DT_CRC_PAGE:
 LDY #0
DT_CRC_BYTE:
 LDA ($E0),Y
 JSR $F8DD
 INY
 BNE DT_CRC_BYTE
 INC $E1
 LDA $E1
 CMP #$78
 BNE DT_CRC_PAGE
 LDA $7D38
 ORA $7D39
 PHA
 LDA #0
 JSR $7848
 PLA
 BNE DT_BAD_PROVIDER
 SEC
 RTS
DT_BAD_PROVIDER:
 STZ $6B00
 CLC
 RTS
'''
 start='''DT_DEBUG_START:
 ; DBG_ENTRY has cleared all slots. Stop before executing the target byte.
 LDA $707A
 STA $7060
 STA $D0
 LDA $707B
 STA $7061
 STA $D1
 LDA ($D0)
 STA $7062
 LDA #3
 STA $7063
 LDA #$D7
 STA $7070
 LDA #0
 STA ($D0)
 JMP ($707A)
'''
 asm_dir=ROOT/'BUILD/asm-base1-g1-r6';dbg_dir=ROOT/'BUILD/dbg-base1-g1-r5'
 amap=json.loads((asm_dir/'asm-app-symbols.json').read_text());dmap=json.loads((dbg_dir/'symbols.json').read_text())
 end='DT_END:\n ENDMOD\n END\n'
 def enter(target):return f'DT_ENTER:\n LDA #3\n JSR $7848\n JMP ${target:04X}\n'
 aa,asy=assemble('ASM-adapter',bridge+provider+enter(amap['APP_START'])+end,0x6740,'DT_END');da,dsy=assemble('DBG-adapter',bridge+start+enter(dmap['DBG_ENTRY'])+end,0x6740,'DT_END');assert max(len(aa),len(da))<=192
 ar=(asm_dir/'ASM-BASE1-RAM.bin').read_bytes();dr=(dbg_dir/'DBG-BASE1-RAM.bin').read_bytes();assert sha(ar)=='b05b71cf95019fb860bce175302d24a39664676d54bb1ee8b21c742f556fe12b' and sha(dr)=='f55b7edddbf5ed783734e6247aa073d367dffdbe3ad3fc54f465c482a4306e12'
 araw=ar[0x3e00:];draw=bytearray(dr[0x3e00:]);site=draw.index(bytes.fromhex('6C7A70'));assert draw.count(bytes.fromhex('6C7A70'))==1;draw[site:site+3]=bytes((0x4c,dsy['DT_DEBUG_START']&255,dsy['DT_DEBUG_START']>>8))
 for name,origin,raw,adapter,sy in [('ASM',0xA000,araw,aa,asy),('DBG',0xC000,bytes(draw),da,dsy)]:
  packed=compact(raw);limit=0x4000+len(raw)
  stores={0xE2:0,0xE3:0x40,0x6708:0,0x6709:limit&255,0x670A:limit>>8,0x670B:0,0x670C:0x40,0x670D:binascii.crc_hqx(raw,65535)&255,0x670E:binascii.crc_hqx(raw,65535)>>8}
  setup=''.join(f' LDA #${v:02X}\n STA ${a:04X}\n' for a,v in stores.items())
  finish=f' JSR ${sy["DT_PROVIDER"]:04X}\n BCC DT_REFUSE\n JMP ${sy["DT_ENTER"]:04X}\nDT_REFUSE:\n JMP $7E67\n' if name=='ASM' else f''' STZ $6B00
DT_PROMPT:
 LDX #<DT_TEXT
 LDY #>DT_TEXT
 JSR ${dmap['DBG_PRINT']:04X}
 JSR ${dmap['DBG_READ_LINE']:04X}
 STZ $D7
 JSR ${dmap['DBG_SPACES']:04X}
 CMP #'Q'
 BNE DT_ADDRESS
 INC $D7
 JSR ${dmap['DBG_SPACES']:04X}
 BEQ DT_CANCEL
 BRA DT_PROMPT
DT_ADDRESS:
 JSR ${dmap['DBG_HEX_WORD']:04X}
 BCC DT_PROMPT
 JSR ${dmap['DBG_SPACES']:04X}
 BNE DT_PROMPT
 LDA $D6
 CMP #2
 BCC DT_PROMPT
 CMP #$40
 BCS DT_PROMPT
 STA $707B
 LDA $D5
 STA $707A
 JMP ${sy['DT_ENTER']:04X}
DT_CANCEL:
 JMP $7E67
DT_TEXT: DB "DBG RAM start 0200-3FFF; Q MON> ",0
'''
  source=f''' MODULE DT_{name}
 CODE
DT_ENTRY:
 SEI
 CLD
 LDX #0
DT_KERNEL_COPY:
 LDA DT_KERNEL,X
 STA $6800,X
 LDA DT_KERNEL+256,X
 STA $6900,X
 INX
 BNE DT_KERNEL_COPY
 LDX #0
DT_ADAPTER_COPY:
 LDA DT_ADAPTER,X
 STA $6740,X
 INX
 CPX #{len(adapter)}
 BCC DT_ADAPTER_COPY
'''+setup+''' LDA #<DT_PACKED
 STA $E0
 LDA #>DT_PACKED
 STA $E1
 LDA #<DT_PACKED_END
 STA $670F
 LDA #>DT_PACKED_END
 STA $6710
 JSR $6740
'''+finish+'DT_KERNEL:\n'+db(decoder)+'DT_ADAPTER:\n'+db(adapter)+'DT_PACKED:\n'+db(packed)+'DT_PACKED_END:\nDT_END:\n ENDMOD\n END\n'
  body,romsy=assemble(name+'-AP02',source,origin+32,'DT_END');assert len(body)+32<=8192
  header=bytearray(32);header[:8]=b'AP\x02\x20PR05';header[8:10]=(32+len(body)).to_bytes(2,'little');header[10:12]=(origin+32).to_bytes(2,'little');header[14:16]=b'\x01\x02';header[16:16+len(name)]=name.encode();header[28:30]=binascii.crc_hqx(header[:28],65535).to_bytes(2,'little');header[30:32]=binascii.crc_hqx(body,65535).to_bytes(2,'little')
  image=(header+body).ljust(8192,b'\xff');(OUT/(name+'-FLASH.bin')).write_bytes(image)
  (OUT/(name+'-expanded.bin')).write_bytes(raw)
  art[name]=dict(bank=0,address=f'{origin:04X}',bytes=len(image),used_bytes=32+len(body),free_bytes=8192-32-len(body),sha256=sha(image),expanded_sha256=sha(raw),expanded_start='4000',expanded_end=f'{limit:04X}',packed_bytes=len(packed),adapter_bytes=len(adapter),debug_entry_patch_offset=site if name=='DBG' else None)
 # Reuse the exact live dispatcher's support files. Add only narrow R aliases.
 stage0=ROOT/'BUILD/storage-installed-auto-r2/E';stage=OUT/'services-inputs';stage.mkdir(exist_ok=resume)
 for p in stage0.iterdir():
  if p.suffix=='.inc':shutil.copyfile(p,stage/p.name)
 text=(REPO/'monitors/src/services.asm').read_text();at='S_MODULE_NAMES:\n'
 # Insert before APP recognition; S_MATCH resets its own X each time.
 alias='''S_MODULE_NAMES:
 LDX #<DT_R_ASM
 LDY #>DT_R_ASM
 JSR S_MATCH
 BCS DT_R_APP
 LDX #<DT_R_DBG
 LDY #>DT_R_DBG
 JSR S_MATCH
 BCC DT_NOT_APP
DT_R_APP:
 LDX #2
 JMP AP_LAUNCH
DT_NOT_APP:
'''
 assert text.count(at)==1;text=text.replace(at,alias);text=text.replace('\nS_END:\n','\nDT_R_ASM: DB "R ASM",0\nDT_R_DBG: DB "R DBG",0\nS_END:\n')
 # Preserve the exact generated loader and bindings, not a second tool build.
 old=(stage0/'services.asm').read_text();tail=re.search(r'SERVICE_LOADER_TAIL',text)
 if tail:
  import re as _re
  loader=(stage/'service-load-image.inc').read_text();length=len(_re.findall(r'\$[0-9A-Fa-f]{2}',loader));text=text.replace('SERVICE_LOADER_TAIL',str(length-256))
 text=text.replace('"WORKBENCH_GENERATION_BYTES"',','.join(f'${v:02X}' for v in (14).to_bytes(4,'little')))
 apps=(REPO/'monitors/src/service-apps.inc').read_text();a=apps.index('AP_NATIVE_TEXT:');b=apps.index('AP_MISSING_TEXT:',a);apps=apps[:a]+'AP_NATIVE_TEXT: DB "R CLOCK/FLASH/MAINT; EDU SRAM WORK",13,10\n DB "R/APP name",13,10,0\n'+apps[b:];(stage/'service-apps.inc').write_text(apps)
 # Services uses local INCLUDEs: feed them unchanged to the common assembler.
 for p in stage.iterdir():
  if p.suffix=='.inc':
   s=p.read_text();
   if p.name not in ('str8n-v2-public.inc','service-layout.inc') and not p.name.endswith('interface.inc'):
    s,_=conservative_branches(s,'DT_E_'+re.sub(r'\W','_',p.name)+'_')
   p.write_text(s)
 text,_=conservative_branches(text,'DT_E_services_');(stage/'image.asm').write_text(text)
 # assemble() creates its stage; this one has copied INCLUDE files already.
 eb,esy=assemble_with_includes(assemble,OUT,text)
 assert len(eb)<=4094
 image=eb.ljust(4094,b'\xff');image+=binascii.crc_hqx(image,65535).to_bytes(2,'big');(OUT/'SERVICES-E.bin').write_bytes(image)
 art['services']=dict(bank=3,address='E000',bytes=4096,used_bytes=len(eb),free_bytes=4094-len(eb),sha256=sha(image))
 result=dict(status='BUILT_NOT_LIVE',F_changed=False,MON_changed=False,F_sha256=freeze['sha256'],artifacts=art,ASM_RAM='output0200-1FFF; source2000-37FF; symbols3800-3FFF; code4000-62FC; state6500-66FF',DBG_RAM='target0200-3FFF; code4000-4F48; tables5F00-6407; state7000-744F',source_storage='AS/1 PROGRAM; FLASH refused81',decoder_sha256=sha(decoder),core_builds=0,CPU_simulations=0)
 (OUT/'manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

def assemble_with_includes(assemble,out,text):
 # The common assembler creates a fresh stage; supply INCLUDEs just before
 # invoking its first subprocess, using a temporary scoped subprocess wrapper.
 original=subprocess.run
 def call(cmd,**kw):
  cwd=Path(kw['cwd'])
  if cwd==out/'services':
   for p in (out/'services-inputs').glob('*.inc'):
    shutil.copyfile(p,cwd/p.name)
  return original(cmd,**kw)
 try:subprocess.run=call;return assemble('services',text,0xE000,'S_END')
 finally:subprocess.run=original

if __name__=='__main__':run()

