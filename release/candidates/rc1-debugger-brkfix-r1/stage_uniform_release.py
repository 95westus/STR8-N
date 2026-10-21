"""Derive immutable r9 after both-board uniform-upgrade closure; no board access."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];Q=ROOT/'output/qualification'
BASE=ROOT/'output/release/staging/str8n-v2.0rc1-dbg1-v1g-r8'
BASE_SHA='82b22179267e90c2a484106861dc4b98c9697b19614b7f18f878e35760cd5bbb'
BASE_MANIFEST='82d5cc9f3c81866cf24c587c16f80d69e3d385bdb1da4fa3470ee7c2c4a55823'
IMAGE='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(value,message):
    if not value:raise ValueError(message)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def portable(value):
    if isinstance(value,dict):return {portable(k):portable(v) for k,v in value.items()}
    if isinstance(value,list):return [portable(v) for v in value]
    if isinstance(value,str):
        value=value.replace(str(ROOT),'repository').replace(ROOT.as_posix(),'repository').replace('\\','/')
        return re.sub(r'[A-Za-z]:/[^\s"\']+',lambda m:'external-runtime/'+m[0].split('/')[-1],value)
    return value


def check_program(path):
    value=subprocess.run([sys.executable,'-B',str(path)],capture_output=True,text=True)
    require(value.returncode==0,value.stdout+value.stderr)
    return value.stdout


def verifier(base,out,bindings):
    text=(base/'verify_package.py').read_text(encoding='utf-8')
    for old,new in [("m['distribution_revision']==8","m['distribution_revision']==9"),
                    ("approval['distribution_revision'] == 8","approval['distribution_revision'] == 9"),
                    ('    verify_register_edits(root)\n','    verify_register_edits(root)\n    verify_uniform_scope(root, manifest, summary)\n')]:
        require(text.count(old)==1,'Unexpected r8 verifier anchor: '+old);text=text.replace(old,new,1)
    text,count=re.subn(r"APPROVAL_SHA = '[0-9a-f]{64}'","APPROVAL_SHA = '"+SHA(out/'qualification/release-authorization.json')+"'",text)
    require(count==1,'Missing owner binding')
    inventory=sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
    text,count=re.subn(r'^EXPECTED_FILES = frozenset\(.*\)$',lambda _: 'EXPECTED_FILES = frozenset('+repr(inventory)+')',text,flags=re.M)
    require(count==1,'Missing exact inventory')
    helper=(HERE/'verify_uniform_scope.inc').read_text(encoding='utf-8').replace('__UNIFORM_BINDINGS__',repr(bindings))
    anchor="if __name__=='__main__':";require(text.count(anchor)==1,'Wrong verifier entry')
    text=text.replace(anchor,helper+'\n\n'+anchor,1)
    (out/'verify_package.py').write_text(text,encoding='utf-8',newline='\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('run','record','out'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--component-model',type=Path,required=True)
    ap.add_argument('--component-history',type=Path,required=True)
    a=ap.parse_args();run=a.run.resolve();record=a.record.resolve();out=a.out.resolve()
    archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256');work=record/'package-work'
    require(run.is_relative_to(Q) and record.is_relative_to(Q) and out.is_relative_to(ROOT/'output/release/staging'),'Unsafe output')
    require(not any(p.exists() for p in (out,archive,checksum,work,record/'package-report.json')),'Never overwrite an immutable package/attempt')
    require(SHA(Path(str(BASE)+'.zip'))==BASE_SHA and SHA(BASE/'package-manifest.json')==BASE_MANIFEST,'Changed published r8')
    check_program(BASE/'verify_package.py')
    report=READ(run/'report.json');ad=READ(run/'admission-v2.json');kit=Path(ad['kit'])
    require(report['passed'] and report['release_ready'] and report['direct_physical_routes_passed']==4,'Uniform qualification not closed')
    require(report['target_firmware_sha256']==IMAGE and SHA(kit/'uniform-manifest.json')==report['qualified_uniform_manifest_sha256'],'Wrong tested bytes')
    require(READ(Q/'serial-coordination/owner.json')['kind']=='idle','Serial operation active')
    for board in ('2604','2609'):
        operation=READ(Q/'device-operations'/f'{board}.json')
        require(operation['uniform_upgrade_board_qualification_passed'] and not any(operation.get(k) for k in ('uniform_upgrade_worker_active','application_RAM_restore_pending','physical_reset_pending','block_snapshot')),'Unclosed board')
    protected={str(p):SHA(p) for p in BASE.rglob('*') if p.is_file()}
    protected[str(Path(str(BASE)+'.zip'))]=BASE_SHA
    protected[str(Path(str(BASE)+'.zip.sha256'))]=SHA(Path(str(BASE)+'.zip.sha256'))
    for name,digest in READ(run/'final-checksums.json')['files'].items():
        require(SHA(run/name)==digest,'Changed closed qualification: '+name);protected[str(run/name)]=digest
    for group in ('source_sha256','evidence_sha256'):
        for name,digest in ad[group].items():require(SHA(name)==digest,'Changed admitted input: '+name);protected[name]=digest
    record.mkdir(parents=True,exist_ok=True);shutil.copytree(BASE,work)
    require(a.component_model.resolve().is_relative_to(Q) and a.component_history.resolve().is_relative_to(Q),'Unsafe model evidence')
    component_model=READ(a.component_model)
    require(component_model['passed'] and component_model['checks']==12 and component_model['model_only'] and not component_model['board_access'],'Missing current component model checks')
    for name,digest in component_model['source_sha256'].items():
        require(SHA(ROOT/name)==digest,'Changed component-model input: '+name)
        protected[str(ROOT/name)]=digest
    sys.path.insert(0,str(ROOT/'tools'));from rc1_v1g_components import emit as emit_components
    component_map=emit_components(work,component_model)
    shutil.copyfile(BASE/'qualification/summary.json',work/'qualification/history/r8-summary.json')
    shutil.copyfile(BASE/'qualification/release-authorization.json',work/'qualification/history/r8-release-authorization.json')
    sources={}
    def export(source,destination):
        source=Path(source);target=work/'qualification/uniform-upgrade'/destination
        save(target,portable(READ(source)))
        sources[destination]=dict(original_sha256=SHA(source),packaged_sha256=SHA(target),path_strings_normalized=True)
    for name in ('report.json','owner-authorization.json','development-history.json','development-history-v2.json','entry-admission-development-history.json','owner-J3-preference.json'):
        if (run/name).exists():export(run/name,name)
    for source,name in [(Q/'rc1-uniform-model-development-r4/report.json','inherited-rc1-CPU-models.json'),
                        (Q/'rc1-uniform-bootstrap-development-r3/report.json','inherited-legacy-CPU-models.json'),
                        (Q/'rc1-uniform-host-workflow-development-r2.json','host-workflow.json')]:export(source,name)
    export(a.component_model,'component-layout-models.json')
    export(a.component_history,'component-model-development-history.json')
    for board in ('2604','2609'):
        export(run/board/'board-final-audit.json',f'{board}/board-final-audit.json')
        trial=READ(Path(ad['trial_roots'][board])/'report.json')
        save(work/f'qualification/uniform-upgrade/{board}/private-fixture-CPU-projection.json',dict(passed=trial['passed'],checks=trial['checks'],source_trial_report_sha256=SHA(Path(ad['trial_roots'][board])/'report.json'),vendor_images_exported=False,private_plans_exported=False))
        for phase in ('stage-wdc','migrate-wdc','stage-beta4','migrate-beta4'):
            folder=run/board/'live-v2'/phase
            if not folder.exists():folder=run/board/'live'/phase
            for name in ('report.json','process-identity.json','process-exit.json','source-admission-audit.json','independent-audit.json','workflow/report.json'):
                if (folder/name).exists():export(folder/name,f'{board}/{phase}/{name}')
        for phase in ('final','current-v2'):
            for name in ('report.json','process-identity.json','process-exit.json','original-comparison.json','independent-no-write-audit.json','monitor-terminal-state-correction.json'):
                if (run/board/phase/name).exists():export(run/board/phase/name,f'{board}/{phase}/{name}')
    # Preserve the failed original beta4 host check as a separate dated record.
    for name in ('report.json','process-exit.json','monitor-comparison-history.json'):
        export(run/'2604/live/stage-beta4'/name,'history/2604-beta4-host-refusal/'+name)
    save(work/'qualification/uniform-upgrade/source-evidence.json',dict(source_run=run.name,source_report_sha256=SHA(run/'report.json'),files=sources,raw_serial_logs_exported=False,private_flash_RAM_EEPROM_SRAM_exported=False,vendor_images_exported=False))
    # The development manifest also sealed interpreter caches inherited from its
    # parent. Preserve that evidence, but distribute exact source/payload bytes
    # without machine-generated bytecode. Only inventory metadata is rewritten.
    (work/'upgrade').mkdir()
    omitted=[]
    for name in ['uniform-manifest.json',*READ(kit/'uniform-manifest.json')['files']]:
        if '__pycache__' in Path(name).parts or Path(name).suffix=='.pyc':
            omitted.append(name);continue
        target=work/'upgrade'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(kit/name,target)
    inner_path=work/'upgrade/migration/kit-manifest.json';inner=READ(inner_path)
    inner['files']={name:info for name,info in inner['files'].items() if '__pycache__' not in Path(name).parts and Path(name).suffix!='.pyc'}
    save(inner_path,inner)
    acceptance=dict(passed=True,qualified_development_manifest_sha256=SHA(kit/'uniform-manifest.json'),
        runtime_bytes_unchanged=True,firmware_sha256=IMAGE,report_sha256=SHA(work/'qualification/uniform-upgrade/report.json'),
        current_scope='qualification/uniform-upgrade/report.json',inner_development_metadata_is_historical=True,
        interpreter_caches_omitted=omitted,metadata_only_changes=['migration/kit-manifest.json'],
        native_debugging=False,RTC_drift_in_release_qualification=False)
    save(work/'upgrade/current-acceptance.json',acceptance)
    uniform=READ(kit/'uniform-manifest.json');uniform.update(hardware_qualified=True,current_acceptance='current-acceptance.json')
    uniform['files']={name:info for name,info in uniform['files'].items() if name not in omitted}
    uniform['files']['migration/kit-manifest.json']=dict(bytes=inner_path.stat().st_size,sha256=SHA(inner_path))
    uniform['files']['current-acceptance.json']=dict(bytes=(work/'upgrade/current-acceptance.json').stat().st_size,sha256=SHA(work/'upgrade/current-acceptance.json'))
    save(work/'upgrade/uniform-manifest.json',uniform)
    for name in READ(kit/'uniform-manifest.json')['files']:
        if name not in omitted and name!='migration/kit-manifest.json':
            require((kit/name).read_bytes()==(work/'upgrade'/name).read_bytes(),'Changed tested runtime: '+name)
    # Exercise the exact cache-free runtime in a separate development-gated copy;
    # only the public acceptance flag differs, so the refusal check remains valid.
    host_copy=record/'cacheless-host-kit';shutil.copytree(work/'upgrade',host_copy)
    host_manifest=READ(host_copy/'uniform-manifest.json');host_manifest['hardware_qualified']=False
    save(host_copy/'uniform-manifest.json',host_manifest)
    host_receipt=record/'cacheless-host-checks.json'
    checked=subprocess.run([sys.executable,'-B',str(ROOT/'tools/test_rc1_uniform_workflow_v2.py'),
        '--package',str(host_copy),'--out',str(host_receipt)],capture_output=True,text=True)
    require(checked.returncode==0,checked.stdout+checked.stderr)
    require(READ(host_receipt)['passed'] and READ(host_receipt)['cases']==12,'Cache-free host checks failed')
    export(host_receipt,'cacheless-host-checks.json')
    save(work/'qualification/uniform-upgrade/source-evidence.json',dict(source_run=run.name,source_report_sha256=SHA(run/'report.json'),files=sources,raw_serial_logs_exported=False,private_flash_RAM_EEPROM_SRAM_exported=False,vendor_images_exported=False))
    code=work/'source/uniform-upgrade-qualification';code.mkdir()
    source_index={}
    for name in ('prepare_rc1_uniform_upgrade.py','prepare_rc1_uniform_v2.py','prepare_rc1_uniform_trials.py','run_rc1_uniform_legacy_trial.py','run_rc1_uniform_legacy_trial_v2.py','capture_rc1_uniform_preservation.py','qualify_rc1_uniform_current.py','audit_rc1_uniform_board.py','close_rc1_uniform_qualification.py','rc1_uniform_cpu_model.py','test_rc1_uniform_upgrade.py','test_rc1_uniform_bootstrap.py','test_rc1_uniform_workflow.py','test_rc1_uniform_workflow_v2.py','rc1_v1g_components.py','test_rc1_v1g_component_layout.py'):
        shutil.copyfile(ROOT/'tools'/name,code/name);source_index[name]=SHA(code/name)
    save(work/'qualification/uniform-upgrade/qualification-source-index.json',dict(files=source_index,source_review_material_requires_repository_and_private_fixtures=True,packaging_does_not_execute_hardware_tools=True))
    approval=READ(BASE/'qualification/release-authorization.json')
    approval.update(distribution_revision=9,uniform_upgrade_qualification_report_sha256=SHA(run/'report.json'),
        qualified_uniform_manifest_sha256=SHA(kit/'uniform-manifest.json'),owner_request=READ(run/'owner-authorization.json')['owner_request'],
        owner_source_clarification=READ(run/'owner-authorization.json')['owner_source_clarification'])
    save(work/'qualification/release-authorization.json',approval)
    summary=READ(BASE/'qualification/summary.json');summary.update(uniform_upgrade_qualified=True,
        uniform_upgrade_summary='qualification/uniform-upgrade/report.json',uniform_upgrade_direct_routes=4,
        native_debugging=False,RTC_drift_in_release_qualification=False,RTC_drift_is_promotion_gate=False,pending=[])
    save(work/'qualification/summary.json',summary)
    # Documentation is supplied by the current source checkout only after closure.
    for name in ('README.md','INSTALL_ROLLBACK.md'):
        source=record/'documents'/name;require(source.is_file(),'Missing reviewed current document: '+name)
        shutil.copyfile(source,work/name)
    for name in ('UNIFORM_UPGRADE.md','V1G_RELEASE_STATUS.md','FLASH_RECLAIM.md','RELEASE_PATHS.md','FIRMWARE_CONTENTS.md'):
        source=record/'documents'/name;require(source.is_file(),'Missing reviewed current document: '+name)
        shutil.copyfile(source,work/'docs/rc1'/name)
    for name in ('README.md','QUICK_START_MIGRATION.md','QUICK_START_WINDOWS.md','QUICK_START_LINUX.md','MIGRATION_RECOVERY.md'):
        path=work/'docs/rc1'/name
        path.write_text('> Distribution r9: use the current [uniform upgrade entry](UNIFORM_UPGRADE.md).\n> The commands and generation-49 scope below are retained historical reference.\n\n'+path.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    sys.path.insert(0,str(ROOT/'tools'));from audit_rc1_dbg_docs import audit
    docs=audit(work,list(work.rglob('*.md')));require(docs['passed'],str(docs['errors']))
    save(work/'qualification/documentation-audit.json',docs)
    bindings={p.relative_to(work).as_posix():SHA(p) for folder in ('upgrade','qualification/uniform-upgrade','source/uniform-upgrade-qualification') for p in (work/folder).rglob('*') if p.is_file()}
    bindings.update({p.relative_to(work).as_posix():SHA(p) for p in [work/'firmware/components.json',
        *[work/'firmware'/name for name in component_map['files']],work/'docs/rc1/FLASH_RECLAIM.md',work/'docs/rc1/RELEASE_PATHS.md']})
    verifier(BASE,work,bindings)
    files={}
    for p in sorted(work.rglob('*')):
        if not p.is_file() or p.name in ('package-manifest.json','SHA256SUMS.txt'):continue
        name=p.relative_to(work).as_posix()
        require(not any(part in ('private','capture','before','after','__pycache__') for part in p.relative_to(work).parts) and p.suffix not in ('.jsonl','.pyc','.zip'),'Private/transient artifact: '+name)
        if p.suffix in ('.py','.json','.md','.txt','.asm'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',p.read_text(encoding='utf-8')),'Host path leak: '+name)
        files[name]=dict(bytes=p.stat().st_size,sha256=SHA(p))
    manifest=READ(BASE/'package-manifest.json');manifest.update(distribution_revision=9,uniform_upgrade_qualified=True,
        uniform_upgrade_kit_manifest_sha256=SHA(work/'upgrade/uniform-manifest.json'),uniform_upgrade_source_routes=uniform['required_source_routes'],
        inherited_source_bound_installer_fields=True,uniform_upgrade_transfer_counts=dict(WDCMONV2=23,beta4=22,current_v1g=0),
        RTC_issue_deferred=True,host_platform='Windows',staged_utc=datetime.now(timezone.utc).isoformat(),files=files,
        package_markdown_links_checked=docs['links_and_anchors_checked'])
    save(work/'package-manifest.json',manifest)
    sums={**files,'package-manifest.json':dict(sha256=SHA(work/'package-manifest.json'))}
    (work/'SHA256SUMS.txt').write_text(''.join(info['sha256']+'  '+name+'\n' for name,info in sorted(sums.items())),encoding='ascii')
    check_program(work/'verify_package.py')
    # Do not expose a final distribution until its temporary extracted tree passes.
    shutil.copytree(work,out);check_program(out/'verify_package.py')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted([*sums,'SHA256SUMS.txt']):
            info=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,21,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,(out/name).read_bytes())
    extracted=record/'archive-extracted';require(not extracted.exists(),'Extraction target exists')
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None and all(n.startswith(out.name+'/') and '..' not in Path(n).parts for n in z.namelist()),'Unsafe/corrupt archive');z.extractall(extracted)
    check_program(extracted/out.name/'verify_package.py')
    checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
    require(all(SHA(p)==digest for p,digest in protected.items()),'Frozen evidence or prior package changed')
    result=dict(integrity_passed=True,release_qualification_passed=True,uniform_upgrade_qualified=True,distribution_revision=9,
        distribution=str(out),archive=str(archive),archive_sha256=SHA(archive),archive_checksum=str(checksum),
        package_manifest_sha256=SHA(out/'package-manifest.json'),files_verified=len(sums)+1,
        markdown_links_checked=docs['links_and_anchors_checked'],extracted_archive_verified=True,
        firmware_sha256=IMAGE,source_qualification_report_sha256=SHA(run/'report.json'),
        tested_uniform_manifest_sha256=SHA(kit/'uniform-manifest.json'),published_uniform_manifest_sha256=SHA(out/'upgrade/uniform-manifest.json'),
        runtime_bytes_unchanged=True,interpreter_caches_omitted=omitted,cacheless_host_checks=12,
        exact_component_slices=len(component_map['files']),component_model_checks=component_model['checks'],
        component_model_scope='CPU models, MON A on both CPUs; no physical erases or generic uninstaller',
        promotion_held=False,native_debugging=False,RTC_drift_in_release_qualification=False,
        prior_r8_archive_sha256=BASE_SHA,protected_files_verified=len(protected),board_access=False,
        stager_sha256=SHA(__file__),verifier_template_sha256=SHA(HERE/'verify_uniform_scope.inc'))
    save(record/'package-report.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
