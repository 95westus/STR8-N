"""Offline bf1 application-image candidate: assemble UCHESS with bf1 ASM 0.5.

No campaign firmware, serial ports or old sealed images are modified. The
result is a provisioning candidate, never a preserving in-place upgrade.
"""
import argparse
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    freeze = json.loads((ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text(encoding='utf-8'))
    workspace = Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',
                      STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'))
    sys.path.insert(0, str(workspace/'tools'))
    import serial
    def forbidden(*args, **kwargs):
        raise RuntimeError('No live serial in image composition')
    serial.Serial = forbidden
    import beta4_migration
    beta4_migration.Link = forbidden
    import test_asm as asm
    from test_v2_status import boot, layout, snapshot
    base_path = ROOT/'output/qualification/bf1-str8n-only-image-2026-10-18-r1/str8n-2.0bf1-str8n-only.bin'
    base = base_path.read_bytes()
    require(sha(base) == 'dd7b9633ea17b04e7e0759ec68d513da64943ad4193b7c35154a0a2c33fadaca', 'Base pin mismatch')
    chess_root = ROOT/'BUILD/microchess-asm04'
    manifest = json.loads((chess_root/'manifest.json').read_text(encoding='utf-8'))
    source_names = ['microchess.asm', 'microchess-readable.asm', 'symbols.json',
                    'Microchess6502-upstream.txt', 'LICENSE.txt', 'README.md']
    for name in source_names+['microchess.bin']:
        require(sha((chess_root/name).read_bytes()) == manifest['files_sha256'][name], 'uChess input mismatch: '+name)
    transcript = []
    checks = []
    def passed(name):
        checks.append(dict(name=name, passed=True))
        print('PASS', name, flush=True)
    def fixture(image):
        cpu, m = asm.fixture(primary=layout())
        m.banks = [bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0, len(image), 32768)]
        m.spi.banks = m.banks
        m.fast = True
        m.bus.rtc_regs[:9] = bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
        return cpu, m
    def command(cpu, data):
        keys = data.encode()+b'\r' if isinstance(data, str) else data
        result = asm.command(cpu, keys)
        transcript.append(dict(keys=repr(keys), output=result.decode('ascii', errors='replace')))
        return result
    try:
        cpu, m = fixture(base)
        before = snapshot(m)
        boot(cpu)
        require(b'ASM 0.5' in command(cpu, 'ASM'), 'Expected bf1 ASM0.5')
        command(cpu, 'NEW')
        require(b'Paste source' in command(cpu, 'PASTE'), 'Paste not active')
        source = (chess_root/'microchess.asm').read_bytes()
        pasted = command(cpu, source.replace(b'\r\n', b'\n').replace(b'\n', b'\r')+b'.\r')
        require(b'Error' not in pasted, 'Paste failed')
        assembled = command(cpu, 'ASM')
        require(b'OK 1439 bytes, origin $0200, buffer $0200' in assembled, 'uChess assembly mismatch')
        body = bytes(m.ram[0x200:0x79f])
        require(body == (chess_root/'microchess.bin').read_bytes(), 'bf1 assembly differs from prior independently built game')
        require(snapshot(m) == before, 'Assembly changed persistent model devices')
        passed('Actual bf1 ASM0.5 paste/assembly matches independently qualified game bytes')
        header = b'SR\x01\x3f'+(0x200).to_bytes(2, 'little')+len(body).to_bytes(2, 'little')+b'UCHESS'.ljust(16, b'\0')
        record = header+body
        require(len(header) == 24 and base[:len(record)] == b'\xff'*len(record), 'Provisioning app placement conflict')
        image = record+base[len(record):]
        require(image[len(record):] == base[len(record):], 'Firmware outside UCHESS changed')
        passed('UCHESS record at B1:8000 leaves all pinned firmware bytes unchanged')
        cpu, m = fixture(image)
        before = snapshot(m)
        boot(cpu)
        require(b'2.0bf1' in command(cpu, 'VERSION'), 'Wrong monitor version')
        table = command(cpu, 'T 1')
        require(b'UCHESS' in table and b'0200-079E' in table, 'Stored-program table missing game')
        require(b'Done' in command(cpu, 'R 1 UCHESS L'), 'Restore failed')
        require(bytes(m.ram[0x200:0x79f]) == body, 'Restored bytes differ')
        passed('bf1 boot, T table and load-only R find the embedded application')
        output = command(cpu, 'R 1 UCHESS')
        require(b'Microchess Copyright 1976 Peter Jennings benlo.com' in output and b'|WK|' in output and b'|BK|' in output, 'Game/banner failed')
        command(cpu, b'P')
        require(m.ram[0x10+15] == 0x33, 'Computer opening move failed')
        command(cpu, b'6343\r')
        require(m.ram[0x10+31] == 0x43, 'Human move failed')
        command(cpu, b'E')
        require(m.ram[0xb7] == 1, 'Exchange failed')
        command(cpu, b'C')
        require(m.ram[0x10+15] == 0x13 and m.ram[0x10+31] == 0x63, 'Reset position failed')
        require(b'B3>' in command(cpu, b'Q'), 'Return through HOLD failed')
        require(snapshot(m) == before and not m.events and not m.bus.writes, 'Game changed persistent devices')
        passed('Embedded game opening, human move, exchange/reset, HOLD and persistent preservation')
        name = 'str8n-2.0bf1-apps-str8n-only.bin'
        (a.out/name).write_bytes(image)
        source_out = a.out/'uchess-source'
        source_out.mkdir()
        for source_name in source_names:
            (source_out/source_name).write_bytes((chess_root/source_name).read_bytes())
        (a.out/'SHA256SUMS').write_text(sha(image)+'  '+name+'\n', encoding='ascii')
        result = dict(passed=True, checks=checks, version='2.0bf1', generation=48,
            filename=name, bytes=len(image), sha256=sha(image), bank_order=[1, 2, 3],
            full_device_base_offset=32768, base_sha256=sha(base),
            image_changes=[dict(bank=1, address=32768, bytes=len(record), label='UCHESS', ram_entry=512)],
            applications=['CLOCK', 'ASM', 'MAINT', 'SRAM', 'WORK', 'EDU', 'UCHESS'],
            providers=['RTC', 'journal', 'boot status', 'battery', 'local display', 'version'],
            sr_table_code_included=True, pinned_firmware_code_unchanged=True,
            uchess_source_sha256={n:sha((source_out/n).read_bytes()) for n in source_names},
            source_assembly='Actual bf1 ASM0.5 console PASTE and ASM in W65C02 model',
            independent_comparison='Exact old readable-source WDC oracle binary equivalence; not a fresh WDC compile',
            model_only=True, board_access=False, hardware_provisioning_tested=False,
            fresh_provisioning_only=True, preserving_upgrade=False,
            distribution_qualified=False, publication_permitted=False,
            pending=['MON B/fallback image regression', 'preserving migration app placement/conflict handling',
                     'Windows/Linux extracted kit and recovery qualification', 'final documentation audit'],
            test_sha256=sha(Path(__file__).read_bytes()), finished_utc=datetime.now(timezone.utc).isoformat())
        (a.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False, checks=checks, error=traceback.format_exc()), indent=2)+'\n', encoding='utf-8')
        raise
    finally:
        (a.out/'transcripts.json').write_text(json.dumps(transcript, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
