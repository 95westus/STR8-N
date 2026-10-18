"""Verify the complete public image and reproduce it from the extracted ZIP."""
import hashlib,json,zipfile,tempfile,importlib.util,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
    prep=read(OUT/'preparation-full-image-r1.json');checks=[]
    for info in prep['assets'].values():assert sha(Path(info['path']))==info['sha256']
    with tempfile.TemporaryDirectory(prefix='bf1-full-extract-',dir=ROOT/'tmp') as tmp:
        k=Path(tmp)
        with zipfile.ZipFile(OUT/'str8n-2.0bf1-firmware-package.zip') as z:
            assert len(z.namelist())==len(set(z.namelist())) and z.testzip() is None
            assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist());z.extractall(k)
        manifest=read(k/'public-manifest.json')
        for name,info in manifest['files'].items():assert sha(k/name)==info['sha256'] and (k/name).stat().st_size==info['bytes']
        for row in (k/'SHA256SUMS').read_text().splitlines():
            digest,name=row.split('  ',1);assert sha(k/name)==digest
        checks.append('ZIP inventory, exact manifest and all checksums')
        composer=k/'release/bf1-prerelease/build_full_image.py';spec=importlib.util.spec_from_file_location('public_composer',composer);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        data,ranges=m.compose(k/'release/candidates/batchfix-r1/payload',read(k/'firmware/full-image-reference.json'))
        assert data==(k/'firmware/str8n-2.0bf1-firmware.bin').read_bytes()==(OUT/'str8n-2.0bf1-firmware.bin').read_bytes()
        assert ranges==read(k/'firmware/firmware-layout.json')['ranges'];checks.append('public extracted composer reproduces every full-image byte')
        pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json');assert manifest['artifacts']==pin['artifacts']
        for name,info in pin['artifacts'].items():assert sha(k/'release/candidates/batchfix-r1/payload'/name)==info['sha256']
        checks.append('all 19 original component pins unchanged')
        provenance=read(k/'release/candidates/batchfix-r1/source-provenance.json');assert len(provenance)==97
        for name,info in provenance.items():assert sha(k/'release/candidates/batchfix-r1'/name)==info['sha256']
        checks.append('all 97 firmware source files unchanged')
        for p in k.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if re.match(r'[a-z]+:',link):continue
                target=(p.parent/link.split('#')[0]).resolve();assert target.is_relative_to(k.resolve()) and target.is_file()
        checks.append('all packaged guide links resolve')
        assert not any(p.name.lower() in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl') for p in k.rglob('*'));checks.append('no captured device dump or serial log')
        assert len(data)==131072 and data[:32768]==b'\xff'*32768;checks.append('full 128 KiB geometry and erased B0')
    result=dict(passed=True,cases=len(checks),checks=checks,preparation_sha256=sha(OUT/'preparation-full-image-r1.json'),image_sha256=sha(OUT/'str8n-2.0bf1-firmware.bin'),test_sha256=sha(Path(__file__)),board_access=False)
    p=Q/'bf1-full-image-package-tests-2026-10-17-r1.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
