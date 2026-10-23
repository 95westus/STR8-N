"""Rehearse the practical resident development kit using offline CPU models.

Default sessions retain source on the host and never use persistent storage.
Optional SRAM tests use separate initialized models. Firmware and boards are
never written; every application and console instruction is from the current
linked firmware, with inherited discovery/delay/SRAM-peripheral fixtures.
"""
import json
from collections import Counter
from pathlib import Path
import re

from test_resident_batch import canonical
from test_resident_contract import ATTEMPTS, parse_s19, sha


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_SHA = 'aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6'


def audited_memory_factory():
    from test_rc1_source_store import Memory

    class BoardDevelopmentMemory(Memory):
        def __init__(self, *args):
            self.auditing = False
            self.io_reads, self.io_writes = Counter(), Counter()
            self.direct_demo_io = []
            super().__init__(*args)

        def observe(self, address, write):
            if self.auditing and 0x7F00 <= address < 0x8000:
                (self.io_writes if write else self.io_reads)[address] += 1
                if 0x0200 <= self.cpu.pc < 0x020E:
                    self.direct_demo_io.append((self.cpu.pc, address, write))

        def __getitem__(self, address):
            if isinstance(address, int):
                self.observe(address, False)
            return super().__getitem__(address)

        def __setitem__(self, address, value):
            self.observe(address, True)
            return super().__setitem__(address, value)

    return BoardDevelopmentMemory


def io_observations(memory):
    assert set(memory.io_reads) <= {0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
    assert set(memory.io_writes) <= {0x7FA0, 0x7FA1, 0x7FE0, 0x7FE1, 0x7FE2, 0x7FE3, 0x7FEC}
    assert not memory.direct_demo_io
    return dict(read_addresses=sorted(memory.io_reads), write_addresses=sorted(memory.io_writes),
                read_counts={format(a, '04X'): n for a, n in memory.io_reads.items()},
                write_counts={format(a, '04X'): n for a, n in memory.io_writes.items()},
                direct_demo_gpio_accesses=0, rtc_i2c_eeprom_chip_select_register_accesses=0,
                monitor_status_writes='$7FA0 LED and $7FA1 PIA control on monitor re-entry; '
                                      '$7FE2 DDRB console initialization. These are monitor instructions, '
                                      'not demo GPIO operations.',
                audit_scope='After initial Harness setup; subsequent ASM/DBG/HOLD/monitor I/O audited')


def listed_records(reply):
    """Independently replay actual decimal LIST rows, preserving their IDs."""
    rows, result = [], bytearray()
    for line in reply.splitlines():
        match = re.fullmatch(r'([1-9][0-9]{0,4}) ([ -~]{1,120})', line)
        if match:
            number, text = int(match[1]), match[2]
            assert 0 < number <= 65535 and (not rows or rows[-1][0] < number)
            raw = text.encode('ascii')
            rows.append((number, text))
            result.extend(number.to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
    assert rows and reply.endswith('ASM> ')
    return rows, canonical(bytes(result))


def symbols(h):
    top = int.from_bytes(h.m.ram[h.asm['SYMTOP']:h.asm['SYMTOP'] + 2], 'little')
    assert 0x4F00 <= top <= 0x6300 and (top - 0x4F00) % 20 == 0
    table = bytes(h.m.ram[0x4F00:top])
    return {table[i:i + 16].rstrip(b'\0').decode('ascii'):
            int.from_bytes(table[i + 16:i + 18], 'little') for i in range(0, len(table), 20)}


def source_matches(h, lane):
    assert canonical(h.source()) == lane['records']


def result_matches(h, lane):
    assert h.m.ram[0x6306] == 1
    length = int.from_bytes(h.m.ram[0x6302:0x6304], 'little')
    origin = int.from_bytes(h.m.ram[0x6304:0x6306], 'little')
    assert length == len(lane['expected']) and origin == lane['origin']
    assert bytes(h.m.ram[0x0200:0x0200 + length]) == lane['expected']
    assert symbols(h) == lane['symbols']
    source_matches(h, lane)


def rehearsal(Harness, cpu_name, slot, edu, kit, out):
    """Accept load_kit's full {'lanes': ..., 'manifest': ...} dictionary.

    out is a fresh/empty profile directory under tmp/ or BUILD/. Only actual
    console captures, transcripts and optional-model reports are written there.
    """
    out = Path(out).resolve()
    assert out.is_relative_to(ROOT) and out.relative_to(ROOT).parts[0].lower() in ('tmp', 'build')
    if out.exists():
        assert out.is_dir() and not any(out.iterdir())
    else:
        out.mkdir(parents=True)
    lanes = kit['lanes']
    assert set(lanes) == {'hello-a', 'hello-b', 'version-fast', 'version-control'}
    for lane in lanes.values():
        assert canonical(lane['records']) == lane['records']
        assert len(lane['records']) <= 7168 and len(lane['symbols']) <= 256
    h = Harness(cpu_name, slot, edu=edu, memory_factory=audited_memory_factory())
    m = h.m
    m.auditing = True
    assert sha(b''.join(bytes(bank) for bank in m.banks[1:])) == FIRMWARE_SHA
    assert h.symbols['core/str8n-v2-vectors']['V2V_RAM_HOLD_ENTRY'] == 0x7E67
    assert h.symbols['core/str8n-v2-vectors']['V2V_RAM_PUTC_ENTRY'] == 0x7E6D
    original_banks, original_sram = list(map(bytes, m.banks)), bytes(m.data)
    captures, checks, runs = {}, [], []
    original_step = h.cpu.step
    demo_active, demo_letter, console_start, console_bytes = False, None, None, []
    demo_entries, demo_instructions = 0, 0

    def step():
        nonlocal console_start, demo_entries, demo_instructions
        pc = h.cpu.pc
        assert not 0x6E00 <= pc < 0x707C, 'Logical VERSION code must never execute in this rehearsal'
        if 0x0200 <= pc < 0x3300:
            assert demo_active and 0x0200 <= pc < 0x020E, 'Only the reviewed RAM demo may execute'
            demo_instructions += 1
            if pc == 0x0200:
                demo_entries += 1
        if demo_active and pc == 0x7E6D:
            lo, hi = (h.cpu.sp + 1) & 255, (h.cpu.sp + 2) & 255
            return_word = m.ram[0x100 + lo] | m.ram[0x100 + hi] << 8
            if return_word == 0x0208:
                assert h.cpu.a == demo_letter
                assert console_start is None
                console_start = len(m.tx)
        if demo_active and pc == 0x0209 and console_start is not None:
            emitted = bytes(m.tx[console_start:])
            assert emitted == bytes([demo_letter])
            console_bytes.append(emitted.decode('ascii'))
            console_start = None
        original_step()

    h.cpu.step = step

    def save_capture(name, kind, text):
        filename = name + '.' + kind + '.txt'
        raw = text.encode('ascii')
        with (out / filename).open('xb') as stream:
            stream.write(raw)
        captures.setdefault(name, {})[kind] = dict(file=filename, bytes=len(raw), sha256=sha(raw))

    def assemble(lane):
        h.command('ASM', contains='OK ')
        result_matches(h, lane)

    def capture(name, lane, listing=True):
        result_matches(h, lane)
        reply = h.command('LIST')
        _, recovered = listed_records(reply)
        assert recovered == lane['records']
        save_capture(name, 'list', reply)
        if listing:
            reply = h.command('LST')
            result_matches(h, lane)
            assert '0200' in reply if lane['origin'] == 0x0200 else '6E00' in reply
            save_capture(name, 'lst', reply)
        reply = h.command('SYMS')
        assert all(name in reply for name in lane['symbols'])
        save_capture(name, 'syms', reply)
        reply = h.command('S19')
        cells, entry = parse_s19(reply)
        assert cells == dict(enumerate(lane['expected'], lane['origin'])) and entry == lane['origin']
        save_capture(name, 's19', reply)
        result_matches(h, lane)

    def execute_demo(name, lane, letter):
        nonlocal demo_active, demo_letter
        h.command('QUIT', context='monitor')
        assert m.bank == 3
        demo_active, demo_letter = True, ord(letter)
        start_console = len(console_bytes)
        ready = h.command('G 0200', context='debug', contains='PC=0206')
        assert 'A=' + format(ord(letter), '02X') in ready
        registers_before = bytes(m.ram[0x7000:0x7007])
        program_before, executed_before = bytes(m.ram[0x0200:0x020E]), demo_instructions
        register_reply = h.command('R', context='debug', contains='PC=0206')
        disassembly = h.command('U 0206 03', context='debug', contains='0206')
        assert 'JSR' in disassembly and 'BRK' in disassembly and 'JMP' in disassembly
        assert bytes(m.ram[0x7000:0x7007]) == registers_before
        assert bytes(m.ram[0x0200:0x020E]) == program_before and demo_instructions == executed_before
        next_reply = h.command('N', context='debug', contains='PC=0209')
        assert console_bytes[start_console:] == [letter]
        second_break = h.command('C', context='debug', contains='PC=020B')
        returned = h.command('C', context='monitor', contains='B3> ')
        demo_active = False
        assert m.bank == 3 and list(map(bytes, m.banks)) == original_banks
        runs.append(dict(lane=name, letter=letter, entry=lane['entry'], ready_pc=0x0206,
                         next_pc=0x0209, second_break_pc=0x020B, console_bytes=letter,
                         return_path='Continued JMP HOLD $7E67 to validated running monitor',
                         inspection_commands=['R', 'U 0206 03'], inspection_preserved_guest_state=True,
                         register_output_sha256=sha(register_reply.encode('ascii')),
                         disassembly_output_sha256=sha(disassembly.encode('ascii')),
                         ready_output_sha256=sha(ready.encode('ascii')),
                         next_output_sha256=sha(next_reply.encode('ascii')),
                         second_break_output_sha256=sha(second_break.encode('ascii')),
                         monitor_output_sha256=sha(returned.encode('ascii'))))

    try:
        h.open()
        h.command_limit = 30000000
        assert h.source() == b'' and m.ram[0x6306] == 0 and m.ram[0x6310] == 0
        hello_a, hello_b = lanes['hello-a'], lanes['hello-b']
        h.command(hello_a['paste'].decode('ascii').rstrip('\r'))
        source_matches(h, hello_a)
        assert m.ram[0x6306] == 0 and m.ram[0x6310] == 1
        h.command('85 LDA #MISSING')
        diagnostic = h.command('ASM', contains='Undefined symbol')
        assert 'MISSING' in diagnostic and '85' in diagnostic and not m.ram[0x6306]
        assert 'Assemble successfully first' in h.command('LST')
        assert 'Assemble successfully first' in h.command('S19')
        save_capture('diagnostic', 'error', diagnostic)
        h.command('85')
        source_matches(h, hello_a)
        assemble(hello_a)
        capture('hello-a', hello_a)
        checks.append('undefined-symbol-diagnostic-repair-and-result-invalidation')
        hello_list = (out / 'hello-a.list.txt').read_bytes().decode('ascii')
        execute_demo('hello-a', hello_a, 'A')

        h.command('ASM', contains='STR8-N ASM')
        assert h.source() == b'' and not m.ram[0x6306]
        # Fresh entry clears the editor. Restore original numbered LIST rows,
        # rather than assuming that source survives application re-entry.
        rows, recovered = listed_records(hello_list)
        assert recovered == hello_a['records']
        for number, text in rows:
            h.command(str(number) + ' ' + text)
        source_matches(h, hello_a)
        replayed = h.command('LIST')
        assert listed_records(replayed)[1] == hello_a['records']
        save_capture('hello-a-replayed', 'list', replayed)
        assert hello_a['lines'][3] == 'CHAR EQU $41' and hello_b['lines'][3] == 'CHAR EQU $42'
        h.command('40 ' + hello_b['lines'][3])
        source_matches(h, hello_b)
        assert not m.ram[0x6306] and m.ram[0x6310] == 1
        assert 'Assemble successfully first' in h.command('S19')
        assemble(hello_b)
        capture('hello-b', hello_b)
        execute_demo('hello-b', hello_b, 'B')
        checks.append('capture-before-quit-fresh-editor-host-list-replay-edit-rebuild-and-rerun')

        h.command('ASM', contains='STR8-N ASM')
        assert h.source() == b''
        fast, control = lanes['version-fast'], lanes['version-control']
        h.command(fast['paste'].decode('ascii').rstrip('\r'))
        source_matches(h, fast)
        assemble(fast)
        capture('version-fast', fast)
        change = [i for i, (a, b) in enumerate(zip(fast['lines'], control['lines'])) if a != b]
        assert len(fast['lines']) == len(control['lines']) and len(change) == 1
        index = change[0]
        assert fast['lines'][index] == 'JSR BN_SHOW_CACHED' and control['lines'][index] == 'JSR BN_SHOW'
        h.command(str((index + 1) * 10) + ' ' + control['lines'][index])
        source_matches(h, control)
        assert not m.ram[0x6306]
        assemble(control)
        capture('version-control', control, listing=False)
        h.command(str((index + 1) * 10) + ' ' + fast['lines'][index])
        source_matches(h, fast)
        assemble(fast)
        capture('version-fast-restored', fast, listing=False)
        checks.append('resident-version-fast-control-fast-edit-compile-export-without-execution')
        h.command('QUIT', context='monitor')
    finally:
        h.cpu.step = original_step
    assert demo_entries == 2 and console_bytes == ['A', 'B']
    assert list(map(bytes, m.banks)) == original_banks and not m.flash_writes
    assert bytes(m.data) == original_sram and not m.transfers
    assert not ATTEMPTS
    (out / 'transcripts.json').write_text(json.dumps(h.transcripts, indent=2) + '\n', encoding='utf-8')
    optional = storage_checks(Harness, cpu_name, slot, edu, lanes['hello-a'], lanes['hello-b'])
    (out / 'optional-sram-transcripts.json').write_text(json.dumps(optional.pop('transcripts'), indent=2) + '\n', encoding='utf-8')
    return dict(passed=True, cpu=cpu_name, slot=slot, edu=edu, firmware_sha256=FIRMWARE_SHA,
                board_access=False, serial_ports_opened=0, network_attempts=0, hardware_qualified=False,
                captures=captures, checks=checks, demo_runs=runs, actual_console_bytes='AB',
                application_reentry_clears_source=True, host_list_replay_preserved_line_ids=True,
                full_version_output_executed=False, executable_store_used=False, flash_source_save_used=False,
                default_sram_unchanged=True, default_sram_transfers=0, optional_sram=optional,
                capacity={name: dict(source_bytes=len(lane['records']), source_capacity=7168,
                                     source_bytes_free=7168 - len(lane['records']),
                                     symbols=len(lane['symbols']), symbol_capacity=256,
                                     output_bytes=len(lane['expected']), output_capacity=12544)
                          for name, lane in lanes.items()},
                all_four_modeled_flash_banks_unchanged=True, flash_writes=0,
                io=io_observations(m),
                transcript_count=len(h.transcripts), transcript_file='transcripts.json',
                model_scope='Actual monitor/ASM/DBG instructions, FT245 and optional initialized SRAM '
                            'models; inherited discovery/delay shortcuts. Only the reviewed14-byte demo '
                            'executes at0200. VERSION exports are assembled and captured, never executed. '
                            'No physical board or reset-vector qualification.')


def storage_checks(Harness, cpu_name, slot, edu, hello_a, hello_b):
    """Optional source persistence in a separate model, never the default lane."""
    h = Harness(cpu_name, slot, edu=edu, memory_factory=audited_memory_factory())
    h.m.auditing = True
    banks, data = list(map(bytes, h.m.banks)), bytes(h.m.data)
    h.open()
    h.command(hello_a['paste'].decode('ascii').rstrip('\r'))
    h.command('ASM', contains='OK ')
    result_matches(h, hello_a)
    answer = h.command('SAVE SRAM HELLO_A')
    assert not h.m.ram[0x6306]
    source_matches(h, hello_a)
    assert 'Assemble successfully first' in h.command('S19')
    if edu:
        assert 'Source saved' in answer and h.m.ram[0x6310] == 0
        _, saved = h.latest('HELLO_A')
        assert saved[:4] == b'AS\x01\x08' and saved[8:] == hello_a['records']
        h.command('40 ' + hello_b['lines'][3])
        h.command('ASM', contains='OK ')
        result_matches(h, hello_b)
        h.command('LOAD SRAM HELLO_A\rNO', contains='Load cancelled')
        result_matches(h, hello_b)
        assert h.m.ram[0x6310] == 1
        h.command('LOAD SRAM HELLO_A\rYES', contains='Source loaded')
        source_matches(h, hello_a)
        assert not h.m.ram[0x6306] and h.m.ram[0x6310] == 0
        assert 'Assemble successfully first' in h.command('S19')
        h.command('ASM', contains='OK ')
        result_matches(h, hello_a)
        assert bytes(h.m.data) != data and h.m.transfers
    else:
        assert 'Source storage:' in answer and not h.m.transfers and bytes(h.m.data) == data
        h.command('ASM', contains='OK ')
        result_matches(h, hello_a)
    assert list(map(bytes, h.m.banks)) == banks and not h.m.flash_writes
    return dict(passed=True, separate_initialized_model=True, source_save_load_exercised=edu,
                bare_refusal_exercised=not edu, source_preserved=True,
                dirty_no_cancel_preserved_valid_result=edu, dirty_yes_replaced_source_and_invalidated=edu,
                reassembly_required_after_source_operation=True, source_capsule='AS/1',
                modeled_sram_capacity_bytes=len(h.m.data) if edu else None,
                modeled_sram_capacity_is_not_board_measurement=True,
                transfers=len(h.m.transfers), flash_writes=0, no_format_reclaim_or_executable_store=True,
                io=io_observations(h.m),
                transcripts=h.transcripts)
