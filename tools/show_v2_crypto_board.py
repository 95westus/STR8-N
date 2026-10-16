"""Load and show the RAM-only crypto client on 2604; archive overwritten RAM."""
import argparse
import hashlib
import json
from pathlib import Path

from beta4_migration import Link
from build_v2_crypto_adapter import OUT as ADAPTER
from build_v2_crypto_display import OUT as BUILD, ROOT
from qualify_v2_crypto_board import load_only, read_pins, save
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease


def main():
    from serial.tools.list_ports import comports
    from rtc_boards import SERIALS
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    a = p.parse_args()
    port = next(x.device for x in comports() if x.serial_number == SERIALS['2604'])
    meta = json.loads((BUILD / 'build.json').read_text())
    tests = json.loads((BUILD / 'test-results.json').read_text())
    adapter = json.loads((ADAPTER / 'build.json').read_text())
    assert tests['passed'] and tests['sha256'] == meta['sha256']
    image = (BUILD / 'crypto-display.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == meta['sha256']
    assert meta['adapter_sha256'] == adapter['sha256']
    a.root.mkdir(parents=True, exist_ok=False)
    report = dict(board='2604', port=port, entry='2800', flash_written=False,
                  display_sha256=meta['sha256'], adapter_sha256=adapter['sha256'],
                  ram_left_loaded=False, ram_backup=None, passed=False)
    save(a.root / 'report.json', report)
    print('Waiting for exclusive 2604 serial access', flush=True)
    with serial_lease('drift', timeout=60), (a.root / 'serial.jsonl').open('x') as log:
        link = Link(port, log)
        staged = False
        prior = None
        try:
            establish_b3(link)
            assert link.dump(0x7e60, 0x7e63) == b'RA\x01\x0d'
            assert link.dump(0x7d04, 0x7d0b) == bytes.fromhex('5356010f0065ff64')
            assert link.dump(0x7d27, 0x7d27) == b'\x01'
            pins = read_pins(link, a.root)
            assert pins[0] & 0x81 == 0 and pins[1] & 0x81 == 0x81
            prior = link.dump(meta['first'], meta['end'] - 1)
            assert prior == link.dump(meta['first'], meta['end'] - 1)
            (a.root / 'ram-prior.bin').write_bytes(prior)
            report['ram_backup'] = str(a.root / 'ram-prior.bin')
            report['ram_prior_sha256'] = hashlib.sha256(prior).hexdigest()
            save(a.root / 'report.json', report)
            staged = True
            load_only(link, BUILD / 'crypto-display.s19')
            for name, value in (('CA_ADDRESS', 0x60), ('CA_MHZ', 8), ('CA_ENABLE', 0xa5)):
                link.write_ram(adapter['symbols'][name], bytes((value,)))
            first = link.command('G 2800')
            (a.root / 'first-console.txt').write_bytes(first)
            result = link.dump(adapter['symbols']['RESULT'], adapter['symbols']['VALID'])
            assert result == b'\x00\x00\x07', result.hex()
            assert link.dump(0x6660, 0x6660) == b'\0'
            assert b'Device:        ATECC608B' in first
            assert b'Configuration: UNLOCKED' in first and b'Data/OTP:      UNLOCKED' in first
            # Last board command prints the actual live report, leaving no
            # verification dump after it. Release COM5 for the owner's terminal.
            final = link.command('G 2800')
            assert b'Status:        Present' in final and b'Cleanup:       OK' in final
            (a.root / 'console.txt').write_bytes(final)
            report.update(passed=True, ram_left_loaded=True,
                          launch='G 2800', original_ram_archived=True,
                          note='Temporary utility; another RAM program may overwrite it')
            save(a.root / 'report.json', report)
            print(final.decode('ascii'), flush=True)
            print('COM5 released; RAM utility remains at G 2800. Original RAM archived.', flush=True)
        except BaseException:
            if staged and prior is not None:
                from beta4_migration import s19
                restore = a.root / 'restore-load-only.s19'
                restore.write_bytes(s19(dict(enumerate(prior, meta['first'])), meta['first']))
                load_only(link, restore)
                report['ram_restored_on_failure'] = True
                save(a.root / 'report.json', report)
            raise
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
