"""Regenerate SRAM/WORK g4, compressed ROM and S19/Store tail from source."""
import binascii,json,re,shutil
from pathlib import Path
from build_mona import ROOT,equs,cells
from build_native_apps import normalized
from mona_branches import conservative_branches
from rebuild_mon_services import assemble
from storage_compact import compact
from sram_named_source import extension,SUPPORT
from build_storage_batch import source as batch_source

def build(out,decoder,program_manifest):
    from build_sram_work import build as build_base
    from build_s19_loader import build as build_s19
    from build_store_front import build as build_store
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    boot=equs(ROOT/'src/core/boot-symbols.inc');eq=equs(ROOT/'src/include/str8n-v2-eq.inc')
    base=out/'base';build_base(base,2)
    stage=out/'g4';stage.mkdir()
    for path in base.glob('*.inc'):shutil.copyfile(path,stage/path.name)
    handoff=out/'handoff';handoff.mkdir()
    shutil.copyfile(ROOT/'monitors/native/native-handoff.asm',handoff/'handoff.asm')
    (handoff/'handoff-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in dict(HC_CRC_INIT=boot['J_CRC_INIT'],HC_CRC_BYTE=boot['J_CRC_BYTE'],HC_CRC_VALUE=eq['J_CRC']).items()))
    hc,_=assemble(handoff,'handoff',0x6b00,'HC_END')
    hcinc='HC_IMAGE:\n'+''.join(' DB '+','.join(f'${v:02X}' for v in hc[i:i+16])+'\n' for i in range(0,len(hc),16))+'HC_IMAGE_END:\n'
    text=(base/'sram-work.asm').read_text(encoding='utf-8').replace('00000002','00000003')
    text=text.replace('SW_INIT:\n','SW_INIT:\n        STZ MX_API_ACTIVE\n',1)
    text=text.replace('SW_SRAM_API:\n','SW_SRAM_API:\n        STZ MX_API_ACTIVE\n',1)
    needle='        STX SM_C_PTR+1\n';at=text.index(needle,text.index('SM_C_API:'))+len(needle)
    text=text[:at]+'''        LDA MX_API_ACTIVE
        CMP #$A5
        BNE SW_X_PUBLIC_REQUEST
        LDA SM_C_PTR
        BNE SW_X_PUBLIC_REQUEST
        CPX #$63
        BEQ SM_C_API_COPY
SW_X_PUBLIC_REQUEST:
        LDA SM_C_PTR
'''+text[at:]
    text=text.replace('        LDA SW_ENTRY_ROUTE\n        BEQ SW_MAIN_ENTRY','        JSR SW_NAMED_PRESET\n        LDA SW_ENTRY_ROUTE\n        BEQ SW_MAIN_ENTRY',1)
    text=text.replace('SW_LONG_COMMAND:\n','''SW_LONG_COMMAND:
        LDA SW_LINE
        CMP #'X'
        BNE SW_NOT_X
        STZ MX_RETURN
        JMP SW_NAMED_COMMAND
SW_NOT_X:
''',1)
    text=text.replace('SW_COPY_RANGE:\n','''SW_COPY_RANGE:
        LDA SM_D_SOURCE_BYTE_HOOK+1
        ORA SM_D_RESTORE_TRANSFER_HOOK+1
        BNE SW_RANGE_OK
''',1)
    reference=(ROOT/'monitors/reference/bank-maint-2.4.inc').read_text(encoding='utf-8')
    vals=('V2_ADDR','V2_COUNT','V2_BYTES','V2_SELECTED','V2_NMI_HOLD','V2_FLASH_PTR','V2_FLASH_DATA')
    bindings=''.join(f'{n} EQU ${eq[n]:04X}\n' for n in vals)
    extra=bindings+extension(reference)+SUPPORT+'\n'+(ROOT/'monitors/native/bank-transfer-alloc.inc').read_text()+'\n'+hcinc
    text=text.replace('SW_CODE_END:',extra+'\nSW_CODE_END:')
    def flatten(text,seen=()):
        def include(m):
            name=m[1]
            if name in seen:raise ValueError('Recursive SRAM include')
            return flatten((stage/name).read_text(encoding='utf-8-sig'),(*seen,name))
        return re.sub(r'^\s*INCLUDE "([^"]+)"\s*$',include,text,flags=re.M)
    text=normalized(flatten(text))
    constants=re.findall(r'^\s*\w+\s+EQU\s+[^\n]+$',text,re.M)
    text=re.sub(r'^\s*\w+\s+EQU\s+[^\n]+\n','',text,flags=re.M)
    text=text.replace('        CODE\n','\n'.join(constants)+'\n        CODE\n',1)
    text,_=conservative_branches(text,'NE_SW_')
    text,_=conservative_branches(batch_source(text),'SB_LONG_')
    (stage/'image.asm').write_text(text,encoding='utf-8')
    body,sy=assemble(stage,'image',0x2000,'SW_CODE_END',False)
    (out/'SRAM-WORK-BATCH-2000.bin').write_bytes(body)
    # The 107-byte bootstrap is emitted from its source layout, then positioned
    # exactly as the accepted g4 compact decoder arrangement.
    stub=bytearray(bytes.fromhex('78D8A2FF9AA901204878A200'));loop=len(stub)
    for src,dst in ((0xb100,0x6800),(0xb200,0x6900)):stub.extend((0xbd,src&255,src>>8,0x9d,dst&255,dst>>8))
    stub.extend((0xe8,0xd0,(loop-len(stub)-3)&255))
    def store(addr,value):stub.extend((0xa9,value,0x8d,addr&255,addr>>8))
    for addr,value in ((0xe0,0x22),(0xe1,0xb2),(0xe2,0),(0xe3,0x20),(0x670b,0),(0x670c,0x20),(0x6708,1)):store(addr,value)
    for src,dst in ((0xb012,0x670f),(0xb013,0x6710),(0xb01a,0x6709),(0xb01b,0x670a),(0xb01c,0x670d),(0xb01d,0x670e)):
        stub.extend((0xad,src&255,src>>8,0x8d,dst&255,dst>>8))
    stub.extend(bytes.fromhex('A91F48A9FF484C0068'))
    if len(stub)!=107:raise ValueError('Storage bootstrap allocation changed')
    kernel_start=0xb000+32+len(stub);packed_start=kernel_start+len(decoder)
    for before,after in ((0xb100,kernel_start),(0xb200,kernel_start+256)):
        old=bytes((0xbd,before&255,before>>8));new=bytes((0xbd,after&255,after>>8))
        if stub.count(old)!=1:raise ValueError('Storage decoder copy moved')
        stub=stub.replace(old,new)
    stub=stub.replace(bytes.fromhex('A9228DE000A9B28DE100'),bytes((0xa9,packed_start&255,0x8d,0xe0,0,0xa9,packed_start>>8,0x8d,0xe1,0)))
    packed=compact(body);end=packed_start+len(packed)
    if end>0xd900:raise ValueError('Storage packed data overlaps the retained helper')
    # S19/Store support is separately reassembled and sealed, not preserved
    # from an old 12KiB flash image.
    build_s19(out/'S19')
    build_store(out/'STORE',out/'S19',Path(program_manifest).parent)
    helper=(out/'STORE/S19-STORE-6B00.bin').read_bytes()
    image=bytearray(b'\xff'*12288)
    image[:8]=b'RP\x01\x03PR05';image[10:14]=bytes.fromhex('00200020');image[14:18]=(4).to_bytes(4,'little');image[22:26]=b'BQ\x01\x01'
    for offset,value in ((8,end-0xb020),(18,end),(26,0x2000+len(body)),(28,binascii.crc_hqx(body,65535))):image[offset:offset+2]=value.to_bytes(2,'little')
    image[32:32+len(stub)]=stub
    image[kernel_start-0xb000:packed_start-0xb000]=decoder
    image[packed_start-0xb000:end-0xb000]=packed
    image[0x2900:0x2f00]=helper
    image[-2:]=binascii.crc_hqx(image[:-2],65535).to_bytes(2,'big')
    (out/'SRAM-WORK-flash.bin').write_bytes(image)
    return bytes(image)
