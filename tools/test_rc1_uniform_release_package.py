"""Host-only release verifier/tamper tests against a fresh immutable package."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
READ=lambda p:json.loads(p.read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def reseal(folder):
    manifest=READ(folder/'package-manifest.json')
    manifest['files']={p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in folder.rglob('*') if p.is_file() and p.name not in ('package-manifest.json','SHA256SUMS.txt') and '__pycache__' not in p.parts}
    write(folder/'package-manifest.json',manifest)
    sums={name:info['sha256'] for name,info in manifest['files'].items()};sums['package-manifest.json']=SHA(folder/'package-manifest.json')
    (folder/'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(sums.items())),encoding='ascii')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    base=args.package.resolve();spec=importlib.util.spec_from_file_location('approved_release_verifier',base/'verify_package.py');verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    require=lambda v,m: verifier.require(v,m)
    result=verifier.verify(base);require(result['integrity_passed'] and result['release_qualification_passed'] and not result['promotion_held'],'Baseline failed')
    checks=[dict(name='full-valid-package',passed=True)]
    def mutation(name,path,change,seal=True):
        with tempfile.TemporaryDirectory(prefix='rc1-r9-tamper-',dir=ROOT/'tmp') as temp:
            require(Path(temp).resolve().is_relative_to((ROOT/'tmp').resolve()),'Unsafe temporary target')
            folder=Path(temp)/'package';shutil.copytree(base,folder)
            target=folder/path;change(target)
            if seal:reseal(folder)
            try:verifier.verify(folder)
            except (ValueError,KeyError,OSError,AssertionError) as error:checks.append(dict(name=name,passed=True,refusal=str(error)));return
            raise AssertionError('Tampering accepted: '+name)
    def field(key,value):
        def change(path):v=READ(path);v[key]=value;write(path,v)
        return change
    for key,value in [('distribution_revision',8),('release_status','staged-promotion-held'),('promotion_held',True),('release_qualification_passed',False),('native_debugging',True),('native_applications_tested',True),('runtime',['65C02','65C816 E=0']),('RTC_drift_in_release_qualification',True),('RTC_drift_is_promotion_gate',True),('register_edits_qualified',False)]:
        mutation('manifest-'+key,'package-manifest.json',field(key,value))
    mutation('uniform-not-qualified','package-manifest.json',field('uniform_upgrade_qualified',False))
    mutation('missing-direct-route','qualification/uniform-upgrade/report.json',field('direct_physical_routes_passed',3))
    mutation('concealed-host-failure','qualification/uniform-upgrade/report.json',field('host_protocol_qualification_failures',0))
    mutation('unresolved-host-failure','qualification/uniform-upgrade/report.json',field('host_protocol_failure_resolved',False))
    mutation('manual-generation49-intermediate','qualification/uniform-upgrade/report.json',field('intermediate_generation49',True))
    mutation('uniform-original-RAM','qualification/uniform-upgrade/2609/board-final-audit.json',field('original_RAM_restored',False))
    mutation('uniform-original-SRAM','qualification/uniform-upgrade/2604/board-final-audit.json',field('SRAM_131072_bytes_unchanged',False))
    mutation('uniform-wear-accounting','qualification/uniform-upgrade/2609/board-final-audit.json',field('reserved_erase_attempts',91))
    mutation('uniform-current-no-write','qualification/uniform-upgrade/2604/board-final-audit.json',field('already_current_no_write_verified',False))
    mutation('uniform-worker-exit','qualification/uniform-upgrade/2609/board-final-audit.json',field('actual_workers_exited',False))
    mutation('uniform-development-kit','upgrade/uniform-manifest.json',field('hardware_qualified',False))
    mutation('uniform-runtime-equivalence','upgrade/current-acceptance.json',field('runtime_bytes_unchanged',False))
    mutation('uniform-host-protocol-tests','qualification/uniform-upgrade/host-workflow.json',field('cases',8))
    mutation('unexpected-vendor-image','upgrade/vendor-image.bin',lambda p:p.write_bytes(b'synthetic vendor-data sentinel'))
    mutation('F-component-is-not-a-standalone-Jn-launcher','firmware/components.json',field('F_only_has_normal_monitor_or_Jn',True))
    mutation('no-invented-DBG1-uninstaller','firmware/components.json',field('erase_only_DBG1_uninstall_supported',True))
    mutation('no-physical-component-removal-claim','qualification/uniform-upgrade/component-layout-models.json',field('hardware_component_removal_tested',True))
    mutation('exact-F-component-bytes','firmware/str8n-2.0rc1-dbg1-gen50-b3-f000-ffff.bin',lambda p:p.write_bytes(p.read_bytes()[:-1]+bytes([p.read_bytes()[-1]^1])))
    mutation('owner-approval-refusal','qualification/release-authorization.json',field('promotion_authorized',False))
    mutation('register-hardware-total','qualification/register-edits/report.json',field('hardware_totals',dict(parser=1)))
    mutation('register-model-matrix','qualification/register-edits/register-edits-CPU-816.json',field('actual_resume_cases',1))
    mutation('register-full-RAM','qualification/register-edits/2609/report.json',field('RAM_restored_host_verified',False))
    mutation('register-worker-exit','qualification/register-edits/2604/process-exit.json',field('actual_exit_verified',False))
    mutation('unsafe-PC-projection','qualification/register-edits/unsafe-PC-execution-refusals.json',field('total_refusals',1))
    mutation('invented-current-gate','qualification/summary.json',field('pending',['drift-review']))
    mutation('broken-document-link','README.md',lambda p:p.write_text(p.read_text()+'\n[broken](not-present.md)\n',encoding='utf-8'))
    mutation('missing-register-receipt','qualification/register-edits/2609/A/resume-receipts.json',lambda p:p.unlink())
    mutation('extra-private-data','private-capture.bin',lambda p:p.write_bytes(b'synthetic private-data sentinel'))
    mutation('raw-inventory-mutation','README.md',lambda p:p.write_text('unsealed mutation',encoding='utf-8'),seal=False)
    # Separate archive integrity from acceptance: even a failed/unavailable RTC
    # measurement must not become a semantic gate when workload restoration passes.
    original_read=verifier.READ
    def without_drift(path):
        value=original_read(path)
        if path.relative_to(base).as_posix()=='qualification/soak/summary.json':
            value=copy.deepcopy(value);value.pop('final_drift',None);value['passed']=False
        return value
    with patch.object(verifier,'READ',side_effect=without_drift):verifier.verify_soak(base,original_read(base/'qualification/history/r7-summary.json'))
    checks.append(dict(name='drift-absent-is-not-a-release-acceptance-gate',passed=True))
    sums=(Path(str(base)+'.zip.sha256')).read_text().strip().split()
    require(sums[0]==SHA(Path(str(base)+'.zip')) and sums[1]==base.name+'.zip','Wrong archive checksum')
    checks.append(dict(name='exact-adjacent-archive-checksum',passed=True))
    require(args.out.resolve().is_relative_to((ROOT/'output/qualification').resolve()) and not args.out.exists(),'Fresh local receipt required')
    write(args.out,dict(passed=True,checks=len(checks),results=checks,package_sha256=SHA(base/'package-manifest.json'),archive_sha256=sums[0],board_access=False,simulated_tampering_not_hardware_failures=True,native_debugging=False,RTC_drift_in_release_qualification=False))
    print(json.dumps(dict(passed=True,checks=len(checks),board_access=False),indent=2))


if __name__=='__main__':main()
