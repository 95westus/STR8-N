"""Package accepted native components with the unchanged Foundation operator kit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
LABEL='STR8N-native-g0000000A-candidate1'
sha=lambda b:hashlib.sha256(b).hexdigest()


def package(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True);stage=out/LABEL;stage.mkdir()
    receipt=json.loads((ROOT/'monitors/validation/2512-native-utilities.json').read_text())
    assert receipt['passed'] and receipt['F_writes']==0
    original=ROOT/'dist/base1-0.3.0/STR8N-F-BASE1-0.3.0.zip'
    foundation=stage/'foundation'
    with zipfile.ZipFile(original) as z:
        for name in z.namelist():
            parts=Path(name).parts
            assert parts[0]=='STR8N-F-BASE1-0.3.0'
            target=(foundation/Path(*parts[1:])).resolve()
            assert target.is_relative_to(foundation.resolve()) and not name.endswith('/')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    f=(foundation/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text());assert len(f)==4096 and sha(f)==freeze['sha256']
    (stage/'F.bin').write_bytes(f)
    native=ROOT/'monitors/candidates/native-g00000001-r8'
    svc=ROOT/'monitors/candidates/services-g00000006-native-r3'
    mon=ROOT/'monitors/candidates/g0000000a-ui1'
    payload=stage/'native/payload';payload.mkdir(parents=True)
    catalog=dict(schema=1,F_sha256=sha(f),Foundation='0.3.0 g00000001 BASE1/PR05',
                 MON='0.1.0-dev g0000000A',native='g1 / loader r7 / HOST r8',targets=[])
    def target(bank,address,body,**flags):
        name=f'B{bank}-{address:04X}'+('-code3072' if len(body)==3072 else '')+'.bin'
        (payload/name).write_bytes(body)
        catalog['targets'].append(dict(bank=bank,address=f'{address:04X}',file='native/payload/'+name,sha256=sha(body),**flags))
    sm=json.loads((svc/'manifest.json').read_text());parts={v['variant']:(svc/n).read_bytes() for n,v in sm['artifacts'].items()}
    b2=parts['B2 bundle']+(native/'CLOCK-g00000001-flash.bin').read_bytes()+(native/'FLASH-MAINT-g00000001-flash.bin').read_bytes()
    assert len(b2)==32768
    for n in range(8):target(2,0x8000+n*4096,b2[n*4096:(n+1)*4096])
    target(3,0x8000,(native/'RTC-BASE1-B3-8000.bin').read_bytes())
    target(3,0x9000,(native/'RTC-HISTORY-B3-9000.bin').read_bytes()[:3072],preserve_RTC_metadata=True)
    mm=json.loads((mon/'manifest.json').read_text())
    for name,v in mm['artifacts'].items():
        if v['variant'] in ('A','B'):target(3,0xA000 if v['variant']=='A' else 0xB000,(mon/name).read_bytes())
    target(3,0xE000,parts['E'])
    assert len(catalog['targets'])==13
    (stage/'NATIVE-COMPONENTS.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
    tools=stage/'tools';tools.mkdir()
    for name in ('nf_native_images.py','nf_factory_image.py'):(tools/name).write_bytes((ROOT/'tools'/name).read_bytes())
    for name in ('NATIVE_UTILITIES_MANUAL.md','2512_NATIVE_UTILITIES_ACCEPTANCE.md'):
        text=(ROOT/'docs'/name).read_text(encoding='utf-8')
        if name=='2512_NATIVE_UTILITIES_ACCEPTANCE.md':
            text=text.replace('../monitors/validation/2512-native-utilities.json','evidence/2512-native-utilities.json')
        (stage/name).write_text(text,encoding='utf-8')
    (stage/'LICENSE').write_bytes((ROOT/'LICENSE').read_bytes())
    evidence=stage/'evidence';evidence.mkdir();(evidence/'2512-native-utilities.json').write_bytes((ROOT/'monitors/validation/2512-native-utilities.json').read_bytes())
    examples=stage/'examples';examples.mkdir();(examples/'NFCOPY.asm').write_bytes((ROOT/'examples/NFCOPY.asm').read_bytes())
    (examples/'NFCOPY-3000.bin').write_bytes(bytes.fromhex('A9 50 20 6D 7E 4C 67 7E'))
    (stage/'README.md').write_text('''# STR8-N native utilities candidate

MON A/B g0000000A above frozen N-F 0.3.0 BASE1/PR05.

Read NATIVE_UTILITIES_MANUAL.md and 2512_NATIVE_UTILITIES_ACCEPTANCE.md.
This is a local, unpublished candidate; remaining full-b35 gates are explicit.
The complete profile reserves B2/B3 (64 KiB including F and C/D).

Run `python verify_candidate.py`, then `python foundation/tools/nf_console.py`.
The unchanged Foundation kit includes its Python serial terminal, RAM migrator,
CONFIG/OPAQUE tools and installation manual. F.bin is its exact frozen F.

Native sector preparation: `python tools/nf_native_images.py --help`.
Factory image preparation: `python tools/nf_factory_image.py --help`.
Neither preparer opens a port. Vendor WDC firmware and board captures are absent.
No board connection, flashing, Git ref change or publication occurs on extraction.
''',encoding='utf-8')
    verifier='''"""Check this extracted candidate only. No serial or application imports."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
m=json.loads((root/'CANDIDATE-MANIFEST.json').read_text())
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert actual==set(m['files'])|{'CANDIDATE-MANIFEST.json'}
for name,meta in m['files'].items():
 p=(root/name).resolve();assert p.is_relative_to(root)
 b=p.read_bytes();assert len(b)==meta['bytes'] and hashlib.sha256(b).hexdigest()==meta['sha256'],name
assert (root/'F.bin').read_bytes()==(root/'foundation/firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
print('PASS extracted native candidate; frozen F and unchanged Foundation runtime verified; no device access')
'''
    (stage/'verify_candidate.py').write_text(verifier,encoding='utf-8')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    source=stage/'source';source.mkdir()
    subprocess.run(['git','archive','--format=zip','--output',str(source/('STR8N-'+head[:7]+'-source.zip')),'HEAD'],cwd=ROOT,check=True)
    manifest=dict(schema=1,status='LOCAL_NATIVE_UTILITIES_CANDIDATE_2512_ACCEPTED_NOT_FULL_B35_RELEASE',
        source_commit=head,F_sha256=sha(f),F_frozen=True,firmware_builds_for_packaging=0,
        foundation_operator_ZIP_sha256=sha(original.read_bytes()),terminal='Unchanged published Foundation console0.1.0',
        new_factory_flash_qualified=False,new_candidate_migration_tested=False,serial_access=False,published=False,
        files={p.relative_to(stage).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(stage.rglob('*')) if p.is_file()})
    (stage/'CANDIDATE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    path=out/(LABEL+'.zip')
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,Path(LABEL)/p.relative_to(stage))
    (out/'SHA256SUMS.txt').write_text(sha(path.read_bytes())+'  '+path.name+'\n',encoding='ascii')
    print(path);print('No firmware rebuild, serial access, flashing or publication.')
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();package(a.out)
