"""Offline preserving b06/native-SNBT -> new bench F/MON transaction.

All three erase attempts are reserved in a committed native snapshot first.
Only F/MON A/B are erased. Existing native history and unknown provenance remain.
An interrupted pin transition safely selects recovery; partial reflashing is not
automatic. F interruption may require external programmer recovery.
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from installer.engine import runtime as r, legacy_transport as wire
from installer.common import save
from str8build.assemble import Assembly
from deployment_plan import snbt_records
import capture_b07_2512 as capture

TEMPLATE = ROOT / 'tools/installer/engine/template'
BASE = ROOT / 'BUILD/pr04-b06-startup-r2'
BASE_SHA = '757da2f43937cb28bf54419e0e95c3e49e0aeb950cb3579beec888bf7a2e1441'


def clean_native(banks):
    r.valid_banks(banks)
    rows = snbt_records(banks)
    r.require(rows, 'Native journal missing')
    known = {off: row for _, off, row in rows}
    for off in range(0x4000, 0x6000, 256):
        row = bytes(banks[3][off:off + 256])
        r.require(row == b'\xff' * 256 or known.get(off) == row, 'Torn or unknown native page')
    seq, offset, row = max(rows)
    cfg = row[32:48]
    r.require(cfg[14:] == wire.config_sum(cfg) and row[7] in b'AB'
              and cfg[8] == (0xa0 if row[7] == ord('A') else 0xb0)
              and row[18:22] == cfg[9:13], 'Native configuration/pin mismatch')
    return seq, offset, row, rows


def updated_snapshot(row, counts, sequence, config):
    value = bytearray(row)
    value[8:12] = sequence.to_bytes(4, 'little')
    value[18:22] = config[9:13]
    value[32:48] = config
    value[64:160] = b''.join(n.to_bytes(3, 'little') for n in counts)
    value[30:32] = wire.crc(value[:30]).to_bytes(2, 'little')
    value[252:254] = wire.crc(value[:252]).to_bytes(2, 'little')
    r.require(value[7] == row[7] and value[12:18] == row[12:18]
              and value[160:252] == row[160:252] and value[254:] == row[254:],
              'Boot target/timeout/entry/history/provenance preservation failed')
    return bytes(value)


def derive(target, source_capture, *, base=BASE, allow_synthetic=False):
    target, base = Path(target), Path(base)
    identity, banks = capture.validate(source_capture, allow_synthetic=allow_synthetic)
    baseline = (base / 'firmware.bin').read_bytes()
    r.require(r.sha(baseline) == BASE_SHA, 'Exact installed b06 source build required')
    for page in (0xa0, 0xb0, 0xf0):
        off = (page - 0x80) * 256
        r.require(banks[3][off:off + 4096] == baseline[65536 + off:65536 + off + 4096],
                  'Source F/MON differs from b06')
    seq, offset, latest, rows = clean_native(banks)
    cfg = latest[32:48]
    r.require(cfg[1] == 0 and cfg[8] == 0xb0 and int.from_bytes(cfg[9:13], 'little') == 0x80000006,
              'Expected b06 disabled-autostart saved MON B')
    r.require(seq < 0xffffffff, 'Native sequence exhausted')
    report = r.read(target / 'prototype-report.json')
    manifest = r.read(target / 'bench-target.json')
    firmware = (target / 'firmware.bin').read_bytes()
    r.require(report['bench_core'] and report['dual_console'] and report['bootstrap_contract'] == 'PR04'
              and report['experimental_generation'] > 0x80000006
              and manifest['firmware_sha256'] == r.sha(firmware) and len(firmware) == 98304,
              'Explicit new PR04 bench target required')
    r.require(firmware[-4096:][:4] == b'SN\x02\0' and firmware[-4096:].count(b'PR04') == 1
              and firmware[-4:-2] == b'\x04\xf0', 'Actual target root contract/vector differs')
    generation = report['experimental_generation']
    r.require(manifest['changed_sectors'] == [[3, 0xa000], [3, 0xb000], [3, 0xf000]],
              'Bench image must overlay only F/MON A/B')
    desired = list(map(bytearray, banks))
    for address in (0xa000, 0xb000, 0xf000):
        off = address - 0x8000
        desired[3][off:off + 4096] = firmware[65536 + off:65536 + off + 4096]
    for page in (0xa0, 0xb0):
        slot = bytes(desired[3][(page - 0x80) * 256:(page - 0x80) * 256 + 4096])
        r.require(wire.slot_valid(slot, page) and slot[20:24] == b'PR04'
                  and int.from_bytes(slot[8:12], 'little') == generation, 'New MON contract/pin invalid')
    counts = [max(int.from_bytes(row[64 + n * 3:67 + n * 3], 'little') for _, _, row in rows) for n in range(32)]
    reserved = counts.copy()
    order = [(3, 0xa000), (3, 0xf000), (3, 0xb000)]
    for bank, address in order:
        index = bank * 8 + (address >> 12) - 8
        r.require(reserved[index] < 0xffffff, 'Wear counter exhausted')
        reserved[index] += 1
    sector = offset & 0xf000
    free = [off for off in range(sector, sector + 4096, 256) if banks[3][off:off + 256] == b'\xff' * 256]
    r.require(free, 'No erased native reservation page; C/D rotation is not admitted')
    final_cfg = r.preference(cfg, 0xb0, generation)
    reserve = updated_snapshot(latest, reserved, seq + 1, final_cfg)
    state = list(map(bytearray, banks)); operations = []; data = []

    def append(kind, bank, address, body, commit):
        before = r.hashes(state)
        off = address - 0x8000
        state[bank][off:off + len(body)] = body
        operations.append(dict(kind=kind, bank=bank, address=address, commit_address=commit,
                               source_sha256=before, after_sha256=r.hashes(state), data_sha256=r.sha(body)))
        data.append(body)

    append('reserve-native-snapshot', 3, free[0] + 0x8000, reserve, free[0] + 0x80ff)
    for bank, address in order:
        append('payload-sector', bank, address, bytes(desired[bank][address - 0x8000:address - 0x7000]),
               address + 31 if address in (0xa000, 0xb000) else None)
    expected = list(map(bytes, state))
    r.require(expected[:3] == banks[:3] and expected[3][:0x2000] == banks[3][:0x2000]
              and expected[3][0x6000:0x7000] == banks[3][0x6000:0x7000], 'Owner/RTC/auxiliary preservation failed')
    tx = dict(label='2512 preserving native SNBT b06 to new PR04 bench core', operations=operations,
              source_sha256=r.hashes(banks), expected_sha256=r.hashes(expected),
              counts_before=counts, reserved_counts=reserved, sequence_before=seq, sequence_after=seq + 1,
              reservation_offset=free[0], planned_erase_order=[[b, a >> 12] for b, a in order],
              source_config=cfg.hex(), target_config=final_cfg.hex(), target_generation=generation,
              bootstrap_contract='PR04', source_bootstrap_contract='PR04',
              model_only=True, installation_permitted=False, native_C_D_erases=0,
              intermediate_default_pin_mismatch_falls_back_to_recovery=True,
              history_unknown_mask=latest[160:164].hex(), provenance=latest[164:168].hex())
    return identity, banks, tx, data, expected


def compose(out, banks, tx, data, expected):
    out = Path(out)
    r.require(not out.exists(), 'Fresh plan directory required')
    out.mkdir(parents=True)
    mf = r.read(TEMPLATE / 'manifest.json')
    r.require(mf['passed'] and r.sha((TEMPLATE / 'integrated-template.s19').read_bytes()) == mf['integrated_sha256'],
              'Qualified template changed')
    image, entry = wire.read_s19(TEMPLATE / 'integrated-template.s19')
    original = image.copy()
    # The extension uses only these unchanged, byte-bound RAM primitives.
    for address, body in {0x3000: '78d89c', 0x305f: '9c3062', 0x30f0: 'a9ff8d3262',
                          0x31f7: 'ad103585e4', 0x3214: '9c3162', 0x3121: 'e078',
                          0x3128: 'cd7836', 0x3130: 'cd7936', 0x323c: 'c97f'}.items():
        raw = bytes.fromhex(body)
        r.require(bytes(image[a] for a in range(address, address + len(raw))) == raw, 'Template opcode drift')
    asm = out / 's/native'
    asm.mkdir(parents=True)
    shutil.copyfile(HERE / 'native-reserve.asm', asm / 'reserve.asm')
    a = object.__new__(Assembly); a.out = out; a.assembler = shutil.which('wdc02as'); a.linker = shutil.which('wdcln')
    a.symbols = {}; a.compiled = []
    r.require(a.assembler and a.linker, 'WDC assembler/linker required for native extension')
    extension, symbols = a.link('native', 'reserve', 0x3380, 'NATIVE_END')
    r.require(0x3380 + len(extension) <= 0x3500, 'Native extension overlaps bound data')
    r.require(all(image[n] == 0 for n in range(0x3380, 0x3380 + len(extension))), 'Extension area is not unused')
    image.update(dict(enumerate(extension, 0x3380)))
    image.update(dict(enumerate(bytes.fromhex('4c8033'), 0x3000)))
    # Reuse qualified CRC and programming loops, extending their native bounds.
    image[0x3122], image[0x3129], image[0x3131], image[0x323d] = 252, 252, 253, 255
    image[mf['count']], image[mf['commit_after']] = len(tx['operations']) - 1, 0
    for key, size in [('banks', 24), ('commits', 24), ('commit_addresses', 96), ('commit_values', 24), ('table', 216)]:
        image.update({mf[key] + n: 0 for n in range(size)})
    image.update(dict(enumerate(b''.join(wire.fnv(b).to_bytes(4, 'little') for b in banks), 0x3500)))
    image.update(dict(enumerate((tx['reservation_offset'] + 0x8000).to_bytes(2, 'little'), 0x3510)))
    r.require(len(data[0]) == 256, 'Native reservation must be one complete snapshot')
    image.update(dict(enumerate(data[0], 0x3600)))
    image.update(dict(enumerate(wire.fnv(data[0]).to_bytes(4, 'little'), 0x3512)))
    state = list(map(bytearray, banks))
    off = tx['reservation_offset']; state[3][off:off + 256] = data[0]
    for n, (operation, body) in enumerate(zip(tx['operations'][1:], data[1:])):
        r.require(r.hashes(state) == operation['source_sha256'], 'Transfer preimage chain changed')
        bank, address, commit = operation['bank'], operation['address'], operation['commit_address']
        transfer = bytearray(body)
        if commit is not None:
            image[mf['commits'] + n] = bank + 1
            image[mf['commit_values'] + n] = body[commit - address]
            image.update(dict(enumerate(commit.to_bytes(2, 'little'), mf['commit_addresses'] + 4 * n)))
            transfer[commit - address] = 255
        image[mf['banks'] + n] = bank
        row = bytes([address >> 8]) + wire.fnv(state[bank]).to_bytes(4, 'little') + wire.fnv(transfer).to_bytes(4, 'little')
        image.update(dict(enumerate(row, mf['table'] + 9 * n)))
        state[bank][address - 0x8000:address - 0x7000] = body
        (out / f'transfer-{n:02d}.bin').write_bytes(transfer)
    r.require(list(map(bytes, state)) == expected, 'Final native plan differs')
    raw = wire.s19(image, entry)
    (out / 'installer-model-only.s19').write_bytes(raw)
    for n in range(4):
        (out / f'source-b{n}.bin').write_bytes(banks[n]); (out / f'expected-b{n}.bin').write_bytes(expected[n])
    save(out / 'native-reservation-extension.json', dict(source_sha256=r.sha((HERE / 'native-reserve.asm').read_bytes()),
         address=0x3380, bytes=len(extension), sha256=r.sha(extension), symbols=symbols,
         original_template_sha256=mf['integrated_sha256'], instruction_patches={hex(n): [original[n], image[n]]
             for n in (0x3000, 0x3001, 0x3002, 0x3122, 0x3129, 0x3131, 0x323d)}))
    return dict(transaction=tx, installer_sha256=r.sha(raw), template_manifest_sha256=r.sha((TEMPLATE / 'manifest.json').read_bytes()),
                source_sha256=r.hashes(banks), expected_sha256=r.hashes(expected), board='2512', usb_serial=capture.USB,
                model_only=True, board_access=False, installation_permitted=False)


def verify(target, folder):
    target, folder = Path(target), Path(folder)
    info = r.read(folder / 'plan.json')
    identity, banks, tx, data, expected = derive(target, folder / 'capture', base=Path(info['source_build']),
                                               allow_synthetic=info['synthetic_model_fixture'])
    r.require(info['transaction'] == tx and info['source_sha256'] == r.hashes(banks)
              and info['expected_sha256'] == r.hashes(expected)
              and info['firmware_sha256'] == r.sha((target / 'firmware.bin').read_bytes())
              and info['installer_sha256'] == r.sha((folder / 'installer-model-only.s19').read_bytes())
              and info['planner_sha256'] == r.sha(Path(__file__).read_bytes())
              and info['native_reserve_source_sha256'] == r.sha((HERE / 'native-reserve.asm').read_bytes()), 'Native plan binding changed')
    r.require(info['capture_manifest_sha256'] == r.sha((folder / 'capture/capture.json').read_bytes())
              and info['application_ram_sha256'] == r.sha((folder / 'capture/application-ram.bin').read_bytes()),
              'Native RAM/capture escrow binding changed')
    with tempfile.TemporaryDirectory(prefix='native-plan-check-', dir=folder.parent) as temp:
        check = Path(temp) / 'plan'
        compose(check, banks, tx, data, expected)
        for name in ('installer-model-only.s19', 'native-reservation-extension.json', 'transfer-00.bin', 'transfer-01.bin', 'transfer-02.bin'):
            r.require((check / name).read_bytes() == (folder / name).read_bytes(), 'Changed native composed member: ' + name)
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', required=True, type=Path); p.add_argument('--capture', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path); p.add_argument('--base', type=Path, default=BASE)
    p.add_argument('--allow-synthetic', action='store_true'); p.add_argument('--qualify', action='store_true')
    p.add_argument('--deps-02', type=Path, default=ROOT / 'BUILD/v1.30/local/test-deps')
    p.add_argument('--deps-816', type=Path, default=ROOT / 'BUILD/test-deps-816')
    args = p.parse_args()
    target, out = args.target.resolve(), args.out.resolve()
    identity, banks, tx, data, expected = derive(target, args.capture, base=args.base, allow_synthetic=args.allow_synthetic)
    info = compose(out, banks, tx, data, expected)
    shutil.copytree(args.capture, out / 'capture')
    info.update(source_build=str(args.base.resolve()), target_build=str(target), firmware_sha256=r.sha((target / 'firmware.bin').read_bytes()),
                synthetic_model_fixture=identity['synthetic_model_fixture'], planner_sha256=r.sha(Path(__file__).read_bytes()),
                capture_manifest_sha256=r.sha((out / 'capture/capture.json').read_bytes()),
                application_ram_sha256=r.sha((out / 'capture/application-ram.bin').read_bytes()),
                native_reserve_source_sha256=r.sha((HERE / 'native-reserve.asm').read_bytes()))
    save(out / 'plan.json', info); verify(target, out)
    if args.qualify:
        import deployment_b07_model
        deployment_b07_model.qualify(target, out, deps02=args.deps_02, deps816=args.deps_816)
    print('PASS preserving native plan: three erases, no C/D erase', out, flush=True)


if __name__ == '__main__':
    main()
