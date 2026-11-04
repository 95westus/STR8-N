"""Pack named copies with the existing SRAM hooks and append-only EDU settings."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,equs,sha
from build_native_apps import normalized
from mona_branches import conservative_branches
from build_bank_features import compact
from sram_named_source import extension,SUPPORT
import port_bank_maint


def build(out,reuse_from=None):
    out=Path(out).resolve();out.mkdir(exist_ok=False);logs=[];arts={};symbols={}
    base=ROOT.parent.parent/'BUILD'
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text());boot=equs(ROOT/'src/core/boot-symbols.inc');eq=equs(ROOT/'src/include/str8n-v2-eq.inc')
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    def emit(n,b):
        (out/n).write_bytes(b);arts[n]=dict(bytes=len(b),sha256=sha(b))
    def link(stage,name,origin,end):
        def flatten(n,seen=()):
            assert n not in seen
            return re.sub(r'^\s*INCLUDE "([^"]+)"\s*$',lambda m:flatten(m[1],(*seen,n)),(stage/n).read_text(encoding='utf-8-sig'),flags=re.M)
        s=normalized(flatten(name+'.asm'));const=re.findall(r'^\s*\w+\s+EQU\s+[^\n]+$',s,re.M)
        s=re.sub(r'^\s*\w+\s+EQU\s+[^\n]+\n','',s,flags=re.M)
        s=s.replace('        CODE\n','\n'.join(const)+'\n        CODE\n',1)
        s,_=conservative_branches(s,'NE_'+stage.name+'_');(stage/'flat.asm').write_text(s)
        prior=Path(reuse_from)/stage.name if reuse_from else None
        reuse=bool(prior and (prior/'flat.asm').exists() and (prior/'image.s19').exists() and (prior/'flat.asm').read_bytes()==(stage/'flat.asm').read_bytes())
        if reuse:
            for n in ('image.s19','image.map'):shutil.copyfile(prior/n,stage/n)
        for cmd in ([] if reuse else ([shutil.which('wdc02as'),'-G','-L','-S','-W','flat.asm'],
                    [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o','image.s19','flat.obj'])):
            p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(stage=stage.name,command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if p.returncode:raise RuntimeError('Inspect '+str(out/'build-log.json'))
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'image.map').read_text(),re.M)}
        m=cells(stage/'image.s19');assert set(m)==set(range(origin,sy[end]))
        b=bytes(m[a] for a in range(origin,sy[end]));symbols[stage.name]=sy
        print(stage.name,len(b),'linked bytes',flush=True);return b,sy
    stage=out/'HANDOFF';stage.mkdir();shutil.copyfile(ROOT/'monitors/native/native-handoff.asm',stage/'handoff.asm')
    (stage/'handoff-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in dict(HC_CRC_INIT=boot['J_CRC_INIT'],HC_CRC_BYTE=boot['J_CRC_BYTE'],HC_CRC_VALUE=eq['J_CRC']).items()))
    hc,_=link(stage,'handoff',0x6B00,'HC_END');assert len(hc)<128;emit('NATIVE-HANDOFF-6B00.bin',hc)
    hcinc='HC_IMAGE:\n'+''.join('        DB '+','.join(f'${x:02X}' for x in hc[i:i+16])+'\n' for i in range(0,len(hc),16))+'HC_IMAGE_END:\n'
    stage=out/'DECODER';stage.mkdir();shutil.copyfile(ROOT/'monitors/native/compact-decode.asm',stage/'decoder.asm')
    bindings=dict(CD_SRC=0xE0,CD_DST=0xE2,CD_MATCH=0xE6,CD_BANK=0x6708,CD_LIMIT=0x6709,CD_ORIGIN=0x670B,
        CD_EXPECTED=0x670D,CD_SOURCE_END=0x670F,CD_FLAGS=0x6711,CD_BITS=0x6712,CD_DISTANCE=0x6713,CD_LENGTH=0x6715,
        CD_SELECT=0x7848,CD_CRC_INIT=boot['J_CRC_INIT'],CD_CRC_BYTE=boot['J_CRC_BYTE'],CD_CRC_VALUE=eq['J_CRC'])
    (stage/'compact-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
    kernel,_=link(stage,'decoder',0x6800,'CD_END');assert len(kernel)<=0x130
    emit('COMPACT-DECODE-6800.bin',kernel)
    bodies={}
    for kind in ('BM_ROM','BM_RAM'):
        stage=out/kind;stage.mkdir()
        for p in (base/'native-apps-g1-maint-r1').glob('*.inc'):shutil.copyfile(p,stage/p.name)
        for p in (ROOT/'monitors/native').glob('bank-*.inc'):shutil.copyfile(p,stage/p.name)
        shutil.copyfile(ROOT/'monitors/native/bank-maint.asm',stage/'bank-maint.asm')
        for n in ('monitor-ui.inc','batch-interface.inc'):shutil.copyfile(ROOT/'monitors/src'/n,stage/n)
        port_bank_maint.generate(True,stage/'bank-maint-classic.inc')
        p=stage/'bank-maint-classic.inc';text=p.read_text()
        old='NAME [1-8 characters | CLEAR] (YES required)'
        new='NAME [name|CLEAR]; EDU [SAVE] ON|OFF (YES)'
        assert len(new)<=len(old)
        text=text.replace(old,new.ljust(len(old)),1).replace('BASE1 PR05 g1','BASE1 PR05 g3')
        p.write_text(text)
        p=stage/'bank-maint.asm';s=p.read_text().replace('        CODE\n','        INCLUDE "bank-features-bindings.inc"\n        CODE\n',1)
        s=s.replace('MAINT_END:', '        INCLUDE "bank-maint-edu.inc"\n        INCLUDE "bank-transfer-handoff.inc"\nMAINT_END:')
        p.write_text(s)
        p=stage/'bank-maint-base1.inc';p.write_text(p.read_text().replace('MB_ALIASES:\n','''MB_ALIASES:
        LDX #<MB_EDU_WORD
        LDY #>MB_EDU_WORD
        JSR MB_MATCH
        BCC MB_NOT_EDU
        PLA
        PLA
        JMP MB_EDU_COMMAND
MB_NOT_EDU:
'''))
        s=(ROOT/'monitors/native/edu-settings.asm').read_text();s=s[s.index('EC_START:'):s.index('EC_END:')].replace('EC_','BE_')
        (stage/'bank-edu-reader.inc').write_text(s);(stage/'handoff-image.inc').write_text(hcinc)
        fixture=kind=='BM_RAM'
        bindings=dict(MB_META_FIRST_PAGE=0x50 if fixture else 0x9C,MB_META_END_PAGE=0x54 if fixture else 0xA0,
            MB_META_FORMAT=0x5400 if fixture else 0x9000,MB_META_BYTE=0x1900 if fixture else 0x7B64,
            BE_SOURCE_PAGE=0x50 if fixture else 0x9C,BE_SOURCE_END_PAGE=0x54 if fixture else 0xA0,
            BE_CRC_INIT=boot['J_CRC_INIT'],BE_CRC_BYTE=boot['J_CRC_BYTE'],BE_CRC_LOW=eq['J_CRC'])
        (stage/'bank-features-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
        b,sy=link(stage,'bank-maint',0x2000,'MAINT_END');assert sy['MAINT_END']<0x5000
        bodies[kind]=b;emit(kind+'-2000.bin',b)
    stage=out/'SW';stage.mkdir()
    for p in (base/'sram-work-g2-native-r1').glob('*.inc'):shutil.copyfile(p,stage/p.name)
    # Reuse the accepted flattened SRAM/WORK implementation and its SPI engine.
    s=(base/'sram-work-g2-native-r1/sram-work.asm').read_text()
    s=s.replace('00000002','00000003')
    s=s.replace('SW_INIT:\n','SW_INIT:\n        STZ MX_API_ACTIVE\n',1)
    s=s.replace('SW_SRAM_API:\n','SW_SRAM_API:\n        STZ MX_API_ACTIVE\n',1)
    # Ordinary public requests keep the0200-1FFF guard. Only the local named
    # wrapper admits its exact private6300 request, without borrowing low RAM.
    needle='        STX SM_C_PTR+1\n'
    at=s.index(needle,s.index('SM_C_API:'))+len(needle)
    s=s[:at]+'''        LDA MX_API_ACTIVE
        CMP #$A5
        BNE SW_X_PUBLIC_REQUEST
        LDA SM_C_PTR
        BNE SW_X_PUBLIC_REQUEST
        CPX #$63
        BEQ SM_C_API_COPY
SW_X_PUBLIC_REQUEST:
        LDA SM_C_PTR
'''+s[at:]
    s=s.replace('        LDA SW_ENTRY_ROUTE\n        BEQ SW_MAIN_ENTRY',
                '        JSR SW_NAMED_PRESET\n        LDA SW_ENTRY_ROUTE\n        BEQ SW_MAIN_ENTRY',1)
    s=s.replace('SW_LONG_COMMAND:\n','''SW_LONG_COMMAND:
        LDA SW_LINE
        CMP #'X'
        BNE SW_NOT_X
        STZ MX_RETURN
        JMP SW_NAMED_COMMAND
SW_NOT_X:
''',1)
    s=s.replace('SW_COPY_RANGE:\n','''SW_COPY_RANGE:
        LDA SM_D_SOURCE_BYTE_HOOK+1
        ORA SM_D_RESTORE_TRANSFER_HOOK+1
        BNE SW_RANGE_OK
''',1)
    ref=(ROOT/'monitors/reference/bank-maint-2.4.inc').read_text()
    vals=('V2_ADDR','V2_COUNT','V2_BYTES','V2_SELECTED','V2_NMI_HOLD','V2_FLASH_PTR','V2_FLASH_DATA')
    bindings=''.join(f'{n} EQU ${eq[n]:04X}\n' for n in vals)
    extra=bindings+extension(ref)+SUPPORT+'\n'+(ROOT/'monitors/native/bank-transfer-alloc.inc').read_text()+'\n'+hcinc
    s=s.replace('SW_CODE_END:',extra+'\nSW_CODE_END:')
    (stage/'named-sram.asm').write_text(s)
    sw,sy=link(stage,'named-sram',0x2000,'SW_CODE_END');assert sy['SW_CODE_END']<0x5B00
    bodies['SW']=sw;emit('NAMED-SRAM-WORK-2000.bin',sw)
    def pack(name,body,original,baseaddr,limit):
        # The decoder fits through+230. Packed data starts at+230;
        # copying the entire second page merely copies unused packed bytes.
        data=compact(body);start=baseaddr+0x222;end=start+len(data)
        assert end<=limit,f'{name} packed end{end:04X} exceeds protected boundary{limit:04X}'
        a=bytearray(original);a[32:limit-baseaddr]=b'\xff'*(limit-baseaddr-32)
        stub=bytearray(bytes.fromhex('78 D8 A2 FF 9A A9 01 20 48 78 A2 00'));loop=len(stub)
        for src,dst in ((baseaddr+0x100,0x6800),(baseaddr+0x200,0x6900)):stub.extend((0xBD,src&255,src>>8,0x9D,dst&255,dst>>8))
        stub.extend((0xE8,0xD0,(loop-len(stub)-3)&255))
        def store(addr,v):stub.extend((0xA9,v,0x8D,addr&255,addr>>8))
        for addr,v in ((0xE0,start&255),(0xE1,start>>8),(0xE2,0),(0xE3,0x20),(0x670B,0),(0x670C,0x20),(0x6708,1)):store(addr,v)
        for src,dst in ((baseaddr+18,0x670F),(baseaddr+19,0x6710),(baseaddr+26,0x6709),(baseaddr+27,0x670A),(baseaddr+28,0x670D),(baseaddr+29,0x670E)):
            stub.extend((0xAD,src&255,src>>8,0x8D,dst&255,dst>>8))
        stub.extend(bytes.fromhex('A9 1F 48 A9 FF 48 4C 00 68'));assert len(stub)<=224
        a[32:32+len(stub)]=stub;a[0x100:0x100+len(kernel)]=kernel;a[0x222:0x222+len(data)]=data
        for offset,v in ((8,end-baseaddr-32),(18,end),(26,0x2000+len(body)),(28,binascii.crc_hqx(body,65535))):a[offset:offset+2]=v.to_bytes(2,'little')
        a[14:18]=(3).to_bytes(4,'little');a[-2:]=binascii.crc_hqx(a[:-2],65535).to_bytes(2,'big')
        assert a[limit-baseaddr:-2]==original[limit-baseaddr:-2] and binascii.crc_hqx(a,65535)==0
        emit(name,a);return dict(raw_bytes=len(body),packed_bytes=len(data),end=f'{end:04X}',boundary=f'{limit:04X}')
    bm=pack('BANK-MAINT-EDU-flash.bin',bodies['BM_ROM'],(base/'flash-status-correction-r4/BANK-MAINT-corrected.bin').read_bytes(),0x8000,0xA31D)
    sw=pack('SRAM-WORK-X-flash.bin',bodies['SW'],(base/'transfer-final-g1-r2/STORAGE-g2-transfer-r1.bin').read_bytes(),0xB000,0xD900)
    (out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    report=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,artifacts=arts,
       BM=bm,SW=sw,flash_sectors=6,helpers_preserved=['B1:A31D-AFFD','B1:D900-DFFD'],
       source_sha256={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in (ROOT/'monitors/native').glob('*') if p.name in ('bank-maint-edu.inc','bank-transfer-alloc.inc','bank-transfer-handoff.inc','native-handoff.asm','compact-decode.asm')})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','artifacts')},indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse-from',type=Path);a=p.parse_args();build(a.out,a.reuse_from)
