"""Publish AP/02 acceptance only after exact WDC/RAM restore and RTC admission."""
import argparse
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t


def close(rtc_path):
    root=t.ROOT;repo=t.REPO
    case=root/'output/qualification/2609-AP02-trial-20261030-r1'
    scope=root/'output/qualification/2609-AP02-scope-20261030-r1'
    r=json.loads((case/'final-receipt.json').read_text());p=json.loads((scope/'plan.json').read_text())
    rtc_path=rtc_path.resolve();rtc=json.loads(rtc_path.read_text())
    audit_path=rtc_path.parent.parent/'campaign-audit.json';audit=json.loads(audit_path.read_text())
    marker=json.loads((root/'output/qualification/device-operations/2609.json').read_text())
    state=json.loads((root/'output/qualification/rtc-drift-3hour-campaign.json').read_text())
    recipe=json.loads((scope/'RTC-admission-recipe.json').read_text())
    assert r['passed'] and r['APP_run_owner_RAM_ZP_unchanged'] and r['original_WDC_bank_restored']
    assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['all_expected_final_banks']
    assert r['erase_requests']==r['erases_completed']==2 and r['checksum_cells']==['901C','901D','901E','901F']
    assert rtc['passed'] and audit['passed'] and marker['AP02_flash_trial_closed']
    assert not marker['block_snapshot'] and not marker['AP02_RTC_admission_pending']
    assert state['baselines']==recipe['baselines']
    assert state['dependencies']['tools/rtc_monb8_2609.py']==recipe['new_adapter_sha256']
    for n,h in recipe['sampler_dependencies'].items():assert state['dependencies'][n]==h
    assert Path(state['base1_profiles']['2609']['qualification_report']).resolve()==rtc_path
    for n in range(4):
        for repeat in (1,2):assert t.sha((case/f'final-pass{repeat}-B{n}.bin').read_bytes())==p['expected_final_bank_sha256'][n]
    receipt=dict(schema=1,board='2609',CPU='65C816 emulation',passed=True,
        phase='AP02_FLASH_RUN_RETURN_WDC_RESTORED_RTC_READMITTED',monitor_generation='00000008',service_generation='00000004',
        application_name='APPDEMO',temporary_target='B0:9000',entry='9020',APP_body_bytes=88,
        APP_body_sha256=p['unchanged_application_body_sha256'],CPU_header='16',
        AP02_fixture_sha256=p['fixture_SHA256']['valid'],source_65C02_example_sha256=p['source_APP_image_sha256'],
        header_and_payload_CRC_refusal_qualified=True,named_flash_launch_qualified=True,
        help_redisplay_qualified=True,bare_Q_public_HOLD_return_qualified=True,
        APP_run_owner_RAM_ZP_unchanged=True,original_owner_RAM_ZP_restored_verified=True,
        original_WDC_sector_restored=True,original_WDC_bank_restored=True,
        original_WDC_sector_sha256=p['original_sector_sha256'],original_WDC_bank_sha256=p['WDC_full_bank_sha256'],
        total_sector_erases=2,sector_erases={'B0:9':2},checksum_1_to_0_cells=r['checksum_cells'],
        journal_appends=2,journal_pages=['D100','D200'],all_17_original_journal_records_retained=True,
        sequence_after=1033,valid_records_after=19,B0_9_count_after=4,counts_unchanged=r['counts_after'],
        saved_default='S',enabled_mask=0,entries=['8000']*4,other_boot_policy_preserved=True,
        all_other_owner_images_unchanged=True,F_sha256=p['F_sha256'],F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,
        final_bank_sha256=p['expected_final_bank_sha256'],SRAM_data_writes=0,WORKSPACE_writes=0,
        full_SRAM_comparison_performed=False,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
        firmware_builds=0,assembler_invocations=0,CPU_simulations=0,RTC_profile_unchanged='BASE1-MONB8-RTC-RAM1-2609',
        RTC_readmission_passed=True,RTC_sampler_bytes_unchanged=True,RTC_baselines_preserved=True,
        RTC_old_adapter_sha256=recipe['old_adapter_sha256'],RTC_new_adapter_sha256=recipe['new_adapter_sha256'],
        final_context='REC>',COM8_released=True,checks=r['checks'],plan_sha256=r['plan_sha256'],
        trial_receipt_sha256=t.sha((case/'final-receipt.json').read_bytes()),
        RTC_report_sha256=t.sha(rtc_path.read_bytes()),RTC_audit_sha256=t.sha(audit_path.read_bytes()),
        driver_sha256=t.sha((case/'trial_2609_ap02.py').read_bytes()),published_downloads_unchanged=True)
    t.save(case/'accepted-final-receipt.json',receipt)
    t.save(repo/'monitors/validation/2609-ap02-positive.json',receipt)
    doc='''# 2609 AP/02 named flash launch: passed

October 30, 2026. **65C816 emulation / FT245**, installed MON B g8 and
services g4, golden N-F v0.3.0 g1 / BASE1 / PR05.
[Public receipt](../monitors/validation/2609-ap02-positive.json),
[approved retained-WDC target review](2609_AP02_SCOPE_REVIEW.md).

## Execution and CRC admission

The existing88-byte public-console/HOLD example ran directly from B0:9020.
Its AP/02 header's CPU tag changed02 to16 with a recalculated header CRC;
the executable body was unchanged and no assembler/firmware build occurred.
The first unsealed-header image was omitted from APPS and named launch was
refused. Sealing only the header CRC still refused the unsealed payload.
Sealing the payload CRC then listed APPDEMO B0:9000 and admitted
`APP APPDEMO`. Help redisplayed; bare Q returned through public HOLD to
MON B/g8/CPU16. Native Dump afterward confirmed all original owner
RAM0200-66FF and ZP00-DF unchanged by the app/return path.

## Exact restoration and history

The occupied B0:9 target was used only under its explicit two-erase approval.
The first erase installed the fixture; four checksum cells at901C-901F were
programmed1-to0 without another erase. The second erase restored its exact
original4096 bytes. Complete original WDC B0 is restored:
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.
APPDEMO is a temporary fixture and is no longer installed at closeout.

Each component and journal postimage matched the sealed plan. Final banks
were independently read twice. All17 old journal records remain intact;
new D100/seq1032 and D200/seq1033 reserve the two B0:9 erases. Final19 valid
rows, B0:9 count4; C=78/D=48/E=45/F=31 unchanged (decimal). Saved default S,
mask00, entries8000, delay, generation fields and prior-wear flags carry
forward. No C/D erase, F/MON A/B/E replacement, other image write, reset or
power cut. No SPI SRAM/WORKSPACE service or data write was part of this
trial; a new full-SRAM comparison is not claimed. The app uses console/HOLD.

Fresh native owner RAM/ZP double escrow matched the prior qualified authority.
After flash restoration those bytes were restored and independently compared
again. Original REC> returned; COM8 released. 2205,2512 and2604 were outside
this trial. No vendor-monitor execution or native816 mode is qualified.

## RTC continuity and release boundary

RTC source admission now validates the new preserving receipt and journal
rows. The profile and exact sampler bytes remain unchanged. A live read-only
RTC/NTP qualification passed with all-bank comparison and owner restoration;
its audit passed. Clock settings, trim, PF flags, baselines, prior samples and
the existing hourly schedule are preserved. This was an admission update,
not a CPU reset or a new firmware image. The prior adapter source is archived.

This closes current-g4 positive AP/02 flash-app launch on816 emulation.
The2512 PROGRAM acceptance separately records its repaired host directory
scope error. ASM/DBG stay deferred and nonblocking; complete b35 parity,
SS2 writes and native-mode tools remain separate work. Published Foundation
and preview archives, tags and frozen F are unchanged. Private WDC backups,
captures, plan, driver and RTC receipts remain under the parent project's
`output/qualification/2609-AP02-*` directories; public evidence contains
hashes and results without owner/vendor firmware bytes.
'''
    for a,b in [('existing88-byte','existing 88-byte'),('changed02 to16','changed 02 to 16'),
        ('at901C','at 901C'),('programmed1-to0','programmed 1-to-0'),('original4096','original 4096'),
        ('All17','All 17'),('Final19','Final 19'),('count4','count 4'),('mask00','mask 00'),
        ('entries8000','entries 8000'),('2205,2512 and2604','2205, 2512 and 2604'),
        ('native816','native 816'),('on816','on 816'),('The2512','The 2512')]:doc=doc.replace(a,b)
    (repo/'docs/2609_AP02_ACCEPTANCE.md').write_text(doc)
    print('PASS public AP/02 receipt: original WDC restored, current g4 launch passed, RTC readmitted')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rtc-report',type=Path,required=True)
    close(parser.parse_args().rtc_report)
