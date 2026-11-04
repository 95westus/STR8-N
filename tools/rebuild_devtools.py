"""Compile paired ASM/DBG cores, source provider and AP loaders from source."""
import binascii,hashlib,json,re,shutil
from pathlib import Path
from build_mona import ROOT,equs
from rebuild_mon_services import assemble
from mona_branches import conservative_branches
from storage_compact import compact

def db(data):return ''.join(' DB '+','.join(f'${v:02X}' for v in data[i:i+16])+'\n' for i in range(0,len(data),16))

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    stage=out/'core';shutil.copytree(ROOT/'monitors/devtools/base1/assembler',stage)
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    for name in ('asm-app.asm','source.asm'):
        text=re.sub(r'^\s*XDEF\b[^\n]*','; local map symbols',(stage/name).read_text(encoding='utf-8'),flags=re.M)
        text,_=conservative_branches(text,'BASE1_'+re.sub(r'\W','_',name)+'_')
        (stage/name).write_text(text,encoding='utf-8')
    core,asy=assemble(stage,'asm-app',0x4000,'APP_END',False)
    (stage/'asm-equ.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in asy.items() if not n.startswith(('_','BM_LONG_','BASE1_','NS_'))))
    source,nsy=assemble(stage,'source',0x5d00,'NS_END',False)
    raw=core.ljust(0x1d00,b'\0')+source
    packet=bytearray(nsy['NS_END']-0x200);packet[:3]=bytes((0x4c,asy['APP_START']&255,asy['APP_START']>>8));packet[0x3e00:]=raw
    (out/'ASM-RAM.bin').write_bytes(packet)
    tables=core[asy['OP_TABLE']-0x4000:asy['OP_END']-0x4000]+core[asy['MODE_LENGTHS']-0x4000:asy['MODE_LENGTHS']-0x4000+16]
    if len(tables)!=1288:raise ValueError('Paired opcode table layout changed')
    dbg=out/'debugger';shutil.copytree(ROOT/'monitors/devtools/base1/debugger',dbg)
    (dbg/'generated.inc').write_text('AS_OP_TABLE EQU $5F00\nAS_OP_END EQU $63F8\nAS_LENGTHS EQU $63F8\n')
    for name in ('debugger.asm','disasm.inc','step-flow.inc'):
        text=(dbg/name).read_text(encoding='utf-8')
        text=re.sub(r'^\s*XDEF\b[^\n]*','; local map symbols',text,flags=re.M)
        text=re.sub(r'^(\w+) (DB|DW)\b',r'\1: \2',text,flags=re.M)
        text,_=conservative_branches(text,'DG2_'+re.sub(r'\W','_',name)+'_')
        (dbg/name).write_text(text,encoding='utf-8')
    code,dsy=assemble(dbg,'debugger',0x4000,'DEBUG_END',False)
    dpacket=bytearray(0x6208);dpacket[:13]=bytes.fromhex('A9008D7A70A9108D7B704C')+dsy['DBG_ENTRY'].to_bytes(2,'little')
    dpacket[0x3e00:0x3e00+len(code)]=code;dpacket[0x5d00:]=tables
    (out/'DBG-RAM.bin').write_bytes(dpacket)
    # Source-only SF/1 provider, paired with the current assembler symbols.
    (stage/'flash-bindings.inc').write_text('V2_ADDR EQU $E2\nV2_COUNT EQU $EA\nV2_BYTES EQU $7C80\nV2_SELECTED EQU $F3\nV2_FLASH_PTR EQU $E4\nV2_FLASH_DATA EQU $F0\n')
    (stage/'ns-equ.inc').write_text(''.join(f'{n} EQU ${nsy[n]:04X}\n' for n in ('NS_CRC_BYTE','NS_YES_WORD')))
    text=(stage/'flash-provider.asm').read_text(encoding='utf-8')
    text=re.sub(r'^\s*XDEF\b[^\n]*','; local map symbols',text,flags=re.M)
    text,_=conservative_branches(text,'SF_flash_provider_')
    (stage/'flash-provider.asm').write_text(text,encoding='utf-8')
    sf,_=assemble(stage,'flash-provider',0x7000,'NF_END',False)
    sf=sf.ljust(2046,b'\xff');sf+=binascii.crc_hqx(sf,65535).to_bytes(2,'big')
    # The unchanged compact decoder is itself compiled, not read from a seed.
    decoder=out/'decoder';decoder.mkdir()
    shutil.copyfile(ROOT/'monitors/native/compact-decode.asm',decoder/'decoder.asm')
    boot=equs(ROOT/'src/core/boot-symbols.inc');eq=equs(ROOT/'src/include/str8n-v2-eq.inc')
    bindings=dict(CD_SRC=0xe0,CD_DST=0xe2,CD_MATCH=0xe6,CD_BANK=0x6708,CD_LIMIT=0x6709,CD_ORIGIN=0x670b,
        CD_EXPECTED=0x670d,CD_SOURCE_END=0x670f,CD_FLAGS=0x6711,CD_BITS=0x6712,CD_DISTANCE=0x6713,CD_LENGTH=0x6715,
        CD_SELECT=0x7848,CD_CRC_INIT=boot['J_CRC_INIT'],CD_CRC_BYTE=boot['J_CRC_BYTE'],CD_CRC_VALUE=eq['J_CRC'])
    (decoder/'compact-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
    kernel,_=assemble(decoder,'decoder',0x6800,'CD_END')
    if len(kernel)!=289:raise ValueError('AP decoder layout changed')
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
    adapters={};entries={}
    for name,body,target in [('ASM',provider,asy['APP_START']),('DBG',start,dsy['DBG_ENTRY'])]:
        folder=out/(name+'-adapter');folder.mkdir()
        text=bridge+body+f'DT_ENTER:\n LDA #3\n JSR $7848\n JMP ${target:04X}\nDT_END:\n ENDMOD\n END\n'
        (folder/'adapter.asm').write_text(text)
        adapters[name],entries[name]=assemble(folder,'adapter',0x6740,'DT_END')
    draw=bytearray(dpacket[0x3e00:]);site=draw.index(bytes.fromhex('6C7A70'));draw[site:site+3]=bytes.fromhex('4C4967')
    templates={};images={}
    for name,origin,data in [('ASM',0xa000,raw),('DBG',0xc000,bytes(draw))]:
        adapter=adapters[name];sy=entries[name];packed=compact(data);limit=0x4000+len(data)
        stores={0xe2:0,0xe3:0x40,0x6708:0,0x6709:limit&255,0x670a:limit>>8,0x670b:0,0x670c:0x40,
                0x670d:binascii.crc_hqx(data,65535)&255,0x670e:binascii.crc_hqx(data,65535)>>8}
        setup=''.join(f' LDA #${v:02X}\n STA ${a:04X}\n' for a,v in stores.items())
        finish=f' JSR ${sy["DT_PROVIDER"]:04X}\n BCC DT_REFUSE\n JMP ${sy["DT_ENTER"]:04X}\nDT_REFUSE:\n JMP $7E67\n' if name=='ASM' else f''' STZ $6B00
DT_PROMPT:
 LDX #<DT_TEXT
 LDY #>DT_TEXT
 JSR ${dsy['DBG_PRINT']:04X}
 JSR ${dsy['DBG_READ_LINE']:04X}
 STZ $D7
 JSR ${dsy['DBG_SPACES']:04X}
 CMP #'Q'
 BNE DT_ADDRESS
 INC $D7
 JSR ${dsy['DBG_SPACES']:04X}
 BEQ DT_CANCEL
 BRA DT_PROMPT
DT_ADDRESS:
 JSR ${dsy['DBG_HEX_WORD']:04X}
 BCC DT_PROMPT
 JSR ${dsy['DBG_SPACES']:04X}
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
        text=f''' MODULE DT_{name}
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
'''+finish+'DT_KERNEL:\n'+db(kernel)+'DT_ADAPTER:\n'+db(adapter)+'DT_PACKED:\n'+db(packed)+'DT_PACKED_END:\nDT_END:\n ENDMOD\n END\n'
        folder=out/(name+'-loader');folder.mkdir()
        text,_=conservative_branches(text,'DG2_AP_' if name=='DBG' else 'SF_ASM_AP02_')
        template=folder/'app.asm';template.write_text(text);templates[name]=template
        body,_=assemble(folder,'app',origin+32,'DT_END',False)
        header=bytearray(32);header[:8]=b'AP\x02 PR05';header[8:10]=(8192 if name=='DBG' else len(body)+32).to_bytes(2,'little')
        header[10:12]=(origin+32).to_bytes(2,'little');header[14:16]=bytes((1,2));header[16:16+len(name)]=name.encode()
        if name=='DBG':tail=body.ljust(0x1800-32,b'\xff')+sf
        else:tail=body.ljust(8192-32,b'\xff')
        header[28:30]=binascii.crc_hqx(header[:28],65535).to_bytes(2,'little')
        header[30:32]=binascii.crc_hqx(tail if name=='DBG' else body,65535).to_bytes(2,'little')
        images[name]=bytes(header)+tail
    return dict(ASM_RAM=bytes(packet),DBG_RAM=bytes(dpacket),ASM_FLASH=images['ASM'],DBG_FLASH=images['DBG'],
                asm_template=templates['ASM'],dbg_template=templates['DBG'],asm_symbols=asy,dbg_symbols=dsy)
