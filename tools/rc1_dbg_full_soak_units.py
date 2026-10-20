"""Bounded, preserving rc1/utility and built-in BRK soak units.

This module owns no port, process, deadline, backup or restoration policy.
The caller must supply an already-idle B3 link and qualified fixture images.
Only volatile application RAM and bank selection change during these units.
"""
import hashlib
import importlib
import re
import time
from pathlib import Path


PROMPTS = {**{f'B{n}': f'\r\nB{n}> '.encode() for n in (1, 2, 3)},
           'BM': b'\r\nBM> ', 'SRAM': b'SRAM> ', 'WORK': b'WORK> ',
           'EDU': b'EDU> ', 'CLOCK': b'CLOCK> ', 'DBG': b'DBG> '}
MONITOR_COMMANDS = frozenset(('VERSION', 'APPS', 'T 1', 'T 2', 'C', 'P', 'W',
                              'TIME', '?', 'M 1', 'M 2', 'M 3', 'B1', 'B2',
                              'B3', 'D 8000 800F', 'BATCH APPS;VERSION',
                              'MAINT', 'SRAM', 'WORK', 'EDU', 'R CLOCK'))
ALLOWED_COMMANDS = {**{f'B{n}': MONITOR_COMMANDS for n in (1, 2, 3)},
                    'BM': frozenset(('?', 'NAME', 'M', 'Q')),
                    'SRAM': frozenset(('?', 'T', 'Q')),
                    'WORK': frozenset(('?', 'HELP', 'Q')),
                    'EDU': frozenset(('?', 'Q')),
                    'CLOCK': frozenset(('HELP', 'TIME', 'STATUS', 'EUI',
                                        'HISTORY', 'STATS', 'Q')),
                    'DBG': frozenset(('?', 'R', 'F', 'B', 'BC *', 'C'))}
BUILTIN_FAMILIES = ('query', 'register-trace', 'text-output',
                    'user-register-call-remove')


def _payload(answer, command, prompt):
    assert isinstance(answer, bytes) and answer.endswith(prompt), (
        'Unexpected prompt', command, prompt, answer[-200:])
    body = answer[:-len(prompt)]
    # FT245 echoes a submitted line. A model may omit that echo.
    lines = body.splitlines()
    if lines and lines[0].strip() == command.encode():
        body = b'\n'.join(lines[1:])
    assert not re.search(rb'(?im)^(?:\?|Invalid command[^\r\n]*|'
                         rb'INVALID / PROTECTED RANGE|BATCH stopped[^\r\n]*|'
                         rb'WRITE/VERIFY FAILED[^\r\n]*)\s*$', body), (
                             'Command refused', command, body)
    return body


class Session:
    """An exact allowlist and context transition, not a generic console sender."""
    def __init__(self, link, context='B3'):
        assert context in PROMPTS
        self.link, self.context = link, context
        self.transcript = bytearray()
        self.commands = []

    def command(self, command, next_context=None, required=(), pattern=None):
        assert command in ALLOWED_COMMANDS[self.context], (
            'Command outside preserving allowlist', self.context, command)
        target = self.context if next_context is None else next_context
        assert target in PROMPTS
        before = self.context
        answer = self.link.command(command, PROMPTS[target])
        body = _payload(answer, command, PROMPTS[target])
        for token in required:
            assert token in body, ('Missing semantic output', command, token, body[-500:])
        if pattern:
            assert re.search(pattern, body), ('Unexpected semantic output', command, body[-500:])
        self.context = target
        self.transcript.extend(answer)
        self.commands.append(dict(command=command, context=before, resulting_context=target,
                                  prompt=PROMPTS[target].decode(), passed=True,
                                  output_sha256=hashlib.sha256(answer).hexdigest()))
        return body


def _clock_status(body):
    for token in (b'Running: yes', b'Calendar valid: yes', b'Backup enabled: yes'):
        assert token in body, ('RTC health check failed', token, body)
    match = re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)', body)
    assert match, ('RTC status lacks raw registers', body)
    raw = bytes.fromhex(match[1].decode())
    assert len(raw) == 9 and raw[0] & 0x80 and raw[3] & 8
    eui = re.search(rb'EUI: ((?:[0-9A-F]{2}:){5}[0-9A-F]{2})', body)
    assert eui, ('RTC status lacks identity', body)
    return dict(control=raw[7], trim_raw=raw[8], oscillator_start=bool(raw[0] & 128),
                weekday_flags=raw[3] & 0x38, EUI=eui[1].decode(), raw_hex=raw.hex())


def _same_clock(before, after):
    fields = ('control', 'trim_raw', 'oscillator_start', 'weekday_flags', 'EUI')
    assert all(before[key] == after[key] for key in fields), (
        'RTC controls/trim/oscillator/backup/latch/identity changed', before, after)


def base_and_utilities(link, transport, cycle):
    """Inspect base rc1 and every supported utility, returning to B3 each time."""
    del transport  # Bank-qualified D is deliberately a monitor read command.
    assert isinstance(cycle, int) and cycle >= 0
    s = Session(link)
    version = s.command('VERSION', required=(b'2.0rc1', b'gen 00000032', b'Board: '),
                        pattern=rb'65C(?:02|816)')
    s.command('APPS', required=(b'MAINT', b'SRAM', b'WORK', b'EDU', b'ASM installed'))
    s.command('T 1', required=(b'UCHESS', b'CLOCK'))
    table2 = s.command('T 2')
    assert not re.search(rb'(?im)^(?:Error|Bad|Protected)\b', table2)
    config = s.command('C', pattern=rb'(?m)^C [0-9A-F]{2} [0-9A-F]{2} [0-9A-F]{4} [0-9A-F]{2}\s*$')
    preference = s.command('P', pattern=rb'Preferred [AB] 00000032')
    wear = s.command('W')
    sectors = re.findall(rb'(?m)^B([0-3]):([89A-F]) ([0-9A-F]{6})\s*$', wear)
    assert len(sectors) == 32 and len({(b, a) for b, a, _ in sectors}) == 32
    base_status = {command: next(row['output_sha256'] for row in s.commands
                                if row['command'] == command) for command in ('C', 'P', 'W')}
    s.command('TIME', pattern=rb'20\d\d-\d\d-\d\d \d\d:\d\d:\d\d')
    s.command('?', required=(b'BATCH', b'M [1 grid|2 ranges|3 wear]'))
    map_number = 1 + cycle % 3
    map_token = {1: b'8  9  A  B  C  D  E  F', 2: b'BANK RANGE CONTENTS ACCESS',
                 3: b'SECTOR RANGE E/U ERASE-ATTEMPTS CONTENTS ACCESS'}[map_number]
    s.command(f'M {map_number}', required=(map_token,))
    banks = []
    for bank in (1, 2, 3):
        s.command(f'B{bank}', f'B{bank}')
        dump = s.command('D 8000 800F')
        assert re.search(rb'(?m)^8000[ :]+(?:[0-9A-F]{2} ){7,}', dump), ('Flash D output', dump)
        banks.append(dict(bank=bank, address=0x8000, bytes=16,
                          output_sha256=hashlib.sha256(dump).hexdigest()))
    # BATCH has an intermediate completion token, then the exact monitor prompt.
    batch = link.command('BATCH APPS;VERSION', b'BATCH done')
    assert batch.endswith(b'BATCH done')
    batch += link.until(PROMPTS['B3'])
    _payload(batch, 'BATCH APPS;VERSION', PROMPTS['B3'])
    assert all(token in batch for token in (b'MAINT', b'ASM installed', b'2.0rc1',
                                           b'gen 00000032'))
    s.transcript.extend(batch)
    s.commands.append(dict(command='BATCH APPS;VERSION', context='B3', resulting_context='B3',
                           prompt=PROMPTS['B3'].decode(), passed=True,
                           output_sha256=hashlib.sha256(batch).hexdigest()))

    utilities = {}
    s.command('MAINT', 'BM', required=(b'BANK MAINT 2.4',))
    s.command('?', required=(b'BANKS AND MEMORY', b'NAME', b'Return to monitor'))
    name = s.command('NAME', required=(b'Board: ',))
    s.command('M', required=(b'BANK RANGE CONTENTS ACCESS',))
    s.command('Q', 'B3')
    utilities['MAINT'] = dict(passed=True, board_name_query=True,
                             board_name_sha256=hashlib.sha256(name).hexdigest(), map_report=True)

    s.command('SRAM', 'SRAM', required=(b'SRAM 1.4',))
    s.command('?', required=(b'S name start end entry; R/G/D name; T C F Q',))
    table = s.command('T')
    initialized = b'Free bytes: $' in table
    assert initialized or re.search(rb'(?m)^SRAM: 40\s*$', table), ('SRAM table output', table)
    s.command('Q', 'B3')
    utilities['SRAM'] = dict(passed=True, table_query=True,
                            storage_status='initialized' if initialized else 'uninitialized-read-only-refusal')

    s.command('WORK', 'WORK', required=(b'WORK 1.4',))
    capacity = s.command('?')
    initialized = b'Programs: ' in capacity and b' KiB; workspace: ' in capacity and b' bytes' in capacity
    assert initialized or b'Storage not initialized.' in capacity, ('WORK capacity output', capacity)
    s.command('HELP', required=(b'? capacity; P 16/32/48/64', b'HELP; Q'))
    s.command('Q', 'B3')
    utilities['WORK'] = dict(passed=True, capacity_query=True,
                            storage_status='initialized' if initialized else 'uninitialized-read-only-refusal')

    s.command('EDU', 'EDU', required=(b'EDU 1.4',))
    edu = s.command('?')
    assert re.search(rb'(?i)EDU', edu) or re.search(rb'(?m)^C [0-9A-F ]+', edu), ('EDU status output', edu)
    s.command('Q', 'B3')
    utilities['EDU'] = dict(passed=True, mode_query=True, saved_mode_changed=False)

    s.command('R CLOCK', 'CLOCK', required=(b'CLOCK 1.11',))
    s.command('HELP', required=(b'TIME/R STATUS/S EUI HISTORY SHOW n', b'Q/QUIT'))
    s.command('TIME', required=(b'UTC:',), pattern=rb'20\d\d-\d\d-\d\d')
    before = _clock_status(s.command('STATUS'))
    identity = s.command('EUI', required=(before['EUI'].encode(),))
    history = s.command('HISTORY')
    assert b'No saved event in requested history' in history or re.search(
        rb'(?m)^UTC slot [1-4] seq [0-9A-F]{8}\b', history), ('CLOCK history output', history)
    s.command('STATS', required=(b'Recent estimates: minutes; year inferred; <1yr assumed.',))
    after = _clock_status(s.command('STATUS'))
    _same_clock(before, after)
    s.command('Q', 'B3')
    utilities['CLOCK'] = dict(passed=True, before=before, after=after,
                             control_trim_oscillator_backup_latch_identity_preserved=True,
                             EUI_output_sha256=hashlib.sha256(identity).hexdigest(),
                             battery_command_issued=False, clock_set=False)

    # This is the same fixed launch/copyright/raw-Q path qualified in apps().
    link.send(b'R 1 UCHESS\r')
    game, known_game = b'', False
    try:
        game = link.until(b'Microchess Copyright', 30)
        known_game = game.endswith(b'Microchess Copyright')
        assert known_game
        time.sleep(.3)
    finally:
        if known_game:
            link.send(b'Q')
            game += link.until(PROMPTS['B3'], 30)
    assert game.endswith(PROMPTS['B3']) and b'Peter Jennings' in game
    s.transcript.extend(game)
    utilities['UCHESS'] = dict(passed=True, fixed_image='R 1 UCHESS',
                              copyright=True, raw_Q_return_to_B3=True,
                              output_sha256=hashlib.sha256(game).hexdigest())
    for command in ('C', 'P', 'W'):
        s.command(command)
        assert s.commands[-1]['output_sha256'] == base_status[command], (
            'Configuration/preference/wear changed within utility unit', command)
    assert s.context == 'B3'
    return dict(passed=True, commands=s.commands, utilities=utilities,
                VERSION_sha256=hashlib.sha256(version).hexdigest(),
                configuration_sha256=hashlib.sha256(config).hexdigest(),
                preference_sha256=hashlib.sha256(preference).hexdigest(),
                base_status_sha256=base_status,
                map_view=map_number, volatile_flash_reads=banks, BATCH=True,
                persistent_commands_issued=False, native_applications_tested=False,
                native_debugging=False, final_context='B3'), bytes(s.transcript)


def _variants():
    try:
        return importlib.import_module('variants')
    except ModuleNotFoundError as error:
        if error.name != 'variants':
            raise
        return importlib.import_module('rc1_dbg_soak_variants')


def _qualified_s19(path, expected):
    cells, entry = {}, None
    for line in path.read_text(encoding='ascii').splitlines():
        assert line[:2] in ('S0', 'S1', 'S9'), ('Unexpected fixture record', path)
        raw = bytes.fromhex(line[2:])
        assert raw and len(raw) == raw[0] + 1 and sum(raw) & 255 == 255
        address = int.from_bytes(raw[1:3], 'big')
        if line.startswith('S1'):
            for offset, value in enumerate(raw[3:-1]):
                assert address + offset not in cells
                cells[address + offset] = value
        elif line.startswith('S9'):
            assert entry is None and len(raw) == 4
            entry = address
    assert entry == 0x200 and cells == dict(enumerate(expected, 0x200)), (
        'Canonical image differs from CPU-qualified bytes; load refused', path)
    assert expected and 0x200 + len(expected) - 1 <= 0x64FF
    return cells


def _inspect_debugger(s, context):
    s.command('?', required=(b'C S N R U D M B BC F X',))
    registers = s.command('R')
    fields = re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})', registers)
    assert fields and [int(v, 16) for v in fields.groups()] == [int.from_bytes(context[:2], 'little'), *context[2:]]
    functions = s.command('F')
    ids = re.findall(rb'(?m)^([0-9A-F]{2})(?: [0-9A-F]{4})?\s*$', functions)
    assert ids == [b'80', b'81', b'82', b'83', b'84'], ('Unexpected function list', functions)
    before = s.command('B')
    assert not re.search(rb'(?m)^[0-9A-F]{4}\s*$', before), ('Unexpected armed breakpoint', before)
    s.command('BC *')
    after = s.command('B')
    assert not re.search(rb'(?m)^[0-9A-F]{4}\s*$', after)
    assert s.link.dump(0x7000, 0x7006, PROMPTS['DBG']) == context, 'Inspection changed saved context'
    enabled = s.link.dump(0x7040, 0x705F, PROMPTS['DBG'])[3::4]
    assert enabled == bytes(8), 'Breakpoint clear failed'
    return dict(passed=True, commands=['?', 'R', 'F', 'B', 'BC *', 'B'],
                builtins=[0x80, 0x81, 0x82, 0x83, 0x84], context_preserved=True,
                eight_breakpoint_slots_disabled=True)


def builtins_unit(link, transport, cases, image_root, cycle):
    """Execute four CPU-qualified canonical images, covering BRK $80-$84."""
    assert isinstance(cycle, int) and cycle >= 0
    seeds = sorted({case['seed'] for case in cases})
    assert len(seeds) == 4
    seed = seeds[cycle % 4]
    selected = []
    for family in BUILTIN_FAMILIES:
        matches = [case for case in cases if case['seed'] == seed and case['family'] == family]
        assert len(matches) == 1, ('Missing or duplicate canonical family', family, seed)
        selected.append(matches[0])
    # Validate all files before the first load; never run an unqualified image.
    root = Path(image_root).resolve()
    fixtures = []
    for case in selected:
        assert Path(case['name']).name == case['name'] and '/' not in case['name'] and '\\' not in case['name']
        expected = bytes.fromhex(case['assembled_hex'])
        path = root / (case['name'] + '.s19')
        cells = _qualified_s19(path, expected)
        fixtures.append((case, expected, path, cells))
    variants, s, results, services = _variants(), Session(link), [], set()
    for index, (case, expected, path, cells) in enumerate(fixtures):
        loaded = transport.load(link, path)
        assert loaded == cells, 'Loader cells differ from qualified image'
        actual = transport.read_range(link, 0x200, 0x200 + len(expected) - 1, PROMPTS['B3'])
        assert actual == expected, 'Loaded image differs; execution refused'
        console = link.command('G 0200', PROMPTS['DBG'])
        _payload(console, 'G 0200', PROMPTS['DBG'])
        s.context = 'DBG'
        s.transcript.extend(console)
        context = link.dump(0x7000, 0x7006, PROMPTS['DBG'])
        variants.check_stop(case, context, actual, console)
        for address, body in case['memory'].items():
            wanted = bytes.fromhex(body)
            assert transport.read_range(link, int(address, 16), int(address, 16) + len(wanted) - 1, PROMPTS['DBG']) == wanted
        inspection = _inspect_debugger(s, context) if index == 0 else None
        s.command('C', 'B3')
        cleanup = variants.check_hold_cleanup(link)
        assert transport.read_range(link, 0x200, 0x200 + len(expected) - 1, PROMPTS['B3']) == expected
        services.update(case['services'])
        results.append(dict(passed=True, name=case['name'], family=case['family'], seed=seed,
                            services=case['services'], bytes=len(expected),
                            image_sha256=hashlib.sha256(expected).hexdigest(),
                            s19_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            exact_model_image_verified_before_execution=True,
                            context_hex=context.hex(), HOLD_cleanup=cleanup,
                            program_bytes_unchanged=True, debugger_inspection=inspection))
    assert set(range(0x80, 0x85)) <= services
    return dict(passed=True, seed=seed, cases=results, builtins=list(range(0x80, 0x85)),
                services=list(range(0x80, 0x85)),
                all_builtins_each_unit=True, native_debugging=False,
                final_context='B3'), bytes(s.transcript)
