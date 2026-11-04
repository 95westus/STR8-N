"""Build isolated RAM probe variants; never modifies the b07 build."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_monitor_size import offline, ATTEMPTS
from str8build.assemble import Assembly
from str8build.formats import save, sha, s19

CASES = {0: 'snapshot', 1: 'exact-con-init', 2: 'release-WR-high-preload',
         3: 'known-A5-strobe', 4: 'known-00-strobe', 5: 'undriven-falling-edge-control',
         8: 'arm-WR-low', 9: 'arm-WR-high', 10: 'arm-WR-input',
         11: 'arm-WR-high-driving-A5'}


def long_branches(source):
    inverse = {'BEQ': 'BNE', 'BNE': 'BEQ', 'BCC': 'BCS', 'BCS': 'BCC',
               'BMI': 'BPL', 'BPL': 'BMI', 'BVS': 'BVC', 'BVC': 'BVS'}
    rows, number = [], 0
    for line in source.splitlines():
        match = re.fullmatch(r'\s*(BEQ|BNE|BCC|BCS|BMI|BPL|BVS|BVC|BRA)\s+(\w+)\s*', line)
        if not match:
            rows.append(line)
            continue
        opcode, destination = match.groups()
        if opcode == 'BRA':
            rows.append('        JMP ' + destination)
        else:
            number += 1
            label = 'RP_LONG_' + str(number)
            rows.extend(['        ' + inverse[opcode] + ' ' + label,
                         '        JMP ' + destination, label + ':'])
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'BUILD/pr04-b07-startup')
    parser.add_argument('--out', type=Path, default=ROOT / 'BUILD/reset-ff-ram-probe-r1')
    args = parser.parse_args()
    offline()
    build, out = args.build.resolve(), args.out.resolve()
    assert not out.exists(), 'Use a fresh isolated probe output directory'
    symbols = json.loads((build / 'symbols.json').read_text())
    assert symbols['core/monitor-b0']['V2_PROMPT'] == 0xb160
    mon = (build / 'payload/monitor-b0-offline-component.bin').read_bytes()
    prompt = mon[0x160:0x170]
    assert prompt.startswith(bytes.fromhex('ADF97DC954'))
    fixed = (build / 'payload/f-offline-component.bin').read_bytes()
    assert fixed[13] == 0x4c  # fixed public PUTC jump veneer
    core = out / 's/core'
    core.mkdir(parents=True)
    source = (HERE / 'probe.asm').read_text()
    (core / 'probe.asm').write_text(long_branches(source))
    assembly = object.__new__(Assembly)
    assembly.out, assembly.assembler, assembly.linker = out, shutil.which('wdc02as'), shutil.which('wdcln')
    assert assembly.assembler and assembly.linker
    assembly.symbols, assembly.compiled = {}, []
    body, local = assembly.link('core', 'probe', 0x2000, 'PROBE_END')
    assert local['PROBE_END'] <= 0x2400
    selector = local['PROBE_SELECTOR'] - 0x2000
    assert body[selector - 1:selector + 1] == bytes([0xa9, 0])
    rows = []
    for case, name in CASES.items():
        variant = bytearray(body)
        variant[selector] = case
        binary_name = f'probe-{case:02x}.bin'
        s19_name = f'probe-{case:02x}.s19'
        (out / binary_name).write_bytes(variant)
        packet = s19(variant, 0x2000, 0x2000)
        (out / s19_name).write_bytes(packet)
        rows.append(dict(id=case, name=name, bin=binary_name, s19=s19_name,
                         sha256=sha(variant), s19_sha256=sha(packet), entry=0x2000,
                         arm_marker_hex=(f'\r\nRFP1 ARM {case:02X}\r\n'.encode().hex() if case >= 8 else None)))
    save(out / 'symbols.json', local)
    save(out / 'manifest.json', dict(format=1, hardware=False, serial_access=False,
         device_or_network_attempts=ATTEMPTS, entry=0x2000, code_end=local['PROBE_END'],
         selector_address=local['PROBE_SELECTOR'], cases=rows,
         capsule=dict(address=0x6400, bytes=256, magic='RFP1', format=1,
                      case_offset=5, rowcount_offset=6, status_offset=7, reason_offset=8,
                      status_values={'busy': 0, 'done': 1, 'armed': 2, 'refused': 128},
                      original_NMI_HOLD_offset=9, case_complement_offset=10,
                      status_complement_offset=11, phase_offset=12, phase_complement_offset=13,
                      checksum_offset=14, checksum='XOR8 of all256 bytes except commit15 is zero',
                      commit_offset=15, commit_value=165, rows_offset=16, row_bytes=16,
                      row_fields=['stage', 'DDRA', 'DDRB', 'IFR_before', 'IER_before', 'PCR',
                                  'ACR', 'ORB_physical_readback', 'ORA_no_handshake_readback',
                                  'IFR_after', 'IER_after', 'reserved', 'reserved', 'reserved', 'reserved', 'reserved'],
                      nonce_offset=240, nonce_bytes=16,
                      host_must_clear_before_G=True, host_must_verify_fresh_nonce=True),
         return_prompt_B160=0xb160, return_prompt_preimage_hex=prompt.hex(),
         return_prompt_preimage_sha256=sha(prompt), source_build=str(build),
         component_hashes={name: sha((build / 'payload' / name).read_bytes()) for name in
                           ('f-offline-component.bin', 'monitor-b0-offline-component.bin')},
         runtime_symbols_sha256=sha((build / 'symbols.json').read_bytes()),
         probe_source_sha256=sha((HERE / 'probe.asm').read_bytes()),
         builder_sha256=sha(Path(__file__).read_bytes()),
         qualification_report='probe-cpu-tests.json',
         invariants=['No flash/RTC/PIA/PCR/ACR/IER writes', 'RD always output-high during active cases',
                     'Only NMI_HOLD F4 in zero page; owner00-DF untouched',
                     'No RX data read/poll; ORB/ORA may acknowledge CB/CA IFR flags',
                     'Arms require READY before final state and physical RESET to leave quiet RAM halt']))
    print('Built', len(rows), 'RAM-only variants', len(body), 'bytes', flush=True)


if __name__ == '__main__':
    main()
