"""Offline MON B fallback regression for the new UCHESS provisioning image."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise ValueError('Output already exists')
    r = json.loads((a.image_dir/'report.json').read_text(encoding='utf-8'))
    image = (a.image_dir/r['filename']).read_bytes()
    if not r['passed'] or hashlib.sha256(image).hexdigest() != r['sha256']:
        raise ValueError('Image pin mismatch')
    freeze = json.loads((ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text(encoding='utf-8'))
    workspace = Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate', STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'))
    sys.path.insert(0, str(workspace/'tools'))
    import serial
    def forbidden(*args, **kwargs):
        raise RuntimeError('Live serial forbidden')
    serial.Serial = forbidden
    import beta4_migration
    beta4_migration.Link = forbidden
    import test_asm as asm
    from test_v2_status import boot, layout, snapshot
    cpu, m = asm.fixture(primary=layout())
    m.banks = [bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0, len(image), 32768)]
    # Only this ephemeral model copy is damaged, not the published candidate.
    m.banks[3][0x201f] = 255
    m.spi.banks = m.banks
    m.fast = True
    m.bus.rtc_regs[:9] = bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
    before = snapshot(m)
    boot(cpu)
    if m.ram[0x7d30] != 0xb0:
        raise ValueError('Did not boot MON B fallback')
    log = []
    def command(keys):
        out = asm.command(cpu, keys)
        log.append(out.decode('ascii', errors='replace'))
        return out
    if b'UCHESS' not in command(b'T 1\r'):
        raise ValueError('MON B cannot find UCHESS')
    if b'Microchess Copyright' not in command(b'R 1 UCHESS\r'):
        raise ValueError('MON B cannot launch game')
    if b'B3>' not in command(b'Q'):
        raise ValueError('Game did not return')
    if b'BATCH done' not in command(b'BATCH R CLOCK;STATUS;Q\r'):
        raise ValueError('MON B CLOCK BATCH regression')
    if snapshot(m) != before or m.events or m.bus.writes:
        raise ValueError('Persistent model devices changed')
    result = dict(passed=True, image_sha256=r['sha256'], checks=['invalid A falls back to B',
        'MON B T discovers UCHESS', 'MON B R executes and HOLD returns',
        'MON B CLOCK BATCH remains functional', 'persistent model devices unchanged'],
        transcripts=log, model_only=True, board_access=False, distribution_qualified=False)
    a.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('PASS MON B fallback, UCHESS T/R/HOLD and CLOCK BATCH')


if __name__ == '__main__':
    main()
