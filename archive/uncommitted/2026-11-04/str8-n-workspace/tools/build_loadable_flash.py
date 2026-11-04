"""Package qualified FLASH g2 as one recovery-loadable $0200 BIN.

Reuse the accepted core and dense-control library. The only core changes are
data pointers to the included RAM library and Q's destination (public F reset).
No flash-resident FLASH, MAINT, MON or private native return image is fetched.
"""
import argparse
import binascii
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()


def build(out):
    base = ROOT / 'BUILD/flash-status-correction-r4'
    manifest = json.loads((base / 'manifest.json').read_text())
    def artifact(name):
        data = (base / name).read_bytes()
        assert sha(data) == manifest['artifacts'][name]['sha256']
        return data
    core = bytearray(artifact('FLASH-RAM.bin'))
    library = artifact('DENSE-CONTROL-4000.bin')
    assert binascii.crc_hqx(library, 65535) == 0
    symbols = {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (base / 'board-tool.map').read_text(), re.M)}
    at = symbols['FI_FRAGMENTS'] - 0x2000
    old_table = b''.join(struct.pack('<HH', int(f['source'], 16), f['length']) for f in manifest['fragments'])
    assert core[at:at+12] == old_table
    table = b''.join(struct.pack('<HH', 0x4300+f['library_offset'], f['length']) for f in manifest['fragments'])
    core[at:at+12] = table
    quit_at = symbols['CONFIG_QUIT'] - 0x2000
    assert core[quit_at:quit_at+3] == bytes.fromhex('4C 00 5E')
    core[quit_at:quit_at+3] = bytes.fromhex('4C 64 7E')
    # Recovery L and MON R at $0200 enter the same packet. No native loader,
    # borrowed MON context or installed utility is required. Q restarts F.
    stub = bytes.fromhex('78 D8 A2 FF 9A 9C F9 7D 9C 00 5D A9 03 8D 00 7D 20 48 78 4C 00 20')
    packet = bytearray(b'\xff' * (0x4300 + len(library) - 0x200))
    packet[:len(stub)] = stub
    packet[0x1e00:0x1e00+len(core)] = core
    packet[0x4100:] = library
    out.mkdir(parents=True, exist_ok=False)
    (out / 'FLASH.bin').write_bytes(packet)
    maint = (ROOT / 'BUILD/loadable-maint-PR05-r1/payload/STR8N-F-MAP-RAM.bin').read_bytes()
    assert sha(maint) == '63ca93828a2e5b31150cf4a72fa7453916b3c3f2597197886f31823ed055c41b'
    (out / 'MAINT-RO.bin').write_bytes(maint)
    report = dict(format=1, load='0200', entry='0200', end=f'{0x1ff+len(packet):04X}',
                  bytes=len(packet), sha256=sha(packet), F_sha256=manifest['F_sha256'],
                  core_input_sha256=manifest['artifacts']['FLASH-RAM.bin']['sha256'],
                  library_sha256=sha(library), core_patches=['FI_FRAGMENTS RAM pointers', 'Q to public F reset $7E64'],
                  stored_FLASH_required=False, stored_MAINT_required=False, MON_required=False,
                  MAINT_RO_sha256=sha(maint), hardware_qualification='See board retirement receipt')
    (out / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    (out / 'README.txt').write_text(
        'FLASH g2 loadable RAM tool for N-F 0.3.0 BASE1/PR05.\n'
        'Load FLASH.bin as raw binary at $0200 using recovery L; it starts automatically.\n'
        'Alternatively load at $0200 through a compatible MON loader and run R.\n'
        'Includes its dense S19 library; requires no stored FLASH or MAINT copy.\n'
        'Q restarts F using the saved boot policy. Borrowed application RAM is not restored.\n'
        'RAM code/library: $0200-$4544; tool state and flash buffer also borrow high RAM.\n'
        'FLASH supports writes/erases; inspect target bank/range and confirmation.\n'
        'MAINT-RO.bin is the separate read-only $0200 maintenance tool.\n'
        'Only the F hash in manifest.json is admitted by this package.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    build(p.parse_args().out.resolve())
