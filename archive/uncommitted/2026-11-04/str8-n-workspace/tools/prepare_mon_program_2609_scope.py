"""Prepare the exact 2609 PROGRAM trial/restorer; never opens a serial port."""
import argparse
import binascii
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
sys.path.insert(0, str(REPO / 'tools'))
from build_mona import cells, sha
from mona_branches import conservative_branches
from program_format import inspect


def prepare(capture, out):
    capture, out = capture.resolve(), out.resolve()
    assert out.is_relative_to(ROOT / 'output/qualification') and not out.exists()
    report = json.loads((capture / 'report.json').read_text())
    assert report['passed'] and report['full_SRAM_double_read_equal']
    assert report['owner_RAM_restored'] and report['COM8_released']
    memory = (capture / 'SRAM-pass1-131072.bin').read_bytes()
    assert memory == (capture / 'SRAM-pass2-131072.bin').read_bytes()
    assert sha(memory) == report['SRAM_sha256']
    layout = inspect(memory)
    assert layout['format'] == 'SS1' and layout['boundary'] == '10000'
    assert [s['slot'] for s in layout['free_slots']] == [0, 1, 2, 3]
    assert all(f'{p:02X}' in layout['free_pages'] for p in range(0xc0, 0xc4))
    assert all(r.get('payload_CRC_valid', True) for r in layout['records'])
    blocks = [0x40, 0x80, 0xc0, 0x100] + list(range(0xc000, 0xc400, 64))
    provider_path = REPO / 'monitors/candidates/program-sp1-g00000001-r4'
    provider_manifest = json.loads((provider_path / 'manifest.json').read_text())
    provider = (provider_path / provider_manifest['artifact']['filename']).read_bytes()
    assert sha(provider) == provider_manifest['artifact']['sha256']
    assert binascii.crc_hqx(provider, 65535) == 0
    symbols = {n: int(v, 16) for v, n in re.findall(
        r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',
        (provider_path / 'staging/program-provider.map').read_text(), re.M)}
    f = (REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f) == json.loads((REPO / 'F_FREEZE.json').read_text())['sha256']
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    stage = out / 'source'
    stage.mkdir()
    source = REPO / 'tools/qualification/sram-bench.asm'
    expanded, _ = conservative_branches(source.read_text(), 'QB_LONG_')
    # A distinct prompt prevents a failed guard returning to B3> from being
    # mistaken for the old generic "> " bench prompt.
    old_prompt = "Q_PROMPT:\n        JSR STR8V2_RAM_RX_RESET\n        LDA #'>'"
    new_prompt = ("Q_PROMPT:\n        JSR STR8V2_RAM_RX_RESET\n"
                  "        LDA #'P'\n        JSR STR8V2_RAM_PUTC\n"
                  "        LDA #'B'\n        JSR STR8V2_RAM_PUTC\n        LDA #'>'")
    assert expanded.count(old_prompt) == 1
    expanded = expanded.replace(old_prompt, new_prompt)
    (stage / 'sram-bench.asm').write_text(expanded)
    for name in ('workbench-layout.inc', 'workbench-interface.inc', 'program-layout.inc'):
        shutil.copyfile(REPO / 'monitors/src' / name, stage / name)
    shutil.copyfile(REPO / 'src/include/str8n-v2-public.inc', stage / 'str8n-v2-public.inc')
    crc = binascii.crc_hqx(f, 65535)
    params = dict(BENCH_F_LO=crc & 255, BENCH_F_HI=crc >> 8,
                  BENCH_PV_HI=provider[-2], BENCH_PV_LO=provider[-1],
                  BENCH_TRANSFER=symbols['SP_TRANSFER'], BENCH_LIMIT=0,
                  BENCH_ALLOW_BYTES=len(blocks) * 2)
    (stage / 'sram-bench-params.inc').write_text(''.join(
        f'{k} EQU ${v:04X}\n' for k, v in params.items()))
    table = b''.join(a.to_bytes(2, 'little') for a in blocks)
    (stage / 'sram-bench-allow.inc').write_text(
        '        DB ' + ','.join(f'${v:02X}' for v in table) + '\n')
    logs = []
    for command in ([shutil.which('wdc02as'), '-G', '-L', '-S', '-W', 'sram-bench.asm'],
                    [shutil.which('wdcln'), '-g', '-s', '-t', '-c0200', '-hm19', '-j',
                     '-o', 'sram-bench.s19', 'sram-bench.obj']):
        assert command[0], 'WDC tools not found'
        r = subprocess.run(command, cwd=stage, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / 'build-log.json').write_text(json.dumps(logs, indent=2) + '\n')
        if r.returncode:
            raise RuntimeError('Restorer build failed; inspect build-log.json')
    sy = {n: int(v, 16) for v, n in re.findall(
        r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (stage / 'sram-bench.map').read_text(), re.M)}
    linked = cells(stage / 'sram-bench.s19')
    assert set(linked) == set(range(0x200, sy['Q_END'])) and sy['Q_END'] < 0x2000
    body = bytearray(linked[a] for a in range(0x200, sy['Q_END']))
    offset = sy['Q_IMAGE_CRC'] - 0x200
    body[offset:offset + 2] = binascii.crc_hqx(body[:offset], 65535).to_bytes(2, 'big')
    assert binascii.crc_hqx(body, 65535) == 0
    filename = '2609-PRIVATE-PROGRAM-RESTORE-RAM.bin'
    (out / filename).write_bytes(body)
    # Same position-independent public-console/HOLD fixture previously run on
    # 2512. Only the deliberate RAM load/entry address differs in this trial.
    fixtures = {name: bytes.fromhex(value) for name, value in {
        'OK': 'A9 4F 20 6D 7E A9 4B 20 6D 7E A9 0D 20 6D 7E A9 0A 20 6D 7E 4C 67 7E',
        'UP': 'A9 55 20 6D 7E A9 50 20 6D 7E A9 0D 20 6D 7E A9 0A 20 6D 7E 4C 67 7E',
    }.items()}
    for name, value in fixtures.items():
        (out / f'PROGRAM-{name}-23.bin').write_bytes(value)
    for address in blocks:
        (out / f'original-{address:04X}.bin').write_bytes(memory[address:address + 64])
    plan = dict(schema=1, status='PREPARED_NOT_AUTHORIZED', board='2609', port='COM8',
                usb_serial='A10MPQXCA', CPU='65C816 emulation', capture=str(capture),
                capture_report_sha256=sha((capture / 'report.json').read_bytes()),
                SRAM_sha256=sha(memory), source_bank_sha256=report['bank_sha256'],
                directory_slots=[0, 1, 2, 3], directory_bytes=256,
                payload_range='C000-C3FF', payload_bytes=1024,
                allowed_64_byte_writes=[f'{a:04X}' for a in blocks],
                temporary_byte_scope=1280, all_test_bytes_restore_required=True,
                retained_record_slots=[r['slot'] for r in layout['records']],
                WORKSPACE_start='10000', WORKSPACE_writes=0, primary_header_writes=0,
                mode_register_writes=0, flash_writes=0, journal_writes=0,
                boot_setting_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0,
                power_cuts=0, other_board_access=False,
                unchanged_counts=dict(C=78, D=48, E=45, F=31), sequence=1031,
                saved_default='S', provider_sha256=sha(provider),
                F_sha256=sha(f),
                restorer=dict(filename=filename, bytes=len(body), sha256=sha(body), prompt='PB> '),
                restorer_build_passes=1, firmware_rebuilt=False,
                fixture_sha256={n: sha(b) for n, b in fixtures.items()},
                driver_sha256=sha((ROOT / 'tools/mon_program_2609_trial.py').read_bytes()),
                scope_preparer_sha256=sha(Path(__file__).read_bytes()),
                final_context='REC>', COM8_release_required=True,
                tests=['AUTO-preview-NO', 'four-PROGRAM-stores', 'short-after-long-name',
                       'latest-same-name-version', 'explicit-C300-placement',
                       'full-directory-refusal', 'combined-and-explicit-Table',
                       'load-only-exact-RAM', 'positive-public-HOLD-run-return',
                       'CRC-refusal-before-owner-copy', 'CRC-repair-and-restore',
                       'full-SRAM-restore-and-compare', 'all-bank-and-owner-RAM-ZP-verify'],
                not_in_scope=['flash/AP02-app-fixture', 'SOURCE/ASM/DEBUG',
                              'SS2 positive writes', '65C816 native mode'])
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    prepare(a.capture, a.out)
