"""Verify owner-requested soak shutdown and retain unqualified actual evidence."""
import hashlib,json,re,subprocess
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    active=read(Q/'active-rtc-campaign.json');state_path=Path(active['campaign_state']);campaign=read(state_path)
    run=Path(campaign['soak_run']);s=read(run/'status.json');restore=read(run/'restore-needed.json')
    request=run/'owner-stop-request-2026-10-18.json';owner=read(request)
    assert campaign['soak_board']==s['board']==owner['board']=='2604'
    assert s['state']=='stopped-by-request' and owner['owner_authorized'] and owner['worker_pid']==s['pid']
    assert s['application_ram_restored'] and not restore['needed'] and restore['verified']
    assert sha(run/'application-ram-original.bin')==restore['sha256']
    assert sha(ROOT/'tools/run_bf1_2604_soak.py')==s['runner_sha256'] and (run/'STOP').exists()
    assert not Path(str(run)+'.stderr.log').read_text().strip()
    command=f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(s['pid'])}' | Select-Object ProcessId,CommandLine | ConvertTo-Json"
    result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,check=True)
    assert not result.stdout.strip(),'Worker still exists; wait for restoration/exit'
    units=[]
    for path in sorted(run.glob('*/report.json')):
        match=re.fullmatch(r'(\d{6})-(.+)',path.parent.name)
        if not match:continue
        r=read(path);assert r['passed']
        assert int(match[1])==len(units) and match[2]==s['groups'][len(units)%34]
        if match[2]=='led':assert r['result']['original_led_restored']
        units.append(path)
    assert len(units)==s['passed_units'] and len(s['groups'])==34
    end=datetime.fromtimestamp(s['updated'],timezone.utc)
    hours=(end-datetime.fromisoformat(s['started_utc'])).total_seconds()/3600
    receipt=run/'owner-stop-verified-2026-10-18.json';assert not receipt.exists()
    checkpoint=dict(passed=True,board='2604',worker_pid=s['pid'],owner_authorized=True,
        owner_instruction=owner['owner_instruction'],request=str(request),request_sha256=sha(request),
        safe_stop=True,original_RAM_verified=True,restored_RAM_sha256=restore['sha256'],
        process_exited=True,monitored_end_utc=end.isoformat(),finished_utc=datetime.now(timezone.utc).isoformat(),
        actual_passed_units=len(units),complete_cycles=len(units)//34,units_per_cycle=34,
        monitored_hours=hours,no_acceptance_pass_inferred=True,RTC_sampling_continues=True,
        clock_trim_changes=False,powered_off_boards=active['powered_off_boards'],
        status_sha256=sha(run/'status.json'),restore_receipt_sha256=sha(run/'restore-needed.json'))
    publish(receipt,checkpoint)
    policy_pointer=Q/'bf1-acceptance-policy-current.json';prior=read(policy_pointer);policy=read(Path(prior['policy']))
    assert sha(Path(prior['policy']))==prior['sha256']
    policy['soaks']['2604'].update(owner_requested_stop=True,owner_stop_receipt=str(receipt),
        owner_stop_receipt_sha256=sha(receipt),automatic_restart_permitted=False,continue_after_gate=False)
    policy.update(supersedes_policy_sha256=prior['sha256'],amended_utc=checkpoint['finished_utc'],
        amendment='Owner stopped 2604 soak. Verify safe stop, original application RAM restoration and process exit; retain actual counts without a 72-hour/300-cycle pass or waiver. RTC sampling remains on 2604/2609; neither workload restarts automatically. Other gates unchanged.')
    next_policy=Q/'bf1-acceptance-policy-2026-10-18-r8.json';assert not next_policy.exists();publish(next_policy,policy)
    publish(policy_pointer,dict(policy=str(next_policy),sha256=sha(next_policy)))
    campaign.update(soak_active=False,soak_state='owner-stopped-RAM-restored',
        soak_stop_request=dict(board='2604',state='complete',receipt=str(receipt),sha256=sha(receipt),no_restart=True,RTC_sampling_continues=True),
        **{'2604_role':'Powered-on RTC drift only; workload soak stopped by owner request'})
    publish(state_path,campaign)
    guard_path=Q/'device-operations/2604.json';guard=read(guard_path)
    guard.update(state='RTC-only-owner-stopped-soak',block_snapshot=False,soak_stop_checkpoint=str(receipt),
        application_RAM_restore_verified=True,no_workload_restart=True)
    publish(guard_path,guard)
    work_path=Q/'bf1-distribution-work-state.json';work=read(work_path)
    work.update(soak_2604_status='Owner-stopped; original RAM verified restored; RTC sampling continues',
        soak_2604_stop_checkpoint=str(receipt));publish(work_path,work)
    plan_path=Q/'bf1-tonight-publication-plan.json';plan=read(plan_path)
    plan['tools']['check_bf1_acceptance.py']=sha(ROOT/'tools/check_bf1_acceptance.py')
    plan.update(acceptance_policy_revision='r8',acceptance_policy_sha256=sha(next_policy),
        owner_stopped_2604=True,soak_2604_stop_checkpoint=str(receipt),publication_hold=True)
    publish(plan_path,plan)
    print(json.dumps(checkpoint,indent=2))

if __name__=='__main__':main()
