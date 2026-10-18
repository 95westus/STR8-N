"""Create an explicit, owner-local bf1 review ZIP and verify its extraction."""
import argparse,hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--extract',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists() and not a.extract.exists()
    cp_path=Q/'bf1-manual-gate-2026-10-17-r1/checkpoint.json';cp=read(cp_path);assert cp['passed']
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json');build=read(ROOT/'tmp/bfx5/build-report.json')
    assert sha((ROOT/'tmp/bfx5/build-report.json').read_bytes())==pin['build_report_sha256']
    candidate=ROOT/'release/candidates/batchfix-r1';files={}
    def add(name,path):assert name not in files;files[name]=path.read_bytes()
    base='release/candidates/batchfix-r1/'
    for name in ('README.md','build.py','release.json','source-provenance.json','derivation.json'):add(base+name,candidate/name)
    for name,digest in pin['source_files'].items():
        assert sha((candidate/name).read_bytes())==digest;add(base+name,candidate/name)
    for name,info in pin['artifacts'].items():
        path=ROOT/'tmp/bfx5/payload'/name;assert dict(bytes=path.stat().st_size,sha256=sha(path.read_bytes()))==info;add(base+'payload/'+name,path)
    for name,digest in cp['documents'].items():
        path=ROOT/'docs/bf1'/name;assert sha(path.read_bytes())==digest;add('docs/bf1/'+name,path)
    for name in ('STR8N_V2_BATCHFIX_R1.md','STR8N_BF1_2604_INSTALL_RECOVERY.md'):add('docs/'+name,ROOT/'docs'/name)
    policy=ROOT/'release/bf1-prerelease/acceptance-scope.json';assert sha(policy.read_bytes())==cp['acceptance_policy_sha256'];add('release/bf1-prerelease/acceptance-scope.json',policy)
    for name in ('README.md','REMAINING_GATES.md','verify_review.py','build_helper.py'):add(name,ROOT/'release/bf1-prerelease/review'/name)
    helper=read(ROOT/'tmp/bfr2/build-report.json');hfiles={}
    for name,path in [('reservation.asm',ROOT/'release/candidates/batchfix-route-r1/source/reservation.asm'),('str8n-v2-eq.inc',candidate/'source/migration/str8n-v2-eq.inc'),('reservation-links.inc',ROOT/'tmp/bfr2/asm/reservation-links.inc')]:
        hfiles[name]=sha(path.read_bytes());add('release/candidates/batchfix-route-r1/source/'+name,path)
    assert hfiles['reservation.asm']==helper['source_sha256'] and hfiles['str8n-v2-eq.inc']==helper['eq_sha256']
    example=Q/'bf1-manual-abi-2026-10-17-r1'
    for slot in ('A','B'):add('examples/'+slot+'-example.s19',example/(slot+'-example.s19'))
    files['examples/asm-print-a.bin']=bytes.fromhex('78d8a941206d7e4c677e')
    files['examples/asm-print-a.numbered.txt']=re.search(r'```asm\n(.*?)```',(ROOT/'docs/bf1/ASM_GUIDE.md').read_text(encoding='utf-8'),re.S).group(1).encode()
    summary=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,clock_version='1.11',processor_execution_scope='W65C02',deferred=['native 816','ACIA','crypto'],installation_permitted=False,release_qualified=False,publication_permitted=False,
        manual_abi=dict(fresh_checks=26,checkpoint_sha256=sha(cp_path.read_bytes()),CPU_report_sha256=cp['model_report_sha256'],both_slot_examples_fresh=True),
        recovery_models=dict(selected_cut_states=49,fresh_CPU_transactions=93,fresh_CPU_boots=64,identical_input_boot_checks_reused=34,transport_CPU_tests=42,planner_replay_refusals=27,checkpoint_sha256=cp['recovery_checkpoint_sha256']),
        prior_source_reproduction=dict(independent_builds=2,links_per_build=27,identical_artifacts=19),
        initial_hardware=dict(slots=['B','A'],groups_per_slot=11,physical_reset_owner_confirmed=True,physical_interruption_qualified=False),
        extracted_build_and_package_audit='Fresh extraction/build/refusal outcomes are recorded in the separate ZIP receipt, not inferred from these prior results.',
        caveat='Selected model boundaries do not cover every programming byte or electrical timing. No generic migration route or release permission.')
    objects={'review-evidence-summary.json':summary,'reference-build.json':dict(candidate_id='batchfix-r1',generation=48,builder_sha256=build['build_script_sha256'],release_manifest_sha256=build['release_manifest_sha256'],source_files=pin['source_files'],artifacts=pin['artifacts']),
        'helper-reference.json':dict(entry=0x3000,bytes=helper['bytes'],binary_sha256=helper['binary_sha256'],source_files=hfiles,links=helper['links'])}
    for name,obj in objects.items():files[name]=(json.dumps(obj,indent=2)+'\n').encode()
    files['review-allowlist.json']=(json.dumps(sorted([*files,'review-allowlist.json']),indent=2)+'\n').encode()
    manifest=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,installation_permitted=False,release_qualified=False,publication_permitted=False,deferred=['native 816','ACIA','crypto'],files={n:dict(bytes=len(v),sha256=sha(v)) for n,v in sorted(files.items())})
    files['review-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.out,'x') as z:
        for name,data in sorted(files.items()):
            i=zipfile.ZipInfo(name,(2026,10,17,0,0,0));i.external_attr=0o100644<<16;z.writestr(i,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(a.out) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(files) and z.testzip() is None;z.extractall(a.extract)
    r=subprocess.run([sys.executable,'-B',str(a.extract/'verify_review.py'),str(a.extract)],capture_output=True,text=True)
    receipt=dict(archive=str(a.out.resolve()),archive_sha256=sha(a.out.read_bytes()),archive_bytes=a.out.stat().st_size,extraction=str(a.extract.resolve()),packager_sha256=sha(Path(__file__).read_bytes()),manual_checkpoint_sha256=sha(cp_path.read_bytes()),verified=r.returncode==0,stdout=r.stdout,stderr=r.stderr,created_utc=datetime.now(timezone.utc).isoformat(),board_access=False)
    a.out.with_suffix('.package.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert r.returncode==0,(r.stdout,r.stderr);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
