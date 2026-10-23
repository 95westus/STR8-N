"""Full VERSION CPU-model equivalence and board-name reader fixtures.

Imported by the Phase-9 proof; no hardware, network or import-time actions.
"""
import binascii
import hashlib
import json


ORIGIN = 0x6E00
ENTRY = 0x6E04
LENGTH = 636
JOURNAL = 0x9C00


def digest(value):
    return hashlib.sha256(value).hexdigest()


def record(name=b'', sequence=1):
    assert len(name) <= 8 and 0 <= sequence <= 0xFFFFFFFF
    result = bytearray(b'\xFF' * 32)
    result[:4] = b'BN\x01\x00'
    result[4:8] = sequence.to_bytes(4, 'little')
    result[8] = len(name)
    result[9:17] = name.ljust(8, b'\x00')
    result[31] = 0
    return reseal(result)


def reseal(value):
    value[28:30] = binascii.crc_hqx(value[:28], 0xFFFF).to_bytes(2, 'little')
    return value


def journal(records):
    result = bytearray(b'\xFF' * 1024)
    for index, value in records:
        assert 0 <= index < 32 and len(value) == 32
        result[index * 32:(index + 1) * 32] = value
    return bytes(result)


def fixtures():
    """Explicit expectations freeze acceptance rules, including current quirks."""
    rows = []

    def add(name, records, selected=b'', sequence=0, free=JOURNAL, full=False):
        rows.append(dict(name=name, journal=journal(records), selected=selected,
                         sequence=sequence, free=free, full=full))

    add('unnamed-blank-journal', [], full=True)
    add('one-character-name', [(0, record(b'N'))], b'N', 1, JOURNAL + 32, True)
    add('eight-character-name-max-sequence', [(0, record(b'WALTER-8', 0xFFFFFFFF))],
        b'WALTER-8', 0xFFFFFFFF, JOURNAL + 32, True)
    add('latest-sequence-and-later-equal-sequence',
        [(0, record(b'OLD', 7)), (1, record(b'FIRST', 9)), (2, record(b'LATER', 9))],
        b'LATER', 9, JOURNAL + 96, True)
    add('newer-empty-name-tombstone', [(0, record(b'OLD')), (1, record(b'', 2))],
        b'', 2, JOURNAL + 64, True)
    add('zero-sequence-valid', [(0, record(b'ZERO', 0))], b'ZERO', 0, JOURNAL + 32)
    add('sequence-byte-carry-numeric-order', [(0, record(b'LOW', 255)),
                                             (1, record(b'HIGH', 256))],
        b'HIGH', 256, JOURNAL + 64)
    add('sequence-does-not-wrap', [(0, record(b'MAX', 0xFFFFFFFF)),
                                  (1, record(b'WRAPPED', 0))],
        b'MAX', 0xFFFFFFFF, JOURNAL + 64)
    add('last-record-scanned', [(31, record(b'TAIL', 5))], b'TAIL', 5, JOURNAL)

    def rejected(name, offset, value, seal=True):
        candidate = record(b'NEW', 8)
        candidate[offset] = value
        if seal:
            reseal(candidate)
        add(name, [(0, record(b'KEEP', 7)), (1, candidate)], b'KEEP', 7, JOURNAL + 64)

    rejected('uncommitted-record-is-occupied', 31, 0xFF)
    rejected('malformed-magic-is-occupied', 0, ord('X'))
    rejected('unsupported-record-version', 2, 2)
    rejected('nonzero-header-flags', 3, 1)
    rejected('crc-corruption', 28, record(b'NEW', 8)[28] ^ 1, seal=False)
    rejected('length-nine-refused', 8, 9)
    rejected('space-character-refused', 9, 0x20)
    rejected('del-character-refused', 9, 0x7F)
    rejected('high-bit-character-refused', 9, 0x80)
    rejected('embedded-zero-refused', 10, 0)
    rejected('nonzero-name-padding-refused', 12, 1)

    reserved = record(b'RESERVED', 3)
    reserved[17:28] = bytes(range(11))
    reseal(reserved)
    add('non-ff-crc-covered-reserved-bytes-accepted', [(0, reserved)], b'RESERVED', 3, JOURNAL + 32)
    ignored = record(b'BYTE30', 4)
    ignored[30] = 0x12
    add('non-ff-uncovered-byte30-accepted', [(0, ignored)], b'BYTE30', 4, JOURNAL + 32)
    # Printable endpoint characters are accepted; spaces are intentionally not.
    add('printable-name-endpoints', [(0, record(b'!~', 6))], b'!~', 6, JOURNAL + 32)
    add('full-journal-no-free-slot', [(i, record(b'FULL', i)) for i in range(32)],
        b'FULL', 31, 0)
    return rows


def runtime_checks(Harness, cpu_name, slot, edu, host_body, resident_body):
    """Pair host/resident executions; only modeled RAM receives replacement bytes.

    Two complete VERSION commands per profile use the real monitor, asset loader,
    CRC, bootstrap services and console; A/bare profiles add three command cases.
    All 24 journal fixtures separately execute
    BN_READ/TZ_CRC, allowing malformed-record coverage without repeating every
    complete monitor CRC scan. No console or bootstrap instruction is stubbed.
    """
    from test_rc1_source_store import Memory

    class AuditMemory(Memory):
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

    assert len(host_body) == len(resident_body) == LENGTH and host_body == resident_body
    register_names = ('pc', 'sp', 'p', 'a', 'x', 'y')
    if cpu_name == '65c816-e':
        register_names += ('b', 'mode', 'pbr', 'dbr', 'dpr')

    def execute(body, fixture, scope):
        h = Harness(cpu_name, slot, edu=edu, memory_factory=AuditMemory)
        m, cpu = h.m, h.cpu
        symbols = h.symbols['version/version']
        assert symbols['START'] == ORIGIN and symbols['APP_END'] == ORIGIN + LENGTH
        # Inherited Harness skips hardware discovery at E014. Publish the exact
        # state normally supplied by verified status-mode-init FRAME_POINTER.
        m.ram[0x7D0F:0x7D11] = bytes.fromhex('06ef')
        m.ram[0x7D27] = 1 if edu else 2
        m.banks[3][JOURNAL - 0x8000:JOURNAL - 0x8000 + 1024] = fixture['journal']
        original_banks = list(map(bytes, m.banks))
        original_sram = bytes(m.data)
        original_pcr, original_bank = m.ram[0x7FEC], m.bank
        original_active, original_selected = m.ram[0x7D30], m.ram[0xF3]
        original_sp = cpu.sp
        start_steps = h.steps
        counters = dict(entry=0, BN_READ=0, TZ_CRC=0, BOOT_SELECT=0,
                        BOOT_SLOT_CHECK=0, BOOT_CHOICE_SLOT=0)
        addresses = {symbols[name]: name for name in ('BN_READ', 'TZ_CRC',
                     'BOOT_SELECT', 'BOOT_SLOT_CHECK', 'BOOT_CHOICE_SLOT')}
        original_step = cpu.step

        def step():
            if scope == 'full-command' and cpu.pc == ENTRY:
                counters['entry'] += 1
                assert counters['entry'] == 1
                assert m.bank == 3 and m.ram[ORIGIN:ORIGIN + LENGTH] == host_body
                assert m.ram[0x7D2B] == 7 and m.ram[0xF3] == original_selected
                # The loader has already validated the complete sealed asset.
                # This is an in-model RAM substitution, never a flash write.
                m.ram[ORIGIN:ORIGIN + LENGTH] = body
            name = addresses.get(cpu.pc)
            if name is not None:
                counters[name] += 1
            if scope == 'BN_READ':
                assert ORIGIN <= cpu.pc < ORIGIN + LENGTH
            original_step()

        cpu.step = step
        m.auditing = True
        try:
            if scope == 'full-command':
                output = h.command('VERSION', context='monitor')
                assert counters['entry'] == counters['BOOT_SELECT'] == 1
                # The pinned bootstrap journal prefers validated MON A, so
                # BOOT_SELECT returns after checking A. Both displayed slots
                # are still checked independently, plus the running slot.
                assert counters['BOOT_CHOICE_SLOT'] == 2 and counters['BOOT_SLOT_CHECK'] == 4, counters
                assert counters['BN_READ'] == (2 if fixture['selected'] else 1)
                expected_cpu = '65C816' if cpu_name == '65c816-e' else '65C02'
                name = fixture['selected'].decode('ascii') if fixture['selected'] else 'unnamed'
                assert 'STR8-N 2.0rc1 B3 ' + expected_cpu + '\r\n' in output
                assert 'ABI 65C02 | 816E | 816N-VEC\r\n' in output
                assert 'Board: ' + name + '\r\n' in output
                assert 'Running: MONITOR ' + slot + ', gen 00000032\r\n' in output
                assert 'MONITOR A gen 00000032 VALID default\r\n' in output
                assert 'MONITOR B gen 00000032 VALID\r\n' in output
                assert output.endswith('B3> ') and cpu.sp == original_sp
            else:
                m.ram[ORIGIN:ORIGIN + LENGTH] = body
                cpu.stPushWord(0x7AFF)
                cpu.pc = symbols['BN_READ']
                h.run(lambda: cpu.pc == 0x7B00)
                output = ''
                assert counters['entry'] == 0 and counters['BN_READ'] == 1
                assert cpu.sp == original_sp
        finally:
            m.auditing = False
            cpu.step = original_step

        length = m.ram[symbols['BN_LENGTH']]
        selected = bytes(m.ram[symbols['BN_TEXT']:symbols['BN_TEXT'] + length])
        sequence = int.from_bytes(m.ram[symbols['BN_SEQ']:symbols['BN_SEQ'] + 4], 'little')
        # When the journal is full, BN_READ only initializes BN_FREE's high
        # byte. Consumers use that high byte as the no-free-slot sentinel.
        free = int.from_bytes(m.ram[symbols['BN_FREE']:symbols['BN_FREE'] + 2], 'little')
        assert selected == fixture['selected'] and sequence == fixture['sequence']
        assert free == fixture['free'] if fixture['free'] else free >> 8 == 0
        assert original_banks == list(map(bytes, m.banks)) and not m.flash_writes
        assert bytes(m.data) == original_sram and not m.transfers
        assert (m.ram[0x7FEC], m.bank) == (original_pcr, original_bank)
        assert (m.ram[0x7D30], m.ram[0xF3]) == (original_active, original_selected)
        assert m.io_reads <= {0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        assert m.io_writes <= {0x7FA0, 0x7FE0, 0x7FE1, 0x7FE3, 0x7FEC}
        if scope == 'BN_READ':
            assert m.io_reads == {0x7FEC} and m.io_writes == {0x7FEC}
        if cpu_name == '65c816-e':
            assert cpu.b == 0xA5 and cpu.mode == 1 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        return dict(output=output, output_sha256=digest(output.encode('ascii')),
                    ram_sha256=digest(bytes(m.ram)), sram_sha256=digest(bytes(m.data)),
                    banks_sha256=[digest(bytes(bank)) for bank in m.banks],
                    registers={name: getattr(cpu, name) for name in register_names},
                    steps=h.steps - start_steps, calls=counters, bank=m.bank,
                    pcr=m.ram[0x7FEC], boot_active=m.ram[0x7D30], selected_bank=m.ram[0xF3],
                    selected_name=selected.decode('ascii'), sequence=sequence,
                    free_slot=free if free >> 8 else None,
                    io_reads=sorted(m.io_reads), io_writes=sorted(m.io_writes),
                    flash_writes=0, sram_transfers=0, all_banks_unchanged=True,
                    sram_unchanged=True)

    rows = []
    all_fixtures = fixtures()
    for scope in ('full-command', 'BN_READ'):
        for fixture in all_fixtures:
            if scope == 'full-command':
                if not fixture['full']:
                    continue
                if (slot, edu) != ('A', False) and fixture['name'] not in (
                        'unnamed-blank-journal', 'eight-character-name-max-sequence'):
                    continue
            host = execute(host_body, fixture, scope)
            resident = execute(resident_body, fixture, scope)
            assert host == resident, (cpu_name, slot, edu, scope, fixture['name'])
            rows.append(dict(name=fixture['name'], type=scope, scope=scope, passed=True,
                             host_resident_equal=True, journal_sha256=digest(fixture['journal']),
                             **resident))
    full_count = sum(row['scope'] == 'full-command' for row in rows)
    return dict(passed=True, case_count=len(rows),
                full_command_pairs=full_count, board_name_reader_pairs=len(rows) - full_count,
                host_and_resident_executions=2 * len(rows),
                scope='Full command pairs plus separately scoped callable BN_READ pairs',
                discovery_fixture=dict(banner_pointer=0xEF06, mode=1 if edu else 2,
                                       inherited_hardware_discovery_skipped_at=0xE014),
                model_scope='Real linked monitor/loader/VERSION/bootstrap/FT245 CPU instructions; '
                            'inherited discovery/delay model. Mode-init publication at 7D0F=EF06 '
                            'is supplied as a discovery fixture. No RTC/I2C/EEPROM/SRAM transfer '
                            'or physical board access. Replacement occurs only in model RAM.',
                preserved_quirks=['Equal sequence chooses later record',
                                  'Sequence comparisons are unsigned and do not wrap',
                                  'CRC-covered bytes 17..27 need not be FF',
                                  'Byte 30 is not checked',
                                  'No-free-slot sentinel is BN_FREE high byte zero'],
                cases=rows)
