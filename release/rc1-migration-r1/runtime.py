"""Portable rc1 transaction core; extracted from qualified algorithms, no repository paths."""
import hashlib,json
from pathlib import Path
import legacy_transport as migration
crc=migration.crc
def require(condition,message='Migration invariant failed'):
    if not condition:raise ValueError(message)
sha=lambda data:hashlib.sha256(data).hexdigest()
hashes=lambda banks:[sha(bytes(b)) for b in banks]
read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))

def valid_banks(banks):
    require(len(banks)==4 and all(len(bank)==32768 for bank in banks),
            'Four complete 32768-byte banks required')

def latest(banks):
    valid_banks(banks)
    valid = []
    for off in range(16384, 24576, 128):
        r = bytes(banks[3][off:off + 128])
        if r[:4] == b'WC\x01\x00' and r[127] == 0 and (crc(r[:120]) == int.from_bytes(r[120:122], 'little')):
            valid.append((int.from_bytes(r[4:8], 'little'), off, r))
    require(bool(valid), 'No valid journal')
    seq, off, r = max(valid, key=lambda v: v[0])
    require(len({v for s, o, v in valid if s == seq}) == 1, 'Ambiguous latest journal')
    return (seq, off, r, valid)
def record(config, counts, sequence):
    require(len(config)==16 and config[14:]==migration.config_sum(config), 'Invalid configuration')
    require(len(counts)==32 and all(type(n) is int and 0<=n<=0xffffff for n in counts), 'Invalid wear counts')
    require(1 <= sequence <= 4294967295, 'Journal sequence exhausted')
    r = bytearray(b'\xff' * 128)
    r[:8] = b'WC\x01\x00' + sequence.to_bytes(4, 'little')
    r[8:24] = config
    r[24:120] = b''.join((n.to_bytes(3, 'little') for n in counts))
    r[120:122] = crc(r[:120]).to_bytes(2, 'little')
    r[127] = 0
    return bytes(r)

def preference(config, page, generation):
    require(len(config)==16 and page in (0xa0,0xb0) and 1<=generation<=0xffffffff,
            'Invalid monitor preference')
    cfg = bytearray(config)
    cfg[7:13] = b'P' + bytes([page]) + generation.to_bytes(4, 'little')
    cfg[14:] = migration.config_sum(cfg)
    return bytes(cfg)
def clean_journal(banks):
    seq, off, row, valid = latest(banks)
    for i in range(16384, 24576, 128):
        r = bytes(banks[3][i:i + 128])
        require(r == b'\xff' * 128 or any((o == i and bytes(v) == r for _, o, v in valid)), 'Torn or unknown wear record')
    require(row[8:24][14:] == migration.config_sum(row[8:24]), 'Migration invariant failed')
    return (seq, off, row, valid)

def transaction(banks, destination, target_config, label, *, attested_cut=False):
    banks = list(map(bytes, banks))
    destination = list(map(bytes, destination))
    valid_banks(banks)
    valid_banks(destination)
    require(banks[0] == destination[0], 'B0 replacement forbidden')
    seq, offset, row, valid = latest(banks)
    if not attested_cut:
        clean_journal(banks)
    require(seq <= 4294967292 and target_config[:7] == row[8:15] and (target_config[13] == row[21]), 'Migration invariant failed')
    require(target_config[14:] == migration.config_sum(target_config), 'Migration invariant failed')
    retained = offset // 4096 + 8
    staging = 25 - retained
    start = (retained - 8) * 4096
    free = [i for i in range(start, start + 4096, 128) if banks[3][i:i + 128] == b'\xff' * 128]
    require(free, 'No erased reservation slot')
    counts = [max((int.from_bytes(r[24 + i * 3:27 + i * 3], 'little') for _, _, r in valid)) for i in range(32)]
    changed = []
    for bank in range(1, 4):
        for sector in range(8, 16):
            if bank == 3 and sector in (12, 13):
                continue
            off = (sector - 8) * 4096
            if banks[bank][off:off + 4096] != destination[bank][off:off + 4096]:
                changed.append((bank, sector))
    b3_order = {8: 0, 9: 1, 11: 2, 10: 3, 14: 4, 15: 5}
    if destination[3][:4] == b'SR\x01?':
        b3_order[9], b3_order[8] = (0, 1)
    changed.sort(key=lambda x: (x[0] == 3, x[0], -x[1] if x[0] != 3 else b3_order[x[1]]))
    erases = [(3, staging)] + changed + [(3, retained)]
    reserved = list(counts)
    for bank, sector in erases:
        i = bank * 8 + sector - 8
        require(reserved[i] < 16777215, 'Wear counter exhausted')
        reserved[i] += 1
    state = list(map(bytearray, banks))
    operations = []
    data = []

    def append(kind, bank, address, body, commit=None):
        before = hashes(state)
        off = address - 32768
        state[bank][off:off + len(body)] = body
        operations.append(dict(kind=kind, bank=bank, address=address, commit_address=commit, source_sha256=before, after_sha256=hashes(state), data_sha256=sha(body)))
        data.append(body)
    cfg = row[8:24]
    if attested_cut:
        pages = [p for p in (160, 176) if migration.slot_valid(banks[3][(p - 128) * 256:(p - 128) * 256 + 4096], p)]
        require(pages, 'No valid monitor fallback; retain evidence for programmer recovery')
        cfg = preference(cfg, pages[-1], int.from_bytes(banks[3][(pages[-1] - 128) * 256 + 8:(pages[-1] - 128) * 256 + 12], 'little'))
    append('reserve-record', 3, free[0] + 32768, record(cfg, reserved, seq + 1), free[0] + 32895)
    append('stage-journal', 3, staging << 12, record(cfg, reserved, seq + 2) + b'\xff' * 3968)
    for bank, sector in changed:
        off = (sector - 8) * 4096
        body = destination[bank][off:off + 4096]
        commit = None
        if bank == 3 and sector in (10, 11) and (body[:3] == b'MI\x01') and (body[31] == 0):
            commit = (sector << 12) + 31
        if body[:4] == b'SR\x01?':
            commit = (sector << 12) + 3
        append('payload-sector', bank, sector << 12, body, commit)
    append('activate-journal', 3, retained << 12, record(target_config, reserved, seq + 3) + b'\xff' * 3968)
    require(len(operations) - 1 <= 24, 'Migration invariant failed')
    return (dict(label=label, source_sha256=hashes(banks), expected_sha256=hashes(state), operations=operations, counts_before=counts, reserved_counts=reserved, sequence_before=seq, sequence_after=seq + 3, reservation_offset=free[0], planned_erase_order=[list(x) for x in erases], source_config=cfg.hex(), target_config=target_config.hex(), model_only=True, installation_permitted=False), data, list(map(bytes, state)))

def compose(build, out, banks, tx, data, expected):
    require(not out.exists(), 'Migration invariant failed')
    out.mkdir(parents=True)
    mf = read(build / 'manifest.json')
    require(mf['passed'] and sha((build / 'integrated-template.s19').read_bytes()) == mf['integrated_sha256'], 'Migration invariant failed')
    image = migration.read_s19(build / 'integrated-template.s19')[0]
    image[mf['count']] = len(tx['operations']) - 1
    image[mf['commit_after']] = 0
    for key, n in [('banks', 24), ('commits', 24), ('commit_addresses', 96), ('commit_values', 24), ('table', 216)]:
        image.update({mf[key] + i: 0 for i in range(n)})
    image.update(dict(enumerate(b''.join((migration.fnv(b).to_bytes(4, 'little') for b in banks)), 13568)))
    image.update(dict(enumerate((tx['reservation_offset'] + 32768).to_bytes(2, 'little'), 13584)))
    page = data[0] + b'\xff' * 128
    image.update(dict(enumerate(page, 13824)))
    image.update(dict(enumerate(migration.fnv(page).to_bytes(4, 'little'), 13586)))
    state = list(map(bytearray, banks))
    state[3][tx['reservation_offset']:tx['reservation_offset'] + 128] = data[0]
    for n, (op, body) in enumerate(zip(tx['operations'][1:], data[1:])):
        require(hashes(state) == op['source_sha256'], 'Migration invariant failed')
        bank = op['bank']
        address = op['address']
        transfer = bytearray(body)
        commit = op['commit_address']
        if commit is not None:
            image[mf['commits'] + n] = bank + 1
            image[mf['commit_values'] + n] = body[commit - address]
            image.update(dict(enumerate(commit.to_bytes(2, 'little'), mf['commit_addresses'] + 4 * n)))
            transfer[commit - address] = 255
        row = bytes([address >> 8]) + migration.fnv(state[bank]).to_bytes(4, 'little') + migration.fnv(transfer).to_bytes(4, 'little')
        image[mf['banks'] + n] = bank
        image.update(dict(enumerate(row, mf['table'] + 9 * n)))
        state[bank][address - 32768:address - 28672] = body
        (out / f'transfer-{n:02d}.bin').write_bytes(transfer)
    require(list(map(bytes, state)) == expected, 'Migration invariant failed')
    raw = migration.s19(image, 8192)
    (out / 'installer-model-only.s19').write_bytes(raw)
    for n, b in enumerate(banks):
        (out / f'source-b{n}.bin').write_bytes(b)
    for n, b in enumerate(expected):
        (out / f'expected-b{n}.bin').write_bytes(b)
    info = dict(transaction=tx, installer_sha256=sha(raw), template_manifest_sha256=sha((build / 'manifest.json').read_bytes()), source_sha256=hashes(banks), expected_sha256=hashes(expected), board='unspecified', model_only=True, board_access=False, installation_permitted=False)
    (out / 'plan.json').write_text(json.dumps(info, indent=2) + '\n')
    return info
