"""Build MAINT 2.1 identifying sealed B2 firmware assets; no board access."""
import hashlib
import json
import shutil
from pathlib import Path
from beta4_migration import s19
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'BUILD/v2-version'
OUT = ROOT/'BUILD/v2-map-assets'
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):
        p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta = json.loads((BASE/'build.json').read_text())
    source = OUT/'maint/map-source'
    shutil.copytree(BASE/'maint/asm', source, dirs_exist_ok=True)
    text = (BASE/'maint/bank-maint.asm').read_text()
    text = text.replace('bank maintenance 2.0', 'bank maintenance 2.1').replace('BANK MAINT 2.0', 'BANK MAINT 2.1')
    # Preserve ordinary SR ownership, including B2:C's mixed use.
    marker = 'MAP_STORE_KIND:        STA MAP_KIND\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'''                        JSR MAP_FIRMWARE
                        BCC MF_NORMAL_KIND
                        RTS
MF_NORMAL_KIND:
''', 1)
    marker = 'MAP_DESCRIPTION:      LDA MAP_KIND\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'''                        CMP #'F'
                        BNE MF_NORMAL_DESCRIPTION
                        JMP MF_DESCRIPTION
MF_NORMAL_DESCRIPTION:
''', 1)
    marker = 'MAP_ACCESS:           LDX #<MAP_WRITABLE_TEXT\n'
    assert text.count(marker) == 1
    text = text.replace(marker, '''MAP_ACCESS:
                        LDA MAP_KIND
                        CMP #'F'
                        BNE MF_NORMAL_ACCESS
                        LDX #<MF_RESERVED_TEXT
                        LDY #>MF_RESERVED_TEXT
                        JMP MAP_ACCESS_PRINT
MF_NORMAL_ACCESS:      LDX #<MAP_WRITABLE_TEXT
''', 1)
    text = text.replace('DB "P application; V application-bank vectors"',
        'DB "F firmware assets; P application; V application-bank vectors"', 1)
    marker = '                       DB "* active.",$0D,$0A,0'
    assert text.count(marker) == 1
    text = text.replace(marker, '''                       DB "B2:C800-D1FF status; B2:E local/board + VERSION.",$0D,$0A
'''+marker, 1)
    extra = long_branches((ROOT/'tools/v2-spi/map-firmware.inc').read_text()).replace('BM_LONG_', 'MF_LONG_')
    text = text.replace('BM_END:', extra+'\nBM_END:', 1)
    (source/'bank-maint.asm').write_text(text)
    body, symbols, _ = assemble(source, 'bank-maint', 0x2000, 'BM_END', 0x2007)
    assert len(body)+24 <= 12288 and symbols['BM_END'] <= 0x5000
    folder = OUT/'maint'
    (folder/'bank-maint.asm').write_text((source/'bank-maint.asm').read_text())
    (folder/'board-name.bin').write_bytes(body)
    (folder/'str8n-bank-maint-2.1-2000.s19').write_bytes(s19(dict(enumerate(body, 0x2000)), 0x2000))
    record = b'SR\x01\x3f\x00\x20'+len(body).to_bytes(2, 'little')+b'MAINT'.ljust(16, b'\0')+body
    record += b'\xff'*(12288-len(record))
    name = 'str8n-maint-2.1-b1-8000-afff.bin'
    (OUT/name).write_bytes(record)
    manifest = dict(version='2.1', entry=0x2000, bytes=len(body), end=symbols['BM_END'],
        symbols=symbols, program_sha256=sha(body), storage_sha256=sha(record),
        storage_bytes=len(record), storage_file=name, hardware_tested=False)
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    meta.update(maintenance_version='2.1', maintenance_storage_file=name,
        map_firmware_assets=True, map_firmware_symbol='F',
        hardware_tested=False, board_access=False, boards_flashed=False)
    meta['artifacts'][name] = sha(record)
    for n, h in json.loads((BASE/'build.json').read_text())['artifacts'].items():
        assert sha((OUT/n).read_bytes()) == h, n
    (OUT/'build.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('UNFLASHED MAINT 2.1:', len(body), 'bytes; F = sealed firmware assets; three-sector MAINT allocation retained')


if __name__ == '__main__':
    main()
