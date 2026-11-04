"""Write the completed inventory checkpoint from captured board data, not models."""
import binascii
import hashlib
import json
from pathlib import Path
from installer.common import save

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'output/qualification/board-inventory-20261028'
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    rows = []
    vendor = BASE/'wdcmonv2-private-backups'
    destinations = vendor/'per-board'
    destinations.mkdir(exist_ok=True)
    assignments = {
        '2205': ('bank0.bin', 'live retained WDCMONv2 EDU/SPI bank; independently read twice'),
        '2512': ('65c02-2512-pre-FLASH-B0.bin', 'historical original B0 before FLASH; current B0 contains FLASH'),
        '2604': ('65c02-EDU-SPI-enhanced-bank.bin', 'CPU-correct enhanced reference; current B0 is erased, not an original live WDC capture'),
        '2609': ('bank0.bin', 'live retained WDCMONv2 EDU/SPI bank; independently read twice')}
    for board, attempt in (('2205', 'r3'), ('2512', 'r2'), ('2604', 'r2'), ('2609', 'r2')):
        folder = BASE/f'{board}-{attempt}'
        report = json.loads((folder/'report.json').read_text())
        manifest = json.loads((folder/'backup-manifest.json').read_text())
        assert report['passed'] and report['port_released'] and manifest['passed']
        assert report['owner_RAM_unchanged'] and report['owner_ZP_unchanged']
        banks = [(folder/f'bank{n}.bin').read_bytes() for n in range(4)]
        for n, body in enumerate(banks):
            assert sha(body) == report['banks'][n]['sha256']
        assert banks[0] == (folder/'bank0-repeat.bin').read_bytes()
        boot = report.get('boot_record')
        if boot is None:
            snapshots = []
            for offset in range(0x4000, 0x6000, 128):
                record = banks[3][offset:offset+128]
                if (record[:3] == b'WC\x01' and record[127] == 0 and
                    binascii.crc_hqx(record[:120], 65535) == int.from_bytes(record[120:122], 'little')):
                    snapshots.append((int.from_bytes(record[4:8], 'little'), record))
            assert snapshots
            seq, record = max(snapshots)
            assert record[15] == ord('P') and record[16] in (0xa0, 0xb0)
            boot = dict(format='WC', sequence=seq, default=chr(record[16]//16+55),
                pinned_generation=f'{int.from_bytes(record[17:21], "little"):08X}',
                saved_EDU='OFF' if record[21] == 0xa5 else 'ON' if record[21] == 0 else 'unknown')
        source_name, kind = assignments[board]
        source = folder/source_name if source_name == 'bank0.bin' else vendor/source_name
        destination = destinations/f'{board}-WDCMONv2-bank.bin'
        data = source.read_bytes()
        assert len(data) == 32768
        destination.write_bytes(data)
        assert destination.read_bytes() == data
        rows.append(dict(board=board, cpu='65C816 emulation' if report['CPU_code'] == '16' else '65C02',
            active_slot=chr(int(report['active_slot_byte'], 16)//16+55),
            monitor_A=report['monitors'][0], monitor_B=report['monitors'][1],
            firmware_strings=report['firmware_strings'], boot=boot,
            bank_sha256=[sha(b) for b in banks], backup=str(folder.relative_to(ROOT)),
            WDCMONv2_backup=str(destination.relative_to(ROOT)), WDCMONv2_sha256=sha(data),
            WDCMONv2_source_kind=kind, WDCMONv2_source=str(source),
            owner_RAM_preserved=True, owner_ZP_preserved=True, flash_written=False,
            SPI_accessed=False, current_external_SRAM_layout_queried=False,
            physical_EDU_note='No hardware absence inferred from unavailable b15 services; this pass did not probe peripherals'))
    summary = dict(passed=True, hardware_inventory=True, date='2026-10-28', boards=rows,
        scope='Fresh four-bank flash captures, independent B0 repeat, resident CPU/slot status, saved records, and unchanged CPU RAM/ZP',
        no_flash_or_application_RAM_writes=True, no_SPI_RTC_or_EEPROM_accesses=True,
        builds=0, simulations=0, journal_allocated=False,
        retained_SPI_note='Existing historical SRAM evidence is separate; new WORK reservations require the actual current layout and claims',
        journal_direction='Persistent reservation exclusively inside WORK; preserve formatted program region, headers, directory and payloads; preserve C/D boot journal',
        message_direction='Keep existing console wording as journal messages; distinguish per-boot observations and state changes; redisplay does not append',
        future_WDCMONv2='CPU-correct EDU/SPI-enhanced fixtures found and privately archived; no fixture flashed or booted')
    save(BASE/'inventory.json', summary)
    text = '# Board inventory and WDCMONv2 backup checkpoint\n\n'
    text += 'Captured October 28, 2026. All four boards were read through their current monitors. '
    text += 'No flash or application RAM was written; no SPI, RTC or EEPROM operations were issued. '
    text += 'CPU RAM $0200-$66FF and zero page $00-$DF match before/after. '
    text += 'Each full flash bank was captured once and B0 independently read again. No simulation or build was run.\n\n'
    text += '| Board | CPU | MON A generation | MON B generation | Saved default | WDCMONv2 backup |\n|---|---|---|---|---|---|\n'
    for row in rows:
        text += f'| {row["board"]} | {row["cpu"]} | {row["monitor_A"]["generation"]} | {row["monitor_B"]["generation"]} | {row["boot"]["default"]} | {row["WDCMONv2_source_kind"]} |\n'
    text += '\n2512 retains FLASH at B0:8. Its historical pre-FLASH B0 is preserved separately. '
    text += '2604 B0 is erased: its archived 65C02 enhanced reference is not represented as a fresh original-board WDC capture. '
    text += '2609 retains VX1 E and ES1 B3:8. All MON slots validate against their stored CRCs.\n\n'
    text += 'Private bank images, RAM, serial logs and SHA-256 manifests are in '
    text += '`output/qualification/board-inventory-20261028/`; vendor originals, local source archives and '
    text += 'CPU-specific enhanced references are in its `wdcmonv2-private-backups/` directory. '
    text += 'They are excluded from Git and public distributions. The Desktop full-device file is retained '
    text += 'as a distinct candidate: its B3 equals the pre-FLASH 2512 B0, while its B0-B2 are erased.\n\n'
    text += 'This pass did not query external SRAM or allocate journal storage. The owner-provided 2205 '
    text += 'display reports 30,720 program payload bytes and 98,272 WORK bytes. The separate last-verified '
    text += '2609 SRAM capture has an SS v1 layout, 63,488 program payload bytes and 65,504 WORK bytes; '
    text += 'that is historical retained-array evidence, not a fresh device query in this pass. '
    text += 'Do not assume equal boundaries or free WORK space across boards.\n\n'
    text += 'The accepted [b16 message-journal direction](STR8N_B16_MESSAGE_JOURNAL_PLAN.md) uses WORK only, '
    text += 'preserves program formatting and the separate boot journal, and retains familiar startup/status messages. '
    text += 'The journal and persistent WORK reservation remain planned. Future WDCMONv2/SPI fixture '
    text += 'installation requires its own selected CPU-correct image and preserving procedure.\n'
    (ROOT/'docs/BOARD_INVENTORY_2026-10-28.md').write_text(text, encoding='utf-8', newline='\n')
    print('Saved four-board inventory, per-board WDC references and checkpoint; no device access')


if __name__ == '__main__':
    main()
