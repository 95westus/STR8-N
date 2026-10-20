"""Adversarial v1g staging checks; modifies temporary copies only, no ports."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def reseal(root):
    path=root/'package-manifest.json';m=json.loads(path.read_text())
    for name in m['files']:
        p=root/name
        if p.is_file():m['files'][name]=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    path.write_text(json.dumps(m,indent=2)+'\n');entries=dict(m['files']);entries['package-manifest.json']=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (root/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in sorted(entries.items())))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    package=a.package.resolve();sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('v1g_verifier',package/'verify_package.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='dbg-v1g-tamper-',dir=ROOT/'tmp') as folder:
        def trial(name,edit=None,update_sums=False):
            dest=Path(folder)/name;shutil.copytree(package,dest)
            if edit:edit(dest)
            if update_sums:reseal(dest)
            try:result=module.verify(dest)
            except (OSError,ValueError,KeyError) as exc:
                if edit is None:raise
                checks.append(dict(name=name,passed=True,refused=str(exc)));return
            if edit:raise AssertionError('Tampered package accepted: '+name)
            assert result['integrity_passed'] and result['offline_qualification_passed'] and result['promotion_held'] and not result['release_qualification_passed'] and result['hardware']==result['soak']=='pending'
            checks.append(dict(name=name,passed=True))
        def field(path,key,value):
            obj=json.loads(path.read_text());obj[key]=value;path.write_text(json.dumps(obj,indent=2)+'\n')
        trial('unchanged-offline-only-package')
        trial('changed-image',lambda p:(p/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin').write_bytes(b'bad'))
        trial('missing-file',lambda p:(p/'requirements.txt').unlink())
        trial('extra-file',lambda p:(p/'extra.txt').write_text('unexpected'))
        for key in ('hardware_requalification_passed','six_hour_soak_passed','final_drift_snapshot_passed'):
            trial('forged-'+key,lambda p,k=key:field(p/'qualification/summary.json',k,True),True)
        trial('parent-hardware-counts',lambda p:field(p/'qualification/summary.json','hardware_registration_scenarios',72),True)
        trial('forged-promotion',lambda p:field(p/'package-manifest.json','promotion_held',False),True)
        trial('native-scope',lambda p:field(p/'package-manifest.json','native_debugging',True),True)
        trial('wrong-offline-image',lambda p:field(p/'qualification/offline/debugger-test-65c816-e-manuals.json','firmware_sha256','923c8fee01310b873e89cc5e8982778e25fd425ccb9050735fb07604ef6228ba'),True)
        trial('changed-tested-manual',lambda p:(p/'docs/rc1/ASM_GUIDE.md').write_text((p/'docs/rc1/ASM_GUIDE.md').read_text()+'\n'),True)
        trial('changed-kit-sector',lambda p:(p/'install/sectors/b1-a000.bin').write_bytes(b'bad'),True)
        def false_edge(p):
            path=p/'qualification/offline/edge-review-02.json';obj=json.loads(path.read_text());obj['checks'][0]['observed']['A']=0x77;path.write_text(json.dumps(obj))
        trial('false-edge-observation',false_edge,True)
        def traversal(p):
            path=p/'package-manifest.json';obj=json.loads(path.read_text());obj['files']['../outside']=dict(bytes=0,sha256='0'*64);path.write_text(json.dumps(obj))
        trial('path-traversal',traversal,True)
    report=dict(passed=True,cases=len(checks),checks=checks,board_access=False,native_debugging=False,package_manifest_sha256=hashlib.sha256((package/'package-manifest.json').read_bytes()).hexdigest())
    a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
