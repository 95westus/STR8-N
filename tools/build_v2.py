"""Build the bank-independent v2 monitor milestone without touching v1 outputs.

Requires WDC02AS and WDCLN on PATH. No board access or flash programming.
All assembler inputs/sidecars and generated output stay under BUILD/v2-alpha21.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.0a21'
STEM = 'str8n-v2-alpha21'
OUT = ROOT / 'BUILD/v2-alpha21'
SOURCE = ROOT / 'src/v2'
INTERRUPT_PROBE_SOURCE = ROOT / 'tools/v2-interrupt-test'
ACIA_TEST_SOURCE = ROOT / 'tools/v2-acia-test'
RAM_ABI_TEST_SOURCE = ROOT / 'tools/v2-ram-abi-test'
TOP_UPDATE_SOURCE = ROOT / 'tools/top-update/str8n-v1.23-top-update-2000.asm'
RESIDENT_START = 0xF000
SIGNATURE_SIZE = 4
EXPANSION_RESERVE_START = 0xFF20
EXPANSION_RESERVE_SIZE = 0xC0
PUBLIC_CALLS = (
    ('STR8V2_RESET', 'START', 'V2_RESET'),
    ('STR8V2_HOLD', 'V2_PROMPT_ENTRY', 'V2_REENTER'),
    ('STR8V2_CON_INIT', 'V2_CON_INIT_ENTRY', 'V2W_CON_INIT'),
    *((f'STR8V2_{name}', f'V2_{name}_ENTRY', f'V2_{name}') for name in (
        'PUTC', 'GETC', 'RAW_POLL', 'CHECK_CANCEL', 'RX_RESET')),
    ('STR8V2_RESERVED_LINE', 'V2_READ_LINE_ENTRY', 'V2_RESERVED'),
    *((f'STR8V2_{name}', f'V2_{name}_ENTRY', f'V2_{name}') for name in (
        'HEX_OUT', 'NEWLINE', 'HEX_NIBBLE')),
    ('STR8V2_CAPS_QUERY', 'V2_CAPS_QUERY_ENTRY', 'V2_CAPS_QUERY'),
    ('STR8V2_BOARD_QUERY', 'V2_BOARD_QUERY_ENTRY', 'V2_BOARD_QUERY'),
    *((f'STR8V2_RESERVED{index}', f'V2_RESERVED{index}_ENTRY', 'V2_RESERVED')
      for index in range(2, 4)),
)
RAM_PUBLIC_CALLS = (
    ('STR8V2_RAM_RESET', 'V2V_RAM_RESET_ENTRY', 'V2V_RAM_RESET'),
    ('STR8V2_RAM_HOLD', 'V2V_RAM_HOLD_ENTRY', 'V2V_RAM_HOLD'),
    ('STR8V2_RAM_CON_INIT', 'V2V_RAM_CON_INIT_ENTRY', 'V2W_CON_INIT'),
    ('STR8V2_RAM_PUTC', 'V2V_RAM_PUTC_ENTRY', 'V2W_PUTC'),
    ('STR8V2_RAM_GETC', 'V2V_RAM_GETC_ENTRY', 'V2W_GETC'),
    ('STR8V2_RAM_RAW_POLL', 'V2V_RAM_RAW_POLL_ENTRY', 'V2W_RAW_POLL'),
    ('STR8V2_RAM_CHECK_CANCEL', 'V2V_RAM_CHECK_CANCEL_ENTRY', 'V2W_CHECK_CANCEL'),
    ('STR8V2_RAM_RX_RESET', 'V2V_RAM_RX_RESET_ENTRY', 'V2W_RX_RESET'),
    ('STR8V2_RAM_HEX_OUT', 'V2V_RAM_HEX_OUT_ENTRY', 'V2V_RAM_HEX_OUT'),
    ('STR8V2_RAM_NEWLINE', 'V2V_RAM_NEWLINE_ENTRY', 'V2V_RAM_NEWLINE'),
    ('STR8V2_RAM_HEX_NIBBLE', 'V2V_RAM_HEX_NIBBLE_ENTRY', 'V2V_RAM_HEX_NIBBLE'),
    ('STR8V2_RAM_CAPS_QUERY', 'V2V_RAM_CAPS_QUERY_ENTRY', 'V2V_RAM_CAPS_QUERY'),
    ('STR8V2_RAM_BOARD_QUERY', 'V2V_RAM_BOARD_QUERY_ENTRY', 'V2V_RAM_BOARD_QUERY'),
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


def assemble(name, address, assembler, linker, source=SOURCE, source_file=None,
             include_dirs=(), defines=()):
    stage = OUT / 'asm'
    # Never let a failed external tool leave us reading a previous link result.
    for suffix in ('.obj', '.map', '.s19'):
        (stage / (name + suffix)).unlink(missing_ok=True)
    shutil.copyfile(source_file or source / (name + '.asm'), stage / (name + '.asm'))
    command = [assembler, '-G', '-L', '-S', '-W', '-I', str(SOURCE)]
    for directory in include_dirs:
        command.extend(('-I', str(directory)))
    command.extend(f'-D{name}={value}' for name, value in defines)
    command.append(name + '.asm')
    subprocess.run(command, cwd=stage, check=True)
    linked = stage / (name + '.s19')
    link_command = [linker, '-g', '-s', '-t']
    if address is not None:
        link_command.append(f'-c{address:04X}')
    link_command.extend(('-hm19', '-j', '-o', linked.name, name + '.obj'))
    subprocess.run(link_command, cwd=stage, check=True)
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
    assembler = shutil.which('wdc02as')
    native_assembler = shutil.which('wdc816as')
    linker = shutil.which('wdcln')
    if not assembler or not native_assembler or not linker:
        raise SystemExit('WDC02AS, WDC816AS and WDCLN must be on PATH')
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    # Invalidate only this build's named generated artifacts, including an old
    # optional full-bank image and test receipts. Preserve earlier milestones.
    for name in ('build.json', 'test-results.json', 'monitor-test-results.json',
                 'load-test-results.json', 'flash-test-results.json', 'config-test-results.json',
                 f'{STEM}-e000-ffff.bin', f'{STEM}-e000-ffff.s19',
                 f'{STEM}-8000-ffff.bin', f'{STEM}-8000-ffff.s19',
                 f'{STEM}-b3-top-update-2000.s19'):
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
    ram_targets = ('V2W_SELECT', 'V2W_CON_INIT', 'V2W_PUTC', 'V2W_GETC',
                   'V2W_RAW_POLL', 'V2W_CHECK_CANCEL', 'V2W_RX_RESET')
    (OUT / 'asm/worker-public-symbols.inc').write_text(''.join(
        f'{name:24} EQU     ${worker_sym[name]:04X}\n' for name in ram_targets),
        encoding='ascii')
    vector_mem, vector_sym = assemble(
        'str8n-v2-vectors', 0x7E20, assembler, linker,
        include_dirs=(OUT / 'asm',))
    worker = dense_image(worker_mem, 0x7900, worker_sym['V2W_END'])
    vectors = dense_image(vector_mem, 0x7E20, vector_sym['V2V_END'])
    if not 0 < len(worker) <= 0x300 or not 0 < len(vectors) <= 0xE0:
        raise ValueError('Milestone RAM copy limit exceeded')
    if (vector_sym['V2V_RAM_SIGNATURE'] != 0x7E60 or
            bytes(vector_mem[a] for a in range(0x7E60, 0x7E64)) != b'RA\x01\x0d'):
        raise ValueError('RAM ABI descriptor moved or changed')
    for index, (public, entry_label, target) in enumerate(RAM_PUBLIC_CALLS):
        address = 0x7E64 + 3*index
        if vector_sym[public] != address or vector_sym[entry_label] != address:
            raise ValueError(f'RAM public entry moved: {public}')
        expected = b'\x4c' + vector_sym[target].to_bytes(2, 'little')
        if bytes(vector_mem[a] for a in range(address, address+3)) != expected:
            raise ValueError(f'RAM public entry is not the expected JMP: {public}')
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
    descriptor = b'CA\x01\x17'
    if resident['STR8V2_CAPS_DATA'] != 0xF035 or resident['V2_CAPS_DATA'] != 0xF035:
        raise ValueError('Capability descriptor moved')
    if bytes(memory[a] for a in range(0xF035, 0xF035+len(descriptor))) != descriptor:
        raise ValueError('Capability descriptor changed')
    if resident['V2_END'] > EXPANSION_RESERVE_START:
        raise ValueError('Resident overlaps reserved expansion tail $FF20-$FFDF')
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
        if start == 0x8000:
            (OUT / f'{STEM}-8000-ffff.bin').write_bytes(payload)
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
    # Guarded RAM updater for the final B3:F transition. B2:F holds a verified
    # recovery copy of the old top while the new clean V2 top is programmed.
    top = bytes(image[-4096:])
    top_include = OUT / 'asm' / 'str8n-v2-current-top-image.inc'
    top_sum = sum(top) & 0xFFFF
    top_include.write_text(f'TU_CANDIDATE_SUM        EQU             ${top_sum:04X}\n',
                           encoding='ascii')
    with top_include.open('a', encoding='ascii') as stream:
        stream.write(''.join('                        DB              ' +
            ','.join(f'${v:02X}' for v in top[i:i+16]) + '\n'
            for i in range(0, len(top), 16)))
    updater_name = f'{STEM}-b3-top-update-2000'
    updater_mem, updater_symbols = assemble(
        updater_name, None, assembler, linker, source_file=TOP_UPDATE_SOURCE,
        include_dirs=(OUT / 'asm',), defines=(
            ('STR8_TOP_EMBED', 0), ('STR8_DIRECTORY_REFRESH', 1),
            ('STR8_V2_TOP_IMAGE', 1), ('STR8_IN65_TOP_IMAGE', 0),
            ('STR8_IN65_VERSION_135', 0), ('STR8_IN65_VERSION_133', 0)))
    candidate = updater_symbols['TU_CANDIDATE_IMAGE']
    assert candidate == 0x4000
    assert bytes(updater_mem[a] for a in range(candidate, candidate+4096)) == top
    code_addresses = sorted(a for a in updater_mem if a < candidate)
    assert code_addresses == list(range(0x2000, code_addresses[-1]+1))
    updater_path = OUT / f'{updater_name}.s19'
    updater_lines = [record('0', 0, f'STR8-N {VERSION} B3'.encode('ascii'))]
    ordered = sorted(updater_mem)
    index = 0
    while index < len(ordered):
        address = ordered[index]
        run = [updater_mem[address]]
        index += 1
        while (index < len(ordered) and len(run) < 32 and
               ordered[index] == address + len(run)):
            run.append(updater_mem[ordered[index]])
            index += 1
        updater_lines.append(record('1', address, bytes(run)))
    updater_lines.append(record('9', 0x2000))
    updater_path.write_text('\n'.join(updater_lines) + '\n', encoding='ascii')
    parsed_updater, updater_entry = read_s19(updater_path)
    assert parsed_updater == updater_mem and updater_entry == 0x2000
    artifacts[updater_path.name] = hashlib.sha256(updater_path.read_bytes()).hexdigest()
    probe_source_name = 'str8n-v2-interrupt-probe-2000'
    probe_name = f'{STEM}-interrupt-probe-2000'
    probe_memory, probe_symbols = assemble(
        probe_source_name, 0x2000, assembler, linker, INTERRUPT_PROBE_SOURCE)
    probe = dense_image(probe_memory, 0x2000, probe_symbols['PROBE_END'])
    probe_path = OUT / f'{probe_name}.s19'
    probe_lines = [record('0', 0, f'STR8-N {VERSION} IRQ'.encode('ascii'))]
    probe_lines.extend(record('1', address, probe[address-0x2000:address-0x2000+32])
                       for address in range(0x2000, 0x2000+len(probe), 32))
    probe_lines.append(record('9', 0x2000))
    probe_path.write_text('\n'.join(probe_lines) + '\n')
    parsed_probe, probe_entry = read_s19(probe_path)
    assert dense_image(parsed_probe, 0x2000, 0x2000+len(probe)) == probe
    assert probe_entry == 0x2000
    artifacts[probe_path.name] = hashlib.sha256(probe_path.read_bytes()).hexdigest()
    nmi_source_name = 'str8n-v2-nmi-probe-2000'
    nmi_name = f'{STEM}-nmi-probe-2000'
    nmi_memory, nmi_symbols = assemble(
        nmi_source_name, 0x2000, assembler, linker, INTERRUPT_PROBE_SOURCE)
    nmi_probe = dense_image(nmi_memory, 0x2000, nmi_symbols['PROBE_END'])
    nmi_path = OUT / f'{nmi_name}.s19'
    nmi_lines = [record('0', 0, f'STR8-N {VERSION} NMI'.encode('ascii'))]
    nmi_lines.extend(record('1', address,
                            nmi_probe[address-0x2000:address-0x2000+32])
                     for address in range(0x2000, 0x2000+len(nmi_probe), 32))
    nmi_lines.append(record('9', 0x2000))
    nmi_path.write_text('\n'.join(nmi_lines) + '\n')
    parsed_nmi, nmi_entry = read_s19(nmi_path)
    assert dense_image(parsed_nmi, 0x2000, 0x2000+len(nmi_probe)) == nmi_probe
    assert nmi_entry == 0x2000
    artifacts[nmi_path.name] = hashlib.sha256(nmi_path.read_bytes()).hexdigest()
    native_source_name = 'str8n-v2-native-probe-2000'
    native_name = f'{STEM}-native-probe-2000'
    native_memory, native_symbols = assemble(
        native_source_name, 0x2000, native_assembler, linker, INTERRUPT_PROBE_SOURCE)
    native_probe = dense_image(native_memory, 0x2000, native_symbols['PROBE_END'])
    native_path = OUT / f'{native_name}.s19'
    native_lines = [record('0', 0, f'STR8-N {VERSION} 816N'.encode('ascii'))]
    native_lines.extend(record('1', address,
                               native_probe[address-0x2000:address-0x2000+32])
                        for address in range(0x2000, 0x2000+len(native_probe), 32))
    native_lines.append(record('9', 0x2000))
    native_path.write_text('\n'.join(native_lines) + '\n')
    parsed_native, native_entry = read_s19(native_path)
    assert dense_image(parsed_native, 0x2000, 0x2000+len(native_probe)) == native_probe
    assert native_entry == 0x2000
    artifacts[native_path.name] = hashlib.sha256(native_path.read_bytes()).hexdigest()
    acia_source_name = 'str8n-v2-acia-test-2000'
    acia_name = f'{STEM}-acia-test-2000'
    acia_memory, acia_symbols = assemble(
        acia_source_name, 0x2000, assembler, linker, ACIA_TEST_SOURCE)
    acia_probe = dense_image(acia_memory, 0x2000, acia_symbols['PROBE_END'])
    acia_path = OUT / f'{acia_name}.s19'
    acia_lines = [record('0', 0, f'STR8-N {VERSION} ACIA'.encode('ascii'))]
    acia_lines.extend(record('1', address,
                             acia_probe[address-0x2000:address-0x2000+32])
                      for address in range(0x2000, 0x2000+len(acia_probe), 32))
    acia_lines.append(record('9', 0x2000))
    acia_path.write_text('\n'.join(acia_lines) + '\n')
    parsed_acia, acia_entry = read_s19(acia_path)
    assert dense_image(parsed_acia, 0x2000, 0x2000+len(acia_probe)) == acia_probe
    assert acia_entry == 0x2000
    artifacts[acia_path.name] = hashlib.sha256(acia_path.read_bytes()).hexdigest()
    ram_abi_source_name = 'str8n-v2-ram-abi-test-2000'
    ram_abi_name = f'{STEM}-ram-abi-test-2000'
    ram_abi_memory, ram_abi_symbols = assemble(
        ram_abi_source_name, 0x2000, assembler, linker, RAM_ABI_TEST_SOURCE,
        include_dirs=(SOURCE,))
    ram_abi_probe = dense_image(
        ram_abi_memory, 0x2000, ram_abi_symbols['PROBE_END'])
    ram_abi_path = OUT / f'{ram_abi_name}.s19'
    ram_abi_lines = [record('0', 0, f'STR8-N {VERSION} RAM ABI'.encode('ascii'))]
    ram_abi_lines.extend(record(
        '1', address,
        ram_abi_probe[address-0x2000:address-0x2000+32])
        for address in range(0x2000, 0x2000+len(ram_abi_probe), 32))
    ram_abi_lines.append(record('9', 0x2000))
    ram_abi_path.write_text('\n'.join(ram_abi_lines) + '\n')
    parsed_ram_abi, ram_abi_entry = read_s19(ram_abi_path)
    assert dense_image(parsed_ram_abi, 0x2000, 0x2000+len(ram_abi_probe)) == ram_abi_probe
    assert ram_abi_entry == 0x2000
    artifacts[ram_abi_path.name] = hashlib.sha256(ram_abi_path.read_bytes()).hexdigest()
    report = dict(milestone='compact-resident', resident_bytes=len(code),
                  resident_start=RESIDENT_START,
                  public_calls={public: resident[public] for public, _, _ in PUBLIC_CALLS},
                  resident_code_bytes=resident['V2_COMMAND_KEYS']-RESIDENT_START,
                  command_table_bytes=resident['V2_TEXT']-resident['V2_COMMAND_KEYS'],
                  text_bytes=len(pool),
                  worker_bytes=len(worker), vector_code_bytes=len(vectors),
                  interrupt_probe_bytes=len(probe), interrupt_probe=probe_symbols,
                  nmi_probe_bytes=len(nmi_probe), nmi_probe=nmi_symbols,
                  native_probe_bytes=len(native_probe), native_probe=native_symbols,
                  acia_probe_bytes=len(acia_probe), acia_probe=acia_symbols,
                  ram_abi_probe_bytes=len(ram_abi_probe), ram_abi_probe=ram_abi_symbols,
                  b3_top_update=updater_symbols,
                  free_before_vectors=0xFFE0-resident['V2_END'],
                  expansion_reserve_start=EXPANSION_RESERVE_START,
                  expansion_reserve_bytes=EXPANSION_RESERVE_SIZE,
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
