"""Run the separately sealed VERSION firmware candidate in offline CPU models.

The inherited Harness starts at monitor-slot initialization, with its existing
discovery/delay shortcuts. The actual ROM asset is copied, CRC-checked, admitted
and executed by the linked loader; this helper never injects application RAM.
"""
from str8build.formats import crc
from str8build.images import version_asset
from test_resident_version_runtime import fixtures
from test_resident_version_candidate_runtime import digest, normalized_ram


ASSET_FIRST, ASSET_END = 0xF800, 0x10000
ORIGIN, ENTRY, BODY_SIZE, PATCH = 0x6E00, 0x6E04, 636, 0x705C
SEAL_OFFSETS = (0x7F6, 0x7F7)
JOURNAL = 0x9C00


def packaged_checks(Harness, cpu_name, slot, edu, baseline_firmware,
                    candidate_firmware, baseline_body, candidate_body, symbols):
    """Compare actual packaged-ROM VERSION runs, plus scoped refusal fixtures."""
    from test_rc1_source_store import Memory

    assert len(baseline_firmware) == len(candidate_firmware) == 98304
    assert len(baseline_body) == len(candidate_body) == BODY_SIZE
    assert symbols['START'] == ORIGIN and symbols['APP_END'] == ORIGIN + BODY_SIZE
    expected_differences = {ASSET_FIRST + PATCH - ORIGIN,
                            *(ASSET_FIRST + value for value in SEAL_OFFSETS)}
    actual_differences = {i for i, (a, b) in enumerate(zip(baseline_firmware, candidate_firmware)) if a != b}
    assert actual_differences == expected_differences
    assert baseline_firmware[ASSET_FIRST:ASSET_FIRST + BODY_SIZE] == baseline_body
    assert candidate_firmware[ASSET_FIRST:ASSET_FIRST + BODY_SIZE] == candidate_body
    assert crc(baseline_firmware[ASSET_FIRST:ASSET_END]) == 0
    assert crc(candidate_firmware[ASSET_FIRST:ASSET_END]) == 0
    register_names = ('pc', 'sp', 'p', 'a', 'x', 'y')
    if cpu_name == '65c816-e':
        register_names += ('b', 'mode', 'pbr', 'dbr', 'dpr')

    def memory_factory(selected_image):
        class PackagedMemory(Memory):
            def __init__(self, image, data=None):
                # Harness reads the fresh unchanged baseline build. Supply the
                # separate selected image at memory construction, before any
                # monitor instructions execute, rather than replacing RAM later.
                assert image == baseline_firmware
                self.auditing = False
                self.io_reads, self.io_writes = set(), set()
                super().__init__(selected_image, data)

            def __getitem__(self, address):
                if self.auditing and isinstance(address, int) and 0x7F00 <= address < 0x8000:
                    self.io_reads.add(address)
                return super().__getitem__(address)

            def __setitem__(self, address, value):
                if self.auditing and 0x7F00 <= address < 0x8000:
                    self.io_writes.add(address)
                return super().__setitem__(address, value)

        # Harness cache keys include the class name. Distinct ROM images must
        # never share an initial CPU/RAM snapshot merely because CPU/slot match.
        PackagedMemory.__name__ = 'PackagedMemory_' + digest(selected_image)
        return PackagedMemory

    def execute(image, body, fixture, refusal=None):
        h = Harness(cpu_name, slot, edu=edu, memory_factory=memory_factory(image))
        m, cpu = h.m, h.cpu
        loader = h.symbols['loader/version-loader']
        assert h.symbols['version/version']['START'] == ORIGIN
        asset = image[ASSET_FIRST:ASSET_END]
        m.ram[0x7D0F:0x7D11] = bytes.fromhex('06ef')
        m.ram[0x7D27] = 1 if edu else 2
        m.banks[3][JOURNAL - 0x8000:JOURNAL - 0x8000 + 1024] = fixture['journal']
        original_banks, original_sram = list(map(bytes, m.banks)), bytes(m.data)
        original_pcr, original_bank = m.ram[0x7FEC], m.bank
        original_active, original_selected, original_sp = m.ram[0x7D30], m.ram[0xF3], cpu.sp
        start_steps, start_cycles = h.steps, cpu.processorCycles
        counts = dict(entry=0, crc_init=0, crc_byte=0, header_check=0, loader_bad=0,
                      storage_asset_fail=0, BN_READ=0, BN_SHOW=0, tail=0, final_rts=0)
        watched = {loader['AP_CRC_INIT']: 'crc_init', loader['AP_CRC_BYTE']: 'crc_byte',
                   loader['HEADER']: 'header_check', loader['BAD']: 'loader_bad',
                   loader['STORAGE_ASSET_FAIL']: 'storage_asset_fail',
                   symbols['BN_READ']: 'BN_READ', symbols['BN_SHOW']: 'BN_SHOW', PATCH: 'tail'}
        timings = {}
        loader_active = False
        original_step = cpu.step

        def step():
            nonlocal loader_active
            if cpu.pc == loader['LOAD']:
                assert cpu.a == 7
                loader_active = True
            if cpu.pc == ENTRY:
                counts['entry'] += 1
                assert counts['entry'] == 1 and refusal is None
                assert m.bank == 3 and m.ram[0x7D2B] == 7
                assert m.ram[ORIGIN:ORIGIN + len(asset)] == asset
                assert m.ram[ORIGIN:ORIGIN + BODY_SIZE] == body
                assert m.ram[0xF3] == original_selected
                assert m.ram[0x7D38:0x7D3A] == b'\0\0'
                timings['entry'] = (h.steps, cpu.processorCycles)
                loader_active = False
            label = watched.get(cpu.pc)
            if label and (label not in ('crc_init', 'crc_byte', 'header_check') or loader_active):
                counts[label] += 1
            if label == 'loader_bad':
                loader_active = False
            if counts['entry'] and cpu.pc == symbols['SLOT_LETTER'] - 1:
                counts['final_rts'] += 1
                assert counts['final_rts'] == 1 and m[cpu.pc] == 0x60 and cpu.p & 1
                timings['pre_final_rts'] = (h.steps, cpu.processorCycles)
            assert not 0x0200 <= cpu.pc < 0x3300, 'Assembler output RAM must not execute'
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
        if refusal is None:
            assert counts['entry'] == counts['final_rts'] == 1
            assert counts['header_check'] == 4
            assert counts['loader_bad'] == counts['storage_asset_fail'] == 0
            assert counts['BN_READ'] == (2 if fixture['selected'] else 1)
            assert counts['BN_SHOW'] == counts['tail'] == int(bool(fixture['selected']))
            expected_cpu = '65C816' if cpu_name == '65c816-e' else '65C02'
            name = fixture['selected'].decode('ascii') if fixture['selected'] else 'unnamed'
            assert 'STR8-N 2.0rc1 B3 ' + expected_cpu + '\r\n' in output
            assert 'ABI 65C02 | 816E | 816N-VEC\r\n' in output
            assert 'Board: ' + name + '\r\n' in output
            assert 'Running: MONITOR ' + slot + ', gen 00000032\r\n' in output
            assert 'MONITOR A gen 00000032 VALID default\r\n' in output
            assert 'MONITOR B gen 00000032 VALID\r\n' in output
            assert m.ram[symbols['BN_LENGTH']] == len(fixture['selected'])
            assert bytes(m.ram[symbols['BN_TEXT']:symbols['BN_TEXT'] + len(fixture['selected'])]) == fixture['selected']
        else:
            assert counts['entry'] == counts['BN_READ'] == counts['BN_SHOW'] == counts['tail'] == 0
            assert counts['final_rts'] == 0
            assert counts['loader_bad'] == counts['storage_asset_fail'] == 1
            assert counts['header_check'] == (4 if refusal == 'sealed-invalid-header' else 0)
            assert 'STR8-N 2.0rc1' not in output and 'Board:' not in output
        assert original_banks == list(map(bytes, m.banks)) and not m.flash_writes
        assert bytes(m.data) == original_sram and not m.transfers
        assert (m.ram[0x7FEC], m.bank) == (original_pcr, original_bank)
        assert (m.ram[0x7D30], m.ram[0xF3]) == (original_active, original_selected)
        assert m.io_reads <= {0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        assert m.io_writes <= {0x7FA0, 0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        if cpu_name == '65c816-e':
            assert cpu.b == 0xA5 and cpu.mode == 1 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        assert m.ram[PATCH] == body[PATCH - ORIGIN]
        comparison = bytearray(normalized_ram(m, cpu.sp))
        # The new seal is intentionally present both in loaded application RAM
        # and the worker's final-read scratch. Assert each concrete value before
        # excluding only these expected packaging-data differences.
        seal_observations = []
        for offset in SEAL_OFFSETS:
            for address in (ORIGIN + offset, 0x7C80 + offset - 0x7F0):
                assert m.ram[address] == asset[offset], (hex(address), m.ram[address], asset[offset])
                seal_observations.append({'ram_address': address, 'value': m.ram[address]})
                comparison[address] = 0
        public = dict(output=output, output_sha256=digest(output.encode('ascii')),
                      normalized_ram_sha256=digest(comparison),
                      registers={name: getattr(cpu, name) for name in register_names}, calls=counts,
                      bank=m.bank, pcr=m.ram[0x7FEC], boot_active=m.ram[0x7D30],
                      selected_bank=m.ram[0xF3], io_reads=sorted(m.io_reads), io_writes=sorted(m.io_writes),
                      sram_sha256=digest(bytes(m.data)))
        body_steps = timings['pre_final_rts'][0] - timings['entry'][0] if timings else None
        body_cycles = timings['pre_final_rts'][1] - timings['entry'][1] if timings else None
        return dict(public=public, firmware_sha256=digest(image), asset_sha256=digest(asset),
                    banks_sha256=[digest(bytes(bank)) for bank in m.banks], ram_sha256=digest(bytes(m.ram)),
                    normalized_ram=bytes(comparison), seal_observations=seal_observations,
                    whole_command_steps=h.steps - start_steps,
                    whole_command_processor_cycles=cpu.processorCycles - start_cycles,
                    version_body_steps=body_steps, version_body_processor_cycles=body_cycles,
                    loader_before_entry_steps=timings['entry'][0] - start_steps if timings else None,
                    loader_before_entry_cycles=timings['entry'][1] - start_cycles if timings else None,
                    all_banks_unchanged=True, sram_unchanged=True, flash_writes=0, sram_transfers=0,
                    application_ram_substituted=False, loaded_asset_from_actual_rom=True)

    selected_fixtures = [fixture for fixture in fixtures() if fixture['name'] in (
        'unnamed-blank-journal', 'eight-character-name-max-sequence')]
    assert len(selected_fixtures) == 2
    pairs = []
    for fixture in selected_fixtures:
        baseline = execute(baseline_firmware, baseline_body, fixture)
        candidate = execute(candidate_firmware, candidate_body, fixture)
        differences = [(hex(i), a, b) for i, (a, b) in enumerate(
            zip(baseline['normalized_ram'], candidate['normalized_ram'])) if a != b]
        assert baseline['public'] == candidate['public'], (cpu_name, slot, edu, fixture['name'], differences[:30],
                                                         baseline['public'], candidate['public'])
        baseline.pop('normalized_ram')
        candidate.pop('normalized_ram')
        reached = int(bool(fixture['selected']))
        assert candidate['version_body_steps'] - baseline['version_body_steps'] == -reached
        assert candidate['version_body_processor_cycles'] - baseline['version_body_processor_cycles'] == -9 * reached
        pairs.append(dict(name=fixture['name'], passed=True, public_behavior_equal=True,
                          journal_sha256=digest(fixture['journal']),
                          version_body_instruction_delta=candidate['version_body_steps'] - baseline['version_body_steps'],
                          version_body_cycle_delta=candidate['version_body_processor_cycles'] - baseline['version_body_processor_cycles'],
                          whole_command_instruction_delta=candidate['whole_command_steps'] - baseline['whole_command_steps'],
                          whole_command_cycle_delta=candidate['whole_command_processor_cycles'] - baseline['whole_command_processor_cycles'],
                          baseline=baseline, candidate=candidate))

    refusals = []
    if (slot, edu) == ('A', False):
        unsealed = bytearray(baseline_firmware)
        unsealed[ASSET_FIRST:ASSET_FIRST + BODY_SIZE] = candidate_body
        corrupt = bytearray(candidate_firmware)
        corrupt[ASSET_FIRST + SEAL_OFFSETS[0]] ^= 1
        asset = candidate_firmware[ASSET_FIRST:ASSET_END]
        invalid_body = bytearray(candidate_body)
        invalid_body[0] ^= 1
        vector_values = [int.from_bytes(asset[offset:offset + 2], 'little') for offset in (0x7FA, 0x7FC, 0x7FE)]
        vectors = dict(zip(('V2V_NMI', 'V2V_RAM_RESET_ENTRY', 'V2V_IRQ_BRK'), vector_values))
        bad_header = bytearray(candidate_firmware)
        bad_header[ASSET_FIRST:ASSET_END] = version_asset(bytes(invalid_body), asset[0x300:0x600], vectors)
        for name, image in (('unsealed-body-replacement', unsealed), ('corrupt-seal', corrupt),
                            ('sealed-invalid-header', bad_header)):
            assert (crc(image[ASSET_FIRST:ASSET_END]) == 0) == (name == 'sealed-invalid-header')
            result = execute(bytes(image), bytes(image[ASSET_FIRST:ASSET_FIRST + BODY_SIZE]),
                             selected_fixtures[0], refusal=name)
            result.pop('normalized_ram')
            refusals.append(dict(name=name, passed=True, version_never_entered=True,
                                 monitor_prompt_restored=True, **result))
    return dict(passed=True, full_command_pairs=len(pairs), actual_image_command_executions=2 * len(pairs),
                refusal_count=len(refusals), firmware_loaded_before_monitor_initialization=True,
                application_ram_substituted=False, actual_asset_copy_crc_and_header_executed=True,
                normalization={'candidate_opcode_ram': PATCH,
                               'expected_asset_seal_ram': [ORIGIN + offset for offset in SEAL_OFFSETS],
                               'expected_seal_read_scratch_ram': [0x7C80 + offset - 0x7F0 for offset in SEAL_OFFSETS],
                               'all_seal_values_asserted_against_selected_rom': True,
                               'inactive_stack': '$0100 through $0100+final SP inclusive',
                               'live_stack_and_all_other_ram': 'Compared exactly'},
                timing_scope='VERSION body measured from entry to pre-finalRTS; named path saves9 modeled '
                             'cycles/1instruction. Whole command includes data-dependent loader CRC work and '
                             'is reported separately.',
                model_scope='Actual selected whole firmware in banked memory; inherited Harness monitor-slot '
                            'initialization/discovery/delay fixture, not CPU reset-vector or physical-board '
                            'qualification. Linked loader reads and checks the actual sealed ROM asset; no '
                            'post-entry RAM injection. Phase10 provides the inherited full journal/tail proof.',
                board_access=False, serial_ports_opened=0, network_attempts=0, hardware_qualified=False,
                all_banks_unchanged=True, sram_unchanged=True, flash_writes=0, sram_transfers=0,
                pairs=pairs, refusals=refusals)
