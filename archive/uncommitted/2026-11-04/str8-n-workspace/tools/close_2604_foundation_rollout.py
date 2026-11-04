"""Host-only closeout: approved27-erasure2604 migration, permanent history/docs."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from installer.common import save
from installer.engine.runtime import sha
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease
import install_named_edu_2512 as ins
from nf_migrate import classify_journal

Q=ROOT/'output/qualification';REPO=ROOT/'release/str8nf-v0.2.0'
SCOPE=Q/'2604-foundation-rollout-scope-20261102-r1'
CONV=Q/'2604-foundation-conversion-installed-20261102-r1'
INSTALL=Q/'2604-foundation-profile-installed-20261102-r1'
RESET=Q/'2604-foundation-default-reset-20261102-r1'
RTC=Q/'2604-foundation-RTC-readmission-20261102-r2'
ARCHIVE=ROOT/'local-archives/STR8-N-rc1-g0034-2604-20261102'


def run():
    p=json.loads((SCOPE/'plan.json').read_text());a=json.loads((SCOPE/'approval.json').read_text())
    cv,iv,reset,rtc=[json.loads((folder/'report.json').read_text()) for folder in (CONV,INSTALL,RESET,RTC)]
    assert a['approved'] and a['plan_sha256']==sha((SCOPE/'plan.json').read_bytes())
    assert a['runtime_policy']=='Use Foundation runtime; archive rc1 cache/vectors'
    assert all(r['passed'] and r['port_released'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] for r in (cv,iv,reset,rtc))
    assert cv['conversion_erases_completed']==3 and cv['F_replacements']==1 and cv['physical_resets']==1
    assert iv['image_erase_requests']==23 and iv['journal_erase_requests']==1 and iv['journal_appends']==25 and iv['total_rollout_erases']==27
    assert reset['physical_resets']==1 and reset['saved_default_B_verified'] and reset['all_four_banks_exact']
    assert rtc['baselines_unchanged'] and rtc['other_boards_admission_unchanged'] and (rtc['trim_steps'],rtc['control'])==(-12,0)
    assert all(r['power_cuts']==0 for r in (cv,iv,reset))
    original=[(SCOPE/f'B{n}-original.bin').read_bytes() for n in range(4)]
    actual=[(INSTALL/f'B{n}-installed.bin').read_bytes() for n in range(4)]
    for n,body in enumerate(actual):assert body==(SCOPE/f'B{n}-expected.bin').read_bytes() and sha(body)==p['expected_bank_sha256'][f'B{n}']
    freeze=json.loads((REPO/'F_FREEZE.json').read_text());assert sha(actual[3][-4096:])==freeze['sha256']
    assert all(sha((REPO/name).read_bytes())==digest for name,digest in freeze['sources'].items())
    assert actual[3][0x1c00:0x2000]==original[3][0x1c00:0x2000]
    for n,start in [(0,s) for s in (0,4096,24576,28672)]+[(1,24576),(1,28672)]:
        assert actual[n][start:start+4096]==original[n][start:start+4096]
    journal=classify_journal(actual[3]);assert journal==p['journal_after']
    assert (journal['sequence'],journal['valid_records'],journal['default'])==(1252,26,'B')
    assert journal['counts'][28:]==[64,53,31,30] and journal['counts'][6]==1024
    ram=(CONV/'owner-ram.bin').read_bytes();zp=(CONV/'owner-zp.bin').read_bytes()
    assert all(r['RAM_sha256']==sha(ram) and r['ZP_sha256']==sha(zp) for r in (cv,iv,reset,rtc))
    receipt=dict(passed=True,board='2604',closed_utc=ins.t.utc(),source='STR8-N2.0rc1 g0034',
        target='Foundation0.3.0/g1 BASE1/PR05; Traditional MON A/Bg10; full native profile and ASM/DBGg2 CPU02',
        total_erases=27,conversion_erases=3,image_erases=23,native_journal_rotation_erases=1,
        old_WC_reservation_appends=1,native_journal_appends=25,original_WC_records_archived=33,original_WC_records_retained_on_chip=0,
        final_sequence=1252,final_valid_records=26,final_C_D_E_F_counts=[64,53,31,30],
        default='B',default_generation='00000010',bank_enable_mask=0,entries=[8,8,8,8],
        board_name='2604',offset_minutes=-360,RTC_trim_steps=-12,RTC_control_register=0,
        owner_RAM_ZP_restored=True,original_rc1_cache_vectors_archived=True,Foundation_runtime_initialized=True,
        approved_runtime_policy=a['runtime_policy'],F_replacements=1,F_rebuilt=False,F_sha256=freeze['sha256'],
        physical_resets_during_approved_rollout=2,earlier_preflight_recovery_resets=1,power_cuts=0,
        SPI_data_writes=0,RTC_setting_writes=0,PF_ACK=0,firmware_builds=0,CPU_simulations=0,automatic_retries=0,
        baselines_unchanged=True,other_boards_accessed=[],published_download_changes=0,
        permanent_archive=str(ARCHIVE),bank_sha256=p['expected_bank_sha256'],RAM_sha256=sha(ram),ZP_sha256=sha(zp),
        final_prompt='REC>',COM5_released=True,RTC_readmitted=True,
        limits=['Exact WC conversion was qualified as this private2604 transaction; public b15 upgrader guard stays unchanged',
          'No new persistent source/STORE/WORKSPACE write fixture or factory restoration trial on2604',
          'Matched installed payloads reused; no claim of repeating the entire2512 adverse-case suite'],
        report_sha256={folder.name:sha((folder/'report.json').read_bytes()) for folder in (CONV,INSTALL,RESET,RTC)})
    target=ARCHIVE/'approved-Foundation-rollout-20261102'
    additions={
        'approved-plan.json':SCOPE/'plan.json','approved-review.md':SCOPE/'review-document.md',
        'runtime-policy-addendum.md':SCOPE/'RUNTIME-PRESERVATION-APPROVED-ADDENDUM.md',
        'WC-reservation-seq1225.bin':SCOPE/'legacy-reservation-128.bin',
        'conversion-static-review.json':SCOPE/'conversion-engine-review/static-review.json',
        'converted-B3-roots-1226-1227.bin':CONV/'B3-converted.bin',
        'final-B3-seq1252.bin':INSTALL/'B3-installed.bin',
        'conversion-report.json':CONV/'report.json','profile-install-report.json':INSTALL/'report.json',
        'default-reset-report.json':RESET/'report.json','default-startup.txt':RESET/'full-startup.txt',
        'RTC-readmission-report.json':RTC/'report.json',
        'preconversion-RTC-preservation-reference.json':RTC/'preconversion-RTC-preservation-reference.json'}
    for name,path in additions.items():durable(target/name,path.read_bytes())
    durable(target/'ROLLOUT-COMPLETE.json',(json.dumps(receipt,indent=2)+'\n').encode())
    members={x.name:dict(bytes=x.stat().st_size,sha256=sha(x.read_bytes())) for x in target.iterdir() if x.is_file()}
    durable(target/'rollout-archive-manifest.json',(json.dumps(dict(permanent=True,local_only=True,files=members),indent=2)+'\n').encode())
    with serial_lease('2604-approved-rollout-host-closeout',timeout=30):
        mp=Q/'device-operations/2604.json';m=json.loads(mp.read_text())
        assert m['foundation_rollout_complete'] and not m['block_snapshot'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
        assert m['current_physical_bank_sha256']==p['expected_bank_sha256']
        counts=m.get('current_tracked_erase_counts',{}).copy()
        counts.update({f'B{n//8}:{8+n%8:X}':value for n,value in enumerate(journal['counts'])})
        counts.update({name:journal['counts'][n] for name,n in zip('ABCDEF',range(26,32))})
        m.update(current_tracked_erase_counts=counts,current_journal_sequence=1252,current_wear_counts=journal['counts'],
            current_valid_journal_records=26,current_journal_valid_records=26,saved_default='B',saved_default_generation='00000010',
            current_owner_RAM_sha256=sha(ram),current_owner_ZP_sha256=sha(zp),
            ASM_DBG_installed_qualified=True,ASM_source_generation='00000002',DBG_generation='00000002',
            foundation_rollout_closeout=str(SCOPE/'completion.json'),rc1_permanent_archive=str(ARCHIVE),
            RTC_control_register=0,RTC_trim_steps=-12,final_prompt='REC>')
        save(mp,m)
    save(SCOPE/'completion.json',receipt)
    docs=REPO/'docs'
    hashes='\n'.join(f'- B{n}: `{sha(body)}`' for n,body in enumerate(actual))
    (docs/'2604_CURRENT_INVENTORY.md').write_text(f'''#2604 current recorded inventory

November2,2026. [Approved rollout and acceptance](2604_FOUNDATION_ROLLOUT_ACCEPTANCE.md)
completed on W65C02SXB/COM5, USB A10MQGVHA. MON A/B have identical commands.

| Region | Installed content |
|---|---|
| B0:8/9/E/F | Original erased bytes retained;8/9 are physically blank, not an automatic write allowance |
| B0:A/B | ASM/source g2, CPU02 AP/02 |
| B0:C/D | DBGg2 and D800-DFFF SF/1 provider, CPU02 AP/02 |
| B1:8-D | Qualified BANK MAINT2.4/g3, SRAM/WORK and transfer tools |
| B1:E/F | Original rc1/legacy owner bytes retained; not automatically BASE1-qualified |
| B2:8-F | WB2gE, PROGRAMg3, STATUS, CLOCK, FLASH/CONFIG and transfer services |
| B3:8/9 | Native RTC/loader/history code; all9C00-9FFF metadata exact |
| B3:A/B | MON A/Bg00000010, Traditional startup |
| B3:C/D | SNBTseq1252,26 valid records; C/D/E/F64/53/31/30 decimal |
| B3:E | Qualified dispatcher including R ASM/R DBG |
| B3:F | Frozen4096-byte Foundation0.3.0/g1 BASE1/PR05 |

Default B/g10; bank autostarts disabled, entries8000. Name2604, offset-06:00,
RTC trim-12/control00, PROGRAM payload14336 and WORKSPACE114656 bytes retained.
The largest tracked sector is B0:E with1024 attempts, carried forward from
the original history. This is not a new destructive wear test or a health claim.

Original rc1g0034 code/source, full128KiB double capture, all33 WC records and
all replaced images are permanently local and untracked under
`C:\\SRC\\STR8-N\\local-archives\\STR8-N-rc1-g0034-2604-20261102`.
The chip now has SNBT instead of WC records. Every tracked lower bound survives;
prior/direct lifetime stays unknown. Do not restore old journal counts blindly.

Owner RAM0200-66FF and ZP00-DF were restored/read back after all checks.
By explicit approval, legacy runtime cache/vectors are archived and matching
Foundation/MON state is initialized. Final REC>, COM5 released; saved B boots
on RESET or can be selected with B at recovery. RTC/NIST collection is readmitted
without resetting baselines. No other board or published download was changed.

Current physical bank SHA256:

{hashes}

No new flash/PROGRAM source-write fixture, WORKSPACE mutation or factory
restoration trial was included. Identical shared components reuse their prior
2512/2609 qualification; this receipt records the actual2604 installed checks.
''',encoding='utf-8')
    (docs/'2604_FOUNDATION_ROLLOUT_ACCEPTANCE.md').write_text(f'''#2604 rc1g0034 to Foundation: completed acceptance

November2,2026. The owner approved the exact27-erase scope and the correction
to archive old provider cache/interrupt/HOLD vectors while initializing the
matching Foundation runtime. Original owner RAM/ZP and persistent data remain
preserved. [Current inventory](2604_CURRENT_INVENTORY.md) records the layout.

## What ran

Fresh native source/owner escrow admitted the exact rc1 F and four source banks.
The unchanged qualified RAM engine appended WCseq1225 at D080, then converted
C/F/D: committed SNBT/S root, exact frozen F, newer SNBT/S root. Physical RESET
reached BASE1 REC>; independent four-bank readback and owner restoration passed.
This separately inspected WC conversion did not bypass the public b15/SNBT
upgrader guard or reset counters. It is a private board-bound transaction.

The23 reviewed image sectors were replaced with accepted binaries, using25
native journal appends including the C rotation and final B-default binding.
Three conversion erases plus23 image erases plus one C rotation =27 total.
There was one F replacement, no F rebuild or later F write. Both rollout CPU
resets passed; no power cut, automatic retry, SPI-data/RTC-setting/PF-ACK write
or other-board access occurred. An earlier RAM-probe cleanup needed one
separately requested CPU RESET; that preflight incident and successful owner
restoration remain recorded rather than being counted as a rollout failure.

## Actual installed checks

- MON A/Bg10 VERSION, CPU02/board metadata, fresh TIME/trim and Traditional startup.
- Full CLOCK, BANK MAINT2.4/g3, FLASH and SRAM/WORK/TABLE front doors; APPS lists ASM/DBG.
- Returning BATCH; assemble/export/read back/run a RAM program through public HOLD.
- Real DBG BRK step, continue and restoration of the new default hooks.
- Physical saved-default B boot with EDU ON and original14336/114656 capacity split.
- Nine native TIME/NIST readings and unchanged794-byte62-second LED sampler.
- Final expected four-bank image/settings/journal/F readback and exact owner RAM/ZP restoration.

The RTC host gate initially assumed another board's control80. Original2604
receipt and both successful new sample sets show control00, trim-12. The host
gate was corrected against that original receipt; successful samples were
reused, no clock register was written and no sampling replay was needed.
The failed outer gate and the r2 closeout are both retained. Baselines,
segment boundaries and the other boards' admission entries remain unchanged.

## Preservation and result

All33 original WC rows, raw C/D and every original image are in the permanent
untracked local archive. Zero old WC rows remain on chip after the approved
format conversion. Maximum historical counts carry forward; final C/D/E/F
64/53/31/30, seq1252 and26 valid SNBT records, prior-lifetime maskFFFFFFFF.
Default B remains B, generation binding becomes g10; disabled bank autostarts
remain disabled. Board name2604, offset-06:00 and all9C00-9FFF metadata bytes
are exact. RTC time/trim/control/PF/EEPROM and SPI PROGRAM/WORKSPACE are retained.

F SHA256: `{freeze['sha256']}`. Owner RAM SHA256: `{sha(ram)}`.
Owner ZP SHA256: `{sha(zp)}`. Final REC>, COM5 released and RTC readmitted.
2205/2512/2609 hardware and published files were untouched by this rollout.
No firmware build or CPU simulation ran.

Private receipts: `output/qualification/2604-foundation-rollout-scope-20261102-r1/completion.json`,
conversion/profile/default-reset cases, and RTC readmission r2. Permanent
history closes at `local-archives/STR8-N-rc1-g0034-2604-20261102/approved-Foundation-rollout-20261102/ROLLOUT-COMPLETE.json`.

The private conversion and installed smoke checks do not claim new2604
persistent source/STORE/WORKSPACE positives, factory restoration or full replay
of2512's adversarial suite. Public release downloads and candidate ZIPs remain
unchanged; this work does not publish a generic rc1 migration route.
''',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':run()
