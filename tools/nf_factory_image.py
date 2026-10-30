"""Prepare a board-matched WDC factory-firmware restoration image; never flash."""
import argparse
import hashlib
import json
from pathlib import Path

sha = lambda data: hashlib.sha256(data).hexdigest()


def prepare(current_file, wdc_file, cpu, out):
    current_file, wdc_file, out = map(lambda p: Path(p).resolve(), (current_file, wdc_file, out))
    current, vendor = current_file.read_bytes(), wdc_file.read_bytes()
    if len(current) != 131072 or len(vendor) not in (4096, 32768):
        raise ValueError('Current image must be 128 KiB; WDC source must be its 4 KiB F or original 32 KiB bank')
    expected = {'65c02': b'SXB2', '65c816e': b'SXB6'}[cpu]
    f = vendor[-4096:]
    if f[0x80C:0x810] != expected:
        raise ValueError('WDC source does not identify the selected SXB CPU profile')
    reset = int.from_bytes(f[0xFFC:0xFFE], 'little')
    if not 0xF000 <= reset <= 0xFFFF:
        raise ValueError('WDC reset vector is outside the supplied F image')
    bank = vendor if len(vendor) == 32768 else b'\xff'*28672+vendor
    result = current[:0x18000]+bank
    assert len(result) == len(current) and result[:0x18000] == current[:0x18000]
    if out.exists():
        raise ValueError('Use a fresh output directory; existing files are never replaced')
    out.mkdir(parents=True)
    files = {'factory-B3.bin': bank, 'factory-full-chip.bin': result,
             'previous-CD-journal.bin': current[0x1C000:0x1E000],
             'previous-F.bin': current[0x1F000:0x20000]}
    for name, body in files.items():
        with (out/name).open('xb') as stream:
            stream.write(body)
    plan = dict(schema=1, operation='prepare-factory-firmware-restoration', CPU=cpu,
        status='PLAN_ONLY_NO_DEVICE_ACCESS', serial_access=False, flash_writes=0,
        current_source=str(current_file), current_sha256=sha(current),
        WDC_source=str(wdc_file), WDC_sha256=sha(vendor), WDC_signature=expected.decode(),
        WDC_reset=f'{reset:04X}', board_identity='Operator must use this board\'s matched original backup',
        replaced_banks=['B3'], image_bytes_outside_B3_preserved=True,
        F_will_be_replaced_if_programmed=True, boot_wear_journal_will_be_replaced=True,
        four_K_source_policy='Erase B3:8-E in the prepared image; retain the supplied WDC F',
        RTC_SRAM_EEPROM_jumper_changes=False,
        programming='Separate explicit programmer operation; this tool opens no device',
        whole_chip_erase='If required by the programmer, all 32 sectors incur an erase even though B0/B1/B2 bytes are restored',
        wear_policy='Archive/import prior counts for a later migration; this used chip is not new and must not be certified zero-wear',
        changed_sectors=[f'B3:{8+n:X}' for n in range(8)
                         if current[0x18000+n*4096:0x19000+n*4096] != bank[n*4096:(n+1)*4096]],
        files={n:dict(bytes=len(b), sha256=sha(b)) for n,b in files.items()})
    (out/'restoration-plan.json').write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
    print('Prepared', out/'restoration-plan.json')
    print('NO DEVICE ACCESS. Programming this image removes Foundation and its on-chip C/D journal.')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current-flash', type=Path, required=True)
    parser.add_argument('--wdc', type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816e'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.current_flash, args.wdc, args.cpu, args.out)
