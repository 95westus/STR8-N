"""Build affected BASE1 RAM tools; create F once, then enforce its freeze.

Uses existing worker/vector images and independent migration helpers. No
reproduction build, CPU model, serial port or installation is invoked.
"""
import argparse
import binascii
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from build import cells, db, s19, save
from build_system import long_branches

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
crc=lambda data:binascii.crc_hqx(data,0xffff)
F_NAME='STR8N-F-BOOT-4096.bin'
F_INPUTS=('src/core/str8n-v2-boot.asm','src/core/prototype-console.inc',
 'src/core/worker-copy.inc','src/core/worker-image.inc','src/core/vectors-image.inc',
 'src/core/vectors-symbols.inc','src/core/str8n-v2-eq.inc','src/core/str8n-v2-public.inc',
 'src/core/sr-stubs.inc','src/include/str8n-v2-eq.inc','src/include/str8n-v2-public.inc',
 'src/include/service-eq.inc','src/core/boot-identity.inc','src/core/boot-banner.inc')


def identity_data(identity):
    row=bytearray(64)
    row[:8]=b'NFI1'+bytes((64,identity['public_ABI_major'],1,0))
    row[8:12]=int(identity['F_generation'],16).to_bytes(4,'little')
    for offset,key in ((12,'product'),(20,'F_version'),(28,'profile')):
        text=identity[key].encode('ascii')
        if len(text)>7:raise ValueError('Identity text exceeds fixed field: '+key)
        row[offset:offset+8]=text.ljust(8,b'\0')
    row[36:40]=identity['private_contract'].encode('ascii')
    row[40:48]=bytes.fromhex('60 7E 04 F0 00 F0 00 10')
    row[62:64]=crc(row[:62]).to_bytes(2,'little')
    banner=(f"\r\n{identity['product']} {identity['F_version']} g{identity['F_generation']}\r\n"
            f"{identity['profile']} / {identity['private_contract']}\r\n\0").encode('ascii')
    return bytes(row),banner


def equs(path):
    return {name:int(value,16) for name,value in re.findall(
        r'^(\w+)\s+EQU\s+\$([0-9a-fA-F]+)',path.read_text(),re.M)}


def build(out,prepare_freeze=False,only=None):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Use a fresh output directory')
    selected=set(only or ('config','opaque','demo','map','readback'))
    if prepare_freeze and only:raise ValueError('Initial freeze must build the matched set')
    lock_path=ROOT/'F_FREEZE.json'
    if prepare_freeze and lock_path.exists():
        raise ValueError('F is already frozen; do not rebuild it under the same identity')
    if not prepare_freeze and not lock_path.exists():
        raise ValueError('First identity build requires --prepare-freeze')
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    if not assembler or not linker:raise RuntimeError('WDC tools must be on PATH')
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src',out/'s')
    core=out/'s/core';payload=out/'payload';payload.mkdir()
    symbols={};compiled=[];artifacts={}
    identity=json.loads((ROOT/'identity.json').read_text())
    descriptor,banner=identity_data(identity)
    db(core/'boot-identity.inc',descriptor);db(core/'boot-banner.inc',banner)

    def link(name,start,end):
        logs=[]
        for command in ([assembler,'-G','-L','-S','-W','-I',str(core),name+'.asm'],
                        [linker,'-g','-s','-t',f'-c{start:04X}','-hm19','-j',
                         '-o',name+'.s19',name+'.obj']):
            process=subprocess.run(command,cwd=core,capture_output=True,text=True)
            logs.append(dict(command=command,returncode=process.returncode,
                             stdout=process.stdout,stderr=process.stderr))
            save(core/(name+'.log.json'),logs)
            if process.returncode:raise RuntimeError('WDC failed: '+str(core/(name+'.log.json')))
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
                    (core/(name+'.map')).read_text(),re.M)}
        memory=cells(core/(name+'.s19'))
        assert set(memory)==set(range(start,sy[end])),name
        body=bytes(memory[a] for a in range(start,sy[end]))
        symbols[name]=sy;compiled.append(dict(module=name,bytes=len(body),sha256=sha(body)))
        print(name,len(body),'bytes',flush=True)
        return body,sy

    def emit(name,body,address,entry=None,reused=False):
        body=bytes(body);entry=address if entry is None else entry
        (payload/name).write_bytes(body)
        (payload/name.replace('.bin','.s19')).write_bytes(s19(body,address,entry))
        artifacts[name]=dict(bytes=len(body),sha256=sha(body),address=f'{address:04X}',
                              entry=f'{entry:04X}',reused_without_rebuild=reused)

    if prepare_freeze:
        old=(ROOT/'reference/minimal-r1/firmware/payload'/F_NAME).read_bytes()
        old_symbols=equs(ROOT/'src/core/boot-symbols.inc')
        body,bs=link('str8n-v2-boot',0xf000,'BOOT_END')
        assert bs['BOOT_END']<=0xffe0
        assert all(bs[n]==v for n,v in old_symbols.items() if n!='BOOT_END'), 'PR05 address moved'
        end=old_symbols['BOOT_END']
        assert bs['BOOT_ID_DESCRIPTOR']==end
        allowed=set(range(0x3c,0x40))
        hook=old_symbols['BOOT_DRAIN_DONE']-0xf000+8
        assert old[hook]==body[hook]==0x4c
        allowed.update(range(hook+1,hook+3))
        assert all(body[n]==old[n] for n in range(end-0xf000) if n not in allowed), 'Unexpected existing F mutation'
        image=bytearray(b'\xff'*4096);image[:len(body)]=body;image[0xfe4:]=old[0xfe4:]
        assert image[0x3c:0x3e]==b'FI' and int.from_bytes(image[0x3e:0x40],'little')==end
        assert image[end-0xf000:end-0xf000+64]==descriptor
        f=bytes(image)
        # Fixed private facade remains PR05; only new appended exports are added.
        (core/'boot-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in bs.items()
            if ((n.startswith('BOOT_') and v>=0xf000) or n in ('J_CRC_INIT','J_CRC_BYTE'))
            and n!='BOOT_API_ERASE'),encoding='ascii')
    else:
        lock=json.loads(lock_path.read_text())
        assert lock['identity']==identity,'F identity changed after freeze'
        for name,digest in lock['sources'].items():
            assert sha((ROOT/name).read_bytes())==digest,'Frozen F source changed: '+name
        f=(ROOT/'firmware/payload'/F_NAME).read_bytes()
        assert sha(f)==lock['sha256'],'Frozen F bytes changed'
        bs=equs(ROOT/'src/core/boot-symbols.inc')
    emit(F_NAME,f,0xf000,0xf004,reused=not prepare_freeze)
    assert len(f)==4096
    (core/'maint-ro-params.inc').write_text(f'MA_F_CRC_LO EQU ${crc(f)&255:02X}\nMA_F_CRC_HI EQU ${crc(f)>>8:02X}\n')

    if not prepare_freeze:
        current=json.loads((ROOT/'firmware/minimal-manifest.json').read_text())
        keys={'config':'CONFIG','opaque':'OPAQUE','demo':'DEMO','map':'MAP','readback':'READBACK'}
        for key,tag in keys.items():
            if key in selected:continue
            name=f'STR8N-F-{tag}-RAM.bin'
            record=current['artifacts'][name]
            data=(ROOT/'firmware/payload'/name).read_bytes()
            assert sha(data)==record['sha256']
            emit(name,data,0x200,reused=True)

    for module,end,name in (('ram-config','CONFIG_END','STR8N-F-CONFIG-RAM.bin'),
                            ('ram-installer','INSTALLER_END','STR8N-F-OPAQUE-RAM.bin'),
                            ('ram-demo','DEMO_END','STR8N-F-DEMO-RAM.bin')):
        if {'ram-config':'config','ram-installer':'opaque','ram-demo':'demo'}[module] not in selected:continue
        raw,sy=link(module,0x200,end);assert 0x200+len(raw)<=0x6500
        emit(name,raw,0x200)
    if 'map' in selected:
        raw,sy=link('ram-maint-ro',0x200,'MA_END')
        data=bytearray(raw);offset=sy['MA_IMAGE_CRC']-0x200
        data[offset:offset+2]=crc(data[:offset]).to_bytes(2,'big')
        assert crc(data[:sy['MA_IMM_END']-0x200])==0 and sy['MA_END']<=0x5000
        emit('STR8N-F-MAP-RAM.bin',data,0x200)

    if 'readback' in selected:
        prefix=('        MODULE BASE1_READBACK\n        INCLUDE "str8n-v2-eq.inc"\n'
                '        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n'
                '        INCLUDE "boot-symbols.inc"\n        CODE\n')
        (core/'readback-service.asm').write_text(long_branches(prefix+
            (core/'mon-absent-service.inc').read_text()+'\n        ENDMOD\n        END\n'))
        raw,sy=link('readback-service',0x6800,'MS_END');assert sy['MS_END']<0x7800
        loader='MS_BOOTSTRAP:\n        SEI\n        CLD\n'
        for n in range(len(raw)):loader+=f'        LDA MS_BLOB+{n}\n        STA ${0x6800+n:04X}\n'
        loader+='        JMP $6800\nMS_BLOB:\n'
        for n in range(0,len(raw),16):loader+=' DB '+','.join(f'${v:02X}' for v in raw[n:n+16])+'\n'
        (core/'readback-loader.asm').write_text(prefix+loader+'MS_LOAD_END:\n        ENDMOD\n        END\n')
        raw,sy=link('readback-loader',0x200,'MS_LOAD_END');assert sy['MS_LOAD_END']<=0x6500
        emit('STR8N-F-READBACK-RAM.bin',raw,0x200)
    save(out/'symbols.json',symbols)
    save(out/'base1-manifest.json',dict(passed=True,profile='BASE1',identity=identity,
         candidate=True,execution_qualified=False,hardware_access=False,CPU_simulations=0,
         F_rebuilt=prepare_freeze,F_sha256=sha(f),F_crc=f'{crc(f):04X}',
         F_bytes=4096,F_end=f'{bs["BOOT_END"]:04X}',usable_tail_bytes=0xffe0-bs['BOOT_END'],
         compiled=compiled,artifacts=artifacts,
         source={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted((ROOT/'src').rglob('*')) if p.is_file()},
         producer_sha256=sha(Path(__file__).read_bytes())))
    print('PASS BASE1 build; no simulation, device access or reproduction build',flush=True)
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--prepare-freeze',action='store_true')
    parser.add_argument('--only',nargs='+',choices=('config','opaque','demo','map','readback'))
    args=parser.parse_args();build(args.out,args.prepare_freeze,args.only)
