"""Offline, exact-preimage g0034 -> PR03 C/D migration planning.

This composes the existing RAM installer; it neither imports serial nor admits
hardware execution. A separately qualified complete target is required. The
first operation durably reserves every erase in the old journal. A hybrid peer
then carries both formats until F has changed; final C/D sectors carry SNBT.
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from installer import capture
from installer.common import REGISTRY, save
from installer.engine import legacy_transport as wire, runtime as r

TEMPLATE = ROOT / 'tools/installer/engine/template'
BASE = ROOT / 'BUILD/rc1-r10p2-g0034'
BASE_SHA = '0df4a802d618c0df5e658dcf2cd05037f0a892a209abaeac6bca0d595c468945'
GENERATION = 0x80000003


def snapshot(config, counts, sequence, target, generation=GENERATION):
    r.require(target in ('A', 'B') and config[14:] == wire.config_sum(config),
              'Invalid migrated configuration')
    r.require(1 <= sequence <= 0xffffffff, 'SNBT sequence exhausted')
    row = bytearray(b'\xff' * 256)
    row[:8] = b'SNBT\x01\x20\x00' + target.encode('ascii')
    row[8:12] = sequence.to_bytes(4, 'little')
    # The old arbitrary-address autostart is deliberately not guessed at.
    # derive() admits only disabled autostart. Preserve its timeout and config.
    row[12:18] = bytes([config[5], 15, 8, 8, 8, 8])
    row[18:22] = generation.to_bytes(4, 'little')
    row[22:30] = bytes(8)
    row[32:48] = config
    row[64:160] = b''.join(n.to_bytes(3, 'little') for n in counts)
    # Legacy counts start at provisioning; pre-provisioning lifetime is unknown.
    # Carry every observed count without claiming unrecorded lifetime was zero.
    row[160:164] = b'\xff' * 4
    row[164:168] = bytes([1, 0, 0, 0])  # provenance: migrated legacy lower bounds
    row[30:32] = wire.crc(row[:30]).to_bytes(2, 'little')
    row[252:254] = wire.crc(row[:252]).to_bytes(2, 'little')
    row[255] = 0
    return bytes(row)


def snbt_records(banks):
    rows = []
    for off in range(0x4000, 0x6000, 256):
        row = bytes(banks[3][off:off + 256])
        target = row[7]
        fields_valid = (row[6] == 0 and row[12] >= 10 and row[13] & 0xf0 == 0
                        and all(8 <= page < 15 for page in row[14:18])
                        and row[17] not in (12, 13)
                        and (target in b'SAB' or (ord('0') <= target <= ord('3')
                                                 and row[13] & (1 << (target - ord('0'))))))
        if (row[:6] == b'SNBT\x01\x20' and fields_valid and row[254:] == b'\xff\x00'
                and wire.crc(row[:30]) == int.from_bytes(row[30:32], 'little')
                and wire.crc(row[:252]) == int.from_bytes(row[252:254], 'little')):
            rows.append((int.from_bytes(row[8:12], 'little'), off, row))
    if rows:
        newest = max(s for s, _, _ in rows)
        r.require(len({row for s, _, row in rows if s == newest}) == 1,
                  'Conflicting newest SNBT snapshots')
    return rows


def derive(target, capture_root, *, base=BASE):
    target, base = Path(target), Path(base)
    identity, banks = capture.validate(capture_root)
    r.require(identity['board'] == '2512', 'This experimental migration is 2512 only')
    source = (base / 'firmware.bin').read_bytes()
    firmware = (target / 'firmware.bin').read_bytes()
    r.require(r.sha(source) == BASE_SHA and len(firmware) == 98304,
              'Exact g0034 base and complete target required')
    for bank, address in REGISTRY['owned_sectors']:
        off, start = address - 0x8000, (bank - 1) * 32768 + address - 0x8000
        r.require(banks[bank][off:off + 4096] == source[start:start + 4096],
                  f'Unknown g0034 source B{bank}:{address:04X}')
    r.require(banks[3][0x1000:0x1c00] == source[0x11000:0x11c00],
              'Unknown RTC journal code prefix')
    seq, offset, latest, valid = r.clean_journal(banks)
    cfg = latest[8:24]
    r.require(cfg[1] == 0, 'Enabled legacy arbitrary-address autostart needs explicit migration policy')
    r.require(cfg[7] == ord('P') and cfg[8] in (0xa0, 0xb0)
              and int.from_bytes(cfg[9:13], 'little') == 52,
              'Expected g0034 monitor preference')
    r.require(10 <= cfg[5] <= 255 and seq <= 0xffffffff - 5,
              'Invalid timeout or exhausted migration sequence')
    active = cfg[8] << 8
    inactive = active ^ 0x1000
    desired = list(map(bytearray, banks))
    for bank, address in REGISTRY['owned_sectors']:
        off, start = address - 0x8000, (bank - 1) * 32768 + address - 0x8000
        desired[bank][off:off + 4096] = firmware[start:start + 4096]
    fixed = desired[3][-4096:]
    r.require(fixed[:4] == b'SN\x02\0' and fixed[0xffc:0xffe] == b'\x04\xf0'
              and fixed.count(b'PR03') == 1, 'Target F must identify the PR03 bootstrap contract')
    generation = int.from_bytes(desired[3][0x2008:0x200c], 'little')
    r.require(0x80000003 <= generation < 0xffffffff, 'Explicit experimental target generation required')
    for address, page in ((0xa000, 0xa0), (0xb000, 0xb0)):
        slot = bytes(desired[3][address - 0x8000:address - 0x7000])
        r.require(wire.slot_valid(slot, page) and slot[20:24] == b'PR03'
                  and int.from_bytes(slot[8:12], 'little') == generation,
                  'Complete target needs two valid PR03 monitor slots')
    r.require(desired[3][0x1000:0x2000] == banks[3][0x1000:0x2000],
              'RTC/TZ history sector must remain byte-identical')
    r.require(desired[3][:0x1000] == banks[3][:0x1000],
              'This preserving migration retains the RTC provider byte-identically')
    retained = (offset + 0x8000) & 0xf000
    peer = retained ^ 0x1000
    free = [off for off in range(retained - 0x8000, retained - 0x7000, 128)
            if banks[3][off:off + 128] == b'\xff' * 128]
    r.require(free, 'No erased legacy wear reservation slot')
    counts = [max(int.from_bytes(row[24 + 3 * n:27 + 3 * n], 'little')
                  for _, _, row in valid) for n in range(32)]
    changed = [(bank, address) for bank, address in REGISTRY['owned_sectors']
               if banks[bank][address - 0x8000:address - 0x7000]
               != desired[bank][address - 0x8000:address - 0x7000]]
    r.require((3, active) in changed and (3, inactive) in changed and (3, 0xf000) in changed,
              'PR03 deployment must replace F and both monitor slots')
    # Install an independently valid new MON first; keep the former active MON
    # until F has changed. The RAM installer, never new ROM, runs all operations.
    auxiliaries = sorted((item for item in changed
                          if item not in ((3, active), (3, inactive), (3, 0xf000))),
                         key=lambda item: (item[0] == 3, item[0], -item[1]))
    order = [(3, inactive), *auxiliaries, (3, 0xf000), (3, active)]
    erases = [(3, peer), *order, (3, retained), (3, peer)]
    reserved = counts.copy()
    for bank, address in erases:
        index = bank * 8 + (address >> 12) - 8
        r.require(reserved[index] < 0xffffff, 'Wear counter exhausted')
        reserved[index] += 1
    final_cfg = r.preference(cfg, active >> 8, generation)
    interim_cfg = r.preference(cfg, inactive >> 8, generation)
    state, operations, data = list(map(bytearray, banks)), [], []

    def append(kind, bank, address, body, commit=None):
        before = r.hashes(state)
        off = address - 0x8000
        state[bank][off:off + len(body)] = body
        operations.append(dict(kind=kind, bank=bank, address=address,
                               commit_address=commit, source_sha256=before,
                               after_sha256=r.hashes(state), data_sha256=r.sha(body)))
        data.append(bytes(body))

    append('reserve-record', 3, free[0] + 0x8000,
           r.record(cfg, reserved, seq + 1), free[0] + 0x807f)
    hybrid = bytearray(b'\xff' * 4096)
    interim_target = 'A' if inactive == 0xa000 else 'B'
    hybrid[:256] = snapshot(interim_cfg, reserved, seq + 3, interim_target, generation)
    hybrid[256:384] = r.record(cfg, reserved, seq + 2)
    append('stage-hybrid-journal', 3, peer, hybrid, peer + 255)
    for bank, address in order:
        off = address - 0x8000
        body = desired[bank][off:off + 4096]
        commit = address + 31 if bank == 3 and address in (0xa000, 0xb000) else None
        if body[:4] == b'SR\x01?':
            commit = address + 3
        append('payload-sector', bank, address, body, commit)
    final_target = 'A' if active == 0xa000 else 'B'
    for address, sequence in ((retained, seq + 4), (peer, seq + 5)):
        body = snapshot(final_cfg, reserved, sequence, final_target, generation) + b'\xff' * 3840
        append('activate-snbt-journal', 3, address, body, address + 255)
    r.require(len(operations) - 1 <= 24, 'Installer transfer table capacity exceeded')
    expected = list(map(bytes, state))
    r.require(expected[0] == banks[0] and expected[3][0x1000:0x2000] == banks[3][0x1000:0x2000],
              'Owner data preservation failed')
    tx = dict(label='Owner-authorized 2512 g0034 to experimental PR03 preserving C/D migration',
              source_sha256=r.hashes(banks), expected_sha256=r.hashes(expected), operations=operations,
              counts_before=counts, reserved_counts=reserved, sequence_before=seq, sequence_after=seq + 5,
              reservation_offset=free[0], planned_erase_order=[[b, a >> 12] for b, a in erases],
              source_config=cfg.hex(), target_config=final_cfg.hex(), model_only=True,
              installation_permitted=False, format_transition='WC1/128 -> SNBT1/256',
              target_generation=generation, bootstrap_contract='PR03',
              interim_default=interim_target, final_default=final_target,
              legacy_history='Counts retained as provisioning lower bounds; unknown lifetime mask FFFFFFFF',
              RTC_TZ_sector_preserved=True, RTC_provider_preserved=True, B0_preserved=True,
              RTC_set_trim_or_ack_operations=False)
    return identity, banks, tx, data, expected


def verify(target, folder):
    target, folder = Path(target), Path(folder)
    info = r.read(folder / 'plan.json')
    identity, banks, tx, data, expected = derive(target, folder / 'capture', base=Path(info['source_build']))
    r.require((info['board'], info['usb_serial']) == (identity['board'], identity['usb_serial']), 'Plan identity changed')
    r.require(info['transaction'] == tx and info['source_sha256'] == r.hashes(banks)
              and info['expected_sha256'] == r.hashes(expected), 'Plan transaction changed')
    r.require(info['firmware_sha256'] == r.sha((target / 'firmware.bin').read_bytes())
              and info['installer_sha256'] == r.sha((folder / 'installer-model-only.s19').read_bytes()),
              'Target or installer changed')
    if 'planner_sha256' in info:
        r.require(info['planner_sha256'] == r.sha(Path(__file__).read_bytes()), 'Planner changed; regenerate plan')
    with tempfile.TemporaryDirectory(prefix='pr03-plan-verify-', dir=folder.parent) as tmp:
        check = Path(tmp) / 'plan'
        r.compose(TEMPLATE, check, banks, tx, data, expected)
        for path in check.iterdir():
            if path.name != 'plan.json':
                r.require(path.read_bytes() == (folder / path.name).read_bytes(), 'Changed artifact ' + path.name)
    return info


def mixed_wear_latest(banks):
    """Independent model oracle: recognize complete committed WC and SNBT rows.

    Normalize only for the existing model's wear oracle; installer bytes and
    its exact source, transfer and result hash checks remain unchanged.
    """
    rows = []
    for off in range(0x4000, 0x6000, 128):
        row = bytes(banks[3][off:off + 128])
        if (row[:4] == b'WC\x01\0' and row[127] == 0
                and wire.crc(row[:120]) == int.from_bytes(row[120:122], 'little')):
            rows.append((int.from_bytes(row[4:8], 'little'), off, row))
    for seq, off, row in snbt_records(banks):
        counts = [int.from_bytes(row[64 + 3 * n:67 + 3 * n], 'little') for n in range(32)]
        rows.append((seq, off, r.record(row[32:48], counts, seq)))
    r.require(rows, 'No durable wear record in either format')
    seq, off, row = max(rows, key=lambda item: item[0])
    r.require(len({v for s, _, v in rows if s == seq}) == 1, 'Conflicting wear state')
    return seq, off, row, rows


def qualify(target, folder, *, deps02, deps816):
    import deployment_model
    target, folder = Path(target), Path(folder)
    info = verify(target, folder)
    _, banks = capture.validate(folder / 'capture')
    # model.execute reads the template from its package. Use a small private
    # package within the already-private plan, without altering target sources.
    pkg = folder / 'model-package'
    if not pkg.exists():
        shutil.copytree(TEMPLATE, pkg / 'installer/engine/template')
    rows = []
    for is816 in (False, True):
        for fault in (None, 'stale', 'corrupt'):
            row = deployment_model.execute(pkg, folder, banks, is816=is816, deps02=deps02,
                                           deps816=deps816, fault=fault,
                                           verifier=lambda _pkg, _folder: info, owner_erased_b0=())
            rows.append(row)
            save(folder / 'model-progress.json', rows)
            print('PASS PR03 migration linked installer', is816, fault, flush=True)
    proof = dict(passed=True, hardware=False, board=info['board'],
                 plan_sha256=r.sha((folder / 'plan.json').read_bytes()),
                 firmware_sha256=info['firmware_sha256'], models=rows,
                 planner_sha256=r.sha(Path(__file__).read_bytes()),
                 model_source_sha256=r.sha(Path(deployment_model.__file__).read_bytes()))
    save(folder / 'model-proof.json', proof)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--qualify', action='store_true')
    parser.add_argument('--deps-02', type=Path, default=ROOT / 'BUILD/v1.30/local/test-deps')
    parser.add_argument('--deps-816', type=Path, default=ROOT / 'BUILD/test-deps-816')
    args = parser.parse_args()
    target, out = args.target.resolve(), args.out.resolve()
    identity, banks, tx, data, expected = derive(target, args.capture, base=args.base)
    info = r.compose(TEMPLATE, out, banks, tx, data, expected)
    shutil.copytree(args.capture, out / 'capture')
    (out / '.gitignore').write_text('*\n')
    info.update(board=identity['board'], usb_serial=identity['usb_serial'],
                source_build=str(args.base.resolve()), target_build=str(target),
                firmware_sha256=r.sha((target / 'firmware.bin').read_bytes()),
                planner_sha256=r.sha(Path(__file__).read_bytes()))
    save(out / 'plan.json', info)
    verify(target, out)
    if args.qualify:
        qualify(target, out, deps02=args.deps_02, deps816=args.deps_816)
    print('PASS exact PR03 preserving plan', len(tx['operations']) - 1, 'transfers', flush=True)


if __name__ == '__main__':
    main()
