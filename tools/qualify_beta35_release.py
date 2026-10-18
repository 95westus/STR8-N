"""Freeze and qualify beta35 offline without changing installed/sealed builds.

Owner-local evidence only: full reference banks may contain vendor firmware.
This is not a distributable release package or a board-access tool.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tmp/b34'
BUILD=SOURCE/'BUILD/v2-beta35-candidate'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def main():
    out=ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('beta35-release-qualification-%Y-%m-%d-%H%M%SZ')
    out.mkdir()
    print('QUALIFICATION',out,flush=True)
    metadata=read(BUILD/'build.json')
    original_hash=sha(BUILD/'build.json')
    assert metadata['version']=='2.0b35' and metadata['generation']==47
    assert original_hash=='2f5319ab1d7bc751d61bc4b00af225466d83b983bc7e5806a33417940be68365'
    for name,digest in metadata['artifacts'].items():assert sha(BUILD/name)==digest,name
    receipt=read(BUILD/'beta35-qualification.json')
    assert receipt['passed'] and receipt['build_sha256']==original_hash
    for name,digest in receipt['source_sha256'].items():assert sha(SOURCE/name)==digest,name
    # The legacy WDC assembler crashes with long include/output paths.
    workspace=ROOT/'tmp'/('q35-'+datetime.now(timezone.utc).strftime('%H%M%S'))
    workspace.mkdir()
    source_hashes={}
    for folder in ('src','tools','examples','docs'):
        for p in sorted((SOURCE/folder).rglob('*')):
            if not p.is_file() or any(x in ('__pycache__','evidence','.git') for x in p.relative_to(SOURCE).parts):continue
            rel=p.relative_to(SOURCE)
            dest=workspace/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,dest);source_hashes[rel.as_posix()]=sha(dest)
    for name in ('Makefile','Makefile.beta4','README.md','LICENSE','TASKS.md','ISSUES.md'):
        if (SOURCE/name).is_file():
            shutil.copyfile(SOURCE/name,workspace/name);source_hashes[name]=sha(workspace/name)
    assert not (workspace/'src/v2.1-alpha').exists()
    for name in ('v2-beta32-candidate','v2-beta34-candidate','v2-beta35-candidate',
                 'v2-rtc-phase1','v2-rtc-phase2-split','v2-rtc-trim','v2-spi-phase2'):
        shutil.copytree(SOURCE/'BUILD'/name,workspace/'BUILD'/name)
    baseline=ROOT/'output/qualification/active-rtc-campaign.json'
    active=read(baseline)
    deps=ROOT/'BUILD/v1.30/local/test-deps/py65'
    shutil.copytree(deps,workspace/'BUILD/test-deps/py65',ignore=shutil.ignore_patterns('__pycache__'))
    save(out/'model-dependencies.json',{p.relative_to(deps).as_posix():sha(p) for p in deps.rglob('*.py')})
    freeze=dict(version='2.0b35',generation=47,build_sha256=original_hash,frozen_source_directory=str(workspace),
        source_worktree=str(SOURCE),source_git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip(),
        dirty_source_captured=True,source_files=source_hashes,
        artifact_hashes={n:sha(BUILD/n) for n in metadata['artifacts']},
        reference_bank_hashes={f'b{i}':sha(BUILD/f'candidate/b{i}.bin') for i in range(4)},
        clock='1.10',assembler='0.5',v21_excluded=True,
        deferred=['ACIA receive hardware investigation','optional crypto integration/qualification'],
        board_access=False,boards_flashed=False,powered_off_boards=['2205','2604','2609'],
        active_rtc_baseline=active['baseline_index'],active_rtc_baseline_sha256=active['baseline_index_sha256'],
        distribution_permitted=False,reference_banks_owner_local_only=True)
    save(out/'freeze.json',freeze)
    result=dict(version='2.0b35',state='running',release_qualified=False,board_access=False,
                candidate_build_sha256=original_hash,tests=[],gates={
                    'offline_regression':'running','reproducible_incremental_build':'pending',
                    'complete_clean_source_build':'pending','source_to_target_migration_matrix':'pending',
                    'ongoing_soak':'collecting','power_off_drift':'collecting; boards remain off',
                    'manuals_and_verified_examples':'pending','public_package_allowlist_and_license_audit':'pending',
                    'physical_migration_and_recovery':'pending; no powered-off board access authorized'},
                deferred=freeze['deferred'])
    save(out/'status.json',result)
    # Version-specific adapters retain historical tests and change only their
    # candidate/version selectors and the deliberately changed VERSION asset.
    integration=(workspace/'tools/test_v2_beta34.py').read_text().replace('beta34','beta35').replace('2.0b34','2.0b35')
    integration=integration.replace('[0x5800:]','[0x5800:0x7800]')
    (workspace/'tools/qa_beta35_integration.py').write_text(integration)
    batch=(workspace/'tools/test_v2_beta34_batch.py').read_text().replace('2.0b34','2.0b35').replace('beta34-batch.json','beta35-batch.json')
    (workspace/'tools/qa_beta35_batch.py').write_text(batch)
    summary=(workspace/'tools/test_v2_clock_summary.py').read_text().replace("b'CLOCK 1.8'","b'CLOCK 1.10'")
    (workspace/'tools/qa_beta35_clock_summary.py').write_text(summary)
    recovery=(workspace/'tools/test_v2_beta23_fixed_recovery.py').read_text()
    recovery=recovery.replace("        cpu,m=fresh(primary=layout());m.rx.extend(b'S');before=snapshot(m);boot(cpu)",
        "        cpu,m=fresh(primary=layout());before=snapshot(m)\n"
        "        sent=[False]\n"
        "        def during_window(cpu):\n"
        "            if not sent[0] and cpu.pc==META['boot']['BOOT_RECOVERY_WINDOW']:\n"
        "                m.rx.extend(b'S');sent[0]=True\n"
        "            return False\n"
        "        boot(cpu,hook=during_window)\n"
        "        assert sent[0], 'Recovery key must follow cold RX flush'")
    recovery=recovery.replace("b'RTCC: UTC' in cmd(cpu,m,b'TIME\\r')", "b'2026-10-08 19:53:15 (+00:00)' in cmd(cpu,m,b'TIME\\r')")
    recovery=recovery.replace('fixed-recovery-test-results.json','qa-beta35-fixed-recovery.json')
    (workspace/'tools/qa_beta35_fixed_recovery.py').write_text(recovery)
    rebuild='''import json\nfrom pathlib import Path\nimport build_v2_beta35 as b\nbase=b.OUT\nb.OUT=b.ROOT/'BUILD/qa-beta35-independent'\nb.main()\nnames=list(json.loads((base/'build.json').read_text())['artifacts'])+['build.json','clock/build.json','pf-worker/build.json']+[f'candidate/b{i}.bin' for i in range(4)]\nfor n in names:assert (base/n).read_bytes()==(b.OUT/n).read_bytes(),n\nprint('PASS',len(names),'independent incremental rebuild files identical')\n'''
    (workspace/'tools/qa_beta35_rebuild.py').write_text(rebuild)
    save(out/'adapters.json',{p.name:sha(p) for p in (workspace/'tools').glob('qa_beta35_*.py')})
    env=os.environ.copy();env.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'))
    tests=['qa_beta35_rebuild.py','test_v2_beta35.py','test_asm.py','qa_beta35_integration.py',
           'qa_beta35_batch.py','qa_beta35_clock_summary.py','qa_beta35_fixed_recovery.py']
    for name in tests:
        print('RUN',name,flush=True)
        log=out/(name+'.log')
        with log.open('w') as f:
            try:
                p=subprocess.run([sys.executable,str(workspace/'tools'/name)],cwd=workspace,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
                item=dict(name=name,passed=p.returncode==0,exit_code=p.returncode,log=str(log),log_sha256=sha(log))
            except subprocess.TimeoutExpired:
                item=dict(name=name,passed=False,error='Timed out at 1200 seconds',log=str(log))
        result['tests'].append(item);save(out/'status.json',result)
        print('PASS' if item['passed'] else 'FAIL',name,flush=True)
    assert sha(BUILD/'build.json')==original_hash,'Sealed candidate changed during qualification'
    for name,digest in freeze['artifact_hashes'].items():assert sha(BUILD/name)==digest,name
    assert read(baseline)['baseline_index_sha256']==freeze['active_rtc_baseline_sha256']
    result['gates']['reproducible_incremental_build']='passed' if result['tests'][0]['passed'] else 'failed'
    result['gates']['offline_regression']='passed' if all(t['passed'] for t in result['tests']) else 'failures require review'
    result.update(state='offline-checks-complete',sealed_candidate_unchanged=True,rtc_baseline_unchanged=True,
        completed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False)
    save(out/'status.json',result)
    print('RESULT',out/'status.json',flush=True)

if __name__=='__main__':main()
