"""Reconstruct standalone FLASH/MAINT from project source; no device access."""
import binascii,hashlib,json,re,shutil,struct
from pathlib import Path
from build_mona import ROOT
from build_native_apps import prepare_stage,normalized
from rebuild_mon_services import assemble
from mona_branches import conservative_branches


def native_maint(out):
    import port_bank_maint
    out,_,freeze,_,_=prepare_stage(out)
    path=out/'bank-maint-classic.inc'
    port_bank_maint.generate(False,path)
    text,_=conservative_branches(normalized(path.read_text(encoding='utf-8')),'NI_bank_maint_classic_inc_')
    path.write_text(text,encoding='utf-8')
    body,sy=assemble(out,'bank-maint',0x2000,'MAINT_END')
    name='BANK-MAINT-g00000001-RAM.bin';(out/name).write_bytes(body)
    (out/'manifest.json').write_text(json.dumps(dict(F_sha256=freeze['sha256'],F_rebuilt=False,
        artifacts={name:dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())}),indent=2)+'\n')
    return body,sy


def flash(out):
    out,_,_,_,_=prepare_stage(out)
    # The accepted dense build supplies this bounded parser after the native
    # include-sizing pass; its local short branch must not be expanded again.
    parser=(ROOT/'monitors/native/s19-loader.asm').read_text(encoding='utf-8')
    (out/'flash-s19-parser.inc').write_text(parser[parser.index('SL_RECORD_READ:'):parser.index('SL_PRINT:')])
    dense=(ROOT/'monitors/native/flash-s19.inc').read_text(encoding='utf-8')
    (out/'flash-s19-state.inc').write_text(dense[:dense.index('FI_COMMAND:')])
    core=(ROOT/'monitors/native/board-tool.asm').read_text(encoding='utf-8')
    core=core.replace('        CODE\n','        INCLUDE "flash-s19-state.inc"\n        CODE\n',1)
    core=core.replace('        JMP CONFIG_START\n','        JSR FI_LIB_LOAD\n        BCC FT_BAD\n        JMP CONFIG_START\n',1)
    a=core.index('        LDX #<FI_WORD');b=core.index('        LDX #<FT_HELP_WORD',a)
    core=core[:a]+'''        LDA V2_LINE
        CMP #'I'
        BNE FC_NOT_I
        LDA FI_LIB_OK
        BEQ FT_BAD
        LDX #1
        JMP $4008
FC_NOT_I:
'''+core[b:]
    core=core.replace('        LDX #<FI_HELP_TEXT\n        LDY #>FI_HELP_TEXT\n        JSR CONFIG_PRINT\n','')
    a=core.index('FT_HELP_TEXT:');b=core.index('FT_VALID:',a)
    core=core[:a]+'''FT_HELP_TEXT:
        DB "BANK READ VIEW EDIT WRITE BYTE ERASE",13,10
        DB "I first last (S19)",13,10
        DB "BOOT B/C/OFF/RUN/DELAY; B/C/W/?",13,10
        DB "HOST; VERSION; Q; B3:C/D/F protected",13,10,0
'''+core[b:]
    replacements={
        'REFUSED: syntax/range/protected/stale; ? help':'REFUSED',
        'Canceled; flash unchanged.':'Canceled',
        'STR8-N FLASH/MAINT g00000001; N-F 0.3.0 BASE1/PR05':'FLASH g2 / N-F0.3.0 BASE1/PR05',
        'EDU profile: Rev D; revision/presence not electrically identified.':'EDU Rev D profile',
        'SXB: W65C02SXB / 65C02':'W65C02SXB / 65C02',
        'SXB: W65C816SXB / emulation':'W65C816SXB / emulation',
        'offset 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F':'offset 00..0F (16 bytes)'}
    for old,new in replacements.items():
        if old not in core:raise ValueError('FLASH source identity moved: '+old)
        core=core.replace(old,new)
    core=core.replace('        INCLUDE "flash-s19.inc"','        INCLUDE "flash-s19-parser.inc"\n        INCLUDE "flash-s19-load.inc"')
    (out/'flash-s19-load.inc').write_bytes((ROOT/'monitors/native/flash-s19-load.inc').read_bytes())
    core,_=conservative_branches(core,'FC_board_tool_')
    (out/'board-tool.asm').write_text(core,encoding='utf-8')
    body,sy=assemble(out,'board-tool',0x2000,'BOARD_END',transform=False)
    if len(body)>0x1a30:raise ValueError('FLASH overlaps its accepted allocation')
    bindings={k:v for k,v in sy.items() if k.startswith('FT_') or k in ('CONFIG_PRINT','JE_ENTER','SL_RECORD_READ','SL_DRAIN')}
    (out/'dense-core.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
    control=dense[dense.index('FI_COMMAND:'):dense.index('        INCLUDE "flash-s19-parser.inc"')]
    control=re.sub(r'^FI_HELP_TEXT:.*\n','',control,flags=re.M)
    text='''        MODULE DENSE_CONTROL
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "batch-interface.inc"
        INCLUDE "flash-s19-state.inc"
        INCLUDE "dense-core.inc"
        CODE
FI_LIBRARY: DB "FI",1,0,"PR05"
        JMP FI_COMMAND
'''+control+'\nFI_CONTROL_END:\n        ENDMOD\n        END\n'
    text,_=conservative_branches(text,'FC_dense_control_')
    (out/'dense-control.asm').write_text(text,encoding='utf-8')
    library,_=assemble(out,'dense-control',0x4000,'FI_CONTROL_END',transform=False)
    library+=binascii.crc_hqx(library,65535).to_bytes(2,'big')
    # Retain the qualified three-fragment RAM-copy layout, now generated from
    # contiguous source-built library bytes rather than a flash capture.
    lengths=(99,308,174)
    if len(library)!=sum(lengths):raise ValueError('Qualified dense-library layout changed')
    core=bytearray(body);offset=0
    table=b''
    for size in lengths:
        table+=struct.pack('<HH',0x4300+offset,size);offset+=size
    at=sy['FI_FRAGMENTS']-0x2000
    if core[at:at+12]!=bytes(12):raise ValueError('FLASH fragment table moved')
    core[at:at+12]=table
    at=sy['CONFIG_QUIT']-0x2000
    if core[at:at+3]!=bytes.fromhex('4C005E'):raise ValueError('FLASH exit moved')
    core[at:at+3]=bytes.fromhex('4C647E')
    stub=bytes.fromhex('78D8A2FF9A9CF97D9C005DA9038D007D2048784C0020')
    packet=bytearray(b'\xff'*(0x4300+len(library)-0x200))
    packet[:len(stub)]=stub;packet[0x1e00:0x1e00+len(core)]=core;packet[0x4100:]=library
    (out/'FLASH.bin').write_bytes(packet)
    return bytes(packet),sy
