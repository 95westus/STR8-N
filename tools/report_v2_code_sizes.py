"""Report a22 linked code sizes, grouping internal labels into complete routines."""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'BUILD/v2-alpha22'
OUT = ROOT / 'output/v2a22-code-sizes'

# Ordered boundaries reviewed against source. A slash joins shared/fall-through
# entries; internal branch labels stay inside their enclosing routine.
GROUPS = {
    'str8n-v2': '''
V2_SIGNATURE|data
START|Resident ABI jump table
V2_RESERVED
V2_CAPS_DATA|data
V2_RESET|V2_RESET / V2_REENTER / V2_ENTER / prompt and dispatch
V2_SHOW_HELP
V2_COMMAND_B
V2_COMMAND_J
V2_BAD_BANK|Error reporting / V2_MESSAGE / V2_CANCELLED
V2_PARSE_BANK
V2_SR_DISPATCH
V2_BAD_HEX|Hex/range/protection error exits
V2_GET_ADDRESS
V2_COMMAND_G
V2_COMMAND_D
V2_COMMAND_M|V2_COMMAND_M / V2_EDIT_BEGIN
V2_COPY_BYTES
V2_APPLICATION_ADDRESS
V2_MODIFIABLE_ADDRESS
V2_SKIP_SPACES
V2_HEX_WORD|V2_HEX_WORD / V2_HEX_BYTE / V2_HEX_PARSE
V2_COMMAND_L
V2_LOAD_ERROR
V2_LOAD_DRAIN
V2_RECORD_END
V2_SREC
V2_SREC_CHAR
V2_SREC_BYTE
V2_COMMAND_F
V2_FLASH_COMPLETE
V2_FLASH_BANK
V2_PRINT_ADDR
V2_CONFIRM
V2_F_RISK_CONFIRM
V2_COMMAND_I
V2_I_BUFFER
V2_I_CANCEL_POLL
V2_FLASH_MODE
V2_COMMAND_C
V2_CONFIG_READ|V2_CONFIG_READ / V2_CONFIG_CHECK
V2_CONFIG_SUM
V2_CONFIG_SHOW
V2_AUTO_HEADLESS
V2_AUTO_KEY
V2_CAPTURE_BANK
V2_READ_LINE
V2_PRINT
V2_COMMAND_KEYS|data
V2_END|end
''',
    'str8n-v2-worker': '''
START|Bank boot / V2W_EXECUTE / V2W_READ / failure exits
V2W_SELECT
V2W_BITS|data
V2W_BEGIN|V2W_BEGIN / V2W_INIT
V2W_NEXT
V2W_SNAPSHOT|V2W_SNAPSHOT / V2W_RETURN
V2W_ANALYZE
V2W_MUTATE|V2W_MUTATE / self-edit result and reset
V2W_OK_TEXT|data
V2W_SEND
V2W_ACIA_SEND
V2W_UNLOCK
V2W_WAIT
V2W_RX_RESET
V2W_RX_SERVICE
V2W_GETC
V2W_CHECK_CANCEL
V2W_CON_INIT
V2W_RAW_POLL
V2W_PUTC
V2W_BOOT_DELAY
V2W_END|end
''',
    'str8n-v2-vectors': '''
V2V_NMI
V2V_COP
V2V_ABORT
V2V_IRQ_BRK
V2V_NATIVE_COP
V2V_NATIVE_BRK
V2V_NATIVE_ABORT
V2V_NATIVE_NMI
V2V_NATIVE_IRQ
V2V_DEFAULT
V2V_RAM_CAPS_QUERY
V2V_RAM_SIGNATURE|data
V2V_RAM_RESET_ENTRY|RAM ABI jump table
V2V_RAM_RESET
V2V_RAM_HOLD
V2V_RAM_HEX_NIBBLE
V2V_RAM_HEX_OUT|V2V_RAM_HEX_OUT / V2V_RAM_NIBBLE_OUT
V2V_RAM_NEWLINE
V2V_RAM_BOARD_QUERY
V2V_END|end
''',
    'str8n-v2-sr': '''
SR_DESCRIPTOR|data
SR_COMMAND_SAVE|S/R/T ABI jump table
SR_API_SAVE
SR_API_RESTORE|SR_API_RESTORE / shared status and bank-return exits
SR_COPY_REQUEST
SR_VALIDATE
SR_HEADER_FITS
SR_LOAD_HEADER
SR_SET_BODY_CURSOR
SR_READ
SR_NEXT
SR_AT_LIMIT
SR_PREFLIGHT
SR_WRITE_RECORD
SR_SNAPSHOT
SR_WRITE_SECTOR
SR_COMMIT_MARKER
SR_CLI_SAVE
SR_CLI_RESTORE|SR_CLI_RESTORE / shared CLI result and errors
SR_PARSE_BANK
SR_PARSE_FLASH
SR_CLI_TABLE
SR_TABLE_ROW
SR_SPACE
SR_END|end
''',
}

# Functional categories cross source-file boundaries (for example, serial send
# routines live in flash-worker.inc but belong to console I/O).
CATEGORIES = {
    'Console I/O': '''V2_READ_LINE V2W_RX_SERVICE V2W_CON_INIT V2W_RAW_POLL V2W_PUTC V2W_GETC V2W_SEND V2W_CHECK_CANCEL V2W_ACIA_SEND V2W_RX_RESET''',
    'Text and formatted output': '''V2_PRINT V2V_RAM_HEX_OUT V2V_RAM_NEWLINE V2_PRINT_ADDR V2_SHOW_HELP V2_FLASH_BANK V2_FLASH_MODE SR_SPACE''',
    'Input parsing and address validation': '''V2_HEX_WORD V2V_RAM_HEX_NIBBLE V2_APPLICATION_ADDRESS V2_MODIFIABLE_ADDRESS V2_GET_ADDRESS V2_PARSE_BANK V2_SKIP_SPACES''',
    'Memory commands and copy': '''V2_COMMAND_D V2_COMMAND_M V2_COMMAND_G V2_COPY_BYTES''',
    'S-record loading': '''V2_COMMAND_L V2_LOAD_ERROR V2_LOAD_DRAIN V2_RECORD_END V2_SREC V2_SREC_CHAR V2_SREC_BYTE''',
    'Flash commands and confirmation': '''V2_COMMAND_I V2_COMMAND_F V2_F_RISK_CONFIRM V2_CONFIRM V2_FLASH_COMPLETE V2_I_BUFFER V2_I_CANCEL_POLL''',
    'Flash programming engine': '''V2W_MUTATE V2W_WAIT V2W_ANALYZE V2W_UNLOCK V2W_BEGIN V2W_SNAPSHOT V2W_NEXT''',
    'Configuration and autostart': '''V2_COMMAND_C V2_AUTO_HEADLESS V2_CONFIG_READ V2_CONFIG_SHOW V2_AUTO_KEY V2_CONFIG_SUM''',
    'Bank selection and execution': '''V2_CAPTURE_BANK V2_COMMAND_B V2_COMMAND_J V2W_SELECT''',
    'Save, restore and inventory': '''SR_VALIDATE SR_API_SAVE SR_CLI_TABLE SR_TABLE_ROW SR_API_RESTORE SR_WRITE_RECORD SR_CLI_SAVE V2_SR_DISPATCH SR_CLI_RESTORE SR_COMMIT_MARKER SR_PREFLIGHT SR_LOAD_HEADER SR_SNAPSHOT SR_HEADER_FITS SR_READ SR_PARSE_FLASH SR_SET_BODY_CURSOR SR_PARSE_BANK SR_AT_LIMIT SR_COPY_REQUEST SR_WRITE_SECTOR SR_NEXT''',
    'Interrupt handlers': '''V2V_IRQ_BRK V2V_NMI V2V_ABORT V2V_COP V2V_NATIVE_ABORT V2V_NATIVE_BRK V2V_NATIVE_COP V2V_NATIVE_IRQ V2V_NATIVE_NMI V2V_DEFAULT''',
    'ABI entries and queries': '''V2V_RAM_BOARD_QUERY V2V_RAM_HOLD V2V_RAM_RESET V2V_RAM_CAPS_QUERY V2_RESERVED''',
    'Startup and command loop': '''V2_RESET V2W_BOOT_DELAY''',
    'Error messages and cancellation': '',
}


def categorized_report(rows, total):
    lookup = {name: category for category, names in CATEGORIES.items() for name in names.split()}
    special = {
        'Resident ABI jump table': 'ABI entries and queries',
        'RAM ABI jump table': 'ABI entries and queries',
        'S/R/T ABI jump table': 'ABI entries and queries',
        'Bank boot / V2W_EXECUTE / V2W_READ / failure exits': 'Bank selection and execution',
        'Error reporting / V2_MESSAGE / V2_CANCELLED': 'Error messages and cancellation',
        'Hex/range/protection error exits': 'Error messages and cancellation',
    }
    categorized = []
    for row in rows:
        category = special.get(row['routine']) or lookup[row['routine'].split()[0]]
        categorized.append(dict(category=category, **row))
    totals = {c: sum(r['bytes'] for r in categorized if r['category'] == c) for c in CATEGORIES}
    ordered = sorted(totals, key=lambda c: (-totals[c], c))
    assert sum(totals.values()) == total
    lines = ['# v2.0a22 subroutine bytes by functional category', '',
             'Categories and routines are sorted largest first. Sizes are assembled machine-code bytes. '
             'Internal branch labels stay with their routine; shared fall-through implementations are grouped. '
             'Called helpers are counted separately, once. Text strings and other data are excluded. '
             'Scope is firmware, excluding install/repair utilities and test probes. '
             'Source hashes match the a22 build manifest.', '',
             f'**Total: {total:,} code bytes.**', '', '| Category | Bytes |', '|---|---:|']
    lines += [f'| {c} | {totals[c]:,} |' for c in ordered]
    for category in ordered:
        lines += ['', f'## {category} — {totals[category]:,} bytes', '', '| Subroutine / shared group | Bytes |', '|---|---:|']
        lines += [f'| {r["routine"]} | {r["bytes"]} |' for r in categorized if r['category'] == category]
    (OUT / 'by-category.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    with (OUT / 'by-category.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=categorized[0].keys())
        writer.writeheader()
        writer.writerows(r for c in ordered for r in categorized if r['category'] == c)


def main():
    build = json.loads((BUILD / 'build.json').read_text())
    for name, expected in build['source_sha256'].items():
        assert hashlib.sha256((ROOT / 'src/v2a22' / name).read_bytes()).hexdigest() == expected, name
    maps = {}
    rows = []
    for module, spec in GROUPS.items():
        syms = dict((n, int(a, 16)) for a, n in re.findall(
            r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
            (BUILD / 'asm' / (module + '.map')).read_text(), re.M))
        maps[module] = syms
        boundaries = [line.split('|', 1) for line in spec.strip().splitlines()]
        for current, following in zip(boundaries, boundaries[1:]):
            start, end = syms[current[0]], syms[following[0]]
            assert end > start, (module, current, following)
            label = current[-1]
            if label == 'data':
                continue
            rows.append(dict(module=module, routine=label, start=f'${start:04X}',
                             end=f'${end-1:04X}', bytes=end-start))
    rows.sort(key=lambda r: (-r['bytes'], r['module'], r['routine']))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'routines.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    m, w = maps['str8n-v2'], maps['str8n-v2-worker']
    modules = [
        ('S/R/T extension', sum(r['bytes'] for r in rows if r['module'].endswith('-sr'))),
        ('Flash commands and install', m['V2_COMMAND_C']-m['V2_COMMAND_F']),
        ('Monitor commands and hex parser', m['V2_COMMAND_L']-m['V2_BAD_HEX']),
        ('Configuration and autostart', m['V2_CAPTURE_BANK']-m['V2_COMMAND_C']),
        ('S-record loader', m['V2_COMMAND_F']-m['V2_COMMAND_L']),
        ('RAM flash worker', w['V2W_RX_RESET']-w['V2W_BEGIN']-(w['V2W_SEND']-w['V2W_OK_TEXT'])),
        ('RAM console', w['V2W_BOOT_DELAY']-w['V2W_RX_RESET']),
        ('RAM vectors and ABI', sum(r['bytes'] for r in rows if r['module'].endswith('-vectors'))),
        ('RAM bank access and boot delay', w['V2W_BITS']-w['START']+w['V2W_END']-w['V2W_BOOT_DELAY']),
    ]
    resident = sum(r['bytes'] for r in rows if r['module'] == 'str8n-v2')
    modules.append(('Resident core, dispatch and text output', resident-sum(n for _, n in modules[1:5])))
    modules.sort(key=lambda r: -r[1])
    total = sum(r['bytes'] for r in rows)
    assert sum(n for _, n in modules) == total
    categorized_report(rows, total)
    # Physical storage counts the worker/vector images once, in resident ROM.
    storage = build['resident_bytes'] + build['sr_bytes']
    lines = ['# v2.0a22 assembled code sizes', '',
             'Largest first. Verified all source SHA-256 hashes against BUILD/v2-alpha22/build.json.', '',
             'Counts are emitted machine-code bytes, including ABI JMP instructions and reset XCE bytes. '
             'Text, descriptors, lookup tables, padding, and hardware vector words are excluded. '
             'RAM worker/vector code is counted once, although its initial image is stored in ROM. '
             'Scope: shipped monitor, RAM worker, RAM vectors/ABI, and S/R/T extension; installers, repair utilities, and test probes are excluded.', '',
             'Routine rows are non-overlapping source blocks with internal branches included. '
             'Shared fall-through entries and shared exit paths are grouped as named; separately listed callees are not added to caller sizes.', '',
             f'**Total machine code: {total:,} bytes.** Code plus embedded data: {storage:,} bytes '
             f'({build["resident_bytes"]:,} resident + {build["sr_bytes"]:,} extension); embedded data: {storage-total:,} bytes.', '',
             '## Complete functional modules', '', '| Module | Code bytes |', '|---|---:|']
    lines += [f'| {name} | {size:,} |' for name, size in modules]
    lines += ['', '## Complete routines and shared routine groups', '',
              '| Routine / group | Code bytes | Address range | Linked module |', '|---|---:|---|---|']
    lines += [f'| {r["routine"]} | {r["bytes"]} | {r["start"]}–{r["end"]} | {r["module"]} |' for r in rows]
    (OUT / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines[:26]))
    print(f'Routine rows: {len(rows)}; report: {OUT / "report.md"}')


if __name__ == '__main__':
    main()
