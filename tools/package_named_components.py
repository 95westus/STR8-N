"""Package a verified naming candidate; no rebuild, serial IO or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def package(build, output, *, label='str8n-components-base1-pr05-sanitized-review-r1'):
    build, output = Path(build).resolve(), Path(output).resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', label):
        raise ValueError('Package label must be a single directory name')
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
                    'requirements-console.txt','firmware/memory-agent/profile.example.json',
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
    examples=build/'examples'
    if examples.exists():
        inventory=examples/'EXAMPLES-MANIFEST.json'
        actual={p.relative_to(examples).as_posix() for p in examples.rglob('*') if p.is_file()}
        if inventory.is_file():
            example_manifest=json.loads(inventory.read_text())
            if example_manifest['F_rebuilt'] or example_manifest['Foundation_sha256']!=manifest['Foundation_sha256']:
                raise ValueError('Examples do not match frozen Foundation')
            if actual!=set(example_manifest['artifacts'])|{'EXAMPLES-MANIFEST.json'}:
                raise ValueError('Unexpected/missing example package files')
            for file,info in example_manifest['artifacts'].items():
                body=(examples/file).read_bytes()
                if len(body)!=info['bytes'] or hashlib.sha256(body).hexdigest()!=info['sha256']:
                    raise ValueError('Changed example: '+file)
            for cpu in ('65c02','65c816-e'):
                tested=json.loads((examples/f'tests-examples-{cpu}.json').read_text())
                if not tested['passed']:raise ValueError('Example checks failed: '+cpu)
                asm_sha=next(info['sha256'] for info in manifest['artifacts'].values()
                             if info['component']=='ASM' and info.get('load')=='0200')
                if tested['DEV_ASM_sha256']!=asm_sha:
                    raise ValueError('Examples were tested with a different DEV ASM')
                for file,digest in tested['example_payload_sha256'].items():
                    if hashlib.sha256((examples/'payload'/file).read_bytes()).hexdigest()!=digest:
                        raise ValueError('Example report does not cover shipped bytes: '+file)
        elif any(Path(file).suffix not in ('.asm','.s','.cfg','.json','.md','.txt') for file in actual):
            raise ValueError('Compiled examples require a verified examples manifest')
        members.update('examples/'+file for file in actual)
    for file in ('tests-memory-65c02.json','tests-memory-65c816-e.json','REUSED-TESTS.json','SOURCE-RECONSTRUCTION.json','MON-SERVICES-RECONSTRUCTION.json','UTIL-DEV-RECONSTRUCTION.json','RELEASE-CANDIDATE.json','HOST-TESTS.json'):
        if (build/file).is_file():
            members.add(file)
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
    parser.add_argument('--label',default='str8n-components-base1-pr05-sanitized-review-r1',
                        help='Single root directory name inside the ZIP')
    args=parser.parse_args()
    package(args.build,args.out,label=args.label)
