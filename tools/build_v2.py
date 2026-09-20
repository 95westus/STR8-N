"""Build the bank-independent v2 boot milestone without touching v1 outputs.

Requires WDC02AS and WDCLN on PATH. No board access or flash programming.
All assembler inputs/sidecars and generated output stay under BUILD/v2-alpha1.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-alpha1'
SOURCE = ROOT / 'src/v2'


def read_s19(path):
    memory, entry = {}, None
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line:
            continue
        if entry is not None or line[:2] not in ('S0', 'S1', 'S9'):
            raise ValueError(f'{path}:{number}: unexpected record')
        raw = bytes.fromhex(line[2:])
        if len(raw) < 4 or raw[0] != len(raw) - 1 or sum(raw) & 255 != 255:
            raise ValueError(f'{path}:{number}: bad length/checksum')
        address = int.from_bytes(raw[1:3], 'big')
        if line[1] == '1':
            data = raw[3:-1]
            if not data or address + len(data) > 65536:
                raise ValueError('Empty/wrapping S1')
            for offset, value in enumerate(data, address):
                if offset in memory:
                    raise ValueError(f'Overlapping S1 at {offset:04X}')
                memory[offset] = value
        elif line[1] == '9':
            if len(raw) != 4:
                raise ValueError('S9 contains data')
            entry = address
    if entry is None:
        raise ValueError(f'{path}: missing S9')
    return memory, entry


def symbols(path):
    return {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$', path.read_text(), re.M)}


def record(kind, address, data=b''):
    raw = bytes([len(data) + 3]) + address.to_bytes(2, 'big') + data
    return 'S' + kind + (raw + bytes([(~sum(raw)) & 255])).hex().upper()


def dense_image(memory, start, end):
    if set(memory) != set(range(start, end)):
        raise ValueError(f'Linked image is not dense within {start:04X}-{end:04X}')
    return bytes(memory[a] for a in range(start, end))


def assemble(name, address, assembler, linker):
    stage = OUT / 'asm'
    shutil.copyfile(SOURCE / (name + '.asm'), stage / (name + '.asm'))
    subprocess.run([assembler, '-G', '-L', '-S', '-W', '-I', str(SOURCE),
                    name + '.asm'], cwd=stage, check=True)
    linked = stage / (name + '.s19')
    subprocess.run([linker, '-g', '-s', '-t', f'-c{address:04X}', '-hm19',
                    '-j', '-o', linked.name, name + '.obj'], cwd=stage, check=True)
    return read_s19(linked)[0], symbols(stage / (name + '.map'))


def include_bytes(path, data):
    path.write_text(''.join('                        DB      ' +
        ','.join(f'${v:02X}' for v in data[i:i+16]) + '\n'
        for i in range(0, len(data), 16)), encoding='ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-bank', action='store_true',
                        help='also emit explicit FF-filled 8-F image; destroys lower payload on install')
    args = parser.parse_args()
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise SystemExit('WDC02AS and WDCLN must be on PATH')
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    worker_mem, worker_sym = assemble('str8n-v2-worker', 0x7900, assembler, linker)
    vector_mem, vector_sym = assemble('str8n-v2-vectors', 0x7E20, assembler, linker)
    worker = dense_image(worker_mem, 0x7900, worker_sym['V2W_END'])
    vectors = dense_image(vector_mem, 0x7E20, vector_sym['V2V_END'])
    if not 0 < len(worker) < 256 or not 0 < len(vectors) <= 0xE0:
        raise ValueError('Milestone RAM copy limit exceeded')
    include_bytes(OUT / 'asm/worker-image.inc', worker)
    include_bytes(OUT / 'asm/vectors-image.inc', vectors)
    (OUT / 'asm/vectors-symbols.inc').write_text(''.join(
        f'{name:24} EQU     ${value:04X}\n'
        for name, value in vector_sym.items() if name.startswith('V2V_')) +
        f'V2_WORKER_SIZE          EQU     ${len(worker):02X}\n' +
        f'V2_VECTOR_SIZE          EQU     ${len(vectors):02X}\n', encoding='ascii')
    memory, resident = assemble('str8n-v2', 0xF000, assembler, linker)
    code = dense_image(memory, 0xF000, resident['V2_END'])
    if resident['V2_END'] > 0xFFE0:
        raise ValueError('Resident overlaps 816 vectors')
    image = bytearray(b'\xff' * 8192)
    image[0x1000:0x1000+len(code)] = code
    # Entire configuration remains erased: this milestone always holds.
    # Reserved vector words remain FF on both CPUs.
    hardware = {0xFFE4: 'V2V_NATIVE_COP', 0xFFE6: 'V2V_NATIVE_BRK',
                0xFFE8: 'V2V_NATIVE_ABORT', 0xFFEA: 'V2V_NATIVE_NMI',
                0xFFEE: 'V2V_NATIVE_IRQ', 0xFFF4: 'V2V_COP',
                0xFFF8: 'V2V_ABORT', 0xFFFA: 'V2V_NMI',
                0xFFFE: 'V2V_IRQ_BRK'}
    for address, name in hardware.items():
        image[address-0xE000:address-0xE000+2] = vector_sym[name].to_bytes(2, 'little')
    image[0x1FFC:0x1FFE] = resident['START'].to_bytes(2, 'little')
    (OUT / 'str8n-v2-alpha1-e000-ffff.bin').write_bytes(image)
    starts = [0xE000] + ([0x8000] if args.full_bank else [])
    artifacts = {}
    for start in starts:
        payload = b'\xff' * (0xE000-start) + image
        path = OUT / f'str8n-v2-alpha1-{start:04x}-ffff.s19'
        lines = [record('0', 0, b'STR8-N 2.0a1')]
        lines.extend(record('1', address, payload[address-start:address-start+32])
                     for address in range(start, 65536, 32))
        lines.append(record('9', resident['START']))
        path.write_text('\n'.join(lines) + '\n', encoding='ascii')
        parsed, entry = read_s19(path)
        assert dense_image(parsed, start, 65536) == payload
        assert entry == int.from_bytes(payload[-4:-2], 'little') == 0xF000
        artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(milestone='boot-console-jump', resident_bytes=len(code),
                  worker_bytes=len(worker), vector_code_bytes=len(vectors),
                  free_before_vectors=0xFFE0-resident['V2_END'],
                  resident=resident, worker=worker_sym, vectors=vector_sym,
                  artifacts=artifacts, board_tested=False,
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(SOURCE.iterdir()) if p.is_file()})
    (OUT / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'v2-alpha1: {len(code)} resident bytes (includes RAM images), '
          f'{len(worker)} worker, {len(vectors)} vector code; '
          f'{report["free_before_vectors"]} bytes free before vectors')
    print(f'Guest E-F image: {OUT / "str8n-v2-alpha1-e000-ffff.s19"}')


if __name__ == '__main__':
    main()
