"""Receipt-bound closure of the owner-authorized 2512 -> 2604 soak handoff."""
import argparse,hashlib,json,re,time,tomllib
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def units(run,state):
    rows=[]
    for p in sorted(run.glob('*/report.json')):
        m=re.fullmatch(r'(\d{6})-(.+)',p.parent.name)
        if m:
            r=read(p);assert r['passed'];rows.append((int(m[1]),m[2],r))
    for i,(n,g,r) in enumerate(rows):
        assert i==n and g==state['groups'][i%len(state['groups'])]
        if g=='led':assert r['result']['original_led_restored']
    assert len(rows)>=state['passed_units'];return rows
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--old-run',type=Path,required=True);ap.add_argument('--new-run',type=Path,required=True);ap.add_argument('--process-receipt',type=Path,required=True);a=ap.parse_args()
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');sp=Path(active['campaign_state']);campaign=read(sp);old=read(a.old_run/'status.json');new=read(a.new_run/'status.json');oldrestore=read(a.old_run/'restore-needed.json');newrestore=read(a.new_run/'restore-needed.json')
    assert old['board']=='2512' and old['state']=='stopped-by-request' and old['application_ram_restored'] and not oldrestore['needed'] and oldrestore['verified']
    assert sha(a.old_run/'application-ram-original.bin')==oldrestore['sha256'] and (a.old_run/'STOP').exists()
    assert new['board']=='2604' and new['state'] in ('running','yielding-to-drift') and new['active_page']==0xa0 and time.time()-new['updated']<300 and newrestore['needed']
    assert sha(a.new_run/'application-ram-original.bin')==newrestore['sha256']
    process=read(a.process_receipt);assert process['old_pid']==old['pid'] and process['old_process_absent'] and process['new_pid']==new['pid'] and 'run_bf1_2604_soak.py' in process['new_command_line'] and str(a.new_run.resolve()).replace('\\','/') in process['new_command_line'].replace('\\','/')
    before=units(a.old_run,old);after=units(a.new_run,new);assert len(after)>=3
    assert not Path(str(a.new_run)+'.stderr.log').read_text().strip() and not Path(str(a.old_run)+'.stderr.log').read_text().strip()
    assert sha(ROOT/'tools/run_bf1_2604_soak.py')==new['runner_sha256'] and sha(ROOT/'tools/bf1_2604_readonly.py')==new['adapter_sha256']
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==new['baseline_sha256']==old['baseline_sha256'] and set(active['powered_off_boards'])=={'2205','2609'}
    hardware=ROOT/'output/qualification/bf1-2604-hardware-2026-10-17';proofs={}
    for phase in ('A','B'):
        rp=hardware/(phase+'-checks/report.json');r=read(rp);assert r['passed'] and r['initial_checks_passed'] and r['full_flash_verified'] and r['application_ram_restored'];assert not read(rp.parent/'restore-needed.json')['needed'];proofs[phase]=dict(report=str(rp),sha256=sha(rp),checks=len(r['checks']))
    assert sha(Path(new['hardware_report']))==new['hardware_report_sha256']==proofs['A']['sha256']
    for name in ['2512-powered-soak-and-rtc-drift','2512-nist-snapshot-every-three-hours']:
        config=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text());assert config['status']=='ACTIVE'
    observed=datetime.now(timezone.utc).isoformat();result=dict(passed=True,observed_utc=observed,status='2604_bf1_soak_running_2512_workload_stopped_RTC_on_both',initial_hardware_checks=proofs,new_soak=dict(board='2604',candidate_id='batchfix-r1',run=str(a.new_run.resolve()),pid=new['pid'],actual_passed_units=len(after),completed_cycles=len(after)//len(new['groups']),units_per_cycle=len(new['groups']),active_page=160,hardware_report_sha256=new['hardware_report_sha256']),prior_soak=dict(board='2512',run=str(a.old_run.resolve()),pid=old['pid'],actual_passed_units=len(before),completed_cycles=len(before)//len(old['groups']),units_per_cycle=len(old['groups']),state=old['state'],application_ram_restored=True,restored_ram_sha256=oldrestore['sha256'],process_absent=True,board_stays_powered_on=True),process_receipt_sha256=sha(a.process_receipt),snapshot_boards=['2512','2604'],original_baseline_sha256=active['baseline_index_sha256'],clock_trim_settings_changed_by_soaks=False,powered_off_boards=active['powered_off_boards'],deferred=['ACIA','crypto'],release_qualified=False,physical_interruption_and_full_release_acceptance_pending=True)
    cp=hardware/'soak-handoff.json';assert not cp.exists();publish(cp,result)
    historical=campaign.setdefault('previous_soak_runs',[])
    if str(a.old_run.resolve()) not in historical:historical.append(str(a.old_run.resolve()))
    campaign.setdefault('soak_handoffs',[]).append(dict(utc=observed,prior_board='2512',new_board='2604',prior_run=str(a.old_run.resolve()),new_run=str(a.new_run.resolve()),prior_passed_units=len(before),prior_completed_cycles=len(before)//len(old['groups']),prior_ram_restored=True,reason='Owner-authorized bf1 hardware acceptance and soak handoff',checkpoint=str(cp)))
    campaign.update(soak_board='2604',soak_run=str(a.new_run.resolve()),soak_runner='tools/run_bf1_2604_soak.py',snapshot_boards=['2512','2604'],soak_handoff=dict(state='complete',checkpoint=str(cp),checkpoint_sha256=sha(cp)),**{'2512_role':'Powered-on RTC drift only; workload soak stopped by owner request','2604_role':'bf1 preserving powered soak and RTC drift','2604_bf1_hardware_state':'initial_checks_passed_soak_running','2604_bf1_hardware_checkpoint':str(cp)})
    publish(sp,campaign);publish(ROOT/'output/qualification/bf1-2604-hardware-current.json',dict(checkpoint=str(cp),checkpoint_sha256=sha(cp)));publish(ROOT/'output/qualification/device-operations/2604.json',dict(board='2604',state='soak-running',run=str(a.new_run.resolve()),hardware_checkpoint=str(cp),block_snapshot=False))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
