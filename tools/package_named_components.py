"""Package a verified naming candidate; no rebuild, serial IO or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(build, output):
    build, output = Path(build).resolve(), Path(output).resolve()
    manifest = json.loads((build/'COMPONENTS.json').read_text())
    members = set(manifest['artifacts'])
    for file, info in manifest['artifacts'].items():
        body = (build/file).read_bytes()
        if len(body)!=info['bytes'] or hashlib.sha256(body).hexdigest()!=info['sha256']:
            raise ValueError('Changed named artifact: '+file)
    for cpu in ('65c02','65c816-e'):
        result = json.loads((build/f'tests-{cpu}.json').read_text())
        if not result['passed']:
            raise ValueError('Naming checks failed: '+cpu)
        members.add(f'tests-{cpu}.json')
    members.update(('README.md','LICENSE','THIRD_PARTY_NOTICES.md','COMPONENTS.json','NATIVE-COMPONENTS.json','product-names.json',
                    'preset-assets.json','str8n-terminal.py','str8n-util-memory.py',
                    'memory-agent-build/manifest.json'))
    agent = json.loads((build/'memory-agent-build/manifest.json').read_text())
    members.add('memory-agent-build/'+agent['file'])
    for cpu in ('65c02','65c816-e'):
        report = json.loads((build/f'tests-memory-{cpu}.json').read_text())
        if not report['passed'] or report['agent_sha256']!=agent['sha256']:
            raise ValueError('MEMORY checks do not cover this agent: '+cpu)
    for folder in ('tools','terminal'):
        members.update(p.relative_to(build).as_posix() for p in (build/folder).rglob('*.py'))
    members.update(p.relative_to(build).as_posix() for p in (build/'docs').glob('*.md'))
    for file in ('tests-memory-65c02.json','tests-memory-65c816-e.json','REUSED-TESTS.json','SOURCE-RECONSTRUCTION.json','MON-SERVICES-RECONSTRUCTION.json','UTIL-DEV-RECONSTRUCTION.json'):
        if (build/file).is_file():
            members.add(file)
    label = 'str8n-components-base1-pr05-sanitized-review-r1'
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in sorted(members):
            archive.write(build/file,label+'/'+file)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive integrity failure')
        for file, info in manifest['artifacts'].items():
            if hashlib.sha256(archive.read(label+'/'+file)).hexdigest()!=info['sha256']:
                raise ValueError('Archive payload verification failed')
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(checksum+'  '+output.name+'\n',encoding='ascii')
    receipt = dict(passed=True, ZIP=str(output), sha256=checksum, members=len(members),
                   payloads=len(manifest['artifacts']), board_access=False, published=False,
                   status='OFFLINE_NAMING_CANDIDATE_LIVE_QUALIFICATION_PENDING')
    (build/'packaging-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    package(args.build,args.out)
