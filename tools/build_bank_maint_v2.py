"""Build the RAM-only sector maintenance/editor S19 at $2000; no .a carrier."""
import hashlib
import json
from pathlib import Path
import re
import shutil

import build_v2_config as assembler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/bank-maint-v2'
SOURCE = ROOT / 'tools/bank-maint-v2/bank-maint.asm'
NAME = 'str8n-bank-maint-2000'


def long_branches(text):
    """Expand 6502 branches without changing flags; generated labels are private."""
    opposite = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
                    BPL='BMI', BMI='BPL', BVC='BVS', BVS='BVC')
    output = []
    for number, line in enumerate(text.splitlines()):
        match = re.fullmatch(r'(\w+:)?\s*(B[A-Z]{2})\s+(\w+)\s*(;.*)?', line)
        if not match or match[2] not in (*opposite, 'BRA'):
            output.append(line)
            continue
        label, op, target, comment = match.groups()
        if label:
            output.append(label)
        if op == 'BRA':
            output.append(f'                        JMP {target}')
        else:
            skip = f'BM_LONG_{number}'
            output.extend([f'                        {opposite[op]} {skip}',
                           f'                        JMP {target}', f'{skip}:'])
    return '\n'.join(output) + '\n'


def main():
    stage = OUT / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'test-results.json', NAME + '.s19'):
        (OUT / name).unlink(missing_ok=True)
    generated = OUT / 'bank-maint-expanded.asm'
    generated.write_text(long_branches(SOURCE.read_text()), encoding='ascii')
    assembler.OUT = OUT
    memory, sym = assembler.assemble(NAME, 0x2000, shutil.which('wdc02as'),
                                     shutil.which('wdcln'), source_file=generated)
    end = sym['BM_END']
    if sym['START'] != 0x2000 or end > 0x4000 or set(memory) != set(range(0x2000, end)):
        raise ValueError('Utility overlaps editor buffer or has an invalid layout')
    lines = [assembler.record('0', 0, b'STR8-N bank maintenance 1.0')]
    lines += [assembler.record('1', a, bytes(memory[x] for x in range(a, min(a+32, end))))
              for a in range(0x2000, end, 32)]
    lines.append(assembler.record('9', 0x2000))
    target = OUT / (NAME + '.s19')
    target.write_text('\n'.join(lines) + '\n', encoding='ascii')
    assert assembler.read_s19(target) == (memory, 0x2000)
    # Staging now lives in the utility's S command; retire the external file.
    (OUT / (NAME + '-b1-staging.s19')).unlink(missing_ok=True)
    report = dict(version='1.0', entry=0x2000, end=end, bytes=len(memory),
                  s19_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  symbols=sym, hardware_tested=False)
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{target}: {len(memory)} bytes, $2000-${end-1:04X}; editor $5000-$5FFF')
    print('Built-in staging: S 8 / W 1 8; S 9 / W 1 9')


if __name__ == '__main__':
    main()
