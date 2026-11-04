"""Record MON A acceptance after physical boot, exact preservation and RTC audit."""
import argparse
import json
from pathlib import Path
import install_2609_mon_a_g8 as install

t = install.t


def close(rtc_path):
    case=install.CASE; scope=install.SCOPE; plan=install.admitted_plan()
    final=json.loads((case/'final-receipt.json').read_text())
    boot=json.loads(Path(final['physical_boot_report']).read_text())
    rtc_path=rtc_path.resolve(); rtc=json.loads(rtc_path.read_text())
    audit_path=rtc_path.parent.parent/'campaign-audit.json'; audit=json.loads(audit_path.read_text())
    recipe=json.loads((scope/'MON-A-RTC-admission-recipe.json').read_text())
    state=json.loads((t.ROOT/'output/qualification/rtc-drift-3hour-campaign.json').read_text())
    marker=json.loads(install.MARK.read_text())
    assert final['passed'] and boot['passed'] and rtc['passed'] and audit['passed']
    assert final['erase_requests']==final['erases_completed']==1 and final['all_19_old_records_retained']
    assert final['owner_RAM_restored'] and final['owner_ZP_restored'] and final['COM8_released']
    assert final['physical_MON_A_boot'] and boot['ROM_startup_owner_RAM_ZP_unchanged']
    assert not marker['block_snapshot'] and not marker['MON_A_g8_RTC_admission_pending']
    assert state['baselines']==recipe['baselines']
    assert state['dependencies']['tools/rtc_monb8_2609.py']==recipe['new_adapter_sha256']
    for name,digest in recipe['sampler_dependencies'].items(): assert state['dependencies'][name]==digest
    assert Path(state['base1_profiles']['2609']['qualification_report']).resolve()==rtc_path
    for n in range(4):
        for repeat in (1,2):
            assert t.sha((case/f'final-pass{repeat}-B{n}.bin').read_bytes())==plan['final_bank_sha256'][n]
            assert t.sha((case/'physical-boot'/f'final-pass{repeat}-B{n}.bin').read_bytes())==plan['final_bank_sha256'][n]
    receipt=dict(schema=1,board='2609',CPU='65C816 emulation',passed=True,
        phase='MON_A_G8_PERMANENT_INSTALL_PHYSICAL_BOOT_PRESERVATION_RTC_PASSED',
        monitor_generation='00000008',MON_A_contract='PR05',MON_B_contract='PR05',
        old_MON_A=plan['old_MON_A'],new_MON_A=plan['candidate_MON_A'],
        source_MON_B_matches_same_build=True,original_A_archived_on_host=True,
        original_A_retained_on_chip_at_finish=False,total_sector_erases=1,sector_erases={'B3:A':1},
        journal_appends=1,journal_page='D300',sequence_after=1034,valid_records_after=20,
        all_19_original_journal_records_retained=True,A_count_before=51,A_count_after=52,
        counts_unchanged=dict(C=78,D=48,E=45,F=31),F_writes=0,C_D_erases=0,
        B_E_or_tool_writes=0,boot_setting_writes=0,saved_default='S',enabled_mask=0,entries=['8000']*4,
        all_other_images_unchanged=True,owner_RAM_ZP_restored_and_native_verified=True,
        RAM_sha256=final['RAM_sha256'],ZP_sha256=final['ZP_sha256'],
        fresh_native_double_escrow=True,physical_MON_A_boot=True,ROM_startup_owner_RAM_ZP_unchanged=True,
        final_bank_sha256=plan['final_bank_sha256'],F_sha256=marker['current_F_sha256'],
        checks=final['checks'],physical_resets=1,power_cuts=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,firmware_builds=0,CPU_simulations=0,
        RTC_profile_unchanged='BASE1-MONB8-RTC-RAM1-2609',RTC_readmission_passed=True,
        RTC_sampler_bytes_unchanged=True,RTC_baselines_preserved=True,
        final_context='REC>',COM8_released=True,plan_sha256=install.PLAN_SHA,
        driver_sha256=t.sha((case/'install_2609_mon_a_g8.py').read_bytes()),
        host_check_resume_driver_sha256=t.sha((case/'host-check-resume/install_2609_mon_a_g8.py').read_bytes()),
        host_banner_assertion_corrected=True,additional_erases_on_resume=0,
        install_receipt_sha256=t.sha((case/'final-receipt.json').read_bytes()),
        boot_report_sha256=t.sha(Path(final['physical_boot_report']).read_bytes()),
        RTC_report_sha256=t.sha(rtc_path.read_bytes()),RTC_audit_sha256=t.sha(audit_path.read_bytes()),
        published_downloads_unchanged=True,source_commits_local_only=True,other_boards_untouched=True)
    t.save(case/'accepted-final-receipt.json',receipt)
    t.save(t.REPO/'monitors/validation/2609-mon-a-g8.json',receipt)
    doc='''# 2609 MON A g8: passed and retained

October 30, 2026. **W65C816SXB / 65C816 emulation / FT245, COM8.**
[Scope review](2609_MON_A_G8_SCOPE_REVIEW.md),
[public receipt](../monitors/validation/2609-mon-a-g8.json),
[current inventory](2609_CURRENT_INVENTORY.md).

## Installed A and tested behavior

MON A is now PR05 **0.1.0-dev g00000008**, matching the functional build of
the already-qualified MON B. A was installed permanently using the prebuilt
g8 image; no firmware rebuild or CPU simulation was performed. The old PR04
generation 8000000F sector and all original banks are archived in verified
private host backups; old A is no longer resident on chip.

Live A checks passed for identity/CPU16, Dump/Modify, refusal of force writes
to F/C/D, M1, W, APPS and TIME. Board-flash CLOCK read/return and MAINT LOAD
of WB2 g5 passed. PROGRAM Table, bounded BATCH and AUTO Store preview with
NO cancellation passed without a record write. Both CLOCK and the workbench
returned through the active-monitor contract to **MON A**, verified by V.

The first host check expected CLOCK Q to repeat the monitor banner; it
actually returns directly to the prompt. The driver restored and verified
owner RAM, then resumed with an explicit V identity check after Q. This was
a host assertion correction; no firmware rebuild or additional erase occurred.

With the receiver armed, one physical CPU RESET displayed the frozen
Foundation identity and selected A once. Cold A g8/CPU16 startup passed;
native Dump verified owner RAM/ZP unchanged by startup. Saved default remained
**S/recovery**, bank mask 00, all entries 8000. This did not change default
selection to A. At REC>, enter `A` or `B` to choose a monitor; Q returns to REC>.

## Exact writes and preservation

Exactly **one B3:A erase** and one native wear reservation **D300/seq1034**.
A's tracked count changed **51 to 52**. All 19 original raw journal records
remain at their original positions; the final journal has **20 valid records**.
C/D/E/F counts remain **78/48/45/31**. There were zero F writes, C/D erases,
B/E/tool replacements or boot-setting writes, and no power cut. Golden F is
the original frozen 4096-byte N-F 0.3.0 BASE1/PR05 image.

Complete before and after banks were independently captured twice and matched
the exact reviewed postimages. WDC B0, B1/B2, B3:8/9, MON B and services E are
unchanged. Fresh native owner RAM0200-66FF and ZP00-DF double escrow matched
the current owner-authorized RAM reference. Trial data and helpers were then
removed by exact restoration, readback and native Dump comparison. Final
context REC>, COM8 released, no pending restoration. No SRAM/WORKSPACE record,
clock SET, trim or PF acknowledgement was issued. Other boards were untouched.

## RTC continuity and remaining work

RTC admission validates the new preserving receipt and D300 record. Live
read-only RTC/NTP requalification and its audit passed. The existing sampler
bytes, profile, RAM authority, schedule, historical points and baselines are
retained. The adapter's admission changed; the RTC instrument did not.

A and B provide identical commands for now. This pass does not claim native
816 execution, a 2609 WDC launcher, resident ASM/DBG or complete b35 parity.
Source changes stay local; frozen F and published downloads are unchanged.
Private captures remain under `output/qualification/2609-MON-A-g8-*` in the
parent project. Public evidence contains hashes/results, not owner/vendor ROMs.
'''
    (t.REPO/'docs/2609_MON_A_G8_ACCEPTANCE.md').write_text(doc,encoding='utf-8')
    inventory=t.REPO/'docs/2609_CURRENT_INVENTORY.md'; text=inventory.read_text(encoding='utf-8')
    text=text.replace('This inventory checks the latest device marker against agreeing complete\ncaptures and the qualification receipts. No new board command, RAM upload,\nflash write or clock operation was performed for this inventory.',
        'Updated after the [permanent MON A g8 installation](2609_MON_A_G8_ACCEPTANCE.md).\nThe installation, physical boot and read-only RTC requalification passed.\nThe inventory agrees with independent complete bank captures and receipts.')
    text=text.replace('Legacy b15 MON A, generation **8000000F**, private contract **PR04**; unqualified under BASE1',
        'Current MON A **0.1.0-dev g00000008**, **PR05**, qualified and retained on 65C816 emulation')
    text=text.replace('**19 records**, latest **D200 / 1033**','**20 records**, latest **D300 / 1034**')
    text=text.replace('which supplies the proposed MON A upgrade.','which supplies the installed MON A.')
    text=text.replace('starts the qualified MON B; its Q returns to recovery. This does not change\nthe saved default. Do not treat the retained PR04 A as a qualified fallback.',
        'starts qualified MON B; `A` starts qualified MON A. Their Q returns to recovery.\nThese selections do not change the saved default. A and B have identical commands.\nOriginal PR04 A is preserved in verified host archives rather than on chip.')
    text=text.replace('B3:A is 51','B3:A is 52').replace('twelve\nordinary append pages D300–DE00','eleven\nordinary append pages D400–DE00')
    text=text.replace('## Next review and WDC boundary','## Qualification and WDC boundary')
    text=text.replace('MON B provides Dump/Modify','MON A and B provide Dump/Modify')
    start=text.index('The [MON A review]'); end=text.index('The 2512 WDC launcher',start)
    text=text[:start]+('The [MON A review](2609_MON_A_G8_SCOPE_REVIEW.md) was approved for the\n'
        'one-erase permanent installation. Its [acceptance](2609_MON_A_G8_ACCEPTANCE.md)\n'
        'closes matching A/B g8 and physical A startup on 2609. Future work needs its\n'
        'own scope; there is no pending automatic flash action.\n\n')+text[end:]
    old_hash=plan['source_bank_sha256'][3];text=text.replace(old_hash,plan['final_bank_sha256'][3])
    inventory.write_text(text,encoding='utf-8')
    review=t.REPO/'docs/2609_MON_A_G8_SCOPE_REVIEW.md'; text=review.read_text(encoding='utf-8')
    text=text.replace('**Prepared only; no new board access or flashing.** October 30, 2026.',
        '**Owner approved install-and-keep; trial passed.** October 30, 2026.\n'
        'See [acceptance](2609_MON_A_G8_ACCEPTANCE.md). The options below retain\n'
        'the original pre-install review; only the one-erase option was executed.')
    text=text.replace('2609 has qualified MON B g8 and retained PR04/b15 MON A.',
        'Before this trial, 2609 had qualified MON B g8 and retained PR04/b15 MON A.')
    review.write_text(text,encoding='utf-8')
    prior=t.REPO/'docs/2609_MON_FEATURE_ACCEPTANCE.md'; text=prior.read_text(encoding='utf-8')
    text=text.replace('services g4, WB2 g5 and PROGRAM/SP1 g1. MON A remains retained b15 firmware\nwhose execution under BASE1 is unqualified.',
        'services g4, WB2 g5 and PROGRAM/SP1 g1. At this installation checkpoint,\nMON A remained retained b15 firmware and was unqualified under BASE1. It has\nsince been replaced by [qualified MON A g8](2609_MON_A_G8_ACCEPTANCE.md).')
    prior.write_text(text,encoding='utf-8')
    print('PASS acceptance recorded locally: one A erase, physical boot, preservation and RTC continuity',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rtc-report',type=Path,required=True)
    close(parser.parse_args().rtc_report)
