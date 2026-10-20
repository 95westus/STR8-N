"""Derive immutable owner-approved r8; verify without boards or publication."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
Q = ROOT / 'output/qualification'
BASE_SHA = '8e3d1f901fe9bcbb4ae15a83214be0999e746bdf4f088e8c9b308f345a47b528'
BASE_MANIFEST = 'a55b4da98b6c43d4b1a6b141c68ad98ef8f92d9adea629f572347e8619927dcf'
BASE_VERIFIER = '0628d666f6dc1a43cced94aa9996dacc69d25e24f262f5dd348fd503feb6b17a'
REGISTER_REPORT = 'fccf71436d7711e47ac852a6b2edcc02af0908dcc188b3908b3b742a9f69676d'
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(value, message):
    if not value:raise ValueError(message)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2);stream.write('\n')


def portable(value):
    if isinstance(value, dict):return {portable(k):portable(v) for k,v in value.items()}
    if isinstance(value, list):return [portable(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT), 'repository').replace(ROOT.as_posix(), 'repository').replace('\\', '/')
        return re.sub(r'[A-Za-z]:/[^\s"\']+', lambda m:'external-runtime/'+m[0].split('/')[-1], value)
    return value


def make_verifier(base, out, bindings, approval):
    source = (base/'verify_package.py').read_text(encoding='utf-8')
    source=source.replace('promotion-held v1g staging snapshot','owner-approved v1g release snapshot').replace('Premature release claim','Wrong current release approval')
    edits = {
        "m['distribution_revision']==7":"m['distribution_revision']==8",
        "m['release_status']=='staged-promotion-held' and m['promotion_held']":"m['release_status']=='owner-approved-rc1' and not m['promotion_held']",
        "summary['candidate_build']==BUILD and summary['firmware_sha256']==IMAGE_SHA and summary['promotion_held'] and summary['release_qualification_passed'] is False":"summary['candidate_build']==BUILD and summary['firmware_sha256']==IMAGE_SHA and not summary['promotion_held'] and summary['release_qualification_passed'] is True",
        '    verify_hardware(root,summary)':"    verify_release_scope(root,m,summary)\n    verify_hardware(root,READ(root/'qualification/history/r7-summary.json'))\n    verify_documentation(root)",
        'candidate_build=BUILD,promotion_held=True,offline_qualification_passed=True':'candidate_build=BUILD,promotion_held=False,offline_qualification_passed=True',
        "release_qualification_passed=False,hardware='passed',soak='owner-stopped-passed',final_drift='passed'":"release_qualification_passed=True,hardware='passed',soak='owner-stopped-passed',RTC_drift_in_release_qualification=False,register_edits='passed'"
    }
    for before, after in edits.items():
        require(source.count(before)==1, 'Unexpected parent verifier: '+before)
        source=source.replace(before,after,1)
    helper=(HERE/'verify_release_scope.inc').read_text(encoding='utf-8')
    helper=helper.replace('__REGISTER_BINDINGS__',repr(bindings)).replace('__APPROVAL_SHA__',SHA(approval))
    helper=helper.replace('__EXPECTED_FILES__',repr(sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())))
    start=source.index('def verify_soak(root, summary):');end=source.index("if __name__=='__main__':",start)
    source=source[:start]+helper+'\n\n'+source[end:]
    (out/'verify_package.py').write_text(source,encoding='utf-8',newline='\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('base-report','register-run','record','out'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();base_report=READ(args.base_report);base=Path(base_report['distribution']).resolve()
    archive_before=Path(base_report['archive']);reg=args.register_run.resolve();record=args.record.resolve();out=args.out.resolve()
    archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256')
    require(record.is_relative_to(Q) and out.is_relative_to(ROOT/'output/release/staging') and reg.is_relative_to(Q),'Unsafe output path')
    require(not any(p.exists() for p in (out,archive,checksum,record/'package-report.json')),'Never overwrite an immutable distribution')
    require(SHA(archive_before)==base_report['archive_sha256']==BASE_SHA and SHA(base/'package-manifest.json')==BASE_MANIFEST,'Changed r7 package')
    require(SHA(base/'verify_package.py')==BASE_VERIFIER,'Changed r7 verifier')
    checked=subprocess.run([sys.executable,'-B',str(base/'verify_package.py')],capture_output=True,text=True)
    require(checked.returncode==0,checked.stdout+checked.stderr)
    require(SHA(reg/'report.json')==REGISTER_REPORT and READ(reg/'report.json')['passed'],'Wrong register qualification')
    protected={str(p):SHA(p) for p in base.rglob('*') if p.is_file()}
    protected.update({str(archive_before):SHA(archive_before),str(Path(str(archive_before)+'.sha256')):SHA(str(archive_before)+'.sha256')})
    for name,digest in READ(reg/'final-checksums.json')['files'].items():
        require(SHA(reg/name)==digest,'Changed frozen register evidence: '+name);protected[str(reg/name)]=digest
    admission=READ(reg/'admission.json')
    for path,digest in {**admission['source_sha256'],**admission['evidence_sha256']}.items():
        require(SHA(path)==digest,'Changed register input: '+path);protected[path]=digest
    approval=READ(HERE/'release-policy.json')
    require(approval['owner_authorized'] and approval['promotion_authorized'] and not approval['native_debugging'] and not approval['RTC_drift_in_release_qualification'],'Wrong owner scope')
    require(approval['register_qualification_report_sha256']==REGISTER_REPORT,'Wrong approved proof')
    require(READ(Q/'serial-coordination/owner.json')['kind']=='idle','Device operation still active')
    for board in ('2604','2609'):
        operation=READ(Q/'device-operations'/f'{board}.json')
        require(not operation['application_RAM_restore_pending'] and not operation.get('register_edit_worker_active'),'Unclosed board operation')
    record.mkdir(parents=True,exist_ok=True);save(record/'owner-authorization.json',approval)
    shutil.copytree(base,out)
    (out/'qualification/history/r7-summary.json').write_bytes((base/'qualification/summary.json').read_bytes())
    save(out/'qualification/release-authorization.json',approval)
    (out/'verification').mkdir(exist_ok=True);shutil.copyfile(ROOT/'tools/audit_rc1_dbg_docs.py',out/'verification/audit_docs.py')
    sources={}
    def export(src,dest,lines=False):
        source=reg/src;target=out/'qualification/register-edits'/dest
        value=[json.loads(v) for v in source.read_text(encoding='utf-8-sig').splitlines()] if lines else READ(source)
        save(target,portable(value));sources[src]=dict(source_sha256=SHA(source),package_path=target.relative_to(out).as_posix(),packaged_sha256=SHA(target),path_strings_normalized=True)
    for name in ('report.json','register-edits-CPU-02.json','register-edits-CPU-816.json','independent-physical-audit.json','unsafe-PC-execution-refusals.json','offline-development-history.json','offline-qualification-summary.json','host-preparation-history.json','runner-policy.json'):
        export(name,name)
    for board in ('2604','2609'):
        export(f'{board}/report.json',f'{board}/report.json');export(f'{board}-process-exit.json',f'{board}/process-exit.json')
        for slot in ('A','B'):
            for kind in ('parser','resume'):export(f'{board}/{slot}/{kind}-receipts.jsonl',f'{board}/{slot}/{kind}-receipts.json',lines=True)
    save(out/'qualification/register-edits/source-evidence.json',dict(source_run=reg.name,source_report_sha256=REGISTER_REPORT,files=sources,private_backups_exported=False,serial_logs_exported=False,board_access_during_packaging=False))
    diag=out/'diagnostics/register-edits';diag.mkdir()
    for src,name in [('rc1_dbg_register_edits.py','cases.py'),('cases.json','cases.json'),('fixture.s19','fixture.s19')]:shutil.copyfile(reg/'model-sources'/src,diag/name)
    code=out/'source/qualification';code.mkdir()
    code_index={}
    for name in ('rc1_dbg_register_edits.py','test_rc1_dbg_register_edits_cpu.py','run_rc1_dbg_register_edits.py','test_rc1_dbg_register_edits_runner.py'):
        require(SHA(ROOT/'tools'/name)==SHA(reg/'model-sources'/name),'Changed qualified source: '+name)
        shutil.copyfile(reg/'model-sources'/name,code/name)
        if name=='test_rc1_dbg_register_edits_cpu.py':
            text=(code/name).read_text(encoding='utf-8')
            require(text.count("ROOT = Path('C:/SRC/STR8-N')")==1,'Unexpected model root declaration')
            (code/name).write_text(text.replace("ROOT = Path('C:/SRC/STR8-N')","ROOT = Path(__file__).resolve().parents[2]",1),encoding='utf-8',newline='\n')
        code_index[name]=dict(original_qualified_sha256=SHA(reg/'model-sources'/name),packaged_sha256=SHA(code/name),root_path_portability_adapter=name=='test_rc1_dbg_register_edits_cpu.py')
    save(out/'qualification/register-edits/source-portability.json',code_index)
    summary=READ(base/'qualification/summary.json');summary.update(promotion_held=False,release_qualification_passed=True,register_edits_qualified=True,RTC_drift_in_release_qualification=False,RTC_drift_is_promotion_gate=False,pending=[],release_authorization='qualification/release-authorization.json',register_edit_summary='qualification/register-edits/report.json')
    summary.pop('final_drift_snapshot_passed',None)
    save(out/'qualification/summary.json',summary)
    changed_docs=[]
    for path in out.rglob('*.md'):
        name=path.relative_to(out).as_posix()
        if name.startswith('install/') or name in ('docs/rc1/ASM_GUIDE.md','docs/rc1/ABI_REFERENCE.md'):continue
        body=path.read_text(encoding='utf-8')
        old=body
        for before,after in [('Promotion remains held','The owner has approved scoped RC1 promotion'),('Promotion stays held','The owner has approved scoped RC1 promotion'),('Promotion is held','The owner has approved scoped RC1 promotion'),('promotion remains held','the owner has approved scoped RC1 promotion'),('promotion stays held','the owner has approved scoped RC1 promotion'),('An explicit promotion/release decision is still required','The owner has now authorized scoped RC1 promotion'),('An explicit owner promotion/release decision remains required','The owner has now authorized scoped RC1 promotion')]:body=body.replace(before,after)
        body=body.replace('an explicit promotion/release decision remains required','the owner has authorized scoped RC1 promotion').replace('This staged, promotion-held **v1g** image','This owner-approved **v1g** image')
        if body!=old:path.write_text(body,encoding='utf-8',newline='\n');changed_docs.append(name)
    guide=out/'docs/rc1/DEBUGGER_GUIDE.md';body=guide.read_text();current=(ROOT/'docs/rc1/DEBUGGER_GUIDE.md').read_text()
    section=current[current.index('## Editing saved registers'):current.index('## All eight persistent breakpoints')]
    section=section.replace('DBG1_CANDIDATE_STATUS.md#saved-register-edit-qualification','V1G_RELEASE_STATUS.md')
    guide.write_text(body.replace('## All eight persistent breakpoints',section+'## All eight persistent breakpoints',1),encoding='utf-8',newline='\n')
    board_results=out/'docs/rc1/DEBUGGER_BOARD_RESULTS.md'
    current_results=(ROOT/'docs/rc1/DEBUGGER_BOARD_RESULTS.md').read_text()
    register_section=current_results[current_results.index('## Saved-register edit qualification'):current_results.index('## Historical v1e and v1f scope')]
    register_section=register_section.replace('../../output/qualification/'+reg.name+'/report.json','../../qualification/register-edits/report.json')
    board_results.write_text(board_results.read_text()+'\n\n'+register_section,encoding='utf-8',newline='\n')
    status='''# Owner-approved rc1 v1g distribution r8

The owner authorized scoped RC1 promotion after both-board MON A/B R-register
qualification. Native applications/debugging are excluded. RTC drift is outside
release qualification and is not a promotion gate. Preserving settings and
RAM remains required. Historical held/drift records retain their original bytes.

The new [register evidence](../../qualification/register-edits/report.json)
records 5,752 physical parser checks, 220 resumes including 48 S/N then C, and
132 expected unsafe-PC refusals, with zero actual hardware failures. Both
25,344-byte original RAM images were restored and reread twice; four-bank
flash/settings and original MON B/2604 and MON A/2609 were preserved. 2609
stayed E=1 with DBR/PBR/direct page zero. The earlier R6 R coverage remains
query-only; this separate evidence covers PC/A/X/Y/P/SP editing.

The [owner decision](../../qualification/release-authorization.json) and
[current qualification summary](../../qualification/summary.json) define scope.
The [register source index](../../qualification/register-edits/source-evidence.json)
distinguishes original receipt hashes from portable packaged JSON hashes.
CPU models additionally passed 5,752 parser, 5,156 resume, 132 refusal and
48 S/N then C cases; hardware resumes used IRQ-masked P and stack-safe SP.

Firmware and installer are byte-identical to r7; see the [package README](../../README.md).
'''
    (out/'docs/rc1/V1G_RELEASE_STATUS.md').write_text(status,encoding='utf-8',newline='\n')
    for name in ('README.md','DEBUGGER_BOARD_RESULTS.md','OPERATOR_GUIDE.md','V1G_STAGING_STATUS.md','DBG1_SOAK_CLOSEOUT.md','ASM_DBG1_REQUALIFICATION.md'):
        path=out/'docs/rc1'/name
        if path.exists():path.write_text(path.read_text()+'\n\n## Distribution r8 release scope\n\nThe owner approved scoped RC1 promotion with native mode excluded and RTC drift\noutside release qualification. New register-edit evidence is separate from R6.\nSee [current scope and register results](V1G_RELEASE_STATUS.md).\n',encoding='utf-8',newline='\n')
    (out/'README.md').write_text('''# STR8-N 2.0rc1 DBG1 v1g — owner-approved distribution r8

Supported: **65C02 and 65C816 E=1**. Native applications/debugging are excluded.
**RTC drift is outside release qualification and is not a promotion gate.**
The owner authorized this package and scoped RC1 promotion after completed
both-board MON A/B register-edit qualification. Earlier held snapshots remain
historical evidence; r7 and earlier archives are unchanged.

New R qualification passed **5,752 parser checks, 220 resumes (including 48
S/N then C), and 132 expected unsafe-PC refusals**, with zero hardware failures.
Both full original 25,344-byte RAM images were restored and reread twice;
flash/settings and original monitor preferences were unchanged. 2609 stayed E=1.
See [scope and results](docs/rc1/V1G_RELEASE_STATUS.md),
[register receipts](qualification/register-edits/report.json),
[earlier hardware](qualification/hardware/summary.json), and
[owner-stopped R6 workload](qualification/soak/summary.json).

## Verify

Check the adjacent ZIP `.sha256`, extract to a new directory, then run
`python -B verify_package.py`. Verification opens no ports and checks all files,
exact firmware/installer, model/hardware/register evidence, the actual owner
decision, native exclusion and documentation links. Historical RTC files are
integrity checked without using drift measurements as release acceptance.

Firmware SHA-256: `6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
Firmware generation is 50; the displayed version stays 2.0rc1. Tested ASM/ABI
manuals and the source-bound installer remain byte exact. See
[install/rollback](INSTALL_ROLLBACK.md) and [debugger guide](docs/rc1/DEBUGGER_GUIDE.md).
The reference BIN is not a preserving updater; the existing kit admits exact
generation-49 sources, not an installed generation-50 candidate directly.

No board-specific backups/plans, original RAM/flash data, serial logs or secrets
are included. Diagnostic sources are review material for the qualified source
checkout; packaging/verification does not run hardware tools. Historical
qualification flags describe the decision at the time, not the current scope.
''',encoding='utf-8',newline='\n')
    install=out/'INSTALL_ROLLBACK.md';install.write_text(install.read_text()+'\n\n## Owner-approved distribution r8\n\nThe owner approved scoped RC1 promotion after the new register-edit checks.\nNative mode is excluded and RTC drift is outside release qualification.\nSee [current scope](docs/rc1/V1G_RELEASE_STATUS.md). These packaging changes\ndo not authorize another board installation or change the tested installer.\n',encoding='utf-8',newline='\n')
    sys.path.insert(0,str(ROOT/'tools'));from audit_rc1_dbg_docs import audit
    docs=audit(out,list(out.rglob('*.md')));require(docs['passed'],str(docs['errors']));save(out/'qualification/documentation-audit.json',docs)
    bindings={p.relative_to(out).as_posix():SHA(p) for folder in ('qualification/register-edits','diagnostics/register-edits','source/qualification') for p in (out/folder).rglob('*') if p.is_file()}
    make_verifier(base,out,bindings,out/'qualification/release-authorization.json')
    # All non-documentary original bytes, except current metadata/verifier, stay exact.
    allowed={'verify_package.py','qualification/summary.json','qualification/documentation-audit.json'}
    for name,info in READ(base/'package-manifest.json')['files'].items():
        if name not in allowed and not name.endswith('.md'):require(SHA(out/name)==info['sha256'],'Changed inherited tested bytes: '+name)
    files={}
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.name in ('package-manifest.json','SHA256SUMS.txt'):continue
        name=path.relative_to(out).as_posix()
        require(not any(part in ('private','capture','before','after','__pycache__') for part in path.relative_to(out).parts) and path.suffix not in ('.jsonl','.pyc','.zip'),'Private artifact exported: '+name)
        if path.suffix in ('.py','.json','.md','.txt','.asm'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',path.read_text(encoding='utf-8')),'Host path leak: '+name)
        files[name]=dict(bytes=path.stat().st_size,sha256=SHA(path))
    manifest=READ(base/'package-manifest.json');manifest.update(distribution_revision=8,release_status='owner-approved-rc1',promotion_held=False,release_qualification_passed=True,register_edits_qualified=True,RTC_drift_in_release_qualification=False,RTC_drift_is_promotion_gate=False,owner_approved=True,staged_utc=datetime.now(timezone.utc).isoformat(),files=files,package_markdown_links_checked=docs['links_and_anchors_checked'])
    manifest.pop('final_drift_passed',None)
    save(out/'package-manifest.json',manifest)
    sums={**files,'package-manifest.json':dict(sha256=SHA(out/'package-manifest.json'))}
    (out/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+name+'\n' for name,v in sorted(sums.items())),encoding='ascii')
    verified=subprocess.run([sys.executable,'-B',str(out/'verify_package.py')],capture_output=True,text=True);require(verified.returncode==0,verified.stdout+verified.stderr)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted([*sums,'SHA256SUMS.txt']):
            info=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,20,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,(out/name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='dbg-r8-extract-',dir=ROOT/'tmp') as temp:
        require(Path(temp).resolve().is_relative_to((ROOT/'tmp').resolve()),'Unsafe extraction path')
        with zipfile.ZipFile(archive) as z:
            require(z.testzip() is None and all(n.startswith(out.name+'/') and '..' not in Path(n).parts for n in z.namelist()),'Unsafe/corrupt ZIP');z.extractall(temp)
        extracted=subprocess.run([sys.executable,'-B',str(Path(temp)/out.name/'verify_package.py')],capture_output=True,text=True);require(extracted.returncode==0,extracted.stdout+extracted.stderr)
    checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
    require(all(SHA(p)==h for p,h in protected.items()),'Prior immutable evidence changed')
    report=dict(integrity_passed=True,distribution_revision=8,archive=str(archive),archive_sha256=SHA(archive),archive_checksum=str(checksum),distribution=str(out),package_manifest_sha256=SHA(out/'package-manifest.json'),files_verified=len(sums)+1,markdown_links_checked=docs['links_and_anchors_checked'],extracted_archive_verified=True,protected_files_verified=len(protected),firmware_sha256=approval['firmware_sha256'],tested_kit_manifest_sha256=approval['tested_kit_manifest_sha256'],register_qualification_passed=True,release_qualification_passed=True,promotion_authorized=True,promotion_held=False,native_debugging=False,RTC_drift_in_release_qualification=False,board_access=False,source_register_report_sha256=REGISTER_REPORT,prior_archive_sha256=BASE_SHA,stager_sha256=SHA(__file__),verifier_template_sha256=SHA(HERE/'verify_release_scope.inc'))
    save(record/'package-report.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as error:raise SystemExit('REFUSED: '+str(error))
