"""Beta25 with the proven beta24 generation-35 ABI family retained."""
import binascii,hashlib,json,re,shutil
from pathlib import Path
from beta4_migration import crc,s19
import build_v2_config as compiler

ROOT=Path(__file__).resolve().parents[1];OLD=ROOT/'BUILD/v2-fix005'
FALLBACK=ROOT/'BUILD/v2-startup-fifo';OUT=ROOT/'BUILD/v2-beta25'
sha=lambda b:hashlib.sha256(b).hexdigest()

def references(stage,name,seen=None):
    seen=set() if seen is None else seen
    if name in seen:return set()
    seen.add(name);result=set()
    for raw in (stage/name).read_text().splitlines():
        line=raw.split(';',1)[0]
        if ' EQU ' in line:continue
        inc=re.search(r'\bINCLUDE\s+"([^"]+)"',line)
        if inc:
            # Definitions do not represent calls made by the old monitor.
            if inc[1] not in ('boot-symbols.inc','vectors-symbols.inc'):
                result.update(references(stage,inc[1],seen))
        else:result.update(re.findall(r'\bBOOT_[A-Z0-9_]+\b',line))
    return result

def main():
    shutil.copytree(OLD,OUT,dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta=json.loads((OLD/'build.json').read_text());prior=json.loads((FALLBACK/'build.json').read_text())
    assert meta['worker']==prior['worker'] and meta['vectors']==prior['vectors']
    refs=references(FALLBACK/'asm','monitor-a0.asm')
    for name in refs:
        if name in prior['boot']:assert meta['boot'][name]==prior['boot'][name],('ABI moved',name)
    for name,value in prior['boot'].items():
        if name.startswith('J_') and value>=0xF000:assert meta['boot'][name]==value,name
    # The contract token identifies this proven ABI family. Exact build identity
    # remains separately pinned by SHA256 and the canonical F CRC32.
    f=bytearray((OLD/'str8n-v2-recovery-f000-ffff.bin').read_bytes())
    oldf=(FALLBACK/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    for label,size in (('BOOT_WORKER_IMAGE',meta['worker_bytes']),('BOOT_VECTOR_IMAGE',meta['vector_bytes'])):
        a=meta['boot'][label]-0xF000;b=prior['boot'][label]-0xF000
        assert f[a:a+size]==oldf[b:b+size],label
    token=prior['boot_compatibility'];offset=meta['boot']['BOOT_COMPAT_DATA']-0xF000
    f[offset:offset+4]=bytes(4);identity=binascii.crc32(f)&0xFFFFFFFF
    f[offset:offset+4]=token.to_bytes(4,'little')
    (OUT/'str8n-v2-recovery-f000-ffff.bin').write_bytes(f)
    # Rebuild same-size text pool and both templates; deployment selects one.
    messages=json.loads((OUT/'source/str8n-v2-text.json').read_text());pool=bytearray()
    prefix=next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    for i,m in enumerate(messages):
        raw=bytearray(m['text'].replace('{version}','2.0b25').encode())
        if i<prefix:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    compiler.include_bytes(OUT/'asm/text-image.inc',pool)
    p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    compiler.OUT=OUT;compiler.SOURCE=OUT/'asm'
    inputs=OUT/'beta25-inputs';inputs.mkdir(exist_ok=True)
    import build_v2_recovery as fw
    slots={};monitors={};fw.OUT=OUT
    for page in (0xA0,0xB0):
        name=f'monitor-{page:02x}';shutil.copyfile(OLD/'asm'/(name+'.asm'),inputs/(name+'.asm'))
        cells,sym=compiler.assemble(name,(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=inputs/(name+'.asm'))
        body=compiler.dense_image(cells,(page<<8)+128,sym['V2_END'])
        before=(OLD/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()[128:128+len(body)]
        assert len(body)==3967 and sum(a!=b for a,b in zip(body,before))==1
        slot=bytearray(fw.slot_image(body,sym,page,37,token))
        slot[70:72]=sym['V2_M_EDIT'].to_bytes(2,'little')
        slot[18:20]=crc(slot[:18]+slot[32:]).to_bytes(2,'little')
        slots[page]=slot;monitors[f'{page:02x}']=sym
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(slot)
    blob=bytearray((OLD/'str8n-v2-recovery-a000-dfff.bin').read_bytes())
    blob[:4096]=slots[0xA0];blob[4096:8192]=slots[0xB0];(OUT/'str8n-v2-recovery-a000-dfff.bin').write_bytes(blob)
    # Existing beta24 MAINT already targets this same ABI. Preserve it exactly.
    name=meta['maintenance_storage_file']
    assert sum(a!=b for a,b in zip((OLD/'maint/board-name.bin').read_bytes(),(FALLBACK/'maint/board-name.bin').read_bytes()))<=4
    shutil.copytree(FALLBACK/'maint',OUT/'maint',dirs_exist_ok=True)
    shutil.copyfile(FALLBACK/name,OUT/name)
    utility=bytearray((OLD/'bootstrap/bootstrap-journal.bin').read_bytes())
    guard=meta['bootstrap_symbols']['EXPECTED_CORE']-0x2000
    utility[guard:guard+4]=token.to_bytes(4,'little')
    (OUT/'bootstrap/bootstrap-journal.bin').write_bytes(utility)
    (OUT/'bootstrap/bootstrap-journal.s19').write_bytes(s19(dict(enumerate(utility,0x2000)),0x2000))
    text=(OUT/'bootstrap/source/bootstrap-symbols.inc').read_text()
    text=re.sub(r'EXPECTED_CORE: DB .*', 'EXPECTED_CORE: DB '+','.join(f'${b:02X}' for b in token.to_bytes(4,'little')),text)
    (OUT/'bootstrap/source/bootstrap-symbols.inc').write_text(text)
    for name,origin in (('f000-ffff',0xF000),('e000-efff',0xE000),('a000-dfff',0xA000),('slot-a0',0xA000),('slot-b0',0xB000)):
        stem='str8n-v2-recovery-'+name;data=(OUT/(stem+'.bin')).read_bytes()
        (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(data,origin)),0xF004))
    meta.update(version='2.0b25',generation=37,boot_compatibility=token,boot_identity_crc32=identity,
        compatibility_kind='proven ABI family; exact F image separately hashed',fallback_version='2.0b24',fallback_generation=35,
        fallback_build_sha256=sha((FALLBACK/'build.json').read_bytes()),fallback_abi_references=sorted(refs),
        mixed_slot_supported=True,monitors=monitors,bootstrap_utility_sha256=sha(utility),hardware_tested=False,
        board_access=False,boards_flashed=False)
    meta['artifacts']={name:sha((OUT/name).read_bytes()) for name in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('BETA25 generation 37; beta24 generation 35 ABI retained; E/TIME and existing MAINT preserved',flush=True)

if __name__=='__main__':main()
