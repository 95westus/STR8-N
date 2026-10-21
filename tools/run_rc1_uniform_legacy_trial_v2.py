"""Execute one sealed, owner-authorized legacy migration qualification phase.

Only 2604/2609; shared serial lease, finite phases, no automatic reset, no
generation49 rollback, native mode or RTC drift collection. Vendor fixtures
and original data remain private. Fixture completion is not final acceptance.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BOARDS={'2604':('COM5','A10MQGVHA'),'2609':('COM8','A10MPQXCA')}
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
NOW=lambda:datetime.now(timezone.utc).isoformat()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=BOARDS,required=True)
    ap.add_argument('--phase',choices=('stage-wdc','migrate-wdc','stage-beta4','migrate-beta4'),required=True)
    a=ap.parse_args();run=a.run.resolve();assert run.is_relative_to(Q)
    auth=READ(run/'owner-authorization.json');ad=READ(run/'admission-v2.json')
    assert auth['owner_authorized'] and auth['physical_RESET_assistance_confirmed'] and auth['fixture_staging_authorized']
    assert not auth['native_debugging'] and not auth['RTC_drift_in_release_qualification'] and not auth['manual_rollback_through_generation49']
    assert ad['passed'] and SHA(run/'owner-authorization.json')==ad['owner_authorization_sha256']
    for path,digest in ad['source_sha256'].items():assert SHA(path)==digest,path
    for path,digest in ad['evidence_sha256'].items():assert SHA(path)==digest,path
    kit=Path(ad['kit']);sys.path[:0]=[str(kit),str(kit/'engine')]
    import upgrade as u
    u.plans.package(kit);assert SHA(kit/'uniform-manifest.json')==ad['uniform_manifest_sha256']
    assert set(READ(Q/'active-rtc-campaign.json')['powered_off_boards'])=={'2205','2512'}
    trial=Path(ad['trial_roots'][a.board]);proof=READ(trial/'report.json');assert proof['passed'] and proof['uniform_manifest_sha256']==ad['CPU_proof_uniform_manifest_sha256']
    expected_case=next(item for item in proof['checks'] if item['name']==a.phase)
    planroot=trial/a.phase;plan=READ(planroot/'plan.json')
    assert SHA(planroot/'plan.json')==expected_case['plan_sha256'] and SHA(planroot/'installer-model-only.s19')==expected_case['installer_sha256']
    original_backup=Path(ad['original_backups'][a.board]);original=(original_backup/'capture/application-ram.bin').read_bytes()
    assert SHA(original_backup/'report.json')==proof['original_backup_report_sha256']
    phases=('stage-wdc','migrate-wdc','stage-beta4','migrate-beta4');position=phases.index(a.phase)
    if position:
        prior_path=run/a.board/'live-v2'/phases[position-1]/'report.json'
        if not prior_path.exists():prior_path=run/a.board/'live'/phases[position-1]/'report.json'
        prior=READ(prior_path)
        if prior['passed']:assert not prior['physical_reset_pending']
        else:
            # Never relabel the failed original host check or repeat its flash
            # transaction. A sealed, exited, device-verified fixture can resume
            # only through the new exact-source capture/preflight workflow.
            assert a.board=='2604' and a.phase=='migrate-beta4'
            handoff=READ(Path(ad['resume_from_verified_fixture']['2604']))
            assert handoff['resume_authorized'] and handoff['actual_worker_exit_verified']
            assert handoff['failed_source_report_sha256']==SHA(prior_path)
            assert prior['transaction_device_verified'] and prior['transfers_completed']==22
            assert handoff['source_fixture_expected_sha256']==plan['source_sha256']
            assert 'Wrong firmware' in prior['failure'] and handoff['physical_beta4_boot_verified']
    base=Path(ad['CPU_proof_kit']);base_manifest=READ(base/'uniform-manifest.json')
    assert SHA(base/'uniform-manifest.json')==ad['CPU_proof_uniform_manifest_sha256']
    for name in base_manifest['files']:
        if name!='upgrade.py':assert (base/name).read_bytes()==(kit/name).read_bytes(),name
    assert READ(kit/'uniform-manifest.json')['host_protocol_provenance']['changed_runtime_members']==['upgrade.py']
    marker_path=Q/'device-operations'/f'{a.board}.json';marker=READ(marker_path)
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped'] and not marker.get('current_soak_worker_pid')
    assert not marker.get('register_edit_worker_active') and not marker.get('physical_reset_pending')
    if marker.get('block_snapshot') or marker.get('application_RAM_restore_pending'):
        assert marker.get('uniform_upgrade_run')==str(run) and position and not marker.get('uniform_upgrade_worker_active')
    out=run/a.board/'live-v2'/a.phase;assert not out.exists();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    state=dict(passed=False,board=a.board,phase=a.phase,pid=os.getpid(),started_utc=NOW(),native_debugging=False,
        RTC_drift_in_release_qualification=False,manual_rollback_through_generation49=False,physical_reset_pending=False,
        original_RAM_restore_pending=bool(marker.get('application_RAM_restore_pending')),source_plan_sha256=SHA(planroot/'plan.json'))
    def checkpoint(phase=None):
        if phase:state['state']=phase
        u.save(out/'report.json',state)
        marker.update(state='uniform-'+state.get('state','entry'),uniform_upgrade_run=str(run),uniform_upgrade_worker_pid=os.getpid(),
            uniform_upgrade_worker_active=state.get('state') not in ('phase-completed','inspection-required'),
            application_RAM_restore_pending=state['original_RAM_restore_pending'],physical_reset_pending=state['physical_reset_pending'],
            block_snapshot=True,uniform_upgrade_receipt=str(out/'report.json'),native_debugging=False,RTC_drift_in_release_qualification=False)
        u.save(marker_path,marker)
    port,usb=BOARDS[a.board]
    from serial.tools.list_ports import comports
    assert sum(p.device==port and p.serial_number==usb for p in comports())==1
    u.coordination.ROOT=Q/'serial-coordination';checkpoint('entry')
    def mode(link):
        if a.board=='2604':return dict(CPU='65C02',native_debugging=False)
        observer=Q/'rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer';reference=READ(observer/'report.json')
        assert reference['passed'] and not reference['enters_native_mode'] and SHA(observer/'mode.s19')==reference['s19_sha256']
        u.board.load(link,observer/'mode.s19');link.command('G 2000');raw=link.dump(0x2440,0x244d)
        assert raw[:6]==bytes.fromhex('160100000000') and raw[6]&12==4 and raw[7:12]==bytes.fromhex('0117040116') and raw[12]&1 and not raw[12]&8 and raw[13]==0xa5
        return dict(CPU='65C816 E=1',E1_verified=True,DBR=0,PBR=0,direct_page=0,mode_hex=raw.hex(),native_debugging=False)
    def restore_original(link):
        u.board.load(link,original_backup/'capture/restore-application-ram.s19')
        for _ in range(2):assert u.board.read_range(link,0x200,0x200+len(original)-1)==original
        state.update(original_RAM_restore_pending=False,full_original_RAM_restored=True,full_original_RAM_rereads=2,original_RAM_sha256=hashlib.sha256(original).hexdigest())
    def smoke(link):
        suite=READ(kit/'smoke/scenarios.json');results={}
        for slot in ('A','B'):
            entry=0xa087 if slot=='A' else 0xb087
            assert link.dump(entry,entry+2)==bytes([0x4c,0x7b,entry>>8])
            link.write_ram(0x2000,bytes([0x78,0xd8,0x4c,entry&255,entry>>8]));link.command('G 2000')
            assert link.dump(0x7d30,0x7d30)==bytes([entry>>8])
            for case in suite['tests']:
                cells=u.board.load(link,kit/case['image'])
                for step in case['steps']:
                    prompt=b'DBG> ' if step['prompt']=='DBG' else b'\r\nB3> '
                    u.board.check(step,link.command(step['command'],prompt))
                assert link.dump(0x7bfc,0x7bff)==bytes(4)
                assert u.board.read_range(link,min(cells),max(cells))==bytes(cells[k] for k in sorted(cells))
            results[slot]=dict(passed=True,breakpoint_hits=16,smoke_cases=len(suite['tests']),C_S_N_D_M_U=True)
        preferred=READ(original_backup/'report.json')['active_page'];entry=0xa087 if preferred==0xa0 else 0xb087
        link.write_ram(0x2000,bytes([0x78,0xd8,0x4c,entry&255,entry>>8]));link.command('G 2000')
        assert link.dump(0x7d30,0x7d30)[0]==preferred
        return results
    try:
        if a.phase.startswith('stage-'):
            with u.coordination.serial_lease('rc1-uniform-'+a.phase+'-'+a.board,timeout=60):
                with (out/'serial.jsonl').open('x') as log:
                    link=u.wire.Link(port,log)
                    try:
                        u.establish_monitor(link);u.identity(link,a.board,50,require_bound_identity=True)
                        assert u.r.hashes(u.flash(link))==plan['source_sha256']
                        state['original_RAM_restore_pending']=True;checkpoint('installing-fixture')
                        def progress(n,op):state['transfers_sent']=n;checkpoint()
                        state.update(u.engine.execute(link,planroot,host_readback=True,progress=progress))
                        state['physical_reset_pending']=True;checkpoint('awaiting-physical-reset')
                        print('RESET REQUIRED:',a.board,a.phase,'device verification passed. Press physical RESET now.',flush=True)
                        if a.phase=='stage-wdc':
                            link.serial.rts=True;raw=link.stock_info_after_reset(seconds=900)
                            assert raw[:4]==(b'SXB2' if a.board=='2604' else b'SXB6')
                            expected=(planroot/'expected-b3.bin').read_bytes()
                            assert link.stock_read(0x8000,32768)==expected and link.stock_read(0x8000,32768)==expected
                            state.update(WDC_identity_hex=raw.hex(),full_B3_source_reread_twice=True,
                                lower_banks='Certified erased by exact CPU-qualified, device-verified fixture transaction; rechecked in bootstrap full-bank preflight')
                        else:
                            boot=link.until(b'\r\nB3> ',900);(out/'boot.txt').write_bytes(boot)
                            u.settle(link);u.identity(link,a.board,beta4=True)
                            assert u.r.hashes(u.flash(link))==plan['expected_sha256'];state['all_four_fixture_banks_host_verified']=True
                        state.update(passed=True,physical_reset_pending=False,source_fixture_verified=True,finished_utc=NOW())
                        checkpoint('phase-completed')
                    finally:link.serial.close()
        else:
            def actual_state(value):
                state['workflow_state']=value['phase'];state['physical_reset_pending']=value['physical_reset_pending']
                state['original_RAM_restore_pending']=True
                if value['phase']=='installing':
                    actual=out/'workflow/plan'
                    assert SHA(actual/'installer-model-only.s19')==expected_case['installer_sha256'],'Fresh actual installer differs from CPU-qualified recipe'
                    assert READ(actual/'plan.json')['transaction']==plan['transaction'],'Fresh actual transaction differs from qualified recipe'
                checkpoint('workflow-'+value['phase'])
            args=argparse.Namespace(port=port,usb_serial=usb,board=a.board,out=out/'workflow',coordination_root=Q/'serial-coordination',reset_timeout=900,
                accept_unknown_wear_history=False,history=trial/'tracked-history.json' if a.phase=='migrate-wdc' else None,metadata_escrow=trial/'private-metadata-escrow.bin')
            result=u.run(args,qualification=True,on_state=actual_state)
            assert result['passed'] and result['action']=='direct-migration'
            state['workflow_receipt_sha256']=SHA(out/'workflow/report.json');state['physical_reset_pending']=False
            with u.coordination.serial_lease('rc1-uniform-smoke-'+a.board,timeout=60):
                with (out/'smoke-serial.jsonl').open('x') as log:
                    link=u.wire.Link(port,log)
                    try:
                        u.establish_monitor(link);u.identity(link,a.board,50,require_bound_identity=True)
                        assert u.r.hashes(u.flash(link))==plan['expected_sha256']
                        state['mode_before_smoke']=mode(link);state['slots']=smoke(link);state['mode_after_smoke']=mode(link)
                        assert u.r.hashes(u.flash(link))==plan['expected_sha256']
                        restore_original(link)
                        state.update(passed=True,finished_utc=NOW(),all_four_target_banks_verified=True,settings_verified_against_plan=True)
                        checkpoint('phase-completed')
                    finally:
                        if state['original_RAM_restore_pending']:
                            try:
                                u.settle(link)
                                prompt=link.command('',b'> ')
                                if prompt.endswith(b'DBG> '):link.command('X')
                                elif prompt.endswith(b'CLOCK> '):link.command('Q')
                                else:assert prompt.endswith(b'\r\nB3> '),'Unknown context; no blind RAM restore'
                                u.establish_monitor(link);u.identity(link,a.board,50)
                                restore_original(link);checkpoint('RAM-restored-after-failure')
                            except BaseException:
                                state['restoration_failure']=traceback.format_exc();checkpoint('inspection-required')
                        link.serial.close()
        print('PASS',a.board,a.phase,'private phase only; final qualification still requires both routes/restoration',flush=True)
    except BaseException:
        state.update(passed=False,failure=traceback.format_exc(),finished_utc=NOW());checkpoint('inspection-required');raise


if __name__=='__main__':main()
