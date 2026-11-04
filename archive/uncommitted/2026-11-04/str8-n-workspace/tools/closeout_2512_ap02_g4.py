"""One-board native RTC continuity and local acceptance after the AP/02 trial."""
import argparse
import json
from pathlib import Path
import trial_2512_ap02_g4 as trial

t=trial.t
CASE=t.ROOT/'output/qualification/2512-AP02-g4-trial-20261030-r1'


def rtc():
    import rtc_mon_time_2512 as native
    c=native.c
    r=json.loads((CASE/'final-receipt.json').read_text())
    assert r['passed'] and r['original_B0_restored'] and r['owner_RAM_restored'] and r['COM4_released']
    assert r['erases_completed']==1 and r['sequence_after']==1042
    before=c.read(c.STATE)
    assert c.sha(t.ROOT/'tools/rtc_mon_time_2512.py')==before['dependencies']['tools/rtc_mon_time_2512.py']
    out=CASE/'RTC-continuity/2512'
    result=native.collect(out)
    assert result['passed'] and result['original_RAM_untouched'] and result['port_released']
    with t.serial_lease('2512-AP02-native-RTC-acceptance',timeout=30):
        state=c.read(c.STATE)
        assert state['baselines']==before['baselines'] and state['dependencies']==before['dependencies']
        path=out/'report.json'
        item=dict(board='2512',report=str(path),sha256=c.sha(path),offset=result['rtc_minus_reference_interval_s'],
            trim=result['trim_steps'],RAM_restored=True,capture_profile=native.PROFILE)
        point=native.audit_board(item,state)
        root=Path(state['root']);points=c.read(root/'points.json')
        if not any(p['board']=='2512' and p['time']==point['time'] for p in points):points.append(point)
        c.save(root/'points.json',points)
        summary=dict(passed=True,started_utc=result['started_utc'],finished_utc=result['finished_utc'],
            boards=[item],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,
            flash_writer=False,ports_released=True)
        c.save(out.parent/'summary.json',summary)
        audit=dict(passed=True,issues=[],new_PF_events=[],summary_sha256=c.sha(out.parent/'summary.json'),
            exact_native_V_TIME_only=True,sampler_source_unchanged=True,no_RAM_upload=True,
            no_NVM_write=True,baselines_preserved=True,PF_latched_observed=point['PF_latched'],
            trim_freshly_read=False,PF_history_freshly_read=False)
        c.save(out.parent/'campaign-audit.json',audit)
        marker=c.read(t.MARK)
        assert marker['current_journal_sequence']==1042 and not marker['application_RAM_restore_pending']
        marker.update(AP02_g4_RTC_continuity_pending=False,last_AP02_g4_RTC_continuity=str(path))
        c.save(t.MARK,marker)
        state['board_admission']['2512']={k:marker.get(k) for k in state['board_admission']['2512']}
        state['base1_profile']=dict(state['base1_profile'],qualification_report=str(path),
            qualification_report_sha256=c.sha(path),qualification_audit=str(out.parent/'campaign-audit.json'),
            qualification_audit_sha256=c.sha(out.parent/'campaign-audit.json'),
            qualification='Native V/TIME exact trace passed after preserving AP/02 g4 trial; no sampler or clock change')
        state.setdefault('firmware_profile_events',[]).append(dict(board='2512',UTC=point['UTC'],
            reason='Current-g4 AP/02 fixture removed; original B0, boot policy and owner RAM preserved; one wear append; native TIME/NTP path unchanged; no reset or clock/PF write',report=str(path)))
        state.update(last_attempt_utc=c.NOW(),last_summary=str(out.parent/'summary.json'))
        c.save(c.STATE,state);c.report(state)
    print('PASS 2512 native V/TIME/NTP exact audit; source, baselines and existing schedule retained',flush=True)


def close():
    case=CASE;scope=trial.SCOPE;repo=t.REPO
    r=json.loads((case/'final-receipt.json').read_text());p=json.loads((scope/'plan.json').read_text())
    rtc_path=case/'RTC-continuity/2512/report.json';rr=json.loads(rtc_path.read_text())
    audit=json.loads((rtc_path.parent.parent/'campaign-audit.json').read_text())
    marker=json.loads(t.MARK.read_text())
    assert r['passed'] and rr['passed'] and audit['passed']
    assert r['erase_requests']==r['erases_completed']==1 and r['program_commands']==17
    assert r['checksum_cells']==['901C','901D','901E','901F'] and r['APP_run_owner_RAM_ZP_unchanged']
    assert r['all_28_original_journal_records_retained'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
    assert r['original_B0_restored'] and r['all_expected_final_banks'] and r['COM4_released']
    assert marker['current_journal_sequence']==1042 and marker['current_journal_valid_records']==29
    assert not marker['block_snapshot'] and not marker['AP02_g4_RTC_continuity_pending']
    for n in range(4):
        for repeat in (1,2):assert t.sha((case/f'final-pass{repeat}-B{n}.bin').read_bytes())==p['stage_bank_sha256']['restored'][n]
    receipt=dict(schema=1,board='2512',CPU='65C02',passed=True,
        phase='CURRENT_G4_AP02_PROGRAM_LAUNCH_RETURN_RESTORE_RTC_PASSED',
        monitor='MON B g00000008',services='g00000004',APP_name='APPDEMO',APP_entry='9020',
        APP_source_sha256=p['source_APP_image_sha256'],APP_bytes=120,APP_body_bytes=88,
        install_erases=0,total_sector_erases=1,sector_erases={'B0:9':1},native_program_commands=17,
        CRC_seal_cells=r['checksum_cells'],header_and_payload_CRC_refusal_qualified=True,
        APPS_valid_inventory=True,flash_APP_launch_help_bare_Q_public_HOLD_qualified=True,
        APP_run_owner_RAM_ZP_unchanged=True,owner_RAM_ZP_restored_and_native_verified=True,
        RAM_sha256=r['RAM_sha256'],ZP_sha256=r['ZP_sha256'],original_B0_restored=True,
        original_sector_restored_to_all_FF=True,all_other_images_unchanged=True,
        journal_appends=1,journal_page='CC00',sequence_after=1042,valid_records_after=29,
        all_28_original_journal_records_retained=True,B0_9_count_before=14,B0_9_count_after=15,
        counts_C_D_E_F_unchanged=[53,33,28,24],ordinary_pages_remaining=['CD00','CE00'],
        saved_default='B',saved_MON_generation='00000008',enabled_mask=15,entries=['8000']*4,
        F_sha256=p['F_sha256'],F_writes=0,C_D_erases=0,MON_A_B_E_or_tool_writes=0,
        boot_setting_writes=0,SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
        RTC_native_TIME_continuity_passed=True,RTC_sampler_source_unchanged=True,
        RTC_baselines_and_schedule_preserved=True,RTC_trim_freshly_read=False,RTC_PF_history_freshly_read=False,
        RTC_PF_latched_observed=rr['PF_latched'],final_context='MON B / B3>',COM4_released=True,
        final_bank_sha256=p['stage_bank_sha256']['restored'],plan_sha256=trial.PLAN_SHA,
        driver_sha256=t.sha((case/'trial-driver.py').read_bytes()),trial_receipt_sha256=t.sha((case/'final-receipt.json').read_bytes()),
        RTC_report_sha256=t.sha(rtc_path.read_bytes()),RTC_audit_sha256=t.sha((rtc_path.parent.parent/'campaign-audit.json').read_bytes()),
        checks=r['checks'],other_boards_untouched=True,published_downloads_unchanged=True,source_commits_local_only=True)
    t.save(case/'accepted-final-receipt.json',receipt);t.save(repo/'monitors/validation/2512-ap02-g4-positive.json',receipt)
    doc='''# 2512 current-g4 AP/02 app launch: passed

October 30, 2026. **65C02 / FT245**, installed MON B g8 and services g4.
[Approved one-erase scope](2512_AP02_G4_SCOPE_REVIEW.md),
[public receipt](../monitors/validation/2512-ap02-g4-positive.json).

The existing 120-byte AP/02 example (88-byte body, PR05/CPU02, entry 9020)
ran directly from B0:9. Fresh native owner RAM/ZP double escrow and complete
bank double captures admitted the still-FF sector before programming. Fifteen
native !M commands installed the unsealed example without an erase. Header
CRC refusal passed; sealing 901C-901D then left payload CRC refusal intact.
Sealing 901E-901F admitted APPS inventory and `APP APPDEMO`. Help redisplayed;
bare Q returned through public HOLD to MON B g8/CPU02. Native Dump proved
the example/return path left original owner RAM0200-66FF and ZP00-DF intact.

The single approved B0:9 erase restored its original 4096 FF bytes. The
native reservation at **CC00/seq1042** changed its tracked count **14 to 15**.
All **28 old raw journal records** remain at their original locations; final
**29 valid records**. C/D/E/F remain **53/33/28/24**. Two ordinary append pages
remain CD00/CE00; CF00 remains reserved. Counts represent tracked attempts,
not lifetime totals. No C/D erase, F/MON/services/tool replacement, other image
write, boot-setting change, reset or power cut occurred.

Complete final banks were independently captured twice and matched the plan.
Original B0, including FLASH at 8 and WDC at F, is restored exactly. Original
default B/generation 8, mask0F, entries8000 and other policy/history fields
carry forward. Fresh owner RAM/ZP was restored, read back, then compared
again through the native monitor. Final MON B/B3>, COM4 released, no pending
restoration. APPDEMO was temporary and is no longer installed.

The unchanged native V/TIME sampler passed its RTC/NTP continuity burst and
exact serial trace audit. Existing clock settings, source/profile, historical
samples, baselines and schedule are retained. Native TIME does not freshly
measure trim or read full PF history; observed PF state is recorded without
acknowledgement. There were no SRAM/PROGRAM/WORKSPACE or EEPROM writes, no
clock SET/trim/PF command, no firmware build or CPU simulation. Other boards
were untouched; F, published downloads and release assets are unchanged.

This closes the current-g4 positive AP/02 case on 2512, complementing the
2609/65C816-emulation acceptance. A bounded soak remains the next proposed
checkpoint and is not started by this closeout. Private captures and owner
data remain under `output/qualification/2512-AP02-g4-*` in the parent project.
'''
    (repo/'docs/2512_AP02_G4_ACCEPTANCE.md').write_text(doc,encoding='utf-8')
    review=repo/'docs/2512_AP02_G4_SCOPE_REVIEW.md';text=review.read_text(encoding='utf-8')
    text=text.replace('**Prepared; awaiting exact target approval.** October 30, 2026.',
        '**Owner approved one-erase trial; passed.** October 30, 2026.\nSee [acceptance](2512_AP02_G4_ACCEPTANCE.md). The scope below retains the pre-trial review.')
    text=text.replace('No board port has been opened\nfor this preparation.', 'The preparation opened no board port; the approved execution is recorded separately.')
    text=text.replace('This review grants no flash permission.', 'The completed approval grants no additional erase or programming allowance.')
    review.write_text(text,encoding='utf-8')
    roadmap=repo/'docs/FOUNDATION_RELEASE_PATH.md';text=roadmap.read_text(encoding='utf-8')
    text=text.replace('| Earlier g3 receipt; not repeated with g4 | Passed; original WDC restored |',
        '| Passed current g4; original FF sector/B0 restored | Passed; original WDC restored |')
    needle='2609\'s subsequent [permanent MON A g8 acceptance]'
    note=('The [2512 current-g4 AP/02 acceptance](2512_AP02_G4_ACCEPTANCE.md) also passed,\n'
        'using one B0:9 restoration erase and CC00/seq1042. Its 28 old records,\n'
        'original images, B default and owner RAM/ZP are preserved; native TIME/NTP\n'
        'continuity passed. No new soak or published download was created.\n\n')
    assert needle in text;text=text.replace(needle,note+needle)
    roadmap.write_text(text,encoding='utf-8')
    print('PASS local current-g4 AP/02 acceptance; one erase, full preservation, RTC continuity',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['rtc','close'])
    {'rtc':rtc,'close':close}[parser.parse_args().phase]()
