"""Offline message inventory of CLOCK-summary build and archived 2609 flash.

Counts explicit quoted DB declarations in selected assembled listings, plus
the packed monitor pool and generated extension help. Not a disassembler:
instruction immediates, numeric-only formatting fragments and runtime data
are outside this inventory. No serial access or firmware writes.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'BUILD/v2-clock-summary'
READBACK = ROOT / 'output/qualification/clock-summary-2609-2026-10-15/upgrade'
# Listing, bank, inclusive start, exclusive end. Each linked module once.
COMPONENTS = [
    ('recovery', 'asm/str8n-v2-boot.lst', 3, 0xF000, 0x10000),
    ('launcher', 'asm/launcher.lst', 3, 0xE000, 0xE800),
    ('storage-service', 'asm/str8n-v2-sr.lst', 3, 0xE800, 0xEF00),
    ('rtc-provider', 'resident-provider/asm/rtc-provider.lst', 3, 0x8000, 0x8900),
    ('rtc-banner', 'banner/asm/rtc-banner.lst', 3, 0x8900, 0x9000),
    ('rtc-journal', 'resident-journal/asm/journal.lst', 3, 0x9000, 0xA000),
    ('status', 'storage-status/asm/storage-status.lst', 2, 0xC800, 0xD200),
    ('local-display', 'local-display/asm/local-display.lst', 2, 0xE000, 0xE700),
    ('MAINT', 'maint/asm/bank-maint.lst', 1, 0x8000, 0xB000),
    ('CLOCK', 'clock/asm/clock.lst', 1, 0xB000, 0xE000),
    ('SRAM-core', 'store/asm/sram-store.lst', 2, 0xA000, 0xB000),
    ('SRAM-data', 'store/asm/sram-data.lst', 2, 0xA000, 0xB000),
    ('SRAM-stream', 'store/asm/sram-stream.lst', 2, 0xA000, 0xB000),
    ('SRAM-layout', 'store/asm/sram-layout.lst', 2, 0xA000, 0xB000),
    ('WORK', 'workspace/asm/workspace.lst', 2, 0xB000, 0xC580),
    ('EDU', 'edu/asm/edu.lst', 2, 0xC580, 0xC800),
]


def declaration(source):
    # Quoted strings may contain commas and semicolons.
    source = re.split(r';(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', source)[0]
    match = re.match(r'\s*(?:(\w+):?\s+)?DB\s+(.+)', source, re.I)
    if not match:
        return None
    tokens = re.findall(r'"[^"]*"|\x27[^\x27]*\x27|[^,]+', match[2])
    data = bytearray()
    quoted = False
    for token in tokens:
        token = token.strip()
        if token.startswith(('"', "'")):
            data.extend(token[1:-1].encode('ascii'))
            quoted = True
        elif re.fullmatch(r'\$[0-9A-Fa-f]+|[0-9]+', token):
            data.append(int(token[1:], 16) if token.startswith('$') else int(token))
        else:
            return None
    return match[1], bytes(data), quoted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'BUILD/message-catalog-audit.json')
    args = parser.parse_args()
    banks = [(READBACK/f'post-reset-b{b}.bin').read_bytes() for b in range(4)]
    receipt = json.loads((READBACK/'post-reset-report.json').read_text())
    assert receipt['passed']
    hashes = [hashlib.sha256(b).hexdigest() for b in banks]
    assert hashes == receipt['expected_hashes']
    rows, components = [], []
    for name, listing, bank, start, end in COMPONENTS:
        path = BUILD/listing
        module = banks[bank][start-0x8000:end-0x8000]
        inherited = None
        lines = path.read_text().splitlines()
        source_lines = path.with_suffix('.asm').read_text().splitlines()
        for index, line in enumerate(lines):
            # WDC listing source starts at column 29. Continuation hex rows
            # have no source and therefore cannot be counted twice.
            if not re.match(r'\s*\d+ [0-9A-F]{2}:[0-9A-F]{4}:', line):
                continue
            source = line[29:]
            match = re.match(r'\s*(?:(\w+):?\s+)?DB\s+(.+)', source, re.I)
            if not match:
                continue
            label = match[1]
            if label:
                inherited = label
            if '"' not in match[2]:
                continue
            # Count emitted bytes: WDC truncates long source lines in listings.
            # Operand parsing would misread a clipped $0A as $0.
            data = bytearray.fromhex(line[16:27])
            for continuation in lines[index+1:]:
                if re.match(r'\s{7}[0-9A-F]{2}:[0-9A-F]{4}:', continuation):
                    data.extend(bytearray.fromhex(continuation[16:27]))
                elif re.match(r'\s*\d+\s', continuation):
                    break
            data = bytes(data)
            full_source = source_lines[int(line[:6])-1]
            full = declaration(full_source)
            assert full and full[2] and full[1].startswith(data), (name, label)
            # The assembler caps a single declaration's displayed bytes at
            # 128. Recover the complete literal from the matching source row.
            data = full[1]
            label = label or inherited or '(anonymous)'
            # Machine identities, parser keywords and formatting tables stay
            # with their code. Explicit labels are reviewed in the JSON output.
            category = 'display'
            if (re.search(r'MAGIC|_ID$|_DISCOVERY$|_SIGNATURE$|_DESCRIPTOR$|^CMD_|_COMMAND$|_WORD$|_WORDS$|_PREFIX$', label)
                    or label in {'MAP_CODES', 'MAP_APP_CAP_ID', 'MAP_APP_TABLE_ID',
                                 'LAYOUT', 'SV_MAGIC', 'SM_MAGIC', 'FORMAT_MAGIC',
                                 'CONFIRM_MAGIC', 'BN_CLEAR_TEXT', 'BN_YES_TEXT',
                                 'TZ_WEEKDAYS', 'WEEKDAYS', 'UNIT_TEXT', 'TRIM_PREFIX',
                                 'START', 'HEADER', '(anonymous)', 'INITIAL_LAYOUT',
                                 'FORMAT_CONFIRM', 'FIXED_CHAR', 'X_MAINT_NAME'}):
                category = 'code-data'
            if name == 'recovery':
                category = 'recovery-retained'
            # Every counted literal must actually occur within this installed
            # component's allocation; a stale listing fails the audit.
            assert data in module, (name, label, data)
            rows.append(dict(component=name, label=label, category=category,
                             bytes=len(data), text=data.decode('latin1'), listing=listing))
        selected = [r for r in rows if r['component'] == name]
        components.append(dict(component=name, bank=bank, start=f'{start:04X}',
                               end=f'{end-1:04X}', declarations=len(selected),
                               display_bytes=sum(r['bytes'] for r in selected if r['category']=='display'),
                               retained_or_code_data_bytes=sum(r['bytes'] for r in selected if r['category']!='display')))

    # Actual packed, high-bit-terminated monitor text, not uncompressed JSON.
    pool = bytes(int(x, 16) for x in re.findall(r'\$([0-9A-F]{2})', (BUILD/'asm/text-image.inc').read_text()))
    for start in (0xA000, 0xB000):
        slot = banks[3][start-0x8000:start-0x8000+4096]
        assert pool in slot or pool.replace(b'2.0b25', b'2.0b24') in slot
    help_start = 0xE7F4-0x8000
    help_end = banks[3].index(0, help_start)+1
    help_data = banks[3][help_start:help_end]
    sectors = [dict(bank=b, sector=f'{s+8:X}', start=f'{0x8000+s*4096:04X}',
                    non_ff_bytes=sum(x!=255 for x in banks[b][s*4096:(s+1)*4096]),
                    erased=banks[b][s*4096:(s+1)*4096]==b'\xff'*4096)
               for b in range(4) for s in range(8)]
    catalog_bytes = sum(r['bytes'] for r in rows if r['category']=='display')+len(pool)+len(help_data)
    entries = len({(r['component'], r['label']) for r in rows if r['category']=='display'})+sum(bool(x&128) for x in pool)+1
    result = dict(baseline=str(BUILD.relative_to(ROOT)), readback=str(READBACK.relative_to(ROOT)),
                  bank_sha256=hashes, components=components, declarations=rows, sectors=sectors,
                  monitor_pool_bytes_per_slot=len(pool), monitor_pool_entries=sum(bool(x&128) for x in pool),
                  extension_help_bytes=len(help_data), extension_help_text=help_data.decode('ascii'),
                  display_inventory_bytes_single_copy=catalog_bytes,
                  display_inventory_entries=entries,
                  proposed_catalog_bytes_8byte_index_64byte_header=catalog_bytes+8*entries+64,
                  proposed_module_directory_bytes=64,
                  proposed_catalog_total_bytes=catalog_bytes+8*entries+128,
                  proposed_copy_capacity_bytes=12288,
                  proposed_copy_spare_bytes=12288-(catalog_bytes+8*entries+128),
                  limitations=['Explicit quoted DB declarations plus generated monitor/help pools only.',
                               'Includes string terminators and control bytes; excludes runtime names and values.',
                               'Numeric-only formatting fragments and character immediates excluded.',
                               'Code-data labels retained; display classification is an audit heuristic.',
                               'Single-copy pool includes normal-monitor errors: final core-retained split remains a design choice.',
                               'Archived readback proves 2609 snapshot only, not live or fleet free space.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('declarations','extension_help_text','sectors')}, indent=2))


if __name__ == '__main__':
    main()
