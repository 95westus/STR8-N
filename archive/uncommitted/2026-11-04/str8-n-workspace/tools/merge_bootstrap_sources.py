"""One-time import of the public source closure for the unified STR8N-F build.

This does not import board captures, journal records or installation plans.
The resulting standalone build never imports this parent-tree helper.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'bootstrap-opaque'
SESSION = ROOT / 'output/qualification/2609-b15-onboarding-20261027T212009Z'
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    origin_path = DEST / 'ORIGIN.json'
    origin = json.loads(origin_path.read_text())
    copied = set()

    def put(source, name=None, generic=False):
        source = Path(source)
        name = name or source.name
        target = DEST / 'src/core' / name
        raw = source.read_bytes()
        text = raw.decode('utf-8').replace('\r\n', '\n')
        if generic:
            text = text.replace('2609', 'STR8')
            if name == 'ram-maint-ro.asm':
                text = text.replace('WDC-BACKUP PROTECTED', 'OWNER IMAGE PRESERVE')
                text = text.replace('VX1-SLOT PROTECTED', 'OPTIONAL OWNER IMG')
        data = text.encode()
        if target.exists():
            assert target.read_bytes() == data, f'Conflicting include: {name}'
        else:
            target.write_bytes(data)
            origin['files']['src/core/' + name] = {
                'source': source.relative_to(ROOT).as_posix(),
                'sha256': sha(raw), 'extracted_sha256': sha(data)}
        copied.add(name)
        for inc in re.findall(r'^\s*INCLUDE\s+"([^"]+)"', text, re.M | re.I):
            if inc in copied or (DEST / 'src/core' / inc).exists():
                continue
            found = source.parent / inc
            assert found.is_file(), (source, inc)
            put(found)

    core = ROOT / 'BUILD/pr04-b15-cancel-r3/s/core'
    put(core / 'monitor-b0.asm', 'monitor-template.asm')
    vx = SESSION / 'step08-VERSION-build-r7/s/core'
    for name in ('version-caps-e000.asm', 'version-caps-client.asm',
                 'version-caps-identities.inc', 'version-caps-public.inc'):
        put(vx / name)
    # Keep the reviewed hook as source; one monitor template produces both
    # existing layouts. No duplicated complete monitor implementation.
    put(ROOT / 'prototypes/boot-record-v2/version-caps-mon.inc')
    maint = SESSION / 'step14-MAINT-RO-build-r1/s/core'
    put(maint / 'ram-maint-ro.asm', generic=True)
    edu = SESSION / 'step15-EDU-SRAM-build-r3/s/core'
    put(edu / 'edu-sram.asm')
    put(edu / 'edu-client.asm', generic=True)
    flash = ROOT / 'BUILD/b15-bank-monitor-led-r1/s/core'
    for name in ('bank-monitor-apply.inc', 'bank-monitor-target.inc', 'bank-monitor-crc.inc'):
        put(flash / name)
    # Canonical commented FLASH source, rather than two generated placement
    # variants. The unified builder generates the placement include.
    for name in ('bank-monitor.asm', 'bank-monitor-entry.asm', 'mon-absent-service.inc'):
        source = ROOT / 'prototypes/boot-record-v2' / name
        target = DEST / 'src/core' / name
        data = source.read_text().replace('\r\n', '\n').encode()
        assert not target.exists() or target.read_bytes() == data
        target.write_bytes(data)
        origin['files']['src/core/' + name] = {
            'source': source.relative_to(ROOT).as_posix(),
            'sha256': sha(source.read_bytes()), 'extracted_sha256': sha(data)}
    origin['unification'] = ('One b15 source closure for both CPU/board profiles; '
        'optional MON/VX1/ES1/FLASH/MAINT sources; no owner captures or wear data')
    origin_path.write_text(json.dumps(origin, indent=2) + '\n', encoding='utf-8', newline='\n')
    entries = {}
    def baseline(name, path, generic=False, symbols=None, crc_label=None):
        data = Path(path).read_bytes()
        original = data
        if generic:
            assert b'2609' in data
            data = bytearray(data.replace(b'2609', b'STR8'))
            if crc_label == 'MA_IMAGE_CRC':
                data = data.replace(b'WDC-BACKUP PROTECTED', b'OWNER IMAGE PRESERVE')
                data = data.replace(b'VX1-SLOT PROTECTED', b'OPTIONAL OWNER IMG')
            sy = json.loads(Path(symbols).read_text())
            sy = next(value for value in sy.values() if crc_label in value)
            offset = sy[crc_label] - 0x200
            import binascii
            data[offset:offset+2] = binascii.crc_hqx(data[:offset], 0xffff).to_bytes(2, 'big')
            data = bytes(data)
        entries[name] = dict(bytes=len(data), sha256=sha(data),
            predecessor_sha256=sha(original), change='Generic same-length banner and its CRC' if generic else 'Byte-identical extraction')
    for flavor, directory in (('BASE', ROOT/'BUILD/pr04-b15-cancel-r3'),
                               ('VX1', SESSION/'step08-VERSION-build-r7')):
        for page in ('a0', 'b0'):
            baseline('STR8N-F-MON-'+flavor+'-'+page[0].upper()+'.bin', directory/f'payload/monitor-{page}-offline-component.bin')
    vx = SESSION/'step08-VERSION-build-r7'
    baseline('STR8N-F-VX1-E.bin', vx/'payload/version-caps-e000.bin')
    baseline('STR8N-F-VERSION-RAM.bin', vx/'payload/version-caps-query-RAM.bin')
    maint = SESSION/'step14-MAINT-RO-build-r1'
    baseline('STR8N-F-MAINT-RO-RAM.bin', maint/'payload/2609-MAINT-RO-RAM.bin', True, maint/'symbols.json', 'MA_IMAGE_CRC')
    edu = SESSION/'step15-EDU-SRAM-build-r3'
    baseline('STR8N-F-ES1-8.bin', edu/'payload/2609-EDU-SRAM-B3-8.bin')
    baseline('STR8N-F-EDU-SRAM-RAM.bin', edu/'payload/2609-EDU-SRAM-RAM.bin', True, edu/'symbols.json', 'EC_IMAGE_CRC')
    flash = ROOT/'BUILD/b15-bank-monitor-led-r1'
    for address in ('8000', '9000'):
        for suffix in ('', '-RAM'):
            baseline('STR8N-F-FLASH-'+address+suffix+'.bin', flash/('payload/bank-monitor-'+address+suffix.lower()+'.bin'))
    baseline('STR8N-F-READBACK-RAM.bin', SESSION/'step05-readback-tools-r1/payload/readback-RAM.bin')
    (DEST/'system-baseline.json').write_text(json.dumps(dict(identity='b15 unified component extraction', artifacts=entries), indent=2)+'\n', encoding='utf-8', newline='\n')
    print('Imported unified public source closure:', len(copied), 'source/include files')


if __name__ == '__main__':
    main()
