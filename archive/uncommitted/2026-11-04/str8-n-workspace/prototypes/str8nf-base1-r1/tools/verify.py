"""Verify the public source preview without an assembler or board access."""
import argparse,hashlib,json,re
from pathlib import Path
from build import cells
from oip import allowed,crc,header

ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
PUBLIC_FILES=('.gitignore','.gitattributes','README.md','LICENSE','CHANGELOG.md','ORIGIN.json','baseline.json','release.json','profiles.json','system-baseline.json')
PUBLIC_DIRS=('src','tools','tests','docs','firmware','validation','.github')


def public_files():
    result=[ROOT/name for name in PUBLIC_FILES]
    for directory in PUBLIC_DIRS:
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':result.append(path)
    return sorted(result,key=lambda p:p.relative_to(ROOT).as_posix())


def require(condition,message):
    if not condition:raise ValueError(message)


def verify(build=None,compare=None):
    raise ValueError('BASE1 uses tools/verify_base1.py; historical CPU evidence is not current qualification')
    if 'candidate' in read(ROOT/'release.json').get('status',''):
        raise ValueError('Unqualified PR05 candidate: use tools/check_fcompact.py for static layout checks; historical CPU evidence does not apply')
    build=Path(build or ROOT/'firmware').resolve();baseline=read(ROOT/'baseline.json');manifest=read(build/'manifest.json')
    require(manifest['passed'] and manifest['hardware_access'] is False,'Build manifest failed or claims hardware access')
    require(set(manifest['artifacts'])==set(baseline['artifacts']),'Artifact set mismatch')
    for name,expected in baseline['artifacts'].items():
        path=build/'payload'/name;data=path.read_bytes();artifact=manifest['artifacts'][name]
        require(len(data)==expected['bytes'] and sha(path)==expected['sha256'],'BIN mismatch: '+name)
        require(artifact['sha256']==sha(path) and artifact['bytes']==len(data),'Manifest mismatch: '+name)
        decoded=cells(path.with_suffix('.s19'));start=int(artifact['address'],16)
        require(set(decoded)==set(range(start,start+len(data))),'S19 address/length mismatch: '+name)
        require(bytes(decoded[a] for a in range(start,start+len(data)))==data,'S19 bytes mismatch: '+name)
        if compare:
            other=Path(compare)/'payload'/name
            require(other.read_bytes()==data,'Reproducibility mismatch: '+name)
    boot=(build/'payload/STR8N-F-BOOT-4096.bin').read_bytes()
    require(boot[:4]==b'SN\x02\0' and boot[0xffc:0xffe]==b'\x04\xf0','F signature or reset vector mismatch')
    actual={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'src').rglob('*')) if p.is_file()}
    require(manifest['source']==actual,'Source hashes differ from built candidate')
    symbols=read(build/'symbols.json')
    for component in ('worker','vectors','boot','config','opaque','demo'):require(component in symbols,'Missing symbol map')
    # Cross-check protocol serialization rather than just importing the helper.
    require(crc(b'123456789')==0x29b1,'CCITT test vector mismatch')
    frame=header(1,0x90,bytes(4096),0x1234)
    require(frame[:12]==b'OIP1\x01\x01\x01\x90\x00\x10\x34\x12' and len(frame)==20,'OIP1 header mismatch')
    require(crc(frame[:18])==int.from_bytes(frame[18:20],'little'),'Header CRC mismatch')
    for sector in (0xc0,0xd0,0xf0):
        require(not allowed(3,sector),'Protected sector admitted')
        try:header(3,sector)
        except ValueError:pass
        else:raise ValueError('Protected header serialized')
    require(not allowed(4,0x90) and not allowed(1,0x91),'Noncanonical target admitted')
    for path in (ROOT/'README.md',ROOT/'CHANGELOG.md',*(ROOT/'docs').glob('*.md')):
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            relative=target.split('#')[0];resolved=(path.parent/relative).resolve()
            require(resolved.is_relative_to(ROOT) and resolved.exists(),f'Broken/nonlocal link in {path.name}: {target}')
    record=read(ROOT/'validation/qualification.json')
    require(record['passed'] and record['checks']==26 and not record['hardware'] and not record['serial_access'],'Missing CPU qualification')
    require(record['artifacts']=={name:data['sha256'] for name,data in manifest['artifacts'].items()},'Qualification artifact binding mismatch')
    require(record['test_sources']=={name:sha(ROOT/name) for name in record['test_sources']},'Qualification test-source mismatch')
    provenance=read(ROOT/'ORIGIN.json')['files']
    for name,record in provenance.items():
        require(sha(ROOT/name)==record.get('extracted_sha256',record['sha256']),'Provenance mismatch: '+name)
    files=public_files()
    require(all(p.exists() for p in files),'Missing public file')
    for path in files:
        rel=path.relative_to(ROOT).as_posix()
        require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(),'Outside/symlink input: '+rel)
        require(path.suffix.lower() not in ('.obj','.lst','.map','.log','.tmp'),'Unexpected public build/log file: '+rel)
        require(path.suffix.lower()!='.bin' or rel.startswith('firmware/payload/'),'Unexpected binary capture: '+rel)
        if path.suffix in ('.py','.asm','.inc','.md','.json','.yml'):
            require(b'\r\n' not in path.read_bytes(),'Noncanonical line endings: '+rel)
            text=path.read_text(encoding='utf-8')
            # Unmodified pinned upstream emulator comments include its author's
            # old example path; it is not a build input or this owner's data.
            if not rel.startswith('tests/vendor/'):
                require(not re.search(r'(?:C:[\\/](?:SRC|Users)[\\/]|\bA10[A-Z0-9]{6}\b)',text,re.I),'Machine-specific/private reference: '+rel)
    package_manifest=ROOT/'PACKAGE-MANIFEST.json'
    if package_manifest.exists():
        declared=read(package_manifest)['files'];actual={p.relative_to(ROOT).as_posix():sha(p) for p in files}
        require(declared==actual,'Package manifest mismatch')
    print(f'PASS {len(files)} public files; four payload hashes, S19s, source/qualification binding and docs; no device access',flush=True)
    return files


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path);parser.add_argument('--compare',type=Path)
    args=parser.parse_args();verify(args.build,args.compare)
