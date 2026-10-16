"""Preserving RAM-only crypto qualification; no flash or provisioning writes."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from beta4_migration import Link, s19, read_s19
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from build_v2_crypto_adapter import OUT as BUILD, ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def wrapper():
    # JSR-compatible engine, then return through the current RAM HOLD ABI.
    return bytes.fromhex(
        'adc37f8d002a adcf7f8d012a adec7f8d022a ba8e032a 08688d042a '
        '200765 8d0b2a a208bdcb669d302aca10f7 '
        '200020 8d052a adc37f8d062a adcf7f8d072a adec7f8d082a '
        'ba8e092a 08688d0a2a '
        '200765 8d0c2a a208bdcb669d402aca10f7 4c677e')


def load_only(link, path):
    """Upload/verify data without Link.monitor_load's automatic execution."""
    cells, _ = read_s19(path)
    assert 0x2000 <= min(cells) <= max(cells) < 0x6500
    link.command('L', b'S19')
    for line in path.read_bytes().splitlines():
        link.send(line + b'\r\n')
        time.sleep(.04)
    link.until(b'\r\nB3> ')
    assert link.dump(min(cells), max(cells)) == bytes(cells[x] for x in range(min(cells), max(cells)+1))


def recover(a, out, port):
    prior = (a.root / 'probe/ram-prior.bin').read_bytes()
    report_path = a.root / 'probe/report.json'
    report = json.loads(report_path.read_text())
    assert len(prior) == 0xb00 and sha(prior) == report['ram_prior_sha256']
    with serial_lease('drift', timeout=60), (out / 'serial.jsonl').open('x') as log:
        link = Link(port, log)
        try:
            establish_b3(link)
            actual = link.dump(0x2000, 0x2aff)
            already_restored = actual == prior
            if not already_restored:
                path = out / 'ram-restore-load-only.s19'
                path.write_bytes(s19(dict(enumerate(prior, 0x2000)), 0x2000))
                load_only(link, path)
            assert link.dump(0x2000, 0x2aff) == prior
            report.update(needs_ram_restore=False, ram_restored=True,
                restoration_incident='Host loader auto-executed saved RAM; user pressed physical RESET',
                user_physical_reset=True, ram_already_restored_after_reset=already_restored)
            save(report_path, report)
            hashes = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(x, x+4095, prompt) for x in range(0x8000, 0x10000, 4096))
                (out / f'b{bank}.bin').write_bytes(data)
                assert data == (a.root / f'probe/prior-b{bank}.bin').read_bytes(), bank
                hashes.append(sha(data))
                print('RECOVERED unchanged flash bank', bank, flush=True)
            link.command('B3')
            pins = read_pins(link, out)
            assert pins[0] & 0x81 == 0 and pins[1] & 0x81 == 0x81
            assert link.dump(0x6660, 0x6660) == b'\x00'
            report.update(flash_unchanged=True, flash_sha256=hashes, recovered=True)
            save(report_path, report)
            save(out / 'report.json', dict(passed=True, ram_restored=True,
                ram_already_restored_after_reset=already_restored,
                flash_sha256=hashes, bus_idle=True, host_reset_issued=False,
                user_physical_reset=True))
            print('PASS recovery: RAM restored, all flash unchanged, bus idle', flush=True)
        finally:
            link.serial.close()


def read_pins(link, out):
    """Read only non-handshake VIA registers through preserved ordinary RAM."""
    code = wrapper()[:18] + bytes.fromhex('4c677e')
    prior_code = link.dump(0x2800, 0x2800 + len(code) - 1)
    prior_data = link.dump(0x2a00, 0x2a02)
    assert prior_code == link.dump(0x2800, 0x2800 + len(code) - 1)
    assert prior_data == link.dump(0x2a00, 0x2a02)
    receipt = dict(prior_code=prior_code.hex(), prior_data=prior_data.hex(), needs_restore=True)
    save(out / 'read-helper.json', receipt)
    try:
        link.write_ram(0x2800, code)
        link.command('G 2800')
        data = link.dump(0x2a00, 0x2a02)
        return data
    finally:
        link.write_ram(0x2800, prior_code)
        link.write_ram(0x2a00, prior_data)
        receipt.update(needs_restore=False, restored=True)
        save(out / 'read-helper.json', receipt)


def main():
    from serial.tools.list_ports import comports
    from rtc_boards import SERIALS
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('preflight', 'probe', 'recover'))
    p.add_argument('--board', choices=('2604',), required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--mhz', type=int, choices=(1, 2, 4, 8), default=8)
    a = p.parse_args()
    a.root.mkdir(parents=True, exist_ok=True)
    port = next(x.device for x in comports() if x.serial_number == SERIALS[a.board])
    out = a.root / a.stage
    out.mkdir(exist_ok=False)
    if a.stage == 'recover':
        return recover(a, out, port)
    meta = json.loads((BUILD / 'build.json').read_text())
    tests = json.loads((BUILD / 'test-results.json').read_text())
    assert tests['passed'] and tests['sha256'] == meta['sha256']
    image = (BUILD / 'crypto-adapter.bin').read_bytes()
    assert sha(image) == meta['sha256']
    for path, digest in meta['sources'].items():
        assert sha((ROOT / path).read_bytes()) == digest
    s = meta['symbols']
    report = dict(board=a.board, usb_serial=SERIALS[a.board], port=port,
                  stage=a.stage, candidate_sha256=meta['sha256'],
                  flash_written=False, provisioning_written=False,
                  rtc_set=False, reset=False, calls=[])
    print('Waiting for shared serial lease; board', a.board, port, flush=True)
    # Use the coordinator's priority lane so the soak yields between restored
    # batches, rather than racing its immediate reacquisition of the lease.
    with serial_lease('drift', timeout=60), (out / 'serial.jsonl').open('x') as log:
        link = Link(port, log)
        try:
            establish_b3(link)
            assert link.dump(0x7e60, 0x7e63) == b'RA\x01\x0d', 'RAM HOLD ABI required'
            pins = read_pins(link, out)
            state = dict(config=link.command('C').decode('ascii'),
                         descriptor=link.dump(0x7d04, 0x7d0b).hex(),
                         edu=link.dump(0x7d27, 0x7d27)[0],
                         active_slot=link.dump(0x7d30, 0x7d30).hex(),
                         ram_abi=link.dump(0x7e60, 0x7e63).hex(),
                         signature=link.dump(0x6510, 0x6513).hex(),
                         locks=link.dump(0x6660, 0x6669).hex(),
                         ddr=pins[0], port_a=pins[1], pcr=pins[2])
            save(out / 'state.json', state)
            assert bytes.fromhex(state['descriptor']) == bytes.fromhex('5356010f0065ff64')
            assert state['edu'] == 1 and state['ram_abi'] == '5241010d'
            assert state['signature'] == '49320101'
            locks = bytes.fromhex(state['locks'])
            # HOLD clears the code-verified bit. The RAM wrapper performs a
            # normal read-only RTC STATUS call to revalidate before crypto.
            assert locks[0] == 0 and locks[9] == 0 and locks[4] & 2
            assert state['ddr'] & 0x81 == 0, 'Bus pins not released; no automatic repair'
            assert state['port_a'] & 0x81 == 0x81, 'Bus stuck; no automatic bus clear'
            report['preflight'] = state
            if a.stage == 'preflight':
                report.update(passed=True, crypto_accessed=False)
                save(out / 'report.json', report)
                print('PASS preflight:', json.dumps(state), flush=True)
                return
            # Preserve every byte overwritten by the dense RAM test package.
            prior = link.dump(0x2000, 0x2aff)
            assert prior == link.dump(0x2000, 0x2aff)
            (out / 'ram-prior.bin').write_bytes(prior)
            report['ram_prior_sha256'] = sha(prior)
            baseline = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(x, x + 4095, prompt) for x in range(0x8000, 0x10000, 4096))
                (out / f'prior-b{bank}.bin').write_bytes(data)
                baseline.append(sha(data))
                print('Archived flash bank', bank, flush=True)
            link.command('B3')
            payload = bytearray(0xb00)
            payload[:len(image)] = image
            code = wrapper()
            payload[0x800:0x800+len(code)] = code
            package = out / 'ram-probe.s19'
            package.write_bytes(s19(dict(enumerate(payload, 0x2000)), 0x2800))
            report.update(needs_ram_restore=True, crypto_accessed=False)
            save(out / 'report.json', report)
            try:
                load_only(link, package)
                # First exercise the refusing configuration with no wake traffic.
                reply = link.command('G 2800')
                (out / 'default.txt').write_bytes(reply)
                assert link.dump(s['RESULT'], s['RESULT']) == b'\x02'
                for name, value in (('CA_ADDRESS', 0x60), ('CA_MHZ', a.mhz), ('CA_ENABLE', 0xa5)):
                    link.write_ram(s[name], bytes((value,)))
                for number in range(3):
                    report['crypto_accessed'] = True
                    save(out / 'report.json', report)
                    started = time.monotonic()
                    reply = link.command('G 2800')
                    elapsed = time.monotonic() - started
                    (out / f'call-{number}.txt').write_bytes(reply)
                    raw = link.dump(0x2000, 0x2aff)
                    (out / f'call-{number}.bin').write_bytes(raw)
                    get = lambda name, n=1: raw[s[name]-0x2000:s[name]-0x2000+n]
                    preserved = raw[0xa00:0xa0d]
                    item = dict(result=get('RESULT')[0], valid=get('VALID')[0],
                        cleanup=get('CLEANUP_ERROR')[0], revision=get('REVISION', 4).hex(),
                        serial=get('SERIAL', 9).hex(), locks=get('LOCKS', 2).hex(),
                        field_errors=get('FIELD_ERRORS', 4).hex(), device_status=get('DEVICE_STATUS')[0],
                        raw_fault=get('CA_FAULT_CODE')[0], fault_phase=get('CA_FAULT_PHASE')[0],
                        stop_error=get('CA_STOP_ERROR')[0], elapsed_host_seconds=elapsed,
                        rtc_status=preserved[11],
                        rtc_status_after=preserved[12],
                        rtc_raw_before=raw[0xa30:0xa39].hex(),
                        rtc_raw_after=raw[0xa40:0xa49].hex(),
                        wrapper_snapshot=preserved.hex())
                    report['calls'].append(item)
                    save(out / 'report.json', report)
                    assert preserved[0] == preserved[6] and preserved[2] == preserved[8]
                    assert (preserved[1] ^ preserved[7]) & preserved[0] == 0
                    assert preserved[3] == preserved[9]
                    assert preserved[4] & 0x0c == preserved[10] & 0x0c
                    assert link.dump(0x6660, 0x6660) == b'\x00'
                    assert item['cleanup'] == 0 and item['stop_error'] == 0, item
                    assert preserved[11] == preserved[12] == 0
                    before_rtc, after_rtc = raw[0xa30:0xa39], raw[0xa40:0xa49]
                    assert before_rtc[7:9] == after_rtc[7:9]
                    assert before_rtc[0] & 0x80 == after_rtc[0] & 0x80
                    assert before_rtc[3] & 0x38 == after_rtc[3] & 0x38
                    print('Crypto call', number, json.dumps(item), flush=True)
                    # Stop cleanly on an unsupported revision or any primary failure.
                    if item['result'] != 0:
                        break
            finally:
                restore = out / 'ram-restore.s19'
                restore.write_bytes(s19(dict(enumerate(prior, 0x2000)), 0x2000))
                load_only(link, restore)
                assert link.dump(0x2000, 0x2aff) == prior
                report.update(needs_ram_restore=False, ram_restored=True)
                save(out / 'report.json', report)
            final = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(x, x + 4095, prompt) for x in range(0x8000, 0x10000, 4096))
                (out / f'final-b{bank}.bin').write_bytes(data)
                final.append(sha(data))
                assert final[-1] == baseline[bank]
                print('Verified unchanged flash bank', bank, flush=True)
            link.command('B3')
            report.update(flash_unchanged=True, flash_sha256=final,
                          passed=bool(report['calls']) and all(c['result'] == 0 and c['valid'] == 7
                              and c['field_errors'] == '00000000' for c in report['calls']))
            save(out / 'report.json', report)
            print('Qualification result:', json.dumps(report), flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
