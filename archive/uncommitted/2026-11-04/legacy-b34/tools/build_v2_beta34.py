"""Offline beta34 candidate: sealed beta33 plus ASM 0.5 save summary."""
import hashlib
import json
from pathlib import Path
import shutil
import build_asm
import build_v2_config as c
import build_v2_recovery as fw
from build_v2_beta33 import descriptor
from beta4_migration import crc,s19,journal,config_sum,metadata

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta33-candidate'
OUT=ROOT/'BUILD/v2-beta34-candidate'
GENERATION=46
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    parent=read(BASE/'build.json');proof=read(BASE/'beta33-qualification.json')
    assert parent['version']=='2.0b33' and proof['passed']
    assert proof['build_sha256']==sha((BASE/'build.json').read_bytes())
    for n,h in parent['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
    assert not OUT.exists(),'Use a fresh output directory; sealed results must be preserved'
    shutil.copytree(BASE,OUT)
    for pattern in ('*test-results.json','*qualification*.json','*hardware*.json','beta33-*.json','usage.json'):
        for p in OUT.glob(pattern):p.unlink()
    (OUT/'assembler/test-results.json').unlink(missing_ok=True)
    build_asm.OUT=OUT/'assembler';build_asm.ADDRESS=0xE000;build_asm.main()
    ar=read(OUT/'assembler/build.json');app=(OUT/'assembler/asm-e000.bin').read_bytes()
    assert ar['version']=='0.5' and ar['ram_first']==0x200 and ar['ram_last']==0x64FF
    assert ar['source_first']==0x3300 and ar['source_end']==0x4F00 and ar['output_end']==0x3300
    extension=bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    assert extension[0x6F4:0x6F7]==b'ASM'
    extension[0x6F4:0x714]=descriptor(app)
    extension[0x7FE:0x800]=crc(extension[:0x7FE]).to_bytes(2,'big')
    assert crc(extension[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(extension)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(extension,0xE000)),0xF004))
    vectors=bytearray(b'\xff'*4096);vectors[:len(app)-4096]=app[4096:]
    vectors[-32:]=(BASE/'assembler/vectors-f000.bin').read_bytes()[-32:]
    (OUT/'assembler/vectors-f000.bin').write_bytes(vectors)
    source=read(OUT/'source/str8n-v2-text.json')
    for m in source:m['text']=m['text'].replace('2.0b33','2.0b34')
    (OUT/'source/str8n-v2-text.json').write_text(json.dumps(source,indent=2)+'\n')
    first=next(i for i,m in enumerate(source) if m['name']=='V2_BAD_PREFIX');pool=bytearray()
    for i,m in enumerate(source):
        raw=bytearray(m['text'].replace('{version}','2.0b34').encode())
        if i<first:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    c.OUT,c.SOURCE,fw.OUT=OUT,OUT/'inputs',OUT
    c.include_bytes(OUT/'asm/text-image.inc',pool)
    p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    monitors={}
    for page in (0xA0,0xB0):
        cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs'/f'monitor-{page:02x}.asm')
        body=c.dense_image(cells,(page<<8)+128,sy['V2_END']);assert len(body)<=3968
        image=bytearray(fw.slot_image(body,sy,page,GENERATION,parent['boot_compatibility']))
        image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image)
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004))
        monitors[f'{page:02x}']=sy
    assert monitors==parent['monitors']
    banks=[bytearray((BASE/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
    banks[1][0x6000:]=b'\xff'*8192;banks[1][0x6000:0x6000+len(app)]=app;banks[1][0x7000:]=vectors
    banks[3][0x6000:0x7000]=extension
    banks[3][0x3000:0x4000]=(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xB0'+GENERATION.to_bytes(4,'little');cfg[14:]=config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
    banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    for i,b in enumerate(banks):(OUT/f'candidate/b{i}.bin').write_bytes(b)
    for name,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
        data=banks[3][off:off+size];(OUT/(name+'.bin')).write_bytes(data)
        (OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+off)),0xF004))
    meta=dict(parent);asm=dict(parent['assembler']);asm.update(version='0.5',bytes=len(app),save_summary=True)
    meta.update(version='2.0b34',generation=GENERATION,monitors=monitors,assembler=asm,
        parent_build_sha256=sha((BASE/'build.json').read_bytes()),candidate_only=True,
        hardware_tested=False,boards_flashed=False,board_access=False,native_bundle_unchanged=True,
        assembler_ram_range_and_save_hint=True,v21_included=False)
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in parent['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'candidate/manifest.json').write_text(json.dumps(dict(candidate_only=True,installation_permitted=False,
        board_access=False,boards_flashed=False,banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),
        note='Offline reference only; requires a separately qualified preserving installer.'),indent=2)+'\n')
    for n in ('xip/utilities.bin','str8n-v2-recovery-f000-ffff.bin'):
        assert (OUT/n).read_bytes()==(BASE/n).read_bytes(),n
    assert banks[0]==(BASE/'candidate/b0.bin').read_bytes() and banks[2]==(BASE/'candidate/b2.bin').read_bytes()
    print(f'BUILT beta34 / ASM 0.5: {len(app)} flash bytes; RAM unchanged; NO BOARD ACCESS',flush=True)


if __name__=='__main__':main()
