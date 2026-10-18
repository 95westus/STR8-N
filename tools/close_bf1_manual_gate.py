"""Close bf1 manual/ABI gate using fresh CPU evidence and final editorial audit."""
import argparse,hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();report=a.audit/'report.json';r=read(report)
    assert r['passed'] and r['candidate_id']=='batchfix-r1' and r['serial_disabled'] and not r['board_access']
    assert sha(ROOT/'tools/audit_bf1_manual_abi.py')==r['test_sha256']
    assert all(v['passed'] for v in r['checks']) and r['persistent_model_devices_unchanged']
    assert sha(Path(r['source_route_report']))==r['source_route_report_sha256']
    for path,digest in r['source_references'].items():assert sha(ROOT/path)==digest
    a.out.mkdir(parents=True,exist_ok=False);links=[];docs={}
    original=a.out/'cpu-audit-documents';original.mkdir()
    for name,digest in r['documents'].items():
        source=ROOT/'docs/bf1'/name
        assert sha(source)==digest
        (original/name).write_bytes(source.read_bytes())
    # Editorial corrections do not alter any runtime test, source or example.
    # Archive the exact CPU-audit drafts above and bind final prose separately.
    changes={}
    for source in (ROOT/'docs/bf1').glob('*.md'):
        text=source.read_text(encoding='utf-8');prior=text
        text=text.replace('bf1 adds an **estimated outage duration**','bf1 retains beta35’s **estimated outage duration**')
        text=text.replace('bf1 duration formatting','The inherited duration formatting').replace("bf1's shared",'The inherited shared')
        text=text.replace('RTI. Publish a native NMI pointer', 'RTI. These native-interrupt details are descriptive and unqualified; native\n816 is deferred. The architectural contract says to publish a native NMI pointer')
        source.write_text(text,encoding='utf-8')
        if text!=prior:changes[source.name]=dict(before_sha256=r['documents'][source.name],after_sha256=sha(source),scope='Prose-only inheritance/deferral clarification; example source unchanged')
        assert 'generation 47' not in text and 'CLOCK 1.10' not in text
        assert 'Native 816' in text or 'native 816' in text
        for target in re.findall(r'\]\(([^)]+)\)',text):
            assert not re.match(r'[a-z]+:',target)
            assert (source.parent/target.split('#')[0]).is_file(),(source,target)
            links.append([source.name,target])
        docs[source.name]=sha(source)
    before=(original/'ASM_GUIDE.md').read_text(encoding='utf-8')
    after=(ROOT/'docs/bf1/ASM_GUIDE.md').read_text(encoding='utf-8')
    assert re.search(r'```asm\n(.*?)```',before,re.S).group(1)==re.search(r'```asm\n(.*?)```',after,re.S).group(1)
    policy_path=ROOT/'release/bf1-prerelease/acceptance-scope.json';policy=read(policy_path)
    assert policy['processor_execution_scope']=='W65C02' and set(policy['deferred'])=={'native 816','ACIA','crypto'}
    assert not policy['release_qualified'] and not policy['installation_permitted']
    policy['completed_gates']=['Version-correct bf1 drafts and fresh W65C02 manual/ABI/example regression']
    policy['next_offline_gate']='Candidate-specific local review package and integrity audit'
    publish(policy_path,policy)
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,value in pin['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==value['sha256']
    for name,digest in pin['source_files'].items():assert sha(ROOT/'release/candidates/batchfix-r1'/name)==digest
    prior_pointer=read(Q/'bf1-offline-current.json');prior_checkpoint=Path(prior_pointer['report'])
    assert sha(prior_checkpoint)==prior_pointer['report_sha256']
    cp=read(prior_checkpoint)
    active=read(Q/'active-rtc-campaign.json')
    assert sha(Path(active['baseline_index']))==cp['baseline_sha256']==active['baseline_index_sha256']
    for name,digest in read(Q/'batchfix-r1-2026-10-17/status.json')['prior_review_archives'].items():assert sha(ROOT/'output/releases'/name)==digest
    archive=a.out/'final-documents';archive.mkdir()
    for name in docs:(archive/name).write_bytes((ROOT/'docs/bf1'/name).read_bytes())
    for name in ('audit_bf1_manual_abi.py','close_bf1_manual_gate.py'):(a.out/name).write_bytes((ROOT/'tools'/name).read_bytes())
    (a.out/'acceptance-scope.json').write_bytes(policy_path.read_bytes())
    result=dict(passed=True,candidate_id='batchfix-r1',generation=48,status='manual_ABI_example_gate_passed_native816_deferred',
        observed_utc=datetime.now(timezone.utc).isoformat(),model_report=str(report.resolve()),model_report_sha256=sha(report),
        fresh_audit_checks=r['cases'],runtime_evidence_reused_from_earlier_candidates=False,
        documents=docs,local_links=len(links),editorial_changes_after_CPU_audit=changes,examples_unchanged=True,
        acceptance_policy=str(policy_path),acceptance_policy_sha256=sha(policy_path),deferred=policy['deferred'],
        processor_execution_scope='W65C02',remaining=policy['remaining_gates'],next_offline_gate=policy['next_offline_gate'],
        recovery_checkpoint=str(prior_checkpoint),recovery_checkpoint_sha256=sha(prior_checkpoint),
        baseline_sha256=active['baseline_index_sha256'],bf1_artifacts_verified=len(pin['artifacts']),prior_review_archives_unchanged=True,
        board_access=False,clock_trim_settings_changed=False,release_qualified=False,installation_permitted=False)
    publish(a.out/'checkpoint.json',result)
    manifest={p.relative_to(a.out).as_posix():sha(p) for p in a.out.rglob('*') if p.is_file()}
    publish(a.out/'manifest.json',dict(files=manifest))
    publish(Q/'batchfix-r1-current.json',dict(candidate_id='batchfix-r1',report=str((a.out/'checkpoint.json').resolve()),report_sha256=sha(a.out/'checkpoint.json'),status=result['status'],installation_permitted=False,release_qualified=False))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
