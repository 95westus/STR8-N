"""Bind completed offline bf1 recovery evidence without accessing boards."""
import argparse,hashlib,json,tomllib,time
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--process-receipt',type=Path,required=True)
    a=ap.parse_args()
    evidence={}
    for mode in ('cuts','transport','refusals'):
        path=Q/f'bf1-offline-{mode}-2026-10-17-r1/report.json'
        r=read(path)
        assert r['passed'] and r['serial_disabled'] and not r['board_access']
        assert not r['release_qualified'] and not r['installation_permitted']
        assert all(v['passed'] for v in r['checks'])
        for source,digest in r['sources'].items():assert sha(Path(source))==digest
        evidence[mode]=dict(report=str(path),sha256=sha(path),records=r['cases'],
            fresh_CPU_transactions=r['fresh_CPU_transactions'],fresh_CPU_boots=r['fresh_CPU_boots'],
            reused_boot_checks=r['reused_boot_checks'],cut_cases=r['cut_cases'],
            prior_full_trace_proofs_reused=r['prior_full_trace_proofs_reused'])
    active=read(Q/'active-rtc-campaign.json')
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    assert set(active['powered_off_boards'])=={'2205','2609'}
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,value in pin['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==value['sha256']
    for name,digest in pin['source_files'].items():assert sha(ROOT/'release/candidates/batchfix-r1'/name)==digest
    freeze=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    frozen=Path(freeze['frozen_source_directory'])/'BUILD/v2-beta35-candidate'
    for name,digest in freeze['artifact_hashes'].items():assert sha(frozen/name)==digest
    original=read(Q/'batchfix-r1-2026-10-17/status.json')
    for name,digest in original['prior_review_archives'].items():assert sha(ROOT/'output/releases'/name)==digest
    schedules={}
    for name in ('2512-powered-soak-and-rtc-drift','2512-nist-snapshot-every-three-hours'):
        s=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text())
        assert s['status']=='ACTIVE';schedules[name]=s['status']
    campaign=read(Path(active['campaign_state']))
    assert campaign['soak_board']=='2604'
    state=read(Path(campaign['soak_run'])/'status.json')
    assert state['state'] in ('running','yielding-to-drift') and time.time()-state['updated']<300
    process=read(a.process_receipt)
    assert process['ProcessId']==state['pid'] and 'run_bf1_2604_soak.py' in process['CommandLine']
    assert campaign['soak_run'].replace('\\','/') in process['CommandLine'].replace('\\','/')
    result=dict(passed=True,status='extended_offline_recovery_transport_refusal_models_passed',
        candidate_id='batchfix-r1',generation=48,observed_utc=datetime.now(timezone.utc).isoformat(),
        evidence=evidence,initial_candidate_checkpoint=str(Q/'batchfix-r1-2026-10-17/status.json'),
        initial_candidate_checkpoint_sha256=sha(Q/'batchfix-r1-2026-10-17/status.json'),
        route_checkpoint=str(Q/'bf1-2604-route-2026-10-17-r2/checkpoint.json'),
        route_checkpoint_sha256=sha(Q/'bf1-2604-route-2026-10-17-r2/checkpoint.json'),
        hardware_handoff=str(Q/'bf1-2604-hardware-2026-10-17/soak-handoff.json'),
        hardware_handoff_sha256=sha(Q/'bf1-2604-hardware-2026-10-17/soak-handoff.json'),
        baseline_sha256=active['baseline_index_sha256'],bf1_artifacts_verified=len(pin['artifacts']),
        beta35_artifacts_verified=len(freeze['artifact_hashes']),prior_review_archives_unchanged=True,
        schedules=schedules,soak_board='2604',soak_run=campaign['soak_run'],snapshot_boards=['2512','2604'],
        soak_process_receipt=str(a.process_receipt.resolve()),soak_process_receipt_sha256=sha(a.process_receipt),
        powered_off_boards=active['powered_off_boards'],deferred=['ACIA','crypto'],
        remaining=['Physical power interruption and original-payload restoration acceptance',
            'Native 816 execution where claimed', 'Long-term bf1 soak and RTC measurement accumulation',
            'Broader candidate regression/manual review and explicit release acceptance'],
        scope='Selected mutation-boundary cuts and exact CPU recovery, not every program byte or electrical timing. Prior full phase traces and identical boot states explicitly reused.',
        board_access=False,clock_trim_settings_changed=False,release_qualified=False,installation_permitted=False)
    out=Q/'bf1-offline-qualification-2026-10-17-r1/checkpoint.json'
    assert not out.exists();out.parent.mkdir(exist_ok=True)
    archived={}
    for name in ('bf1_offline_recovery_model.py','qualify_bf1_offline_recovery.py','close_bf1_offline_qualification.py'):
        source=ROOT/'tools'/name;target=out.parent/name
        assert not target.exists();target.write_bytes(source.read_bytes())
        archived[name]=dict(path=str(target),sha256=sha(target))
    result['archived_harness_sources']=archived
    publish(out,result)
    pointer=dict(candidate_id='batchfix-r1',report=str(out),report_sha256=sha(out),status=result['status'],installation_permitted=False,release_qualified=False)
    publish(Q/'bf1-offline-current.json',pointer)
    publish(Q/'batchfix-r1-current.json',pointer)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
