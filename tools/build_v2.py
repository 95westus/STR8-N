"""Build the bank-independent v2 monitor milestone without touching v1 outputs.

Requires WDC02AS and WDCLN on PATH. No board access or flash programming.
All assembler inputs/sidecars and generated output stay under BUILD/v2-alpha10.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.0a10'
STEM = 'str8n-v2-alpha10'
OUT = ROOT / 'BUILD/v2-alpha10'
SOURCE = ROOT / 'src/v2'
RESIDENT_START = 0xF000
SIGNATURE_SIZE = 4
BLANK_PAGE_START = 0xFE00
BLANK_PAGE_SIZE = 0x100
PUBLIC_CALLS = (
    ('STR8V2_RESET', 'START', 'V2_RESET'),
    ('STR8V2_HOLD', 'V2_PROMPT_ENTRY', 'V2_REENTER'),
    *((f'STR8V2_{name}', f'V2_{name}_ENTRY', f'V2_{name}') for name in (
        'CON_INIT', 'PUTC', 'GETC', 'RAW_POLL', 'CHECK_CANCEL', 'RX_RESET',
        'READ_LINE', 'HEX_OUT', 'NEWLINE', 'HEX_NIBBLE')),
    *((f'STR8V2_RESERVED{index}', f'V2_RESERVED{index}_ENTRY', 'V2_RESERVED')
      for index in range(4)),
)


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
    # Never let a failed external tool leave us reading a previous link result.
    for suffix in ('.obj', '.map', '.s19'):
        (stage / (name + suffix)).unlink(missing_ok=True)
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
    # Invalidate only this build's named generated artifacts, including an old
    # optional full-bank image and test receipts. Preserve earlier milestones.
    for name in ('build.json', 'test-results.json', 'monitor-test-results.json',
                 'load-test-results.json', 'flash-test-results.json', 'config-test-results.json',
                 f'{STEM}-e000-ffff.bin', f'{STEM}-e000-ffff.s19', f'{STEM}-8000-ffff.s19'):
        (OUT / name).unlink(missing_ok=True)
    # One ordinal per message; bit 7 marks the last character. No ROM pointer
    # table or terminator bytes. Keep editable text readable in the source JSON.
    messages = json.loads((SOURCE / 'str8n-v2-text.json').read_text())
    # Leading error messages share the prefix emitted by V2_MESSAGE. Keep
    # their complete human-readable wording in JSON, but store each tail once.
    bad_prefix = next(i for i, m in enumerate(messages) if m['name'] == 'V2_BAD_PREFIX')
    if (messages[bad_prefix]['text'] != 'Bad ' or
            any(not m['text'].startswith('Bad ') for m in messages[:bad_prefix]) or
            any(m['text'].startswith('Bad ') for m in messages[bad_prefix+1:])):
        raise ValueError('Bad-prefix messages must precede V2_BAD_PREFIX')
    ids, pool, names = [], bytearray(), set()
    for index, message in enumerate(messages):
        name = message['name']
        raw = bytearray(message['text'].replace('{version}', VERSION).encode('ascii'))
        if index < bad_prefix:
            raw = raw[4:]
        if index > 255 or name in names or not raw or any(b == 0 or b >= 128 for b in raw):
            raise ValueError('Invalid or duplicate monitor message')
        names.add(name)
        ids.append(f'{name:24} EQU     ${index:02X}\n')
        raw[-1] |= 128
        pool.extend(raw)
    (OUT / 'asm/text-ids.inc').write_text(''.join(ids), encoding='ascii')
    include_bytes(OUT / 'asm/text-image.inc', pool)
    with (OUT / 'asm/text-image.inc').open('r+', encoding='ascii') as stream:
        encoded = stream.read()
        stream.seek(0)
        stream.write('V2_TEXT:\n' + encoded)
    worker_mem, worker_sym = assemble('str8n-v2-worker', 0x7900, assembler, linker)
    vector_mem, vector_sym = assemble('str8n-v2-vectors', 0x7E20, assembler, linker)
    worker = dense_image(worker_mem, 0x7900, worker_sym['V2W_END'])
    vectors = dense_image(vector_mem, 0x7E20, vector_sym['V2V_END'])
    if not 0 < len(worker) <= 0x300 or not 0 < len(vectors) <= 0xE0:
        raise ValueError('Milestone RAM copy limit exceeded')
    include_bytes(OUT / 'asm/worker-image.inc', worker)
    include_bytes(OUT / 'asm/vectors-image.inc', vectors)
    # Copy fixed 256-byte windows together, overlapping the final window to
    # cover a partial page without reading/writing outside the actual worker.
    offsets = list(range(0, len(worker)-255, 256))
    if len(worker) % 256:
        offsets.append(max(0, len(worker)-256))
    copy = ['                        LDX     #$00\n', 'V2_COPY_WORKER:\n']
    for offset in offsets:
        copy.extend((f'                        LDA     V2_WORKER_IMAGE+${offset:04X},X\n',
                     f'                        STA     V2_WORKER+${offset:04X},X\n'))
    copy.append('                        INX\n')
    if len(worker) < 256:
        copy.append(f'                        CPX     #${len(worker):02X}\n')
    copy.append('                        BNE     V2_COPY_WORKER\n')
    (OUT / 'asm/worker-copy.inc').write_text(''.join(copy), encoding='ascii')
    (OUT / 'asm/vectors-symbols.inc').write_text(''.join(
        f'{name:24} EQU     ${value:04X}\n'
        for name, value in (vector_sym | worker_sym).items()
        if name.startswith(('V2V_', 'V2W_'))) +
        f'V2_WORKER_SIZE          EQU     ${len(worker):02X}\n' +
        f'V2_VECTOR_SIZE          EQU     ${len(vectors):02X}\n', encoding='ascii')
    memory, resident = assemble('str8n-v2', RESIDENT_START, assembler, linker)
    code = dense_image(memory, RESIDENT_START, resident['V2_END'])
    for index, (public, entry_label, target) in enumerate(PUBLIC_CALLS):
        address = RESIDENT_START + SIGNATURE_SIZE + 3*index
        if resident[public] != address or resident[entry_label] != address:
            raise ValueError(f'Public entry moved: {public}')
        if bytes(memory[a] for a in range(address, address+3)) != b'\x4c' + resident[target].to_bytes(2, 'little'):
            raise ValueError(f'Public entry is not the expected JMP: {public}')
    if resident['V2_END'] > BLANK_PAGE_START:
        raise ValueError('Resident overlaps reserved blank page $FE00-$FEFF')
    image = bytearray(b'\xff' * 8192)
    offset = RESIDENT_START - 0xE000
    image[offset:offset+len(code)] = code
    # Keep the complete unused tail erased, up to the hardware vector area.
    assert image[resident['V2_END']-0xE000:0x1FE0] == b'\xff' * (0xFFE0-resident['V2_END'])
    # Factory configuration remains erased, so a fresh image holds.
    # Reserved vector words remain FF on both CPUs.
    hardware = {0xFFE4: 'V2V_NATIVE_COP', 0xFFE6: 'V2V_NATIVE_BRK',
                0xFFE8: 'V2V_NATIVE_ABORT', 0xFFEA: 'V2V_NATIVE_NMI',
                0xFFEE: 'V2V_NATIVE_IRQ', 0xFFF4: 'V2V_COP',
                0xFFF8: 'V2V_ABORT', 0xFFFA: 'V2V_NMI',
                0xFFFE: 'V2V_IRQ_BRK'}
    for address, name in hardware.items():
        image[address-0xE000:address-0xE000+2] = vector_sym[name].to_bytes(2, 'little')
    image[0x1FFC:0x1FFE] = resident['START'].to_bytes(2, 'little')
    (OUT / f'{STEM}-e000-ffff.bin').write_bytes(image)
    starts = [0xE000] + ([0x8000] if args.full_bank else [])
    artifacts = {}
    for start in starts:
        payload = b'\xff' * (0xE000-start) + image
        path = OUT / f'{STEM}-{start:04x}-ffff.s19'
        lines = [record('0', 0, f'STR8-N {VERSION}'.encode('ascii'))]
        lines.extend(record('1', address, payload[address-start:address-start+32])
                     for address in range(start, 65536, 32))
        lines.append(record('9', resident['START']))
        path.write_text('\n'.join(lines) + '\n', encoding='ascii')
        parsed, entry = read_s19(path)
        assert dense_image(parsed, start, 65536) == payload
        assert entry == int.from_bytes(payload[-4:-2], 'little') == resident['START']
        artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(milestone='compact-resident', resident_bytes=len(code),
                  resident_start=RESIDENT_START,
                  public_calls={public: resident[public] for public, _, _ in PUBLIC_CALLS},
                  resident_code_bytes=resident['V2_COMMAND_KEYS']-RESIDENT_START,
                  command_table_bytes=resident['V2_TEXT']-resident['V2_COMMAND_KEYS'],
                  text_bytes=len(pool),
                  worker_bytes=len(worker), vector_code_bytes=len(vectors),
                  free_before_vectors=0xFFE0-resident['V2_END'],
                  reserved_blank_page_start=BLANK_PAGE_START,
                  reserved_blank_page_bytes=BLANK_PAGE_SIZE,
                  resident=resident, worker=worker_sym, vectors=vector_sym,
                  artifacts=artifacts, board_tested=False,
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(SOURCE.iterdir()) if p.is_file()})
    (OUT / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{STEM}: {len(code)} resident bytes (includes RAM images), '
          f'{len(worker)} worker, {len(vectors)} vector code; '
          f'{report["free_before_vectors"]} bytes free before vectors')
    print(f'Guest E-F image: {OUT / (STEM + "-e000-ffff.s19")}')


if __name__ == '__main__':
    main()
