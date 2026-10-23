"""Verify the cached VERSION display candidate using actual offline ROM images.

The unchanged Harness supplies monitor initialization and discovery/delay models.
The linked loader copies, CRC-checks and enters the selected ROM asset. No
application bytes are injected into RAM. Journal stability is an explicit model
fixture; IRQ state alone is not claimed to exclude an external/NMI writer.
"""
from collections import Counter
from pathlib import Path

from str8build.formats import crc
from str8build.images import version_asset
from test_resident_version_runtime import fixtures
from test_resident_version_candidate_runtime import digest, normalized_ram


ASSET_FIRST, ASSET_END = 0xF800, 0x10000
ORIGIN, ENTRY, SIZE = 0x6E00, 0x6E04, 636
CALL, CALL_OPERAND, CACHED, TAIL = 0x6E5E, 0x6E5F, 0x7047, 0x705C
FIRST_READ_RETURN, JOURNAL, PCR = 0x6E59, 0x9C00, 0x7FEC
SEAL_OFFSETS = (0x7F6, 0x7F7)
PHASE10_BODY_SHA = '04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7'
WORKING = {'RUNNING_SLOT': 1, 'MON_CALL': 2, 'TZ_SUM': 2, 'BN_LENGTH': 1,
           'BN_WORK': 1, 'BN_TEXT': 8, 'BN_SEQ': 4, 'BN_FREE': 2}


def cached_checks(Harness, cpu_name, slot, edu, baseline_firmware,
                  candidate_firmware, baseline_body, candidate_body, symbols):
    """Compare all journal cases on A/bare, representative cases elsewhere."""
    from test_rc1_source_store import Memory

    assert len(baseline_firmware) == len(candidate_firmware) == 98304
    assert len(baseline_body) == len(candidate_body) == SIZE
    assert symbols['START'] == ORIGIN and symbols['APP_END'] == ORIGIN + SIZE
    assert symbols['BN_SHOW_CACHED'] == CACHED and symbols['BN_SHOW'] == 0x703F
    assert [(ORIGIN + i, a, b) for i, (a, b) in enumerate(zip(baseline_body, candidate_body)) if a != b] == [
        (CALL_OPERAND, 0x3F, 0x47), (TAIL, 0x20, 0x4C)]
    expected_image_differences = {ASSET_FIRST + address - ORIGIN for address in (CALL_OPERAND, TAIL)}
    expected_image_differences.update(ASSET_FIRST + offset for offset in SEAL_OFFSETS)
    assert {i for i, (a, b) in enumerate(zip(baseline_firmware, candidate_firmware)) if a != b} == expected_image_differences
    for image, body in ((baseline_firmware, baseline_body), (candidate_firmware, candidate_body)):
        assert image[ASSET_FIRST:ASSET_FIRST + SIZE] == body
        assert crc(image[ASSET_FIRST:ASSET_END]) == 0
    phase10 = (Path(__file__).resolve().parents[1] / 'tests/baselines/phase10-evidence/resident.bin').read_bytes()
    assert digest(phase10) == PHASE10_BODY_SHA
    assert [(ORIGIN + i, a, b) for i, (a, b) in enumerate(zip(phase10, candidate_body)) if a != b] == [
        (CALL_OPERAND, 0x3F, 0x47)]
    assert candidate_body[symbols['BN_SHOW'] - ORIGIN:] == phase10[symbols['BN_SHOW'] - ORIGIN:]
    register_names = ('pc', 'sp', 'p', 'a', 'x', 'y')
    if cpu_name == '65c816-e':
        register_names += ('b', 'mode', 'pbr', 'dbr', 'dpr')

    def memory_factory(selected_image):
        class CachedMemory(Memory):
            def __init__(self, image, data=None):
                assert image == baseline_firmware
                self.auditing = False
                self.io_reads, self.io_writes = Counter(), Counter()
                super().__init__(selected_image, data)

            def __getitem__(self, address):
                if self.auditing and isinstance(address, int) and 0x7F00 <= address < 0x8000:
                    self.io_reads[address] += 1
                return super().__getitem__(address)

            def __setitem__(self, address, value):
                if self.auditing and 0x7F00 <= address < 0x8000:
                    self.io_writes[address] += 1
                return super().__setitem__(address, value)

        CachedMemory.__name__ = 'CachedMemory_' + digest(selected_image)
        return CachedMemory

    def execute(image, body, fixture, candidate, refusal=None):
        h = Harness(cpu_name, slot, edu=edu, memory_factory=memory_factory(image))
        m, cpu = h.m, h.cpu
        loader = h.symbols['loader/version-loader']
        asset = image[ASSET_FIRST:ASSET_END]
        m.ram[0x7D0F:0x7D11] = bytes.fromhex('06ef')
        m.ram[0x7D27] = 1 if edu else 2
        m.banks[3][JOURNAL - 0x8000:JOURNAL - 0x8000 + 1024] = fixture['journal']
        original_banks, original_sram = list(map(bytes, m.banks)), bytes(m.data)
        original_pcr, original_bank = m.ram[PCR], m.bank
        original_active, original_selected, original_sp = m.ram[0x7D30], m.ram[0xF3], cpu.sp
        start_steps, start_cycles = h.steps, cpu.processorCycles
        counts = dict(entry=0, crc_init=0, crc_byte=0, header_check=0, loader_bad=0,
                      storage_asset_fail=0, BN_READ=0, BN_SHOW=0, cached_entry=0,
                      cached_direct_entry=0, tail=0, first_read_return=0, final_rts=0)
        watched = {loader['AP_CRC_INIT']: 'crc_init', loader['AP_CRC_BYTE']: 'crc_byte',
                   loader['HEADER']: 'header_check', loader['BAD']: 'loader_bad',
                   loader['STORAGE_ASSET_FAIL']: 'storage_asset_fail',
                   symbols['BN_READ']: 'BN_READ', symbols['BN_SHOW']: 'BN_SHOW', TAIL: 'tail'}
        timings, first_state = {}, None
        loader_active, stable_guard, previous_pc = False, False, None
        original_step = cpu.step

        def working_state():
            return {name: bytes(m.ram[symbols[name]:symbols[name] + length]).hex()
                    for name, length in WORKING.items()} | {'TZ_PTR': bytes(m.ram[0xD6:0xD8]).hex()}

        def step():
            nonlocal loader_active, stable_guard, previous_pc, first_state
            if stable_guard:
                assert cpu.p & 4 and not m.flash_writes and not m.transfers
            if cpu.pc == loader['LOAD']:
                assert cpu.a == 7
                loader_active = True
            if cpu.pc == ENTRY:
                counts['entry'] += 1
                assert counts['entry'] == 1 and refusal is None
                assert cpu.p & 4 and m.bank == 3 and m.ram[0x7D2B] == 7
                assert m.ram[ORIGIN:ORIGIN + len(asset)] == asset
                assert m.ram[ORIGIN:ORIGIN + SIZE] == body
                assert m.ram[0xF3] == original_selected and m.ram[0x7D38:0x7D3A] == b'\0\0'
                timings['entry'] = (h.steps, cpu.processorCycles)
                loader_active = False
                stable_guard = candidate and bool(fixture['selected'])
            label = watched.get(cpu.pc)
            if label and (label not in ('crc_init', 'crc_byte', 'header_check') or loader_active):
                counts[label] += 1
                if label == 'BN_READ' and counts[label] == 1:
                    timings['first_read_entry'] = (h.steps, cpu.processorCycles)
            if label == 'loader_bad':
                loader_active = False
            if counts['entry'] and cpu.pc == FIRST_READ_RETURN:
                counts['first_read_return'] += 1
                assert counts['first_read_return'] == 1 and counts['BN_READ'] == 1
                timings['first_read_return'] = (h.steps, cpu.processorCycles)
                first_state = {'working': working_state(), 'x': cpu.x, 'y': cpu.y, 'p': cpu.p}
                assert list(map(bytes, m.banks)) == original_banks
            if counts['entry'] and cpu.pc == CACHED:
                counts['cached_entry'] += 1
                assert counts['cached_entry'] == 1 and 1 <= m.ram[symbols['BN_LENGTH']] <= 8
                assert fixture['selected'] and cpu.a == len(fixture['selected'])
                assert working_state() == first_state['working']
                assert (cpu.x, cpu.y, cpu.p) == (first_state['x'], first_state['y'], first_state['p'] & ~0x82)
                assert list(map(bytes, m.banks)) == original_banks and not m.transfers
                assert m.banks[3][JOURNAL - 0x8000:JOURNAL - 0x8000 + 1024] == fixture['journal']
                assert bytes(m.ram[symbols['BN_TEXT']:symbols['BN_TEXT'] + len(fixture['selected'])]) == fixture['selected']
                if candidate:
                    assert previous_pc == CALL and counts['BN_SHOW'] == 0 and counts['BN_READ'] == 1
                    lo, hi = (cpu.sp + 1) & 255, (cpu.sp + 2) & 255
                    assert m.ram[0x100 + lo] | m.ram[0x100 + hi] << 8 == CALL + 2
                    counts['cached_direct_entry'] += 1
                    assert cpu.p & 4 and stable_guard
                    stable_guard = False
                else:
                    assert previous_pc == CACHED - 2 and counts['BN_SHOW'] == 1 and counts['BN_READ'] == 2
            if counts['entry'] and cpu.pc == symbols['SLOT_LETTER'] - 1:
                counts['final_rts'] += 1
                assert counts['final_rts'] == 1 and m[cpu.pc] == 0x60 and cpu.p & 1
                timings['pre_final_rts'] = (h.steps, cpu.processorCycles)
            assert not 0x0200 <= cpu.pc < 0x3300, 'Assembler output RAM must not execute'
            previous_pc = cpu.pc
            original_step()

        cpu.step = step
        m.auditing = True
        try:
            output = h.command('VERSION', context='monitor')
        finally:
            m.auditing = False
            cpu.step = original_step
        assert output.endswith('B3> ') and cpu.sp == original_sp
        assert counts['crc_init'] == 1 and counts['crc_byte'] == 2048, counts
        named = int(bool(fixture['selected']))
        if refusal is None:
            assert counts['entry'] == counts['first_read_return'] == counts['final_rts'] == 1
            assert counts['header_check'] == 4 and counts['loader_bad'] == counts['storage_asset_fail'] == 0
            assert counts['BN_READ'] == (1 if candidate else 1 + named)
            assert counts['BN_SHOW'] == (0 if candidate else named)
            assert counts['cached_entry'] == counts['tail'] == named
            assert counts['cached_direct_entry'] == (named if candidate else 0) and not stable_guard
            expected_cpu = '65C816' if cpu_name == '65c816-e' else '65C02'
            name = fixture['selected'].decode('ascii') if named else 'unnamed'
            assert 'STR8-N 2.0rc1 B3 ' + expected_cpu + '\r\n' in output
            assert 'ABI 65C02 | 816E | 816N-VEC\r\n' in output
            assert 'Board: ' + name + '\r\n' in output
            assert 'Running: MONITOR ' + slot + ', gen 00000032\r\n' in output
            assert 'MONITOR A gen 00000032 VALID default\r\n' in output
            assert 'MONITOR B gen 00000032 VALID\r\n' in output
            assert m.ram[symbols['BN_LENGTH']] == len(fixture['selected'])
            assert int.from_bytes(m.ram[symbols['BN_SEQ']:symbols['BN_SEQ'] + 4], 'little') == fixture['sequence']
            free = int.from_bytes(m.ram[symbols['BN_FREE']:symbols['BN_FREE'] + 2], 'little')
            assert free == fixture['free'] if fixture['free'] else free >> 8 == 0
        else:
            assert counts['entry'] == counts['BN_READ'] == counts['BN_SHOW'] == counts['tail'] == 0
            assert counts['cached_entry'] == counts['cached_direct_entry'] == counts['final_rts'] == 0
            assert counts['loader_bad'] == counts['storage_asset_fail'] == 1
            assert counts['header_check'] == (4 if refusal == 'sealed-invalid-header' else 0)
            assert 'STR8-N 2.0rc1' not in output and 'Board:' not in output
        assert original_banks == list(map(bytes, m.banks)) and not m.flash_writes
        assert bytes(m.data) == original_sram and not m.transfers
        assert (m.ram[PCR], m.bank) == (original_pcr, original_bank)
        assert (m.ram[0x7D30], m.ram[0xF3]) == (original_active, original_selected)
        assert set(m.io_reads) <= {0x7FE0, 0x7FE1, 0x7FE3, PCR}
        assert set(m.io_writes) <= {0x7FA0, 0x7FE0, 0x7FE1, 0x7FE3, PCR}
        if cpu_name == '65c816-e':
            assert cpu.b == 0xA5 and cpu.mode == 1 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        comparison = bytearray(normalized_ram(m, cpu.sp))
        code_observations, seal_observations = [], []
        for address in (CALL_OPERAND, TAIL):
            assert m.ram[address] == body[address - ORIGIN]
            code_observations.append({'ram_address': address, 'value': m.ram[address]})
            comparison[address] = 0
        for offset in SEAL_OFFSETS:
            for address in (ORIGIN + offset, 0x7C80 + offset - 0x7F0):
                assert m.ram[address] == asset[offset]
                seal_observations.append({'ram_address': address, 'value': m.ram[address]})
                comparison[address] = 0
        public = dict(output=output, output_sha256=digest(output.encode('ascii')),
                      normalized_ram_sha256=digest(comparison),
                      registers={name: getattr(cpu, name) for name in register_names},
                      bank=m.bank, pcr=m.ram[PCR], boot_active=m.ram[0x7D30], selected_bank=m.ram[0xF3],
                      io_reads=sorted(m.io_reads), io_writes=sorted(m.io_writes),
                      other_io_read_counts={a: n for a, n in m.io_reads.items() if a != PCR},
                      other_io_write_counts={a: n for a, n in m.io_writes.items() if a != PCR},
                      sram_sha256=digest(bytes(m.data)))
        def elapsed(first, last, column):
            return timings[last][column] - timings[first][column] if timings else None
        return dict(public=public, calls=counts, firmware_sha256=digest(image), asset_sha256=digest(asset),
                    banks_sha256=[digest(bytes(bank)) for bank in m.banks], ram_sha256=digest(bytes(m.ram)),
                    normalized_ram=bytes(comparison), code_observations=code_observations,
                    seal_observations=seal_observations, pcr_reads=m.io_reads[PCR], pcr_writes=m.io_writes[PCR],
                    whole_command_steps=h.steps - start_steps,
                    whole_command_processor_cycles=cpu.processorCycles - start_cycles,
                    version_body_steps=elapsed('entry', 'pre_final_rts', 0),
                    version_body_processor_cycles=elapsed('entry', 'pre_final_rts', 1),
                    first_read_body_steps=elapsed('first_read_entry', 'first_read_return', 0),
                    first_read_body_processor_cycles=elapsed('first_read_entry', 'first_read_return', 1),
                    loader_before_entry_steps=timings['entry'][0] - start_steps if timings else None,
                    loader_before_entry_cycles=timings['entry'][1] - start_cycles if timings else None,
                    stable_journal_fixture=True, irq_disabled_at_application_entry=refusal is None,
                    cached_entry_precondition_verified=bool(candidate and named and refusal is None),
                    all_banks_unchanged=True, sram_unchanged=True, flash_writes=0, sram_transfers=0,
                    application_ram_substituted=False, loaded_asset_from_actual_rom=True)

    all_fixtures = fixtures()
    selected = all_fixtures if (slot, edu) == ('A', False) else [fixture for fixture in all_fixtures
                if fixture['name'] in ('unnamed-blank-journal', 'eight-character-name-max-sequence')]
    pairs = []
    for fixture in selected:
        baseline = execute(baseline_firmware, baseline_body, fixture, False)
        candidate = execute(candidate_firmware, candidate_body, fixture, True)
        differences = [(hex(i), a, b) for i, (a, b) in enumerate(
            zip(baseline['normalized_ram'], candidate['normalized_ram'])) if a != b]
        assert baseline['public'] == candidate['public'], (cpu_name, slot, edu, fixture['name'],
                differences[:30], baseline['public'], candidate['public'])
        baseline.pop('normalized_ram')
        candidate.pop('normalized_ram')
        named = int(bool(fixture['selected']))
        body_steps = candidate['version_body_steps'] - baseline['version_body_steps']
        body_cycles = candidate['version_body_processor_cycles'] - baseline['version_body_processor_cycles']
        whole_steps = candidate['whole_command_steps'] - baseline['whole_command_steps']
        whole_cycles = candidate['whole_command_processor_cycles'] - baseline['whole_command_processor_cycles']
        assert candidate['first_read_body_steps'] == baseline['first_read_body_steps']
        assert candidate['first_read_body_processor_cycles'] == baseline['first_read_body_processor_cycles']
        assert body_steps == -(baseline['first_read_body_steps'] + 4) * named
        assert body_cycles == -(baseline['first_read_body_processor_cycles'] + 21) * named
        assert whole_steps < 0 and whole_cycles < 0
        assert candidate['pcr_writes'] - baseline['pcr_writes'] == -2 * named
        assert candidate['pcr_reads'] - baseline['pcr_reads'] == -named
        pairs.append(dict(name=fixture['name'], passed=True, named=bool(named), public_behavior_equal=True,
                          journal_sha256=digest(fixture['journal']),
                          version_body_instruction_delta=body_steps, version_body_cycle_delta=body_cycles,
                          whole_command_instruction_delta=whole_steps, whole_command_cycle_delta=whole_cycles,
                          loader_instruction_delta=candidate['loader_before_entry_steps'] - baseline['loader_before_entry_steps'],
                          loader_cycle_delta=candidate['loader_before_entry_cycles'] - baseline['loader_before_entry_cycles'],
                          pcr_write_delta=-2 * named, pcr_read_delta=-named,
                          baseline=baseline, candidate=candidate))
        print('PASS cached VERSION', cpu_name, slot, 'edu' if edu else 'bare', fixture['name'],
              'whole cycles', whole_cycles, flush=True)

    refusals = []
    if (slot, edu) == ('A', False):
        unsealed = bytearray(baseline_firmware)
        unsealed[ASSET_FIRST:ASSET_FIRST + SIZE] = candidate_body
        corrupt = bytearray(candidate_firmware)
        corrupt[ASSET_FIRST + SEAL_OFFSETS[0]] ^= 1
        asset = candidate_firmware[ASSET_FIRST:ASSET_END]
        invalid_body = bytearray(candidate_body)
        invalid_body[0] ^= 1
        vectors = dict(zip(('V2V_NMI', 'V2V_RAM_RESET_ENTRY', 'V2V_IRQ_BRK'),
                          (int.from_bytes(asset[offset:offset + 2], 'little') for offset in (0x7FA, 0x7FC, 0x7FE))))
        bad_header = bytearray(candidate_firmware)
        bad_header[ASSET_FIRST:ASSET_END] = version_asset(bytes(invalid_body), asset[0x300:0x600], vectors)
        for name, image in (('unsealed-body-replacement', unsealed), ('corrupt-seal', corrupt),
                            ('sealed-invalid-header', bad_header)):
            assert (crc(image[ASSET_FIRST:ASSET_END]) == 0) == (name == 'sealed-invalid-header')
            result = execute(bytes(image), bytes(image[ASSET_FIRST:ASSET_FIRST + SIZE]), all_fixtures[0], True, name)
            result.pop('normalized_ram')
            refusals.append(dict(name=name, passed=True, version_never_entered=True,
                                 monitor_prompt_restored=True, **result))
    return dict(passed=True, full_command_pairs=len(pairs), actual_image_command_executions=2 * len(pairs),
                refusal_count=len(refusals), all_whole_commands_faster=True,
                whole_command_cycle_delta_min=min(row['whole_command_cycle_delta'] for row in pairs),
                whole_command_cycle_delta_max=max(row['whole_command_cycle_delta'] for row in pairs),
                body_cycle_delta_min=min(row['version_body_cycle_delta'] for row in pairs),
                body_cycle_delta_max=max(row['version_body_cycle_delta'] for row in pairs),
                cached_entry={'logical_address': CACHED, 'known_caller': CALL, 'return_address': CALL + 2,
                              'precondition': 'First BN_READ completed; main tested nonzero BN_LENGTH, '
                                              '1..8 selected bytes remain stable; IRQ disabled; no interleaved '
                                              'journal writer or injected callback is modeled.',
                              'standalone_BN_SHOW_preserved': True, 'phase10_body_sha256': PHASE10_BODY_SHA,
                              'only_change_from_phase10': CALL_OPERAND},
                normalization={'code_ram': [CALL_OPERAND, TAIL],
                               'asset_seal_ram': [ORIGIN + offset for offset in SEAL_OFFSETS],
                               'seal_read_scratch_ram': [0x7C80 + offset - 0x7F0 for offset in SEAL_OFFSETS],
                               'all_six_values_asserted_against_selected_rom': True,
                               'inactive_stack': '$0100 through $0100+final SP inclusive',
                               'live_stack_all_private_data_pointers_and_other_ram': 'Compared exactly'},
                intended_differences='One fewer BN_READ and BN_SHOW read/check wrapper on named commands; '
                                     'two fewer PCR writes and one fewer PCR read. Cached private entry is '
                                     'called only by the reviewed main caller. Console and all other I/O '
                                     'address/count observations match.',
                model_scope='Actual selected firmware in banked memory; inherited monitor-slot initialization '
                            'and discovery/delay fixture, not reset-vector/hardware qualification. Actual ROM '
                            'asset copy/CRC/header/command; no application RAM injection. Journal bytes are '
                            'stable throughout, with no external/NMI writer modeled.',
                timing_scope='VERSION body entry to pre-finalRTS; complete command includes actual '
                             'data-dependent loader CRC. Both measured, with net improvement required.',
                board_access=False, serial_ports_opened=0, network_attempts=0, hardware_qualified=False,
                application_ram_substituted=False, all_banks_unchanged=True, sram_unchanged=True,
                flash_writes=0, sram_transfers=0, pairs=pairs, refusals=refusals)
