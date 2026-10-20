"""Adversarial checks for the held staging verifier; mutates temporary copies only."""
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
    path.write_text(json.dumps(m,indent=2)+'\n');entries=dict(m['files'])
    entries['package-manifest.json']=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (root/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in sorted(entries.items())))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    package=a.package.resolve();sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('held_verifier',package/'verify_package.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='dbg-staged-tamper-',dir=ROOT/'tmp') as folder:
        root=Path(folder)
        def trial(name,edit=None,reseal_files=False):
            dest=root/name;shutil.copytree(package,dest)
            if edit:edit(dest)
            if reseal_files:reseal(dest)
            try:result=module.verify(dest)
            except (ValueError,OSError,KeyError) as exc:
                if not edit:raise
                checks.append(dict(name=name,passed=True,refused=str(exc)));return
            if edit:raise AssertionError('Tampered package accepted: '+name)
            assert result['integrity_passed'] and result['promotion_held'] and not result['release_qualification_passed'] and result['six_hour_soak']=='pending'
            checks.append(dict(name=name,passed=True))
        def edit_json(path,key,value):
            obj=json.loads(path.read_text());obj[key]=value;path.write_text(json.dumps(obj,indent=2)+'\n')
        trial('unchanged-held-package')
        trial('changed-firmware',lambda p:(p/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin').write_bytes(b'bad'))
        trial('missing-file',lambda p:(p/'requirements.txt').unlink())
        trial('unexpected-file',lambda p:(p/'extra.txt').write_text('unexpected'))
        trial('resealed-false-soak-claim',lambda p:edit_json(p/'qualification/summary.json','six_hour_soak_passed',True),True)
        trial('resealed-missing-findings',lambda p:edit_json(p/'qualification/summary.json','open_findings',[]),True)
        trial('resealed-kit-change',lambda p:(p/'install/sectors/b1-a000.bin').write_bytes(b'bad'),True)
        trial('resealed-promotion-claim',lambda p:edit_json(p/'package-manifest.json','promotion_held',False),True)
        def traversal(p):
            path=p/'package-manifest.json';m=json.loads(path.read_text());m['files']['../outside']=dict(bytes=0,sha256='0'*64);path.write_text(json.dumps(m))
        trial('path-traversal',traversal,True)
    report=dict(passed=True,board_access=False,native_debugging=False,checks=checks,package_manifest_sha256=hashlib.sha256((package/'package-manifest.json').read_bytes()).hexdigest())
    a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
