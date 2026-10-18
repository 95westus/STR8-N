"""Read-only evidence audit for the campaign's designated continuous soak."""
import argparse,hashlib,json,re,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path);ap.add_argument('--minimum-units',type=int,default=1);a=ap.parse_args()
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');campaign=read(Path(active['campaign_state']));run=a.run or Path(campaign['soak_run']);status=read(run/'status.json');board=status['board'];assert board in ('2512','2604') and board not in active['powered_off_boards']
    assert status['state'] in ('running','yielding-to-drift') and time.time()-status['updated']<300
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==status['baseline_sha256']
    restore=read(run/'restore-needed.json');assert restore['needed'] is True and sha(run/'application-ram-original.bin')==restore['sha256']
    runner=ROOT/'tools'/('run_bf1_2604_soak.py' if board=='2604' else 'run_v2_beta35_soak.py');assert sha(runner)==status['runner_sha256'];assert sha(ROOT/'tools/soak_led_patterns.py')==status['led_patterns_sha256']
    if board=='2604':
      assert sha(ROOT/'tools/bf1_2604_readonly.py')==status['adapter_sha256'];assert sha(Path(status['hardware_report']))==status['hardware_report_sha256']
      for archive in run.glob('source-*.py'):assert sha(ROOT/'tools'/archive.name[7:])==sha(archive)
      assert sha(run/'sram-original.bin')==status['sram_reference_sha256']
      assert sha(run/'legacy-reference/retained/devices-after/eeprom-0.bin')==status['eeprom_reference_sha256']
    units=[]
    for p in sorted(run.glob('*/report.json')):
        match=re.fullmatch(r'(\d{6})-(.+)',p.parent.name)
        if match:
            r=read(p);assert r['passed'];units.append((int(match[1]),match[2],r))
    for i,(n,group,r) in enumerate(units):
        assert n==i and group==status['groups'][i%len(status['groups'])]
        if group=='led':assert r['result']['original_led_restored']
    assert len(units)>=max(a.minimum_units,status['passed_units'])
    assert len(units)//len(status['groups'])>=status['completed_cycles'];assert not Path(str(run)+'.stderr.log').read_text().strip()
    samples={}
    sample_boards=tuple(campaign.get('snapshot_boards',['2512','2604']))
    for p in (ROOT/'output/qualification').glob('rtc-campaign-snapshot-*/summary.json'):
        s=read(p)
        if not s.get('passed'):continue
        for b in s['boards']:
            if b['board'] not in sample_boards:continue
            if b['board'] not in samples or b['reference_utc']>samples[b['board']]['reference_utc']:
                assert s['ports_released'] and b['application_ram_restored'] and sha(Path(b['report']))==b['report_sha256'];samples[b['board']]=dict(reference_utc=b['reference_utc'],summary=str(p))
    now=datetime.now(timezone.utc)
    for b in sample_boards:
        age=(now-datetime.fromisoformat(samples[b]['reference_utc'].replace('Z','+00:00'))).total_seconds();assert 0<=age<14400;samples[b]['age_seconds']=age
    result=dict(passed=True,observed_utc=now.isoformat(),board=board,run=str(run.resolve()),pid=status['pid'],state=status['state'],actual_passed_unit_reports=len(units),completed_cycles=len(units)//len(status['groups']),units_per_cycle=len(status['groups']),led_passed_units=sum(g=='led' for _,g,_ in units),latest_samples=samples,application_ram_restore_marker_expected_while_running=True,baseline_sha256=active['baseline_index_sha256'],serial_access=False,worker_modified=False,clock_trim_settings_changed=False,pid_command_requires_independent_process_query=True)
    out=ROOT/'output/qualification'/('powered-soak-evidence-'+board+'-'+now.strftime('%Y-%m-%d-%H%M%SZ')+'.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(receipt=str(out),**result)))
if __name__=='__main__':main()
