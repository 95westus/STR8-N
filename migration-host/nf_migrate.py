"""Prepare and inspect private N/F migration plans. No device/serial operations.

This is host admission/serialization code, not a qualified live migrator.
All source banks and owner RAM are supplied as independent repeated captures.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path


F_SHA256 = '8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
F_SIZE = 4096
BANK_SIZE = 32768
OWNER_RAM_SIZE = 0x6500                 # 0200-66FF, inclusive
OWNER_ZP_SIZE = 0xe0                    # 0000-00DF; E0-FF are runtime scratch
SNBT_MONITOR_GENERATION = 0x8000000f
MAX_COUNT = 0xffffff
CPU_MODELS = {'65c02': 'W65C02SXB', '65c816': 'W65C816SXB'}
sha = lambda body: hashlib.sha256(bytes(body)).hexdigest()
crc = lambda body: binascii.crc_hqx(bytes(body), 0xffff)


def require(value, message):
    if not value:
        raise ValueError(message)


def fnv(body):
    value = 0x811c9dc5
    for byte in body:
        value = ((value ^ byte) * 0x01000193) & 0xffffffff
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def durable_write(path, body):
    """Write a new private receipt/member, fsync, then verify its stored bytes."""
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    require(path.read_bytes() == body, 'Stored bytes differ: ' + path.name)


def bank_hashes(banks):
    return [sha(bank) for bank in banks]


def fields_valid(row):
    target = row[7]
    return (row[6] == 0 and row[12] >= 10 and row[13] & 0xf0 == 0
            and all(8 <= entry <= 14 for entry in row[14:18])
            and row[17] not in (12, 13)
            and (target in b'SAB' or (ord('0') <= target <= ord('3')
                                      and row[13] & (1 << (target - ord('0'))))))


def valid_snapshot(row):
    return (len(row) == 256 and row[:6] == b'SNBT\x01\x20'
            and fields_valid(row) and row[254:] == b'\xff\x00'
            and crc(row[:30]) == int.from_bytes(row[30:32], 'little')
            and crc(row[:252]) == int.from_bytes(row[252:254], 'little'))


def classify_journal(bank3):
    """Use stricter mutation admission than F's header-only boot reader."""
    require(len(bank3) == BANK_SIZE, 'Complete B3 required')
    rows, unknown, damaged, legacy = [], [], [], []
    for offset in range(0x4000, 0x6000, 256):
        row = bytes(bank3[offset:offset+256])
        if row == b'\xff' * 256:
            continue
        if row[:4] == b'SNBT':
            if valid_snapshot(row):
                rows.append((int.from_bytes(row[8:12], 'little'), offset+0x8000, row))
            else:
                damaged.append(offset+0x8000)
        elif row[:4] == b'WC\x01\x00' or row[128:132] == b'WC\x01\x00':
            legacy.append(offset+0x8000)
        else:
            unknown.append(offset+0x8000)
    if damaged or legacy or (rows and unknown):
        return dict(kind='uncertain', valid_records=len(rows), damaged_pages=damaged,
                    legacy_pages=legacy, unknown_pages=unknown,
                    reason='Damaged, legacy or mixed journal history requires a separate inspected import/repair')
    if rows:
        newest = max(sequence for sequence, _, _ in rows)
        newest_rows = [row for sequence, _, row in rows if sequence == newest]
        # A committed equal-sequence disagreement is not resolved by address.
        grouped = {}
        for sequence, _, row in rows:
            grouped.setdefault(sequence, set()).add(row)
        if any(len(copies) > 1 for copies in grouped.values()):
            return dict(kind='uncertain', valid_records=len(rows),
                        reason='Conflicting committed SNBT records at the same sequence')
        selected = newest_rows[0]
        counts = [int.from_bytes(selected[64+3*n:67+3*n], 'little') for n in range(32)]
        # Counts must not regress in a newer committed snapshot.
        if any(any(int.from_bytes(row[64+3*n:67+3*n], 'little') > counts[n]
                   for n in range(32)) for _, _, row in rows):
            return dict(kind='uncertain', valid_records=len(rows),
                        reason='Newest SNBT counters regress relative to retained history')
        return dict(kind='valid-snbt', valid_records=len(rows), sequence=newest,
                    default=chr(selected[7]), enabled_mask=selected[13],
                    entries=list(selected[14:18]), counts=counts,
                    unknown_mask=f'{int.from_bytes(selected[160:164], "little"):08x}')
    if unknown:
        return dict(kind='occupied-unrecognized', occupied_pages=unknown,
                    reason='Not a recognized journal; conversion requires explicit source declaration and provisioning')
    return dict(kind='blank', valid_records=0)


def snapshot(counts, sequence, unknown_mask=0xffffffff):
    require(len(counts) == 32 and all(type(n) is int and 0 <= n <= MAX_COUNT for n in counts),
            'Thirty-two valid 24-bit counters required')
    require(type(sequence) is int and 1 <= sequence <= 0xffffffff, 'Invalid SNBT sequence')
    require(type(unknown_mask) is int and 0 <= unknown_mask <= 0xffffffff, 'Invalid unknown-history mask')
    row = bytearray(b'\xff' * 256)
    row[:8] = b'SNBT\x01\x20\x00S'
    row[8:12] = sequence.to_bytes(4, 'little')
    row[12:18] = bytes((30, 0, 8, 8, 8, 8))
    row[18:22] = SNBT_MONITOR_GENERATION.to_bytes(4, 'little')
    row[22:30] = bytes(8)
    row[32:48] = bytes(16)             # no legacy application configuration inferred
    row[64:160] = b''.join(value.to_bytes(3, 'little') for value in counts)
    row[160:164] = unknown_mask.to_bytes(4, 'little')
    row[164:168] = bytes((1, 0, 0, 0)) # retained/observed provisioning lower bounds
    row[30:32] = crc(row[:30]).to_bytes(2, 'little')
    row[252:254] = crc(row[:252]).to_bytes(2, 'little')
    row[255] = 0
    require(valid_snapshot(row), 'Internal snapshot serialization failure')
    return bytes(row)


def read_capture(root, cpu, source_kind):
    root = Path(root).resolve()
    identity = read_json(root/'capture.json')
    require(identity.get('schema') == 1, 'Unsupported capture schema')
    require(cpu in CPU_MODELS and identity.get('cpu') == cpu
            and identity.get('board_model') == CPU_MODELS[cpu], 'CPU/board declaration mismatch')
    require(identity.get('source_kind') == source_kind and source_kind in ('wdcmonv2', 'nf-recovery'),
            'Source-kind declaration mismatch')
    require(identity.get('method') == 'independent-double-read', 'Independent repeated captures required')
    if source_kind == 'wdcmonv2':
        try:
            info = bytes.fromhex(identity.get('wdc_info_hex', ''))
        except ValueError as error:
            raise ValueError('Malformed saved WDC debugger identity') from error
        require(len(info) == 12 and info[:3] == b'SXB' and 33 <= info[3] <= 126,
                'Saved twelve-byte WDC debugger identity required')
    members = {}

    def pair(stem, size):
        first, second = root/(stem+'.bin'), root/(stem+'-repeat.bin')
        require(not first.samefile(second), 'Repeated captures must be separate files: ' + stem)
        body, repeated = first.read_bytes(), second.read_bytes()
        require(len(body) == size and body == repeated, 'Incomplete/different repeated capture: ' + stem)
        members[first.name], members[second.name] = body, repeated
        return body

    banks = [pair('b'+str(n), BANK_SIZE) for n in range(4)]
    pair('owner-ram', OWNER_RAM_SIZE)
    pair('owner-zp', OWNER_ZP_SIZE)
    members['capture.json'] = encoded(identity)
    return identity, banks, members


def history_for_new_journal(history, source_hashes):
    if history is None:
        return [0]*32, 0, 0xffffffff, 'No imported erase history; previous lifetime remains unknown'
    require(history.get('schema') == 1 and history.get('semantics') == 'tracked-lower-bounds',
            'Imported history must declare tracked-lower-bounds semantics')
    require(history.get('source_sha256') == source_hashes, 'Imported history is not bound to these source banks')
    require(isinstance(history.get('provenance'), str) and history['provenance'].strip(),
            'Imported history needs its owner-local provenance description')
    counts = history.get('counts')
    require(isinstance(counts, list) and len(counts) == 32
            and all(type(value) is int and 0 <= value <= MAX_COUNT for value in counts),
            'Invalid imported erase counters')
    sequence = history.get('sequence')
    require(type(sequence) is int and 0 <= sequence <= 0xfffffffd, 'Imported sequence exhausted/invalid')
    # WDC has no authenticated total-lifetime counter: retain conservative unknown status.
    require(history.get('unknown_mask') == 'ffffffff', 'Factory/imported prior lifetime must remain unknown')
    return counts.copy(), sequence, 0xffffffff, history['provenance']


def derive(banks, f_image, *, source_kind, provision_cd=False, history=None):
    require(len(banks) == 4 and all(len(body) == BANK_SIZE for body in banks), 'Four complete banks required')
    require(len(f_image) == F_SIZE and sha(f_image) == F_SHA256
            and f_image[:4] == b'SN\x02\x00' and f_image[0xffc:0xffe] == b'\x04\xf0',
            'Only the frozen 4096-byte PR05 F candidate is admitted')
    status = classify_journal(banks[3])
    require(status['kind'] != 'uncertain', status.get('reason', 'Uncertain journal'))
    source_hashes = bank_hashes(banks)
    f_changed = bytes(banks[3][-4096:]) != f_image
    if status['kind'] == 'valid-snbt':
        require(not provision_cd and history is None, 'Existing SNBT settings/history must be preserved')
        require(not f_changed,
                'Existing SNBT F upgrade needs an onboard append reservation; not supported by this checkpoint')
        return dict(journal_before=status, source_sha256=source_hashes, expected_sha256=source_hashes,
                    operations=[], counts_before=status['counts'], reserved_counts=status['counts'],
                    prior_history_unknown_mask=status['unknown_mask'], sequence_after=status['sequence'],
                    boot_policy='preserved', completed_noop=True), [], list(map(bytes, banks))
    require(provision_cd, 'No usable SNBT journal; explicit --provision-cd is required for this minimal migration')
    require(source_kind in ('wdcmonv2', 'nf-recovery'), 'Explicit supported source declaration required')
    if source_kind == 'nf-recovery':
        require(not f_changed, 'NF recovery provisioning requires the frozen F already installed')
    counts, sequence, unknown_mask, provenance = history_for_new_journal(history, source_hashes)
    reserved = counts.copy()
    addresses = ([0xf000] if f_changed else []) + [0xd000, 0xc000]
    for address in addresses:
        index = 24 + (address >> 12)-8
        require(reserved[index] < MAX_COUNT, f'Erase counter exhausted for B3:{address:04X}')
        reserved[index] += 1
    require(sequence <= 0xfffffffd, 'Journal sequence exhausted')
    final_rows = [snapshot(reserved, sequence+n+1, unknown_mask) for n in range(2)]
    payloads = ([f_image] if f_changed else []) + [row+b'\xff'*3840 for row in final_rows]
    state, operations, transfers = list(map(bytearray, banks)), [], []
    for n, (address, body) in enumerate(zip(addresses, payloads)):
        before = bank_hashes(state)
        source_b3_fnv = fnv(state[3])
        commit = address+255 if address in (0xc000, 0xd000) else None
        transfer = bytearray(body)
        if commit is not None:
            transfer[255] = 255
        state[3][address-0x8000:address-0x7000] = body
        operations.append(dict(index=n, bank=3, address=address, bytes=4096, erase=True,
            kind='bootstrap-F' if address == 0xf000 else 'first-SNBT-journal',
            commit_address=commit, commit_value=0 if commit is not None else None,
            source_sha256=before, after_sha256=bank_hashes(state),
            data_sha256=sha(body), transfer_sha256=sha(transfer),
            source_b3_fnv=f'{source_b3_fnv:08x}', transfer_fnv=f'{fnv(transfer):08x}',
            final_b3_fnv=f'{fnv(state[3]):08x}',
            transfer_file=f'transfer-{n:02d}.bin', final_file=f'final-sector-{n:02d}.bin'))
        transfers.append((bytes(transfer), bytes(body)))
    require(all(state[n] == banks[n] for n in range(3)) and state[3][:0x4000] == banks[3][:0x4000]
            and state[3][0x6000:0x7000] == banks[3][0x6000:0x7000], 'Mutation escaped F/C/D')
    require(classify_journal(state[3])['kind'] == 'valid-snbt', 'Expected journal is invalid')
    return dict(journal_before=status, source_sha256=source_hashes, expected_sha256=bank_hashes(state),
                operations=operations, counts_before=counts, reserved_counts=reserved,
                prior_history_unknown_mask=f'{unknown_mask:08x}', history_provenance=provenance,
                sequences=[sequence+1, sequence+2], sequence_after=sequence+2,
                boot_policy='S recovery; all banks disabled; entries 8000', completed_noop=False), transfers, list(map(bytes, state))


def engine_plan(plan):
    """Serialize the RAM engine's 256-byte NFM1 parameter area."""
    tx = plan['transaction']
    operations = tx['operations']
    require(1 <= len(operations) <= 3, 'No-op plans do not execute a RAM engine')
    require([op['address'] for op in operations] in ([0xf000, 0xd000, 0xc000], [0xd000, 0xc000]),
            'This host checkpoint only renders complete first-journal provisioning')
    require(len(plan['source_bank_fnv']) == 4
            and all(isinstance(value, str) and len(value) == 8
                    and all(char in '0123456789abcdefABCDEF' for char in value)
                    for value in plan['source_bank_fnv']), 'Invalid complete-bank FNV guards')
    row = bytearray(256)
    row[:8] = b'NFM1'+bytes((1, len(operations), 0, 0))
    row[8:24] = b''.join(int(value, 16).to_bytes(4, 'little') for value in plan['source_bank_fnv'])
    for index, op in enumerate(operations):
        require(op['bank'] == 3 and op['erase'] is True and op['address'] in (0xf000, 0xd000, 0xc000),
                'Unsupported RAM operation')
        commit = int(op['commit_address'] is not None)
        require(commit == int(op['address'] in (0xd000, 0xc000)), 'Missing/unexpected journal commit')
        offset = 32+index*16
        row[offset:offset+4] = bytes((op['address'] >> 8, commit, 0, 0))
        for position, key in ((4, 'source_b3_fnv'), (8, 'transfer_fnv'), (12, 'final_b3_fnv')):
            row[offset+position:offset+position+4] = int(op[key], 16).to_bytes(4, 'little')
    return bytes(row)


def s19(image, entry):
    def record(kind, address, body=b''):
        row = bytes((len(body)+3,))+address.to_bytes(2, 'big')+body
        return 'S'+kind+(row+bytes((255-(sum(row)&255),))).hex().upper()
    rows = [record('0', 0, b'STR8N-F verbose RAM migrator NFM1')]
    rows += [record('1', 0x2000+n, image[n:n+32]) for n in range(0, len(image), 32)]
    return ('\n'.join(rows+[record('9', entry)])+'\n').encode('ascii')


def render_engine(template, plan):
    require(len(template) == 8192, 'RAM engine template must occupy exactly 2000-3FFF')
    image = bytearray(template)
    image[0x1000:0x1100] = engine_plan(plan)
    image[0x1ffc:] = fnv(image[:0x1ffc]).to_bytes(4, 'little')
    entry = 0x2010 if plan['cpu'] == '65c816' and plan['source_kind'] == 'wdcmonv2' else 0x2000
    return bytes(image), entry


def progress_lines(plan):
    tx = plan['transaction']
    lines = [f"N/F PREPARE: {plan['board_model']} / {plan['cpu']} / {plan['source_kind']}",
             'CAPTURE: four complete banks and owner RAM/ZP; repeated bytes agree',
             'F TARGET: 4096 bytes; PR05 SHA-256 '+F_SHA256,
             'JOURNAL: '+tx['journal_before']['kind'],
             'KEEP: B0/B1/B2 and B3:8/9/A/B/E; no WDC backup copied into user banks']
    if tx['completed_noop']:
        lines.append('NO-OP: F matches and existing valid journal/settings are preserved')
    for op in tx['operations']:
        lines.append(f"PLAN {op['index']+1}/{len(tx['operations'])}: erase/program/verify B3:{op['address']:04X}, 4096 bytes"
                     + ('; journal commit byte written last' if op['commit_address'] is not None else ''))
    wear = ('WEAR: existing journal counts and prior-history mask preserved' if tx['completed_noop'] else
            'WEAR: counts are observed/imported lower bounds; prior lifetime remains unknown')
    lines += [wear,
              'RAM: escrowed; restoration has NOT been performed by this preparation tool',
              'STOP: no device opened; no flash written; execution/hardware qualification pending']
    return lines


def prepare(capture, f_file, out, *, cpu, source_kind, provision_cd=False, history_file=None, template_file=None):
    out = Path(out).resolve()
    require(not out.exists(), 'Use a fresh private output directory')
    identity, banks, capture_members = read_capture(capture, cpu, source_kind)
    f_image = Path(f_file).read_bytes()
    history = read_json(history_file) if history_file else None
    tx, transfers, expected = derive(banks, f_image, source_kind=source_kind,
                                     provision_cd=provision_cd, history=history)
    plan = dict(schema=1, purpose='Unqualified minimal N/F migration preparation',
                cpu=cpu, board_model=CPU_MODELS[cpu], source_kind=source_kind,
                source_identity=identity, F_bytes=4096, F_sha256=F_SHA256,
                source_bank_fnv=[f'{fnv(bank):08x}' for bank in banks], transaction=tx,
                hardware_access=False, serial_access=False, flash_written=False,
                execution_qualified=False, installation_permitted=False,
                live_source_admitted=False, owner_RAM_restored=False,
                owner_RAM_restore_required=not tx['completed_noop'],
                owner_RAM_range='0200-66FF', owner_ZP_range='0000-00DF',
                counts_semantics='Conservative erase-attempt reservations; preparation does not update authoritative history',
                files={})
    members = {'source/'+name: body for name, body in capture_members.items()}
    members['target-F-4096.bin'] = f_image
    if history is not None:
        members['imported-history.json'] = encoded(history)
    for n, body in enumerate(expected):
        members[f'expected-b{n}.bin'] = body
    for op, (transfer, final) in zip(tx['operations'], transfers):
        members[op['transfer_file']] = transfer
        members[op['final_file']] = final
    reservation = dict(schema=1, source_sha256=tx['source_sha256'], operations=tx['operations'],
                       counts_before=tx['counts_before'], reserved_counts=tx['reserved_counts'],
                       prior_history_unknown_mask=tx['prior_history_unknown_mask'],
                       status='planned-not-executed', authoritative_history_updated=False)
    members['erase-intent.json'] = encoded(reservation)
    if template_file and tx['operations']:
        template = Path(template_file).read_bytes()
        image, entry = render_engine(template, plan)
        plan.update(engine_template_sha256=sha(template), engine_image_sha256=sha(image),
                    RAM_entry=f'{entry:04X}', RAM_load='2000', RAM_end='3FFF')
        members.update({'engine-template.bin': template, 'migrator.bin': image, 'migrator.s19': s19(image, entry)})
    for name, body in members.items():
        plan['files'][name] = dict(bytes=len(body), sha256=sha(body))
    out.mkdir(parents=True)
    durable_write(out/'.gitignore', b'*\n')
    for name, body in members.items():
        path = out/name
        path.parent.mkdir(parents=True, exist_ok=True)
        durable_write(path, body)
    durable_write(out/'plan.json', encoded(plan))
    durable_write(out/'PREPARE.txt', ('\n'.join(progress_lines(plan))+'\n').encode('utf-8'))
    inspect(out)
    return plan


def inspect(root):
    root = Path(root).resolve()
    plan = read_json(root/'plan.json')
    require(plan.get('schema') == 1 and plan.get('installation_permitted') is False
            and plan.get('execution_qualified') is False and plan.get('flash_written') is False,
            'This checkpoint can only inspect unexecuted, unqualified plans')
    for name, record in plan['files'].items():
        member = root/name
        path = member.resolve()
        require(path.is_relative_to(root) and not member.is_symlink(), 'Outside/symlink plan member')
        body = path.read_bytes()
        require(len(body) == record['bytes'] and sha(body) == record['sha256'], 'Changed plan member: '+name)
    identity, banks, _ = read_capture(root/'source', plan['cpu'], plan['source_kind'])
    require(plan['source_identity'] == identity and plan['board_model'] == CPU_MODELS[plan['cpu']],
            'Changed source/CPU declaration')
    history = read_json(root/'imported-history.json') if (root/'imported-history.json').exists() else None
    derived, transfers, expected = derive(banks, (root/'target-F-4096.bin').read_bytes(),
        source_kind=plan['source_kind'], provision_cd=bool(plan['transaction']['operations']), history=history)
    require(derived == plan['transaction'], 'Changed derived transaction')
    require([f'{fnv(bank):08x}' for bank in banks] == plan['source_bank_fnv'], 'Changed bank FNV guards')
    for n, body in enumerate(expected):
        require((root/f'expected-b{n}.bin').read_bytes() == body, 'Changed complete expected bank')
    for op, (transfer, final) in zip(derived['operations'], transfers):
        require((root/op['transfer_file']).read_bytes() == transfer
                and (root/op['final_file']).read_bytes() == final, 'Changed sector transfer')
    if 'engine_image_sha256' in plan:
        template = (root/'engine-template.bin').read_bytes()
        require(sha(template) == plan['engine_template_sha256'], 'Changed engine-template binding')
        image, entry = render_engine(template, plan)
        require((root/'migrator.bin').read_bytes() == image and sha(image) == plan['engine_image_sha256']
                and plan['RAM_entry'] == f'{entry:04X}'
                and (root/'migrator.s19').read_bytes() == s19(image, entry), 'Changed rendered RAM engine')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    make = commands.add_parser('prepare', help='prepare private backups, erase intent and exact transfer plan; no device access')
    make.add_argument('--capture', type=Path, required=True)
    make.add_argument('--f-image', type=Path, required=True)
    make.add_argument('--out', type=Path, required=True)
    make.add_argument('--cpu', choices=tuple(CPU_MODELS), required=True)
    make.add_argument('--source-kind', choices=('wdcmonv2', 'nf-recovery'), required=True)
    make.add_argument('--provision-cd', action='store_true')
    make.add_argument('--history', type=Path)
    make.add_argument('--template', type=Path)
    show = commands.add_parser('inspect', help='re-derive and check an existing unexecuted private plan')
    show.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            plan = prepare(args.capture, args.f_image, args.out, cpu=args.cpu,
                           source_kind=args.source_kind, provision_cd=args.provision_cd,
                           history_file=args.history, template_file=args.template)
            print('PRIVATE BACKUP/PLAN:', args.out.resolve())
        else:
            plan = inspect(args.plan)
        print('\n'.join(progress_lines(plan)))
    except (KeyError, OSError, ValueError) as error:
        parser.exit(2, 'REFUSED: '+str(error)+'\nNo device was opened by this tool.\n')


if __name__ == '__main__':
    main()
