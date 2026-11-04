"""Build bounded named transfers and EDU save once; no device access or F build."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,equs,sha
from build_native_apps import normalized
from mona_branches import conservative_branches
from named_transfer_source import bank_source,provider_source
import port_bank_maint


def compact(data):
    out=bytearray();pos=0;seen={}
    while pos<len(data):
        flagpos=len(out);out.append(0);flags=0
        for bit in range(8):
            if pos==len(data):break
            key=data[pos:pos+3];best=0;distance=0
            for old in reversed(seen.get(key,())[-64:]):
                if pos-old>4096:break
                length=0
                while length<18 and pos+length<len(data) and data[old+length]==data[pos+length]:length+=1
                if length>best:best=length;distance=pos-old
                if best==18:break
            size=best if best>=3 else 1
            if size==1:flags|=1<<bit;out.append(data[pos])
            else:out.extend(((distance-1)&255,((distance-1)>>8)<<4|(size-3)))
            for address in range(pos,pos+size):seen.setdefault(data[address:address+3],[]).append(address)
            pos+=size
        out[flagpos]=flags
    assert expand(out,len(data))==data
    return bytes(out)


def expand(data,count):
    out=bytearray();p=0
    while len(out)<count:
        flags=data[p];p+=1
        for bit in range(8):
            if len(out)==count:break
            if flags>>bit&1:out.append(data[p]);p+=1
            else:
                lo,hi=data[p:p+2];p+=2;distance=1+lo+((hi>>4)<<8);size=(hi&15)+3
                assert distance<=len(out) and len(out)+size<=count
                for _ in range(size):out.append(out[-distance])
    assert p==len(data);return bytes(out)


def build(out):
    out=Path(out).resolve();out.mkdir(exist_ok=False)
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    boot=equs(ROOT/'src/core/boot-symbols.inc');eq=equs(ROOT/'src/include/str8n-v2-eq.inc')
    logs=[];artifacts={};symbols={}
    def emit(name,body):
        (out/name).write_bytes(body);artifacts[name]=dict(bytes=len(body),sha256=sha(body))
    def link(stage,name,origin,end):
        def flatten(n,seen=()):
            assert n not in seen
            s=(stage/n).read_text(encoding='utf-8-sig')
            return re.sub(r'^\s*INCLUDE "([^"]+)"\s*$',lambda m:flatten(m[1],(*seen,n)),s,flags=re.M)
        text=normalized(flatten(name+'.asm'))
        constants=re.findall(r'^\s*\w+\s+EQU\s+[^\n]+$',text,re.M)
        text=re.sub(r'^\s*\w+\s+EQU\s+[^\n]+\n','',text,flags=re.M)
        text=text.replace('        CODE\n','\n'.join(constants)+'\n        CODE\n',1)
        text,_=conservative_branches(text,'BF_'+name.replace('-','_')+'_')
        (stage/(name+'-flat.asm')).write_text(text)
        for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',name+'-flat.asm'],
                    [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',name+'.s19',name+'-flat.obj']):
            r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
            logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if r.returncode:raise RuntimeError('Build failed; inspect '+str(out/'build-log.json'))
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(name+'.map')).read_text(),re.M)}
        m=cells(stage/(name+'.s19'));assert set(m)==set(range(origin,sy[end]))
        body=bytes(m[a] for a in range(origin,sy[end]));symbols[stage.name]=sy
        print(stage.name,name,len(body),'bytes',flush=True);return body,sy
    # The provider is separate from the unchanged public SP/01 component.
    stage=out/'XP';stage.mkdir()
    for n in ('program-layout.inc','program-layout-check.inc','program-spi.inc','workbench-layout.inc','workbench-interface.inc','batch-interface.inc','monitor-ui.inc'):
        shutil.copyfile(ROOT/'monitors/src'/n,stage/n)
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    p=stage/'program-layout.inc';p.write_text(p.read_text().replace('PTR EQU $E2','PTR EQU $D2'))
    (stage/'named-program.asm').write_text(provider_source((ROOT/'monitors/src/program-provider.asm').read_text()))
    xp,xps=link(stage,'named-program',0x6B00,'SP_END');assert len(xp)<=3326
    xp=xp.ljust(3326,b'\xff');xp+=binascii.crc_hqx(xp,65535).to_bytes(2,'big');emit('NAMED-PROGRAM-6B00.bin',xp)
    common=dict(CD_SRC=0xE0,CD_DST=0xE2,CD_MATCH=0xE6,CD_BANK=0x6708,CD_LIMIT=0x6709,CD_ORIGIN=0x670B,
        CD_EXPECTED=0x670D,CD_SOURCE_END=0x670F,CD_FLAGS=0x6711,CD_BITS=0x6712,CD_DISTANCE=0x6713,CD_LENGTH=0x6715,
        CD_SELECT=0x7848,CD_CRC_INIT=boot['J_CRC_INIT'],CD_CRC_BYTE=boot['J_CRC_BYTE'],CD_CRC_VALUE=eq['J_CRC'])
    stage=out/'DECODER';stage.mkdir();shutil.copyfile(ROOT/'monitors/native/compact-decode.asm',stage/'compact-decode.asm')
    (stage/'compact-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in common.items()))
    kernel,ks=link(stage,'compact-decode',0x6800,'CD_END');assert len(kernel)<=512
    emit('COMPACT-DECODE-6800.bin',kernel)
    port_bank_maint.generate()
    reference=(ROOT/'monitors/reference/bank-maint-2.4.inc').read_text()
    transfer=bank_source(reference)+'\n        INCLUDE "bank-transfer-alloc.inc"\n'
    (ROOT/'monitors/native/bank-maint-transfer.inc').write_text(transfer)
    bodies={}
    for kind in ('ROM','RAM'):
        stage=out/kind;stage.mkdir()
        prior=ROOT.parent.parent/'BUILD/native-apps-g1-maint-r1'
        for p in prior.glob('*.inc'):shutil.copyfile(p,stage/p.name)
        for p in (ROOT/'monitors/native').glob('bank-*.inc'):shutil.copyfile(p,stage/p.name)
        for n in ('bank-maint.asm',):shutil.copyfile(ROOT/'monitors/native'/n,stage/n)
        for n in ('batch-interface.inc','monitor-ui.inc'):shutil.copyfile(ROOT/'monitors/src'/n,stage/n)
        source=(ROOT/'monitors/native/edu-settings.asm').read_text()
        source=source[source.index('EC_START:'):source.index('EC_END:')].replace('EC_','BE_')
        (stage/'bank-edu-reader.inc').write_text(source)
        bindings=dict(MB_META_FIRST_PAGE=0x9C if kind=='ROM' else 0x50,MB_META_END_PAGE=0xA0 if kind=='ROM' else 0x54,
            MB_META_FORMAT=0x9000 if kind=='ROM' else 0x5400,MB_META_BYTE=0x7B64 if kind=='ROM' else 0x1900,
            BE_SOURCE_PAGE=0x9C if kind=='ROM' else 0x50,BE_SOURCE_END_PAGE=0xA0 if kind=='ROM' else 0x54,
            BE_CRC_INIT=boot['J_CRC_INIT'],BE_CRC_BYTE=boot['J_CRC_BYTE'],BE_CRC_LOW=eq['J_CRC'],
            SM_C_API=xps['API'],SM_C_TRANSFER=xps['TRANSFER'],SM_D_LOAD=0x69A6,SM_D_LENGTH=0x69A8,SM_D_ENTRY=0x69AC,
            SM_D_BEST_SEQ=0x69B2,SM_D_BP=0x69A2,SM_D_COUNT=0x69B6,SM_D_SOURCE_BYTE_HOOK=0x67F1,
            SM_D_SAVE_TRANSFER_HOOK=0x67F3,SM_D_RESTORE_TRANSFER_HOOK=0x67F5)
        (stage/'bank-features-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
        loader=(stage/'bank-compact.inc').read_text()
        if kind=='RAM':
            a,b=loader.index('MB_LOAD_XP:'),loader.index('MB_XP_ADMIT:')
            loader=loader[:a]+'MB_LOAD_XP:\n        BRA MB_XP_ADMIT\n'+loader[b:]
        (stage/'bank-compact.inc').write_text(loader)
        p=stage/'bank-maint.asm';p.write_text(p.read_text().replace('        INCLUDE "bank-maint-transfer.inc"',
            '        INCLUDE "bank-maint-transfer.inc"\n        INCLUDE "bank-compact.inc"'))
        body,sy=link(stage,'bank-maint',0x2000,'MAINT_END');assert sy['MAINT_END']<=0x5000,'Editor/code overlap'
        bodies[kind]=body;emit('BANK-FEATURES-'+kind+'-2000.bin',body)
    # Pack within the unchanged three-sector RP image, preserving all helpers.
    original=(ROOT.parent.parent/'BUILD/flash-status-correction-r4/BANK-MAINT-corrected.bin').read_bytes()
    packed=bytearray(original);main=compact(bodies['ROM']);xpdata=compact(xp)
    xpbase=0x8300+len(main);end=xpbase+len(xpdata)
    assert end<=0xA31D,f'Packed code reaches{end:04X}; dense helper begins A31D'
    packed[32:0x231D]=b'\xff'*(0x231D-32)
    # An admitted bootstrap copies512 decoder bytes, uses ROM input (no low
    # owner-RAM staging), and returns into the expanded MAINT entry at2000.
    stub=bytearray(bytes.fromhex('78 D8 A2 FF 9A A9 01 20 48 78 A2 00'))
    loop=len(stub);stub.extend(bytes.fromhex('BD 00 81 9D 00 68 BD 00 82 9D 00 69 E8 D0'))
    stub.append((loop-len(stub)-1)&255)
    def store(address,value):stub.extend((0xA9,value,0x8D,address&255,address>>8))
    for address,value in ((0xE0,0),(0xE1,0x83),(0xE2,0),(0xE3,0x20),(0x670B,0),(0x670C,0x20),(0x6708,1)):
        store(address,value)
    for src,dst in ((0x8012,0x670F),(0x8013,0x6710),(0x801A,0x6709),(0x801B,0x670A),(0x801C,0x670D),(0x801D,0x670E)):
        stub.extend((0xAD,src&255,src>>8,0x8D,dst&255,dst>>8))
    stub.extend(bytes.fromhex('A9 1F 48 A9 FF 48 4C 00 68'));assert len(stub)<=224
    packed[32:32+len(stub)]=stub;packed[0x100:0x100+len(kernel)]=kernel
    packed[0x300:0x300+len(main)]=main;packed[xpbase-0x8000:end-0x8000]=xpdata
    for offset,value in ((8,end-0x8020),(18,xpbase),(20,xpbase),(22,end),(26,0x2000+len(bodies['ROM'])),
                         (28,binascii.crc_hqx(bodies['ROM'],65535))):packed[offset:offset+2]=value.to_bytes(2,'little')
    packed[14:18]=(2).to_bytes(4,'little')
    packed[-2:]=binascii.crc_hqx(packed[:-2],65535).to_bytes(2,'big')
    assert packed[0x231D:-2]==original[0x231D:-2] and binascii.crc_hqx(packed,65535)==0
    emit('BANK-FEATURES-flash.bin',packed)
    (out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    report=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,artifacts=artifacts,
       raw_main_bytes=len(bodies['ROM']),packed_main_bytes=len(main),packed_XP_bytes=len(xpdata),packed_end=f'{end:04X}',
       helpers_preserved='B1:A31D-AFFD exact; RP CRC resealed',flash_sectors=3,EDU_record='ED/1 append-only32 bytes; metadata9C00-9FFF; never C/D',
       named_copy='X bank NAME P NAME / X P NAME bank NAME; S alias; source retained; no erase',
       source_sha256={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in (ROOT/'monitors/native').glob('bank-*.inc')})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','artifacts')},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out)
