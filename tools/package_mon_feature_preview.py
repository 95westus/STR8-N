"""Package the scoped optional MON/tools preview; copy existing firmware only."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LABEL='STR8N-MON-g8-tools-preview1'
sha=lambda b:hashlib.sha256(b).hexdigest()


def package(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=out/LABEL;root.mkdir()
    report_path=ROOT/'monitors/validation/2609-mon-feature-install.json'
    live=json.loads(report_path.read_text())
    assert live['passed'] and live['installed_services_g4_passed'] and live['owner_RAM_ZP_restored_verified']
    assert live['COM8_released'] and live['sequence_after']==1031 and live['default_boot']=='S'
    rtc=json.loads((ROOT/'monitors/validation/2609-mon-feature-rtc.json').read_text())
    assert rtc['passed'] and rtc['owner_RAM_ZP_restored_verified'] and rtc['historical_samples_and_baselines_retained']
    original=ROOT/'dist/base1-0.3.0/STR8N-F-BASE1-0.3.0.zip'
    foundation=root/'foundation';foundation.mkdir()
    with zipfile.ZipFile(original) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            path=Path(name);assert path.parts[0]=='STR8N-F-BASE1-0.3.0'
            relative=Path(*path.parts[1:]);target=(foundation/relative).resolve()
            assert target.is_relative_to(foundation.resolve()) and not name.endswith('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))
    from verify_release_kit import verify
    verify(foundation)
    payload=root/'monitor/payload';payload.mkdir(parents=True)
    host=root/'monitor/host';host.mkdir()
    (host/'time_samples.py').write_bytes((ROOT/'tools/time_samples.py').read_bytes())
    for folder,variants in [('g00000008-r2',('A','B')),
                            ('services-g00000004',('E','B2 bundle'))]:
        source=ROOT/'monitors/candidates'/folder
        manifest=json.loads((source/'manifest.json').read_text())
        for name,info in manifest['artifacts'].items():
            if info['variant'] not in variants:continue
            body=(source/name).read_bytes();assert sha(body)==info['sha256']
            (payload/name).write_bytes(body)
            if info['variant']=='B2 bundle':
                for index in range(3):
                    (payload/f'STR8N-TOOLS-B2-{0x8000+index*4096:04X}.bin').write_bytes(body[index*4096:(index+1)*4096])
    (root/'MONITOR-MANUAL.md').write_bytes((ROOT/'docs/MON_FEATURE_PREVIEW.md').read_bytes())
    (root/'README.md').write_text(
        '# STR8-N optional MON/tools candidate\n\n'
        '**Optional feature preview; see the precise hardware limits in the manual.**\n\n'
        'Requires frozen N-F v0.3.0 BASE1/PR05. MON/g8, services/g4, WB2/g5 and PROGRAM/SP1.\n\n'
        'Read [the monitor manual](MONITOR-MANUAL.md) before installation. '
        'The unchanged [foundation manual](foundation/README.md) includes migration, recovery and Python terminal instructions.\n\n'
        'Run `python verify_candidate.py`, then '
        '`python foundation/tools/nf_console.py`. No tool connects or flashes automatically.\n\n'
        'ASM/DEBUG and full b35/rc1 replacement remain unfinished.\n',encoding='utf-8')
    verifier='''"""Verify candidate bytes only; no serial imports or port access."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
m=json.loads((root/'CANDIDATE-MANIFEST.json').read_text())
files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert files==set(m['files'])|{'CANDIDATE-MANIFEST.json'}
for name,record in m['files'].items():
 p=(root/name).resolve();assert p.is_relative_to(root)
 body=p.read_bytes();assert len(body)==record['bytes'] and hashlib.sha256(body).hexdigest()==record['sha256'],name
print('PASS preview hashes; scoped hardware evidence included')
'''
    (root/'verify_candidate.py').write_text(verifier,encoding='utf-8')
    evidence=root/'monitor/evidence';evidence.mkdir()
    (evidence/'2609-installed-features.json').write_bytes(report_path.read_bytes())
    for name in ('2609-mon-feature-rtc.json','2609-mon-features-ram.json','2609-maint-reload-g4-RAM.json'):
        (evidence/name).write_bytes((ROOT/'monitors/validation'/name).read_bytes())
    for name in ('2512-program-cleanup-time-samples.json','2512-storage-apps-ram.json'):
        (evidence/name).write_bytes((ROOT/'validation'/name).read_bytes())
    source=root/'source';source.mkdir()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output',str(source/f'STR8N-MON-{head[:7]}-source.zip'),'HEAD'],cwd=ROOT,check=True)
    (source/'package_mon_feature_preview.py').write_bytes(Path(__file__).read_bytes())
    manifest=dict(status='SCOPED_FEATURE_PREVIEW_HARDWARE_ACCEPTED',
                  F_frozen=True,foundation_operator_ZIP_sha256=sha(original.read_bytes()),
                  component_source_commit=head,terminal='Unchanged foundation Python Serial Console0.1.0',
                  product='Optional STR8-N MON/tools; distinct from N-Fv0.3.0',
                  files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
                         for p in sorted(root.rglob('*')) if p.is_file()})
    (root/'CANDIDATE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    subprocess.run([__import__('sys').executable,str(root/'verify_candidate.py')],check=True)
    path=out/(LABEL+'.zip')
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for member in sorted(root.rglob('*')):
            if member.is_file():archive.write(member,Path(LABEL)/member.relative_to(root))
    with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
    (out/'SHA256SUMS.txt').write_text(sha(path.read_bytes())+'  '+path.name+'\n')
    print(path)
    print('No firmware build, flash operation, Git ref change or publication.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    package(parser.parse_args().out)
