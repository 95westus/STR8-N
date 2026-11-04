"""Pin the existing native utility profile for 2609; no build or port access."""
import binascii
import json
import sys
from pathlib import Path
import install_2512_native_utilities as d

t = d.t
sys.path.insert(0, str(t.REPO / 'tools'))
from native_journal_room import inspect
from nf_migrate import valid_snapshot

CAPTURE = t.ROOT / 'output/qualification/2609-CLOCK-capture-20261031-r1'
SOURCE = t.ROOT / 'output/qualification/STATUS-install-20261031-r1/2512'
OUT = t.ROOT / 'output/qualification/2609-CLOCK-native-scope-20261031-r1'


def run():
    capture = json.loads((CAPTURE / 'report.json').read_text())
    assert capture['passed'] and capture['owner_RAM_restored'] and capture['owner_ZP_restored']
    assert json.loads((t.ROOT / 'output/qualification/2512-CLOCK-equivalence-20261031-r1/report.json').read_text())['passed']
    old2 = (CAPTURE / 'B2-before.bin').read_bytes()
    old3 = (CAPTURE / 'B3-before.bin').read_bytes()
    new2 = (SOURCE / 'B2-after.bin').read_bytes()
    reference3 = (SOURCE / 'B3-after.bin').read_bytes()
    freeze = json.loads((t.REPO / 'F_FREEZE.json').read_text())
    frozen = (t.REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert t.sha(frozen) == freeze['sha256'] and old3[-4096:] == frozen
    for name,digest in freeze['sources'].items():
        assert t.sha((t.REPO / name).read_bytes()) == digest
    native = t.REPO / 'monitors/candidates/native-g00000001-r16'
    nm = json.loads((native / 'manifest.json').read_text())
    for name,a in nm['artifacts'].items():
        assert t.sha((native / name).read_bytes()) == a['sha256']
    assert new2[0x3000:0x6000] == (native / 'CLOCK-g00000001-flash.bin').read_bytes()
    assert reference3[:4096] == (native / 'RTC-BASE1-B3-8000.bin').read_bytes()
    assert reference3[4096:7168] == (native / 'RTC-HISTORY-B3-9000.bin').read_bytes()[:3072]
    # 2609's old sector9 tail is executable legacy code, not a compatible
    # metadata pocket. Archive it; never copy 2512's board/EUI/battery records.
    for offset in range(0x1C00, 0x2000, 32):
        row = old3[offset:offset+32]
        assert not (row[:2] in (b'BN', b'TZ', b'BA', b'EI') and row[31] == 0 and
                    binascii.crc_hqx(row[:28],65535) == int.from_bytes(row[28:30],'little'))
    new3 = bytearray(old3)
    new3[:0x1C00] = reference3[:0x1C00]
    new3[0x1C00:0x2000] = b'\xff' * 1024
    new3[0x6000:0x7000] = reference3[0x6000:0x7000]
    assert new3[0x2000:0x6000] == old3[0x2000:0x6000]
    assert new3[0x7000:] == frozen
    for a,b in ((0x300,0x1F00),(0x1F00,0x2C00),(0x3000,0x6000),(0x6000,0x8000)):
        assert binascii.crc_hqx(new2[a:b],65535) == 0
    # Same sealed STATUS extents and MON slots, with no additional build.
    for a,b in ((0x40,0x100),(0x240,0x300),(0x2C00,0x3000),(0x7A50,0x7FFA)):
        assert old2[a:b] == new2[a:b]
    old = t.classify_journal(old3); room = inspect(old3)
    assert old['kind'] == 'valid-snbt' and old['sequence'] == 1039
    assert room['zero_erase_native_operations'] == 6 and room['peer_sector'] == 'C000'
    OUT.mkdir(exist_ok=False); (OUT / '.gitignore').write_text('*\n')
    for name,data in [('B2-before.bin',old2),('B3-before.bin',old3),
                      ('old-CD-history.bin',old3[0x4000:0x6000]),
                      ('B2-target.bin',new2),('B3-image-target.bin',new3)]:
        (OUT / name).write_bytes(data)
    order = [(3,0x80),(3,0x90),(2,0x80),(2,0x90),(2,0xA0),(3,0xE0),
             (2,0xB0),(2,0xC0),(2,0xD0),(2,0xE0),(2,0xF0)]
    targets = []
    counts = old['counts'].copy()
    for bank,page in order:
        offset = page * 256 - 0x8000
        prior = (old2 if bank == 2 else old3)[offset:offset+4096]
        body = (new2 if bank == 2 else new3)[offset:offset+4096]
        assert len(body) == 4096 and prior != body
        name = f'B{bank}-{page:02X}00.bin'; (OUT / name).write_bytes(body)
        targets.append(dict(bank=bank,page=page,address=f'{page:02X}00',file=name,
                            before_sha256=t.sha(prior),sha256=t.sha(body)))
        counts[bank*8+(page-0x80)//16] += 1
    counts[28] += 1
    old_C = sum(valid_snapshot(old3[o:o+256]) for o in range(0x4000,0x5000,256))
    assert len(targets) == 11 and old_C == 16
    plan = dict(status='REVIEW_READY_NOT_APPROVED_NOT_INSTALLED',board='2609',port='COM8',
        USB_serial='A10MPQXCA',F_sha256=freeze['sha256'],F_writes=0,firmware_builds=0,
        image_erases=11,C_rotation_erases=1,D_erases=0,total_erases=12,power_cuts=0,
        targets=targets,before_B2_sha256=t.sha(old2),before_B3_sha256=t.sha(old3),
        final_B2_sha256=t.sha(new2),counts_before=old['counts'],counts_after=counts,
        sequence_before=old['sequence'],sequence_after=1051,records_before=old['valid_records'],
        records_after=old['valid_records']-old_C+12,old_C_records_archived_on_host=old_C,
        old_records_retained_exact_on_chip=old['valid_records']-old_C,
        journal_room=room,default=old['default'],enabled_mask=old['enabled_mask'],
        entries=old['entries'],unknown_mask=old['unknown_mask'],
        metadata='No compatible old BN/TZ/BA/EI records; new pocket FF. Board--*, UTC, Battery--*; no invented policy or identity.',
        legacy_assets='Old B2 utilities, B2 legacy vectors and B3:8/9/E utilities archived/replaced. B0/B1 and MON A/B retained.',
        no_writes=['B0','B1','B3:A','B3:B','B3:F','SRAM data','WORKSPACE','RTC calendar','RTC trim','RTC EEPROM history','RTC PF flags'],
        qualification=['R CLOCK summary','HELP/TIME/STATUS/HISTORY/STATS/EUI',
            'invalid-date rejection','SET/OFFSET/TRIM cancellation','VERSION/Q',
            'APPS and named tool admission','M1/W','shared STATUS intact',
            'original default/mask/entries and wear accounting','fresh owner RAM/ZP restore and readback'],
        RTC_sampling='Keep current native gC TIME driver, clock/trim/baseline and schedule; update admitted B2/B3 image hashes after acceptance',
        excluded_boards=['2205','2512','2604'],published_download_changes=0)
    assert plan['records_after'] == 21 and plan['default'] == 'S'
    t.save(OUT / 'plan.json',plan)
    print(json.dumps({k:v for k,v in plan.items() if k not in ('counts_before','targets','no_writes','qualification')},indent=2))


if __name__ == '__main__': run()
