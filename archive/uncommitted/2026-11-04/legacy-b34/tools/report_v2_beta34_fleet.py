"""Record the completed fleet deployment without accessing any board."""
from datetime import datetime, timezone
from pathlib import Path

import deploy_v2_beta34_fleet as f


def main():
    f.base.build_audit()
    root = f.OUT
    backup = f.read(root/'fresh/manifest.json')
    assert backup['passed']
    assert (f.DATA/'output/qualification/beta32-enhanced-soak-2512-2026-10-16/STOP').exists()
    receipts = {}
    for board in ('2205','2609','2604'):
        f.audit(board)
        report = f.read(root/board/'hardware/report.json')
        assert report['passed'] and report['application_ram_restored']
        assert not report['soak_started'] and not report['migration_matrix_run']
        assert report['final_hashes'] == f.read(root/board/'plan.json')['final_hashes']
        version = (root/board/'hardware/query-VERSION.txt').read_bytes()
        assert (b'65C816' if board == '2609' else b'65C02') in version
        original = (root/board/'hardware/ram-prior.bin').read_bytes()
        assert original == (root/board/'hardware/ram-restored.bin').read_bytes()
        assert not f.read(root/board/'hardware/ram-restore-needed.json')['needed']
        campaign=f.read(root/board/'plan.json')
        labels=campaign.get('completed_stages',[])+campaign['stages']
        assert len(labels)==len(set(labels))
        for label in labels:
            stage=root/board/label/'upgrade'
            plan=f.read(stage/'plan.json');model=f.read(stage/'model-check.json')
            assert model['installer_sha256']==plan['installer_sha256']==f.sha((stage/'installer.s19').read_bytes())
        source=(f.ROOT/'tools/deploy_v2_beta34_fleet.py') if board=='2604' else root/'deploy-tool-before-return-fix.py'
        assert report['source_tool_sha256']==f.sha(source.read_bytes())
        receipts[board] = dict(report=f'{board}/hardware/report.json',
            report_sha256=f.sha((root/board/'hardware/report.json').read_bytes()),
            final_flash_sha256=report['final_hashes'], application_ram_sha256=f.sha(original),
            new_sector_erases=sum(len(f.read(root/board/label/'upgrade/plan.json')['steps'])
                for label in labels))
    recovery=f.read(root/'2604/reset-recovery/report.json')
    regression=f.read(root/'2604/return-bank-regression.json')
    assert recovery['passed'] and recovery['application_ram_restored'] and regression['passed']
    assert regression['source_sha256']==f.sha((f.ROOT/'tools/finish_v2_beta34_2604.py').read_bytes())
    assert regression['main_installer_sha256']==f.read(root/'2604/firmware/upgrade/plan.json')['installer_sha256']
    assert f.read(root/'return-regression/clock/upgrade/functional.json')['passed']
    assert f.read(root/'return-regression/clock/upgrade/model-check.json')['passed']
    assert (root/'2604/clock-attempt-hardware/ram-prior.bin').read_bytes()==(root/'2604/hardware/ram-restored.bin').read_bytes()
    peer = f.read(root/'2512-already-current.json'); assert peer['passed'] and not peer['flash_written']
    assert f.read(root/'fresh/2512/report.json')['application_ram_restored']
    receipts['2512'] = dict(report='2512-already-current.json',
        report_sha256=f.sha((root/'2512-already-current.json').read_bytes()),
        final_flash_sha256=peer['full_flash_sha256'],new_sector_erases=0,
        previous_live_qualification=str(f.DATA/'output/qualification/beta34-2512-2026-10-16/hardware/report.json'))
    archive = root/'before-beta34-all-boards.zip'
    archive_hash = f.sha(archive.read_bytes())
    assert (root/'before-beta34-all-boards.sha256').read_text().split()[0] == archive_hash
    result = dict(passed=True,finished_utc=datetime.now(timezone.utc).isoformat(),
        version='2.0b34',asm='0.5',monitor='B',generation=46,fallback='2.0b28 A',
        build_sha256=f.sha((f.BUILD/'build.json').read_bytes()),boards=receipts,
        backup_zip=str(archive),backup_sha256=archive_hash,
        fleet_deploy_source_sha256=f.sha((f.ROOT/'tools/deploy_v2_beta34_fleet.py').read_bytes()),
        original_deploy_source_sha256=f.sha((root/'deploy-tool-before-return-fix.py').read_bytes()),
        return_bank_recovery=dict(board='2604',physical_reset_count=1,
            recovery_reflash_erases=0,regression='2604/return-bank-regression.json',
            recovery='2604/reset-recovery/report.json',
            source_sha256=f.sha((f.ROOT/'tools/finish_v2_beta34_2604.py').read_bytes())),
        backup_source_sha256=f.sha((f.DATA/'tools/archive_fleet_as_is.py').read_bytes()),
        all_ports_released=f.read(f.DATA/'output/qualification/serial-coordination/owner.json')['kind']=='idle',
        application_ram_restored=True,spi_sram_eeprom_rtc_preserved=True,b0_preserved=True,
        migration_matrix_run=False,soak_started=False,v21_flashed=False)
    assert result['all_ports_released']
    f.save(root/'report.json',result)
    for directory in (f.BUILD,f.DATA/'BUILD/v2-beta34-candidate'):
        assert f.sha((directory/'build.json').read_bytes())==result['build_sha256']
        f.save(directory/'beta34-hardware-fleet.json',result)
    text = '''# Beta34 / ASM 0.5 on all four boards

All four boards now have beta34 monitor B, generation 46 (`0000002E`),
ASM 0.5, the common MAINT 2.4 and SRAM/WORK/EDU 1.4 native utilities,
and CLOCK 1.9. Beta28 monitor A remains a valid fallback on every board.
The 65C816 board runs the monitor in emulation mode.

| Board | CPU | Port | Previous running version | Result | Sector erases this request |
|---|---|---|---|---|---:|
| 2512 | 65C02 | COM4 | beta34 | Full backup/readback confirmed; no rewrite | 0 |
| 2205 | 65C02 | COM3 | beta32 | Flashed and verified | 6 |
| 2609 | 65C816 | COM8 | beta32 | Flashed and verified | 6 |
| 2604 | 65C02 | COM5 | beta25 | CLOCK, system and ASM updated; verified | 19 |

## Verification and preservation

Before any writes, all four boards were backed up in parallel. Each capture
read all four flash banks and all 128 KiB SPI SRAM twice, compared EEPROM
normal/protected/status and RTC SRAM/settings/history, and restored and
verified application RAM. The backup archive passed ZIP CRC and all 147
archived file hashes.

Each new installer was bound to those exact bank preimages. The CPU model
verified final bank contents, allowed sector order, descriptor/monitor
publication, and rejection of stale preimages and damaged payloads. Model
and hardware checks covered installer return, J3 boot, native utility BATCH,
CLOCK 1.9, and ASM PASTE/assembly of a RAM program calling public PUTC/HOLD.
ASM printed the correct inclusive range and Store command:

```text
RAM $0200-$0207
S 1 AUTO 0200 0207 PROGRAM
```

The newly updated boards also booted their beta28 A fallback, returned to
beta34 through J3, and passed another complete four-bank readback. All SPI
SRAM, EEPROM, RTC settings/history and application RAM matched the saved
bytes afterward; calendar time was allowed to advance. All B0 images were
preserved. 2205 retains its unnamed board setting. 2604's uninitialized SPI
SRAM was preserved without formatting. Its known legacy flash CLOCK record
was updated to 1.9; the legacy MAINT record was preserved.

2604 used a four-sector CLOCK step followed by a fifteen-sector firmware
step. The source A monitor stayed intact until new B was verified and the
common fixed recovery image was installed; beta28 A was installed last.
Each erase, including both journal-sector erases, was included in the
tracked counts.

The CLOCK step exposed an installer return-stub defect: its last transfer
selected B1, but the stub jumped to F004 without selecting B3. The flash
step completed and verified before the wrong-bank jump. One physical RESET
was required because the halted console could not accept J3. After reset,
all four banks matched the CLOCK target and the saved application RAM was
restored. The main update resumed without rewriting the CLOCK record.

The deployment helper now explicitly selects B3 before entering ROM RESET.
A regression reproduced the original B1 return, verified the corrected
actual installer end state, and booted from that actual final bank instead
of assuming B3 in the functional fixture. The corrected main installer
passed these checks and the normal source/payload guards. Original failed
attempt/source evidence is retained in `2604/clock-attempt-hardware/` and
`deploy-tool-before-return-fix.py`; reset recovery and passing regressions
are recorded separately.

2512 was already current: its fresh full flash readback matched the earlier
successful beta34/ASM/Microchess hardware receipt. Its saved SRAM CLOCK
matches the sealed CLOCK 1.9 body. Its existing UCHESS record remains intact;
the other boards received no additional saved demonstration records. Their
ASM smoke tests made no persistent test writes.

## Backup and evidence

All paths below are relative to `C:\\SRC\\STR8-N`:

- `output/qualification/beta34-fleet-2026-10-16/report.json`: fleet receipt,
  build/source hashes and per-board final flash hashes.
- `output/qualification/beta34-fleet-2026-10-16/before-beta34-all-boards.zip`:
  complete fresh pre-update archive and its adjacent `.sha256` checksum.
- `output/qualification/beta34-fleet-2026-10-16/fresh/<board>/`: raw flash,
  SPI SRAM, EEPROM, RTC and application RAM images, repeat reads, file hashes
  and load-only application RAM restore S-record.
- `output/qualification/beta34-fleet-2026-10-16/<board>/hardware/`: complete
  final flash/SRAM readbacks, RTC/EEPROM comparisons, console transcripts,
  original/restored RAM and completed restoration marker.
- `output/qualification/beta34-fleet-2026-10-16/<board>/<stage>/upgrade/`:
  exact installer, sector payloads, target images, model receipts and plan.
- `output/qualification/beta34-2512-2026-10-16/`: earlier live ASM 0.5,
  Microchess assembly and Store/Table/Restore proof on 2512.

Raw archives remain ignored and contain board-specific data. Application
RAM restore S-records are loaded with `L` without executing `G`; these are
data backups, not resumable CPU execution checkpoints. Historical migration
source archives were retained for later fixture restoration.

All serial ports are released. The soak remains completely stopped. No
migration matrix was run, and no v2.1 alpha code was flashed.
'''
    (f.ROOT/'docs/STR8N_V2_BETA34_FLEET_2026-10-16.md').write_text(text,encoding='utf-8')
    path=f.ROOT/'README.md'; current=path.read_text(encoding='utf-8')
    start=current.index('## Beta34 / ASM 0.5 on 2512')
    end=current.find('\n## ',start+4)
    assert end != -1
    replacement='''## Beta34 / ASM 0.5 on all four boards

Boards 2512, 2205, 2609 and 2604 now run hardware-verified beta34 B generation
46 and ASM 0.5, with beta28 A retained. ASM reports inclusive RAM addresses
and a copyable Store command after assembly. The common native utilities
and CLOCK 1.9 were verified; retained data and application RAM were preserved.
All ports are released and the soak is stopped. Migration tests remain deferred.
See the [fleet installation and backup record](docs/STR8N_V2_BETA34_FLEET_2026-10-16.md)
and [candidate/output example](docs/STR8N_V2_BETA34_CANDIDATE_2026-10-16.md).
The [2512 record](docs/STR8N_V2_BETA34_2512_2026-10-16.md) covers its existing
on-board Microchess assembly and UCHESS Store/Table/Restore demonstration.
'''
    path.write_text(current[:start]+replacement+current[end:],encoding='utf-8')
    print('PASS all four boards, receipts, preservation and released serial ports')


if __name__=='__main__':main()
