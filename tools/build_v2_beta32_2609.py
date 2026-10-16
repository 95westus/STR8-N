"""Relink sealed beta32 for 2609's retained F31B recovery and inactive A slot.

No hardware access. The sealed 2512 build is never modified.
"""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil

import build_v2_config as c
import build_v2_recovery as fw
from build_v2_spi_resident import assemble, sha
from beta4_migration import crc, s19, slot_valid, journal, metadata, config_sum
from deploy_v2_beta32_2512 import audit_build

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta32-candidate'
SOURCE=ROOT/'BUILD/v2-beta27'
DEFAULT=ROOT/'BUILD/v2-beta32-2609-candidate'
read=lambda p:json.loads(p.read_text())


def main(out,replace=False):
    parent=audit_build();old=read(SOURCE/'build.json')
    assert not out.exists() or (replace and not list(out.glob('hardware-qualification-*.json'))),'Never overwrite a hardware-qualified package'
    assert parent['worker']==old['worker'] and parent['vectors']==old['vectors']
    assert old['boot']['BOOT_SLOT_CHECK']==0xF31B and parent['boot']['BOOT_SLOT_CHECK']==0xF30D
    shutil.copytree(BASE,out,dirs_exist_ok=replace)
    for pattern in ['*test-results.json','*qualification*.json','usage.json']:
        for p in out.glob(pattern):p.unlink()

    def bindings(path):
        text=path.read_text()
        for name,value in old['boot'].items():
            if name.startswith('BOOT_') and value>=0xF000:
                text=re.sub(r'^'+re.escape(name)+r' EQU \$[0-9A-F]+$',f'{name} EQU ${value:04X}',text,flags=re.M)
        path.write_text(text)

    # The original fixed F and resident device code are retained exactly.
    for name in ['str8n-v2-recovery-f000-ffff.bin','str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin']:
        shutil.copyfile(SOURCE/name,out/name)
    shutil.copyfile(SOURCE/'asm/boot-symbols.inc',out/'asm/boot-symbols.inc')
    bindings(out/'xip/source/system.inc')
    p=out/'xip/source/utilities.asm';text=p.read_text()
    for i,(before,after) in enumerate(zip(parent['boot_compatibility'].to_bytes(4,'little'),old['boot_compatibility'].to_bytes(4,'little'))):
        before_text=f'JSR X28_R{9+i}\n                        CMP #${before:02X}'
        assert text.count(before_text)==1
        text=text.replace(before_text,f'JSR X28_R{9+i}\n                        CMP #${after:02X}')
    hook='LDA $7D30\n        CMP #$B0'
    assert text.count(hook)==7
    text=text.replace(hook,'LDA $7D30\n        CMP #$A0')
    p.write_text(text)
    body,symbols,_=assemble(p.parent,'utilities',0x8000,'X28_END',0x8000)
    x=read(BASE/'xip/build.json');assert len(body)==x['flash_linked_bytes']
    for name,value in x['symbols'].items():
        if not name.startswith('BOOT_'):assert symbols[name]==value,(name,value,symbols[name])
    asset=body+b'\xff'*(0x57FE-len(body));asset+=crc(asset).to_bytes(2,'big')
    before=(BASE/'xip/utilities.bin').read_bytes()
    changes=[i for i,(a,b) in enumerate(zip(before[:-2],asset[:-2])) if a!=b]
    assert len(changes)==12,changes  # 4 ABI bytes, 7 slot guards, 1 validator operand.
    (out/'xip/utilities.bin').write_bytes(asset)
    x.update(symbols=symbols,sha256=sha(asset),batch_target_active_page=0xA0)
    (out/'xip/build.json').write_text(json.dumps(x,indent=2)+'\n')

    # Only the fixed-F validator operand changes in each monitor body.
    c.OUT,c.SOURCE=out,out/'asm';fw.OUT=out
    monitors={}
    for page in (0xA0,0xB0):
        cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=BASE/'inputs'/f'monitor-{page:02x}.asm')
        code=c.dense_image(cells,(page<<8)+128,sy['V2_END'])
        prior=(BASE/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()[128:128+len(code)]
        assert len(code)<=3968 and sum(a!=b for a,b in zip(code,prior))==1
        image=bytearray(fw.slot_image(code,sy,page,44,old['boot_compatibility']))
        image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little')
        image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
        assert slot_valid(image,page)
        (out/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image)
        (out/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004))
        monitors[f'{page:02x}']=sy
    assert monitors['a0']['V2_BANK_READ_LINE']==parent['monitors']['a0']['V2_BANK_READ_LINE']

    # VERSION calls the retained F validator too. Retain the B2 vector pocket.
    stage=out/'version/source';bindings(stage/'version-links.inc')
    c.OUT,c.SOURCE=out/'version',stage
    cells,vs=c.assemble('version',0x6E00,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    code=c.dense_image(cells,0x6E00,vs['APP_END'])
    v=bytearray((BASE/'version/asset.bin').read_bytes())
    assert len(code)==parent['version_code_bytes'] and sum(a!=b for a,b in zip(code,v))==1
    v[:len(code)]=code;seed=crc(v[:-10])
    for word in range(65536):
        patch=word.to_bytes(2,'big')
        if binascii.crc_hqx(patch+v[-8:],seed)==0:v[-10:-8]=patch;break
    assert crc(v)==0
    (out/'version/asset.bin').write_bytes(v)

    # Keep the optional CLOCK 1.9 RAM artifact consistent with A's batch ABI.
    # It is not installed over the owner's existing SRAM CLK 1.8 record.
    stage=out/'clock/source';p=stage/'clock.asm';text=p.read_text()
    assert text.count('LDA $7D30\n        CMP #$B0')==1
    p.write_text(text.replace('LDA $7D30\n        CMP #$B0','LDA $7D30\n        CMP #$A0'))
    cb,cs,_=assemble(stage,'clock',0x2000,'APP_END',0x2000)
    previous=(BASE/'clock/clock.bin').read_bytes()
    assert len(cb)==len(previous) and sum(a!=b for a,b in zip(cb,previous))==1
    clock_image=s19(dict(enumerate(cb,0x2000)),0x2000)
    (out/'clock/clock.bin').write_bytes(cb)
    for name in ['clock.s19','clock-1.9-2000.s19']:(out/'clock'/name).write_bytes(clock_image)
    record=b'SR\x01?\x00\x20'+len(cb).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+cb
    (out/'clock/storage.bin').write_bytes(record+b'\xff'*(12288-len(record)))
    cm=read(BASE/'clock/build.json');cm.update(symbols=cs,sha256=sha(cb),s19_sha256=sha(clock_image),
        source_sha256=sha(p.read_bytes()),storage_sha256=sha((out/'clock/storage.bin').read_bytes()),batch_target_active_page=0xA0)
    (out/'clock/build.json').write_text(json.dumps(cm,indent=2,sort_keys=True)+'\n')

    # Regenerate coherent offline reference banks/combined images. Deployment
    # still requires a fresh backup-bound plan; these are not direct installers.
    reference=ROOT/'output/qualification/beta27-2026-10-15/2609/upgrade'
    banks=[bytearray((reference/f'post-reset-b{i}.bin').read_bytes()) for i in range(4)]
    banks[2][:]=(BASE/'candidate/b2.bin').read_bytes()
    banks[2][:0x5800]=asset;banks[2][0x7800:]=v
    banks[3][0x2000:0x3000]=(out/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    banks[3][0x6000:0x7000]=(out/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    assert banks[3][0x7000:]==(out/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xA0'+(44).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
    banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    for i,b in enumerate(banks):(out/f'candidate/b{i}.bin').write_bytes(b)
    for suffix,offset,size in [('a000-dfff',0x2000,16384),('c000-dfff',0x4000,8192)]:
        name='str8n-v2-recovery-'+suffix;data=banks[3][offset:offset+size]
        (out/(name+'.bin')).write_bytes(data)
        (out/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+offset)),0xF004))
    for name,address in [('str8n-rtc-component-8000-8fff',0x8000),('str8n-journal-9000-9fff',0x9000),('str8n-v2-recovery-f000-ffff',0xF000)]:
        (out/(name+'.s19')).write_bytes(s19(dict(enumerate((out/(name+'.bin')).read_bytes(),address)),0xF004))

    meta=dict(parent)
    meta.update(boot=old['boot'],boot_bytes=old['boot_bytes'],boot_compatibility=old['boot_compatibility'],
                boot_identity_crc32=old['boot_identity_crc32'],monitors=monitors,version_asset_sha256=sha(v),version_symbols=vs,
                source_profile_build='BUILD/v2-beta27',profile_parent_build_sha256=sha((BASE/'build.json').read_bytes()),
                batch_target_active_page=0xA0,fallback_version='2.0b27',fallback_generation=39,
                native_bundle_unchanged=False,native_bundle_binding_changes_only=True,clock_sha256=sha(cb),clock_symbols=cs,
                candidate_only=True,hardware_tested=False,boards_flashed=False,board_access=False)
    meta['artifacts']={n:sha((out/n).read_bytes()) for n in meta['artifacts']}
    (out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    proof=dict(passed=True,build_sha256=sha((out/'build.json').read_bytes()),base_build_sha256=sha((BASE/'build.json').read_bytes()),
               retained_recovery_sha256=sha((out/'str8n-v2-recovery-f000-ffff.bin').read_bytes()),fixed_f_unchanged=True,
               worker_vectors_unchanged=True,utility_linked_layout_unchanged=True,utility_changed_body_offsets=changes,
               batch_target_active_page=0xA0,artifacts=meta['artifacts'],board_access=False)
    (out/'profile-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('PASS beta32 F31B/A profile: fixed recovery retained; 12 native-body bytes rebound; no layout growth',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT);parser.add_argument('--replace-unqualified',action='store_true')
    args=parser.parse_args();main(args.out.resolve(),args.replace_unqualified)
