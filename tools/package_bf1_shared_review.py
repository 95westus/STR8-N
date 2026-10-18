"""Build a new shared-CPU review kit from sealed r2 plus explicit updates."""
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    archive=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r3.zip'
    kit=ROOT/'tmp/bf1k3';out=Q/'bf1-review-gate-2026-10-17-r3'
    assert not archive.exists() and not kit.exists() and not out.exists()
    prior=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r2.zip'
    assert sha(prior.read_bytes())=='042500224adf7fa68aac1057192512eca539cac06b238457b9eea5b77402993b'
    hp=Q/'bf1-2609-hardware-current.json';pointer=read(hp);cp=Path(pointer['checkpoint'])
    assert sha(cp.read_bytes())==pointer['checkpoint_sha256'];hardware=read(cp)
    assert hardware['passed'] and hardware['one_firmware_set']
    out.mkdir();route=Q/'bf1-2609-route-2026-10-17-r1';model=read(route/'report.json')
    assert model['passed'] and model['cases']==28
    for name,digest in model['sources'].items():assert sha(Path(name).read_bytes())==digest
    stages=[];previous=read(Q/'bf1-2609-hardware-2026-10-17/A-checks/report.json')['expected_hashes']
    for name in ('restore-A40-retain-Bbf1','restore-original-B35-complete'):
        folder=route/name;plan=read(folder/'plan.json');assert previous==plan['source_sha256']
        assert sha((folder/'installer-model-only.s19').read_bytes())==plan['installer_sha256']
        for i,digest in enumerate(plan['transfer_sha256']):assert sha((folder/f'transfer-{i:02d}.bin').read_bytes())==digest
        stages.append(dict(case=name,plan_sha256=sha((folder/'plan.json').read_bytes()),
                           installer_sha256=plan['installer_sha256'],source_sha256=plan['source_sha256'],
                           expected_sha256=plan['expected_sha256'],transfer_sha256=plan['transfer_sha256']))
        previous=plan['expected_sha256']
    readiness=dict(passed=True,status='offline_readiness_only_physical_gate_pending',board='2609',
                   current_hardware_checkpoint_sha256=sha(cp.read_bytes()),model_report_sha256=sha((route/'report.json').read_bytes()),
                   exact_clean_restoration_chain_admits_registered_post_install_state=True,stages=stages,
                   required_fresh_live_backup_and_preimage_admission=True,cut_state_replanning_required=True,
                   physical_interruption_performed=False,live_restoration_performed=False,board_access=False,
                   clocks_trims_changed=False,installation_permitted=False,release_qualified=False,
                   proposed_physical_board='2609; coordinated owner session required',
                   keep_soak_board='2604',powered_off_boards=['2205'])
    (out/'recovery-gate-readiness.json').write_text(json.dumps(readiness,indent=2)+'\n')
    with zipfile.ZipFile(prior) as z:files={n:z.read(n) for n in z.namelist() if n not in ('review-manifest.json','review-allowlist.json')}
    changes={}
    def add(name,path):
        data=path.read_bytes()
        if name not in files or files[name]!=data:changes[name]=sha(data)
        files[name]=data
    for name in ('README.md','REMAINING_GATES.md','NEXT_GATE.md','verify_review.py'):
        add(name,ROOT/'release/bf1-prerelease/review-shared'/name)
    add('release/bf1-prerelease/acceptance-scope.json',ROOT/'release/bf1-prerelease/shared-cpu-scope.json')
    for path in (ROOT/'docs/bf1').glob('*.md'):add('docs/bf1/'+path.name,path)
    add('docs/STR8N_BF1_2609_INSTALL_RECOVERY.md',ROOT/'docs/STR8N_BF1_2609_INSTALL_RECOVERY.md')
    add('evidence/shared-cpu-acceptance.json',cp)
    h=cp.parent;add('evidence/shared-firmware-preflight.json',h/'shared-firmware-preflight.json')
    for phase in ('B','A'):
        add(f'evidence/2609-{phase}-report.json',h/(phase+'-checks/report.json'))
        add(f'evidence/2609-{phase}-reset.json',h/(phase+'-reset-confirmation.json'))
    add('evidence/2604-A-report.json',Q/'bf1-2604-hardware-2026-10-17/A-checks/report.json')
    add('evidence/recovery-gate-readiness.json',out/'recovery-gate-readiness.json')
    summary=json.loads(files['review-evidence-summary.json']);summary.update(
        processor_execution_scope='65C02 and 65C816 emulation-mode runtime',
        shared_hardware=dict(board_65C02='2604',board_65C816='2609',same_firmware_set=True,
                             groups_2609_per_slot=12,emulation_observations=14,receipt='evidence/shared-cpu-acceptance.json'),
        manual_revision='CPU scope, hardware evidence and campaign prose updated. Prior 26 W65C02 model/ABI/example checks explicitly reused; no new native 816 model tests claimed.',
        next_gate='Physical electrical interruption/original restoration; offline readiness only',
        startup_detection_exception='Owner accepted unchanged brief native-mode CPU detection before E=1 runtime')
    files['review-evidence-summary.json']=(json.dumps(summary,indent=2)+'\n').encode()
    files['review-allowlist.json']=(json.dumps(sorted([*files,'review-allowlist.json']),indent=2)+'\n').encode()
    manifest=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,installation_permitted=False,
                  release_qualified=False,publication_permitted=False,deferred=['native 816','ACIA','crypto'],
                  files={n:dict(bytes=len(v),sha256=sha(v)) for n,v in sorted(files.items())})
    files['review-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(archive,'x') as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,17,0,0,0));info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and z.testzip() is None;z.extractall(kit)
    result=subprocess.run([sys.executable,'-B',str(kit/'verify_review.py'),str(kit)],capture_output=True,text=True)
    receipt=dict(verified=result.returncode==0,archive=str(archive.resolve()),archive_sha256=sha(archive.read_bytes()),
                 archive_bytes=archive.stat().st_size,files=len(files),extraction=str(kit.resolve()),
                 previous_archive_sha256=sha(prior.read_bytes()),changed_or_added=changes,
                 shared_hardware_checkpoint_sha256=sha(cp.read_bytes()),
                 stdout=result.stdout,stderr=result.stderr,board_access=False,
                 created_utc=datetime.now(timezone.utc).isoformat(),packager_sha256=sha(Path(__file__).read_bytes()))
    archive.with_suffix('.package.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert result.returncode==0,(result.stdout,result.stderr)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
