"""Create an explicit, deterministic beta35 source/payload review archive."""
import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'release/beta35'
ROOT_FILES = ['README.md','LICENSE','build.py','verify.py','release.json',
              'source-provenance.json','layout.json']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--extract',required=True,type=Path)
    args = p.parse_args()
    report = json.loads((args.build/'build-report.json').read_text())
    meta = json.loads((SOURCE/'release.json').read_text())
    assert report['passed'] and report['source_only'] and report['binary_inputs']==[]
    assert report['build_script_sha256']==sha((SOURCE/'build.py').read_bytes())
    assert report['release_manifest_sha256']==sha((SOURCE/'release.json').read_bytes())
    assert report['artifacts']==meta['expected']
    assert not args.out.exists() and not args.extract.exists(), 'Use new archive/extract paths'
    provenance = json.loads((SOURCE/'source-provenance.json').read_text())
    files = {n:(SOURCE/n).read_bytes() for n in ROOT_FILES+sorted(provenance)}
    for name,info in meta['expected'].items():
        data = (args.build/'payload'/name).read_bytes()
        assert {'sha256':sha(data),'bytes':len(data)}==info, name
        files['payload/'+name] = data
    manifest = {'version':'2.0b35','generation':47,'installation_permitted':False,
                'purpose':'Local source/payload review; migration and physical gates remain open',
                'build_script_sha256':report['build_script_sha256'],
                'candidate_build_sha256':meta['candidate_build_sha256'],
                'deferred':['ACIA','crypto'],
                'files':{n:{'sha256':sha(d),'bytes':len(d)} for n,d in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest,indent=2)+'\n').encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info = zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(args.out) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(files)
        assert set(z.namelist())==set(files)
        assert z.testzip() is None
        z.extractall(args.extract)
    # Import the extracted verifier, including its extracted build helper.
    sys.path.insert(0,str(args.extract.resolve()))
    spec = importlib.util.spec_from_file_location('review_verify',args.extract/'verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verified = module.verify(args.extract)
    result = {**verified,'archive':str(args.out.resolve()),'sha256':sha(args.out.read_bytes()),
              'bytes':args.out.stat().st_size,'extracted':str(args.extract.resolve()),
              'build_report_sha256':sha((args.build/'build-report.json').read_bytes()),
              'excluded':['full-bank images','vendor firmware','CLOCK 1.9','legacy MAINT payloads',
                          'board data/backups','private evidence','unrelated v2.1 source']}
    args.out.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
