"""Build beta25 for a registered source ABI, preserving its fallback token."""
import argparse,binascii,hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
import build_v2_recovery as fw
from beta4_migration import crc,s19
from build_v2_beta25 import references

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'BUILD/v2-beta25'
sha=lambda b:hashlib.sha256(b).hexdigest()

def build(source,out):
    source=Path(source).resolve();out=Path(out).resolve();assert source!=out and out!=BASE
    assert not any(out.glob('hardware-qualification-*.json')),'Qualified package is frozen; choose a new output directory'
    prior=json.loads((source/'build.json').read_text());meta=json.loads((BASE/'build.json').read_text())
    shutil.copytree(BASE,out,dirs_exist_ok=True)
    for p in out.glob('*test-results.json'):p.unlink()
    for p in out.glob('*qualification*.json'):p.unlink()
    inputs=out/'profile-source';shutil.copytree(BASE/'asm',inputs,dirs_exist_ok=True)
    text=(BASE/'asm/str8n-v2-boot.asm').read_text();slot=prior['boot']['BOOT_SLOT_CHECK']
    if slot==0xF30D:
        begin=text.index('BOOT_SELECT_SKIP:');end=text.index('; PTR is a sector-aligned',begin)
        text=text[:begin]+'BOOT_SELECT_SKIP:       JMP BOOT_SELECT_SKIP_OUT\n\n'+text[end:]
        old='                        JMP BOOT_SELECT_SKIP\nBOOT_SELECT_NEW:'
        assert text.count(old)==1;text=text.replace(old,'                        BRA BOOT_SELECT_SKIP\nBOOT_SELECT_NEW:',1)
        # The old selector used 16 bytes. Its equivalent TSB form uses 11;
        # putting it after the validator plus 3 padding bytes restores every
        # later private entry, including SR_ROUTE and all J CRC routines.
        helper='''BOOT_SELECT_SKIP_OUT:   LDA #$10
                        TSB BOOT_SLOT
                        BNE BOOT_SELECT_DONE_OUT
                        JMP BOOT_SELECT_NEXT
BOOT_SELECT_DONE_OUT:   RTS
                        DB $FF,$FF,$FF
'''
        text=text.replace('BOOT_SR_ROUTE:',helper+'BOOT_SR_ROUTE:',1)
    elif slot==0xF318:
        begin=text.index('BOOT_SELECT_SKIP:');end=text.index('; PTR is a sector-aligned',begin)
        # Save exactly three bytes before the beta24 generation-34 validator;
        # restore the padding after it so SR_ROUTE and all J entries stay put.
        helper='''BOOT_SELECT_SKIP:       LDA #$10
                        TSB BOOT_SLOT
                        BNE BOOT_SELECT_DONE
                        JMP BOOT_SELECT_NEXT
BOOT_SELECT_DONE:       RTS
                        DB $FF,$FF

'''
        text=text[:begin]+helper+text[end:]
        text=text.replace('BOOT_SR_ROUTE:','                        DB $FF,$FF,$FF\nBOOT_SR_ROUTE:',1)
    else:assert slot==0xF31B,'Unregistered direct-call ABI'
    (inputs/'str8n-v2-boot.asm').write_text(text)
    compiler.OUT=out;compiler.SOURCE=inputs
    cells,boot=compiler.assemble('str8n-v2-boot',0xF000,shutil.which('wdc02as'),shutil.which('wdcln'),source=inputs)
    body=compiler.dense_image(cells,0xF000,boot['BOOT_END']);assert len(body)<=0xFE0
    assert boot['BOOT_SLOT_CHECK']==slot
    refs=references(source/'asm','monitor-a0.asm')
    for name in refs:
        if name in prior['boot']:assert boot[name]==prior['boot'][name],('source ABI moved',name)
    for name,value in prior['boot'].items():
        if name.startswith('J_') and value>=0xF000:assert boot[name]==value,name
    assert meta['worker']==prior['worker'] and meta['vectors']==prior['vectors']
    f=bytearray((BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes());f[:0xFE0]=b'\xff'*0xFE0;f[:len(body)]=body
    token=prior['boot_compatibility'];i=boot['BOOT_COMPAT_DATA']-0xF000
    f[i:i+4]=bytes(4);identity=binascii.crc32(f)&0xFFFFFFFF;f[i:i+4]=token.to_bytes(4,'little')
    (out/'str8n-v2-recovery-f000-ffff.bin').write_bytes(f)
    (inputs/'boot-symbols.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in boot.items() if k.startswith('BOOT_') and v>=0xF000 and k!='BOOT_API_ERASE'))
    # assemble() stages only the .asm file; includes are resolved in OUT/asm.
    shutil.copyfile(inputs/'boot-symbols.inc',out/'asm/boot-symbols.inc')
    slots={};monitors={};fw.OUT=out
    for page in (0xA0,0xB0):
        name=f'monitor-{page:02x}';cells,sym=compiler.assemble(name,(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source=inputs)
        assert sym['BOOT_SLOT_CHECK']==boot['BOOT_SLOT_CHECK']
        code=compiler.dense_image(cells,(page<<8)+128,sym['V2_END']);assert len(code)<=3968
        image=bytearray(fw.slot_image(code,sym,page,37,token));image[70:72]=sym['V2_M_EDIT'].to_bytes(2,'little')
        image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little');slots[page]=image;monitors[f'{page:02x}']=sym
        (out/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image)
    blob=bytearray((BASE/'str8n-v2-recovery-a000-dfff.bin').read_bytes());blob[:4096]=slots[0xA0];blob[4096:8192]=slots[0xB0]
    (out/'str8n-v2-recovery-a000-dfff.bin').write_bytes(blob)
    # Rebind shared MAINT's guarded ABI token; no program logic changes.
    folder=out/'maint';path=folder/'bank-maint.asm';text=path.read_text()
    for n,v in enumerate(token.to_bytes(4,'little')):
        addr=meta['boot']['BOOT_COMPAT_DATA']+n;old=meta['boot_compatibility'].to_bytes(4,'little')[n]
        oldtext=f'LDA ${addr:04X}\n                        CMP #${old:02X}'
        assert text.count(oldtext)==1;text=text.replace(oldtext,f'LDA ${addr:04X}\n                        CMP #${v:02X}',1)
    path.write_text(text);compiler.OUT=folder;compiler.SOURCE=folder/'asm'
    cells,maint=compiler.assemble('bank-maint',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    program=compiler.dense_image(cells,0x2000,maint['BM_END']);before=(BASE/'maint/board-name.bin').read_bytes()
    assert len(program)==len(before) and sum(a!=b for a,b in zip(program,before))<=4
    (folder/'board-name.bin').write_bytes(program);(folder/'str8n-bank-maint-2.0-2000.s19').write_bytes(s19(dict(enumerate(program,0x2000)),0x2000))
    name=meta['maintenance_storage_file'];record=bytearray((BASE/name).read_bytes());record[24:24+len(program)]=program;(out/name).write_bytes(record)
    manifest=json.loads((folder/'manifest.json').read_text());manifest.update(symbols=maint,program_sha256=sha(program),storage_sha256=sha(record))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    utility=bytearray((BASE/'bootstrap/bootstrap-journal.bin').read_bytes());n=meta['bootstrap_symbols']['EXPECTED_CORE']-0x2000
    utility[n:n+4]=token.to_bytes(4,'little');(out/'bootstrap/bootstrap-journal.bin').write_bytes(utility)
    (out/'bootstrap/bootstrap-journal.s19').write_bytes(s19(dict(enumerate(utility,0x2000)),0x2000))
    bp=out/'bootstrap/source/bootstrap-symbols.inc';bt=bp.read_text()
    bt=bt[:bt.index('EXPECTED_CORE:')]+'EXPECTED_CORE: DB '+','.join(f'${v:02X}' for v in token.to_bytes(4,'little'))+'\n';bp.write_text(bt)
    # RAM installer must commit both an SR header (3F) and a monitor (00).
    # Pointer low bytes are deliberately restricted by the host plan to 03/1F.
    mig=out/'migrator';path=mig/'rtc-migrator.asm';text=path.read_text()
    old='                        LDA #$3F\n                        STA V2_FLASH_DATA\n                        JMP V2W_BYTE'
    new='''                        LDA #$3F
                        LDY V2_FLASH_PTR
                        CPY #$1F
                        BNE MIG_COMMIT_VALUE_READY
                        LDA #$00
MIG_COMMIT_VALUE_READY:  STA V2_FLASH_DATA
                        JMP V2W_BYTE'''
    assert text.count(old)==1;path.write_text(text.replace(old,new))
    compiler.OUT=mig;compiler.SOURCE=mig/'asm'
    cells,ms=compiler.assemble('rtc-migrator',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    data=s19(cells,0x2000);(mig/'rtc-migrator-2000.s19').write_bytes(data)
    mm=json.loads((mig/'manifest.json').read_text());mm.update(symbols=ms,sha256=sha(data),mixed_commit_values=True)
    for key,symbol in (('count','MIG_PLAN_COUNT'),('commit_after','MIG_COMMIT_AFTER'),('commits','MIG_COMMITS'),('banks','MIG_BANKS'),('table','MIG_TABLE'),('commit_addresses','MIG_COMMIT_ADDRS')):mm[key]=ms[symbol]
    (mig/'manifest.json').write_text(json.dumps(mm,indent=2)+'\n')
    meta.update(boot=boot,boot_bytes=len(body),boot_compatibility=token,boot_identity_crc32=identity,monitors=monitors,
        source_profile_build=str(source.relative_to(ROOT)),fallback_version=prior['version'],fallback_generation=prior['generation'],
        fallback_build_sha256=sha((source/'build.json').read_bytes()),bootstrap_utility_sha256=sha(utility),fallback_abi_references=sorted(refs),
        migration_abi_profile='slot-check-'+f'{slot:04x}',hardware_tested=False)
    for name in meta['artifacts']:meta['artifacts'][name]=sha((out/name).read_bytes())
    (out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    for suffix,origin in (('f000-ffff',0xF000),('e000-efff',0xE000),('a000-dfff',0xA000),('slot-a0',0xA000),('slot-b0',0xB000)):
        name='str8n-v2-recovery-'+suffix;data=(out/(name+'.bin')).read_bytes();(out/(name+'.s19')).write_bytes(s19(dict(enumerate(data,origin)),0xF004))
    assert (out/'str8n-v2-recovery-e000-efff.bin').read_bytes()==(BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    print('BUILT beta25 profile for',prior['version'],'generation',prior['generation'],'F entry',hex(slot),'bytes',len(body),flush=True)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();build(a.source,a.out)
