"""Verify the separate VERSION tail-call candidate using offline CPU models.

Imported by the Phase-10 proof. No import-time actions or physical interfaces.
The complete-command model validates the unchanged sealed asset before replacing
its RAM body. An additional explicitly stubbed BN_SHOW probe stresses the tail.
"""
import hashlib

from test_resident_version_runtime import fixtures


ORIGIN, ENTRY, LENGTH, PATCH = 0x6E00, 0x6E04, 636, 0x705C
JOURNAL = 0x9C00
ALIASES = {'BOOT_CHOICE_SLOT': 'BOOT_CHOICE'}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def normalized_ram(memory, sp):
    """Keep pointers, private data and live caller stack in the exact comparison."""
    result = bytearray(memory.ram)
    result[PATCH] = 0
    # Returned calls may leave different, inactive return addresses. The live
    # caller frames above final SP remain in the byte-for-byte RAM comparison.
    assert 0 <= sp <= 255
    result[0x100:0x101 + sp] = bytes(sp + 1)
    return bytes(result)


def candidate_checks(Harness, cpu_name, slot, edu, baseline_body, candidate_body,
                     baseline_symbols, candidate_symbols):
    """Compare real full commands and callable BN_READ executions.

    All output, registers, pointer/private RAM, live stack frames, bank state and
    I/O sets must match exactly. Timing differences are reported separately.
    """
    from test_rc1_source_store import Memory

    class CandidateAuditMemory(Memory):
        def __init__(self, *args):
            self.auditing = False
            self.io_reads, self.io_writes = set(), set()
            super().__init__(*args)

        def __getitem__(self, address):
            if self.auditing and isinstance(address, int) and 0x7F00 <= address < 0x8000:
                self.io_reads.add(address)
            return super().__getitem__(address)

        def __setitem__(self, address, value):
            if self.auditing and 0x7F00 <= address < 0x8000:
                self.io_writes.add(address)
            return super().__setitem__(address, value)

    assert len(baseline_body) == len(candidate_body) == LENGTH
    assert baseline_symbols == candidate_symbols
    assert baseline_symbols['START'] == ORIGIN and baseline_symbols['APP_END'] == ORIGIN + LENGTH
    assert [(ORIGIN + i, a, b) for i, (a, b) in enumerate(zip(baseline_body, candidate_body))
            if a != b] == [(PATCH, 0x20, 0x4C)]
    registers = ('pc', 'sp', 'p', 'a', 'x', 'y')
    if cpu_name == '65c816-e':
        registers += ('b', 'mode', 'pbr', 'dbr', 'dpr')

    def symbol(name):
        if name in baseline_symbols:
            return baseline_symbols[name]
        return baseline_symbols[ALIASES[name]]

    def execute(body, fixture, scope, active=None):
        h = Harness(cpu_name, slot, edu=edu, memory_factory=CandidateAuditMemory)
        m, cpu = h.m, h.cpu
        assert h.symbols['version/version']['APP_END'] == ORIGIN + LENGTH
        m.ram[0x7D0F:0x7D11] = bytes.fromhex('06ef')
        m.ram[0x7D27] = 1 if edu else 2
        m.banks[3][JOURNAL - 0x8000:JOURNAL - 0x8000 + 1024] = fixture['journal']
        original_banks, original_sram = list(map(bytes, m.banks)), bytes(m.data)
        original_pcr, original_bank = m.ram[0x7FEC], m.bank
        original_active, original_selected = m.ram[0x7D30], m.ram[0xF3]
        original_sp = cpu.sp
        start_steps, start_cycles = h.steps, cpu.processorCycles
        counters = dict(entry=0, BN_READ=0, TZ_CRC=0, BOOT_SELECT=0,
                        BOOT_SLOT_CHECK=0, BOOT_CHOICE_SLOT=0)
        addresses = {symbol(name): name for name in counters if name != 'entry'}
        tail_reached, entry_sp = 0, None
        original_step = cpu.step

        def step():
            nonlocal tail_reached, entry_sp
            if scope in ('full-command', 'invalid-active-command-body') and cpu.pc == ENTRY:
                counters['entry'] += 1
                assert counters['entry'] == 1
                entry_sp = cpu.sp
                assert m.bank == 3 and m.ram[ORIGIN:ORIGIN + LENGTH] == baseline_body
                assert m.ram[0x7D2B] == 7 and m.ram[0xF3] == original_selected
                # The actual original asset and seal have already validated.
                # Only this CPU model's application RAM receives the candidate.
                m.ram[ORIGIN:ORIGIN + LENGTH] = body
                if active is not None:
                    m.ram[0x7D30] = active
            name = addresses.get(cpu.pc)
            if name is not None:
                counters[name] += 1
            if scope == 'BN_READ':
                assert ORIGIN <= cpu.pc < ORIGIN + LENGTH
            if cpu.pc == PATCH:
                tail_reached += 1
            assert not 0x0200 <= cpu.pc < 0x3300, 'Physical assembler output must never execute'
            original_step()

        cpu.step = step
        m.auditing = True
        try:
            if scope in ('full-command', 'invalid-active-command-body'):
                if scope == 'full-command':
                    output = h.command('VERSION', context='monitor')
                else:
                    # An invalid BOOT_ACTIVE is outside the monitor return ABI:
                    # its loader later derives a bad return address from it.
                    # Exercise the existing INVALID display, then stop before
                    # VERSION's final RTS rather than pretending monitor return
                    # is supported for this deliberately malformed state.
                    assert active not in (None, 0xA0, 0xB0)
                    start_output = len(m.tx)
                    m.rx.extend(b'VERSION\r')
                    final_rts = baseline_symbols['SLOT_LETTER'] - 1
                    assert body[final_rts - ORIGIN:final_rts - ORIGIN + 2] == b'\x60\xC9'
                    h.run(lambda: counters['entry'] == 1 and cpu.pc == final_rts)
                    output = bytes(m.tx[start_output:]).decode('ascii')
                    assert cpu.sp == entry_sp and cpu.p & 1
                assert counters['entry'] == counters['BOOT_SELECT'] == 1
                assert counters['BOOT_CHOICE_SLOT'] == 2
                valid_running = active is None or active in (0xA0, 0xB0)
                assert counters['BOOT_SLOT_CHECK'] == (4 if valid_running else 3), counters
                assert counters['BN_READ'] == ((2 if fixture['selected'] else 1) if valid_running else 0)
                if valid_running:
                    expected_cpu = '65C816' if cpu_name == '65c816-e' else '65C02'
                    name = fixture['selected'].decode('ascii') if fixture['selected'] else 'unnamed'
                    assert 'STR8-N 2.0rc1 B3 ' + expected_cpu + '\r\n' in output
                    assert 'ABI 65C02 | 816E | 816N-VEC\r\n' in output
                    assert 'Board: ' + name + '\r\n' in output
                    assert 'Running: MONITOR ' + slot + ', gen 00000032\r\n' in output
                else:
                    assert 'Running monitor: INVALID\r\n' in output and 'Board: ' not in output
                assert 'MONITOR A gen 00000032 VALID default\r\n' in output
                assert 'MONITOR B gen 00000032 VALID\r\n' in output
                if scope == 'full-command':
                    assert output.endswith('B3> ') and cpu.sp == original_sp
                else:
                    assert output.endswith('\r\n') and not output.endswith('B3> ')
            else:
                assert scope == 'BN_READ'
                m.ram[ORIGIN:ORIGIN + LENGTH] = body
                cpu.stPushWord(0x7AFF)
                cpu.pc = baseline_symbols['BN_READ']
                h.run(lambda: cpu.pc == 0x7B00)
                output = ''
                assert counters['entry'] == 0 and counters['BN_READ'] == 1
                assert cpu.sp == original_sp
        finally:
            m.auditing = False
            cpu.step = original_step

        length = m.ram[baseline_symbols['BN_LENGTH']]
        selected = bytes(m.ram[baseline_symbols['BN_TEXT']:baseline_symbols['BN_TEXT'] + length])
        sequence = int.from_bytes(m.ram[baseline_symbols['BN_SEQ']:baseline_symbols['BN_SEQ'] + 4], 'little')
        free = int.from_bytes(m.ram[baseline_symbols['BN_FREE']:baseline_symbols['BN_FREE'] + 2], 'little')
        if scope == 'BN_READ' or active is None:
            assert selected == fixture['selected'] and sequence == fixture['sequence']
            assert free == fixture['free'] if fixture['free'] else free >> 8 == 0
        assert original_banks == list(map(bytes, m.banks)) and not m.flash_writes
        assert bytes(m.data) == original_sram and not m.transfers
        assert (m.ram[0x7FEC], m.bank) == (original_pcr, original_bank)
        expected_active = original_active if active is None else active
        assert (m.ram[0x7D30], m.ram[0xF3]) == (expected_active, original_selected)
        assert m.io_reads <= {0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        assert m.io_writes <= {0x7FA0, 0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        if scope == 'BN_READ':
            assert m.io_reads == {0x7FEC} and m.io_writes == {0x7FEC}
        if cpu_name == '65c816-e':
            assert cpu.b == 0xA5 and cpu.mode == 1 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        comparison_ram = normalized_ram(m, cpu.sp)
        public = dict(output=output, output_sha256=digest(output.encode('ascii')),
                      normalized_ram_sha256=digest(comparison_ram),
                      registers={name: getattr(cpu, name) for name in registers}, calls=counters,
                      bank=m.bank, pcr=m.ram[0x7FEC], boot_active=m.ram[0x7D30],
                      selected_bank=m.ram[0xF3], selected_name=selected.decode('ascii'),
                      sequence=sequence, free_slot=free if free >> 8 else None,
                      io_reads=sorted(m.io_reads), io_writes=sorted(m.io_writes),
                      sram_sha256=digest(bytes(m.data)), banks_sha256=[digest(bytes(bank)) for bank in m.banks])
        return dict(public=public, ram_sha256=digest(bytes(m.ram)),
                    steps=h.steps - start_steps, processor_cycles=cpu.processorCycles - start_cycles,
                    normalized_ram=comparison_ram, tail_reached=tail_reached,
                    all_banks_unchanged=True, sram_unchanged=True, live_caller_stack_compared=True,
                    flash_writes=0, sram_transfers=0)

    rows = []

    def pair(fixture, scope, active=None):
        host = execute(baseline_body, fixture, scope, active)
        candidate = execute(candidate_body, fixture, scope, active)
        if host['public'] != candidate['public']:
            differences = [(hex(i), a, b) for i, (a, b) in enumerate(
                zip(host['normalized_ram'], candidate['normalized_ram'])) if a != b]
            raise AssertionError((cpu_name, slot, edu, scope, fixture['name'], active,
                                  'public behavior differs', differences[:30], host['public'], candidate['public']))
        host.pop('normalized_ram')
        candidate.pop('normalized_ram')
        reached = int(scope == 'full-command' and active is None and bool(fixture['selected']))
        assert host['tail_reached'] == candidate['tail_reached'] == reached
        assert candidate['steps'] - host['steps'] == -reached
        assert candidate['processor_cycles'] - host['processor_cycles'] == -9 * reached
        rows.append(dict(name=fixture['name'], scope=scope, passed=True,
                         baseline_candidate_public_behavior_equal=True, active_override=active,
                         journal_sha256=digest(fixture['journal']),
                         instruction_delta=candidate['steps'] - host['steps'],
                         processor_cycle_delta=candidate['processor_cycles'] - host['processor_cycles'],
                         baseline=host, candidate=candidate))

    journal_fixtures = fixtures()
    for scope in ('full-command', 'BN_READ'):
        for fixture in journal_fixtures:
            if scope == 'full-command':
                if not fixture['full']:
                    continue
                if (slot, edu) != ('A', False) and fixture['name'] not in (
                        'unnamed-blank-journal', 'eight-character-name-max-sequence'):
                    continue
            pair(fixture, scope)
    if (slot, edu) == ('A', False):
        for active in (0, 0xFF):
            pair(journal_fixtures[0], 'invalid-active-command-body', active)
    full = [row for row in rows if row['scope'] == 'full-command']
    readers = [row for row in rows if row['scope'] == 'BN_READ']
    tail = tail_checks(Harness, cpu_name, baseline_body, candidate_body, baseline_symbols) \
        if (slot, edu) == ('A', False) else None
    return dict(passed=True, case_count=len(rows), full_command_pairs=len(full),
                board_name_reader_pairs=len(readers),
                invalid_active_command_body_pairs=sum(row['scope'] == 'invalid-active-command-body' for row in rows),
                baseline_and_candidate_executions=2 * len(rows),
                comparison='Exact public output, all registers and all RAM except the one candidate opcode '
                           'and inactive stack cells. Private data, pointers and live caller frames match exactly.',
                normalization={'candidate_opcode': PATCH,
                               'inactive_stack': '$0100 through $0100+final SP inclusive',
                               'live_stack': 'Every byte above final SP compared exactly'},
                discovery_fixture={'banner_pointer': 0xEF06, 'mode': 1 if edu else 2,
                                   'inherited_hardware_discovery_skipped_at': 0xE014},
                model_scope='Actual linked monitor/loader/CRC/VERSION/bootstrap/FT245 instructions; inherited '
                            'discovery/delay shortcuts. Candidate replaces only modeled RAM after the original '
                            'sealed asset validates. Invalid ACTIVE00/FF cases stop before VERSION final RTS '
                            '(outside the monitor return ABI); separate callable BN_READ probes. No RTC/I2C/EEPROM/SRAM '
                            'transfer or physical board access.',
                timing_scope='CPU-model processorCycles and Harness instruction counts; changed tail saves '
                             'nine modeled cycles and one instruction when reached. Unreached paths are unchanged.',
                all_banks_unchanged=True, sram_unchanged=True, flash_writes=0, sram_transfers=0,
                tail_probe=tail, cases=rows)


def tail_checks(Harness, cpu_name, baseline_body, candidate_body, symbols):
    """Stress actual BN_SHOW code with explicit BN_READ/console/newline stubs.

    Real full-command checks above cover the actual services. Here stable stubs
    retain arbitrary incoming status flags so the tail's return semantics can be
    checked across lengths 0..8, including states outside the admitted ABI.
    """
    h = Harness(cpu_name, 'A', edu=False)
    m, cpu = h.m, h.cpu
    initial_ram, initial_bank = bytes(m.ram), m.bank
    initial_banks, initial_sram = list(map(bytes, m.banks)), bytes(m.data)
    original_sp = cpu.sp
    registers = ('pc', 'sp', 'p', 'a', 'x', 'y')
    if cpu_name == '65c816-e':
        registers += ('b', 'mode', 'pbr', 'dbr', 'dpr')
    initial_registers = {name: getattr(cpu, name) for name in registers}
    statuses = [p for p in range(256) if cpu_name != '65c816-e' or p & 0x30 == 0x30]
    name = b'A!~3xyz9'

    def execute(body, length, status):
        m.ram[:] = initial_ram
        m.bank = initial_bank
        m.ram[ORIGIN:ORIGIN + LENGTH] = body
        for key, value in initial_registers.items():
            setattr(cpu, key, value)
        cpu.a, cpu.x, cpu.y, cpu.p = 0x5A, 0xA6, 0x39, status
        cpu.processorCycles = 0
        cpu.stPushWord(0x7AFF)
        cpu.pc = symbols['BN_SHOW']
        output, instructions, calls, newline_sp = bytearray(), 0, 0, []
        while cpu.pc != 0x7B00:
            instructions += 1
            assert instructions < 300
            if cpu.pc == symbols['BN_READ']:
                calls += 1
                m.ram[symbols['BN_LENGTH']] = length
                m.ram[symbols['BN_TEXT']:symbols['BN_TEXT'] + 8] = name
                cpu.pc = (cpu.stPopWord() + 1) & 65535
                cpu.processorCycles += 6  # Explicit modeled RTS stub.
            elif cpu.pc in (0x7E6D, 0x7E7F):
                if cpu.pc == 0x7E6D:
                    output.append(cpu.a)
                else:
                    newline_sp.append(cpu.sp)
                    output.extend(b'\r\n')
                cpu.pc = (cpu.stPopWord() + 1) & 65535
                cpu.processorCycles += 6  # Preserve registers/status, then RTS.
            else:
                assert ORIGIN <= cpu.pc < ORIGIN + LENGTH
                cpu.step()
        assert cpu.sp == original_sp and calls == 1
        assert output == (b'Board: ' + name[:length] + b'\r\n' if length else b'')
        assert len(newline_sp) == int(length != 0)
        assert initial_banks == list(map(bytes, m.banks)) and not m.flash_writes
        assert bytes(m.data) == initial_sram and not m.transfers
        assert m.bank == initial_bank
        if cpu_name == '65c816-e':
            assert cpu.b == 0xA5 and cpu.mode == 1 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        return dict(registers={key: getattr(cpu, key) for key in registers}, output=bytes(output),
                    ram=normalized_ram(m, cpu.sp), instructions=instructions,
                    cycles=cpu.processorCycles, newline_sp=newline_sp)

    rows = []
    for length in range(9):
        for status in statuses:
            host = execute(baseline_body, length, status)
            candidate = execute(candidate_body, length, status)
            assert host['registers'] == candidate['registers']
            assert host['output'] == candidate['output'] and host['ram'] == candidate['ram']
            assert candidate['instructions'] - host['instructions'] == (-1 if length else 0)
            assert candidate['cycles'] - host['cycles'] == (-9 if length else 0)
            if length:
                assert candidate['newline_sp'][0] == (host['newline_sp'][0] + 2) & 255
            rows.append(dict(length=length, input_status=status, passed=True,
                             admitted_irq_disabled_decimal_clear=bool(status & 4) and not status & 8,
                             public_registers_equal=True, ram_equal_except_opcode_and_inactive_stack=True,
                             output_sha256=digest(candidate['output']),
                             normalized_ram_sha256=digest(candidate['ram']),
                             baseline_instructions=host['instructions'],
                             candidate_instructions=candidate['instructions'],
                             instruction_delta=candidate['instructions'] - host['instructions'],
                             baseline_processor_cycles=host['cycles'], candidate_processor_cycles=candidate['cycles'],
                             processor_cycle_delta=candidate['cycles'] - host['cycles'],
                             baseline_newline_sp=host['newline_sp'], candidate_newline_sp=candidate['newline_sp'],
                             final_sp=candidate['registers']['sp']))
    return dict(passed=True, pair_count=len(rows), executions=2 * len(rows), lengths=list(range(9)),
                unique_input_status_values=len(statuses),
                admitted_subset_pairs=sum(row['admitted_irq_disabled_decimal_clear'] for row in rows),
                status_scope='65C02: 256 raw CPU-model P values; 65C816 E=1: 64 unique legal '
                             'values with M/X forced high. Includes out-of-ABI I/D stress flags.',
                stub_scope='BN_READ sets selected length/text, then RTS; console appends A, newline appends '
                           'CRLF, then RTS; all preserve registers/status. Other BN_SHOW/PRINT instructions '
                           'execute unchanged. Stubs are separate from real-service full-command fixtures.',
                stack_result='Named path has one fewer pending return frame (two stack bytes) during '
                             'newline; final SP and live caller frames match. No whole-command peak claim.',
                all_banks_unchanged=True, sram_unchanged=True, flash_writes=0, sram_transfers=0, cases=rows)
