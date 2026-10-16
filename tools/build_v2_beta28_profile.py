"""Rebind beta28 to the registered beta25/b23 ABI without rewriting fixed F."""
import binascii,json,re,shutil
from pathlib import Path
import build_v2_config as c
import build_v2_recovery as fw
from build_v2_spi_resident import assemble,sha
from beta4_migration import crc,s19
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta28';SOURCE=ROOT/'BUILD/v2-beta25-b23';OUT=ROOT/'BUILD/v2-beta28-b23'
read=lambda p:json.loads(p.read_text())

def main():
    assert not list(OUT.glob('hardware-qualification-*.json'))
    meta=read(BASE/'build.json');old=read(SOURCE/'build.json')
    qualification=read(BASE/'beta28-qualification.json')
    assert qualification['passed'] and qualification['build_sha256']==sha((BASE/'build.json').read_bytes())
    for n,h in meta['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
    assert meta['worker']==old['worker'] and meta['vectors']==old['vectors']
    shutil.copytree(BASE,OUT,dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):p.unlink()
    for p in OUT.glob('*qualification*.json'):p.unlink()
    # Public and journal entry points agree. Only the slot validator and its
    # internal labels moved; every other boot reference must agree exactly.
    for n,v in meta['boot'].items():
        if n in old['boot'] and v>=0xF000 and v!=old['boot'][n]:
            assert 0xF2F8<=v<=0xF40E,(n,v,old['boot'][n])
    token=old['boot_compatibility']
    shutil.copyfile(SOURCE/'str8n-v2-recovery-f000-ffff.bin',OUT/'str8n-v2-recovery-f000-ffff.bin')
    # 2512's resident service code is retained; differences in the newer
    # package are display text and its internal string addresses.
    shutil.copyfile(SOURCE/'str8n-rtc-component-8000-8fff.bin',OUT/'str8n-rtc-component-8000-8fff.bin')
    (OUT/'asm/boot-symbols.inc').write_text((SOURCE/'asm/boot-symbols.inc').read_text())
    stage=OUT/'xip/source'
    p=stage/'system.inc';text=p.read_text()
    for n,v in old['boot'].items():
        if n.startswith('BOOT_') and v>=0xF000:text=re.sub(r'^'+n+r' EQU \$[0-9A-F]+$',f'{n} EQU ${v:04X}',text,flags=re.M)
    p.write_text(text)
    p=stage/'utilities.asm';text=p.read_text()
    for i,(before,after) in enumerate(zip(meta['boot_compatibility'].to_bytes(4,'little'),token.to_bytes(4,'little'))):
        a=f'JSR X28_R{9+i}\n                        CMP #${before:02X}'
        assert text.count(a)==1;text=text.replace(a,f'JSR X28_R{9+i}\n                        CMP #${after:02X}')
    p.write_text(text)
    body,sym,_=assemble(stage,'utilities',0x8000,'X28_END',0x8000)
    original=(BASE/'xip/utilities.bin').read_bytes();x=read(BASE/'xip/build.json')
    assert len(body)==x['flash_linked_bytes'] and sym=={**x['symbols'],'BOOT_SLOT_CHECK':old['boot']['BOOT_SLOT_CHECK'],**{n:v for n,v in old['boot'].items() if n in x['symbols'] and n.startswith('BOOT_') and v>=0xF000}},'Unexpected relink layout'
    asset=body+b'\xff'*(0x57FE-len(body));asset+=crc(asset).to_bytes(2,'big')
    differences=[i for i,(a,b) in enumerate(zip(asset[:-2],original[:-2])) if a!=b]
    assert len(differences)==5,differences
    (OUT/'xip/utilities.bin').write_bytes(asset);x.update(symbols=sym,sha256=sha(asset))
    (OUT/'xip/build.json').write_text(json.dumps(x,indent=2)+'\n')
    c.OUT,c.SOURCE=OUT,OUT/'asm';fw.OUT=OUT;monitors={}
    for page in (0xA0,0xB0):
        cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=BASE/'asm'/f'monitor-{page:02x}.asm')
        code=c.dense_image(cells,(page<<8)+128,sy['V2_END'])
        prior=(BASE/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()[128:128+len(code)]
        assert sum(a!=b for a,b in zip(code,prior))==1
        image=bytearray(fw.slot_image(code,sy,page,40,token));image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
        from beta4_migration import slot_valid
        assert slot_valid(image,page)
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image);monitors[f'{page:02x}']=sy
    # VERSION contains direct calls to the same validator. Preserve all linked
    # offsets and the provider vectors when resealing its whole-image CRC.
    stage=OUT/'version/source';p=stage/'version-links.inc';text=p.read_text().replace('BOOT_SLOT_CHECK EQU $F31B','BOOT_SLOT_CHECK EQU $F30D');p.write_text(text)
    # Use the original source verbatim; the generic utility linker additionally
    # shrinks branches, which would change VERSION's qualified layout.
    shutil.copytree(BASE/'version/source',stage,dirs_exist_ok=True)
    p=stage/'version-links.inc';p.write_text(p.read_text().replace('BOOT_SLOT_CHECK EQU $F31B','BOOT_SLOT_CHECK EQU $F30D'))
    c.OUT,c.SOURCE=OUT/'version',stage
    cells,vs=c.assemble('version',0x6E00,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    code=c.dense_image(cells,0x6E00,vs['APP_END'])
    v=bytearray((BASE/'version/asset.bin').read_bytes());assert len(code)==meta['version_code_bytes']
    assert sum(a!=b for a,b in zip(code,v))==1
    v[:len(code)]=code;seed=crc(v[:-10])
    for word in range(65536):
        patch=word.to_bytes(2,'big')
        if binascii.crc_hqx(patch+v[-8:],seed)==0:v[-10:-8]=patch;break
    assert crc(v)==0
    (OUT/'version/asset.bin').write_bytes(v)
    # B2 is wholly reserved in the XIP layout. The bytewise legacy SR scan
    # can otherwise interpret instruction/string bytes as a saved program.
    # Replace the 27-byte limit selector with a same-size bank exclusion;
    # all subsequent private/public entry addresses stay fixed.
    p=OUT/'asm/str8n-v2-sr.asm';text=p.read_text();a=text.index('SR_TABLE_NEXT:');b=text.index('str8n_v2_sr_LONG_601:',a)
    text=text[:a]+'''SR_TABLE_NEXT:          LDA SR_BANK
                        CMP #2
                        BEQ X28_SR_SKIP_BANK
                        CMP #3
                        LDA SR_RECORD+1
                        BCC X28_SR_OTHER_BANK
                        CMP #$A0
                        BRA X28_SR_LIMIT
X28_SR_OTHER_BANK:      CMP #$E0
X28_SR_LIMIT:           BCC str8n_v2_sr_LONG_601
X28_SR_SKIP_BANK:       JMP SR_TABLE_DONE
                        NOP
                        NOP
'''+text[b:];p.write_text(text)
    stage=OUT/'profile-source';stage.mkdir(exist_ok=True);p=stage/'str8n-v2-sr.asm';p.write_text(text)
    c.OUT,c.SOURCE=OUT,stage
    cells,sr=c.assemble('str8n-v2-sr',0xE800,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=p)
    code=c.dense_image(cells,0xE800,sr['SR_END']);assert len(code)==meta['sr_bytes']
    for n in ['SR_CLI_SAVE','SR_CLI_RESTORE','SR_CLI_TABLE','SR_PARSE_BANK','SR_CLI_BAD']:
        assert sr[n]==int(re.search(r'^'+n+r' EQU \$([0-9A-F]+)',(OUT/'storage-status/source/status-links.inc').read_text(),re.M)[1],16)
    e=bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes());e[0x800:0x800+len(code)]=code;e[-2:]=crc(e[:-2]).to_bytes(2,'big');assert crc(e)==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    blob=bytearray((BASE/'str8n-v2-recovery-a000-dfff.bin').read_bytes())
    for page,off in ((0xA0,0),(0xB0,4096)):blob[off:off+4096]=(OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
    (OUT/'str8n-v2-recovery-a000-dfff.bin').write_bytes(blob)
    for suffix,origin in (('f000-ffff',0xF000),('a000-dfff',0xA000),('slot-a0',0xA000),('slot-b0',0xB000)):
        name='str8n-v2-recovery-'+suffix;(OUT/(name+'.s19')).write_bytes(s19(dict(enumerate((OUT/(name+'.bin')).read_bytes(),origin)),0xF004))
    meta.update(boot=old['boot'],boot_bytes=old['boot_bytes'],boot_compatibility=token,boot_identity_crc32=old['boot_identity_crc32'],monitors=monitors,version_asset_sha256=sha(v),version_symbols=vs,source_profile_build=str(SOURCE.relative_to(ROOT)),profile_parent_build_sha256=sha((BASE/'build.json').read_bytes()),fallback_version='2.0b25',fallback_generation=37)
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    proof=dict(passed=True,base_build_sha256=sha((BASE/'build.json').read_bytes()),build_sha256=sha((OUT/'build.json').read_bytes()),utility_body_changed_bytes=differences,fixed_f_unchanged=True,worker_vectors_unchanged=True,reserved_b2_excluded_from_saved_program_scan=True,sr_entry_addresses_unchanged=True,artifacts=meta['artifacts'])
    (OUT/'profile-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('PASS beta28 old-ABI profile; utility layout unchanged; fixed F retained')

if __name__=='__main__':main()
