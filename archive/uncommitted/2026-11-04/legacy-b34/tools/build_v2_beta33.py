"""Offline beta33 freeze candidate: beta32 plus standalone ASM 0.4.

No serial access, installer, flash writes or v2.1 inputs. Reference app placement
is B1:E000-F863 with application vectors at the end of B1:F. Occupied sectors require
a separately qualified preserving installation plan.
"""
import hashlib
import json
from pathlib import Path
import shutil

import build_asm
import build_v2_config as c
import build_v2_recovery as fw
from beta4_migration import crc, s19, journal, config_sum, metadata
from build_v2_spi_resident import assemble

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'BUILD/v2-beta32-candidate'
OUT = ROOT / 'BUILD/v2-beta33-candidate'
read = lambda p: json.loads(p.read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
GENERATION = 45
APP_ADDRESS = 0xE000


def descriptor(image, bank=1):
    row = bytearray(32)
    row[:3] = b'ASM'
    row[12:14] = bytes((bank, 1))
    for offset, value in ((14, APP_ADDRESS), (16, len(image)), (18, APP_ADDRESS+16),
                          (20, 0x200), (22, 0x64FF)):
        row[offset:offset+2] = value.to_bytes(2, 'little')
    row[24:26] = bytes((0, 0x3F))
    row[26:28] = crc(image).to_bytes(2, 'little')
    row[30] = 0x3F
    row[28:30] = crc(row[:28]+row[30:]).to_bytes(2, 'little')
    assert image[:4] == b'AP\x01\x01' and image[4:14] == row[16:26]
    assert crc(image[:14]) == int.from_bytes(image[14:16], 'little')
    return bytes(row)


def main():
    parent = read(BASE/'build.json')
    proof = read(BASE/'beta32-qualification.json')
    assert parent['version'] == '2.0b32' and proof['passed']
    assert proof['build_sha256'] == sha((BASE/'build.json').read_bytes())
    for name, digest in parent['artifacts'].items():
        assert sha((BASE/name).read_bytes()) == digest, name
    assert not OUT.exists(), 'Use a fresh output directory; never overwrite qualification'
    shutil.copytree(BASE, OUT)
    for pattern in ('*test-results.json', '*qualification*.json', 'usage.json', 'profile-proof.json'):
        for path in OUT.glob(pattern): path.unlink()
    # 'A' is APPS in the monitor BATCH allowlist, not an arbitrary named app.
    # ASM has its own interactive reader and cannot consume queued segments.
    stage = OUT/'xip/source'; p = stage/'utilities.asm'; text = p.read_text()
    marker = "B29_MON_NOT_HELP:\n        JSR B30_ALIAS\n"
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'''        LDA $7C00
        CMP #'A'
        BNE B33_NOT_APP
        JSR B33_BATCH_APPS
        BCS B33_NOT_APP
        JMP B29_SEGMENT_BAD
B33_NOT_APP:
''')
    text = text.replace('X28_END:', '''B33_BATCH_APPS:
        LDX #0
B33_APPS_MATCH:
        LDA $7C00,X
        CMP B33_APPS_WORD,X
        BNE B33_APPS_BAD
        INX
        CPX #4
        BNE B33_APPS_MATCH
B33_APPS_TAIL:
        LDA $7C00,X
        BEQ B33_APPS_OK
        CMP #' '
        BNE B33_APPS_BAD
        INX
        BRA B33_APPS_TAIL
B33_APPS_OK: SEC
        RTS
B33_APPS_BAD: CLC
        RTS
B33_APPS_WORD DB "APPS"
X28_END:''')
    p.write_text(text)
    utility, us, _ = assemble(stage,'utilities',0x8000,'X28_END',0x8000)
    oldx = read(BASE/'xip/build.json')
    for name in ('MM_START','SM_ENTRY','WK_ENTRY','WK_API','ED_START','X28_APPS','B29_ENGINE'):
        assert us[name] == oldx['symbols'][name],name
    assert len(utility) <= 0x57FE
    asset = utility+b'\xff'*(0x57FE-len(utility)); asset += crc(asset).to_bytes(2,'big')
    (OUT/'xip/utilities.bin').write_bytes(asset)
    x = dict(oldx); x.update(version='2.0b33',generation=GENERATION,symbols=us,
        flash_linked_bytes=len(utility),flash_spare_bytes=0x57FE-len(utility),sha256=sha(asset))
    (OUT/'xip/build.json').write_text(json.dumps(x,indent=2)+'\n')
    appdir = OUT/'assembler'
    build_asm.OUT = appdir
    build_asm.ADDRESS = APP_ADDRESS
    build_asm.main()
    ar=read(appdir/'build.json');asy=ar['symbols']
    assert (asy['OUTPUT_START'],asy['OUTPUT_END'],asy['SOURCE_START'],asy['SOURCE_END'],asy['SYMBOL_START'],asy['SYMBOL_END'],asy['STATE_END']) == (0x200,0x3300,0x3300,0x4F00,0x4F00,0x6300,0x6500)
    app = (appdir/'asm-e000.bin').read_bytes()
    assert len(app) <= 8192
    # The existing named-app launcher already verifies descriptor, header,
    # workspace, exception vectors and whole image before bank transfer.
    extension = bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    assert extension[0x6F0:0x6F4] == b'AT\x01\x08'
    assert extension[0x6F4:0x7F4] == bytes(256), 'Parent must have an empty app table'
    extension[0x6F4:0x714] = descriptor(app)
    extension[0x7FE:0x800] = crc(extension[:0x7FE]).to_bytes(2, 'big')
    assert crc(extension[:0x800]) == 0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(extension)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(extension,0xE000)),0xF004))
    vectors = bytearray(b'\xff'*4096)
    vectors[:len(app)-4096] = app[4096:]
    vectors[-32:] = (BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()[-32:]
    vectors[-4:-2] = (0x7E67).to_bytes(2, 'little')
    (appdir/'vectors-f000.bin').write_bytes(vectors)
    source = read(OUT/'source/str8n-v2-text.json')
    for msg in source: msg['text'] = msg['text'].replace('2.0b32', '2.0b33')
    (OUT/'source/str8n-v2-text.json').write_text(json.dumps(source,indent=2)+'\n')
    pool = bytearray()
    first = next(i for i,m in enumerate(source) if m['name']=='V2_BAD_PREFIX')
    for i, msg in enumerate(source):
        raw = bytearray(msg['text'].replace('{version}','2.0b33').encode())
        if i < first: raw = raw[4:]
        raw[-1] |= 128
        pool.extend(raw)
    c.OUT, c.SOURCE, fw.OUT = OUT, OUT/'inputs', OUT
    c.include_bytes(OUT/'asm/text-image.inc', pool)
    p = OUT/'asm/text-image.inc'; p.write_text('V2_TEXT:\n'+p.read_text())
    monitors = {}
    for page in (0xA0, 0xB0):
        cells, sy = c.assemble(f'monitor-{page:02x}', (page<<8)+128,
            shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs'/f'monitor-{page:02x}.asm')
        body = c.dense_image(cells,(page<<8)+128,sy['V2_END'])
        assert len(body) <= 3968
        image = bytearray(fw.slot_image(body,sy,page,GENERATION,parent['boot_compatibility']))
        image[70:72] = sy['V2_M_EDIT'].to_bytes(2,'little')
        image[18:20] = crc(image[:18]+image[32:]).to_bytes(2,'little')
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image)
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004))
        monitors[f'{page:02x}'] = sy
    assert monitors == parent['monitors']
    banks = [bytearray((BASE/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
    banks[2][:0x5800] = asset
    # Offline reference placement only. No live user bank is treated as erased.
    banks[1][:] = b'\xff'*32768
    banks[1][0x6000:0x6000+len(app)] = app
    banks[1][0x7000:] = vectors
    banks[3][0x6000:0x7000] = extension
    banks[3][0x3000:0x4000] = (OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    j = journal(banks[3]); cfg = bytearray(j[8:24])
    cfg[7:13] = b'P\xB0'+GENERATION.to_bytes(4,'little'); cfg[14:] = config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
    banks[3][0x4000:0x5000] = metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    for i,b in enumerate(banks): (OUT/f'candidate/b{i}.bin').write_bytes(b)
    for name,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
        data = banks[3][off:off+size]
        (OUT/(name+'.bin')).write_bytes(data)
        (OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+off)),0xF004))
    meta = dict(parent)
    meta.update(version='2.0b33',generation=GENERATION,monitors=monitors,
        parent_build_sha256=sha((BASE/'build.json').read_bytes()),candidate_only=True,
        hardware_tested=False,boards_flashed=False,board_access=False,intended_freeze_candidate=True,
        native_bundle_unchanged=False,batch_apps_exact_match=True,
        assembler=dict(version='0.4',bytes=len(app),bank=1,address=APP_ADDRESS,entry=APP_ADDRESS+16,
            ram_first=0x200,ram_last=0x64FF,zp_first=0,zp_last=0x3F,encodings=212,
            source_checkpoint='5313633',host='65C02 / 65C816 emulation',descriptor_address=0xE6F4,
            persistent_ram_increase=0,source_bytes=7168,output_bytes=12544,symbols=256,
            user_code_start=0x200,user_code_end=0x32FF,default_origin=0x200,
            source_start=0x3300,symbol_start=0x4F00,state_start=0x6300),
        v21_included=False)
    meta['artifacts'] = {n:sha((OUT/n).read_bytes()) for n in parent['artifacts']}
    for n in ('assembler/asm-e000.bin','assembler/build.json','assembler/vectors-f000.bin'):
        meta['artifacts'][n] = sha((OUT/n).read_bytes())
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'candidate/manifest.json').write_text(json.dumps(dict(candidate_only=True,
        installation_permitted=False,board_access=False,boards_flashed=False,
        banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),
        note='Reference placement only; no live board writes or destructive bank replacement authorized.'),indent=2)+'\n')
    assert banks[2][0x5800:] == (BASE/'candidate/b2.bin').read_bytes()[0x5800:]
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes() == (BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    print(f'BUILT beta33: ASM 0.4 {len(app)} bytes; native bundle {len(utility)+2} bytes; fixed recovery unchanged; NO FLASH',flush=True)


if __name__ == '__main__': main()
