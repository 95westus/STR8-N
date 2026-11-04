"""Extract an explicit public-source allowlist into a standalone F/opaque tree.

No hardware, Git mutation, remote operation or private capture is copied.
The exported assembler inputs are the qualified derived b15 sources, replacing
the historical chain of source transformations with directly editable inputs.
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/pr04-b15-cancel-r3'
CFG=ROOT/'output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-build-r1'
sha=lambda data:hashlib.sha256(data).hexdigest()


def main(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT) and not out.exists()
    out.mkdir(parents=True);origins={}
    def copy(source,destination):
        source=source.resolve();dest=out/destination;dest.parent.mkdir(parents=True,exist_ok=True)
        raw=source.read_bytes();dest.write_bytes(raw)
        origins[destination]=dict(source=source.relative_to(ROOT).as_posix(),sha256=sha(raw))
    # Copy INCLUDE closure only. No OBJ/S19/LST, unrelated applications or data.
    visited=set()
    def closure(source,destination):
        destination=Path(destination).as_posix()
        if destination in visited:return
        visited.add(destination);copy(source,destination)
        for name in re.findall(r'\bINCLUDE\s+"([^"]+)"',source.read_text(),re.I):
            closure((source.parent/name).resolve(),(Path(destination).parent/name).as_posix())
    for name in ('str8n-v2-boot.asm','str8n-v2-worker.asm','str8n-v2-vectors.asm','ram-installer.asm','service-eq.inc'):
        closure(BASE/'s/core'/name,'src/core/'+name)
    closure(CFG/'s/core/ram-config.asm','src/core/ram-config.asm')
    # The included direct CONFIG private engine is separate from OIP1's engine.
    # RAM-only demonstration provides a minimal user application/return example.
    demo=ROOT/'prototypes/boot-record-v2/f-user-demo-b15.asm'
    copy(demo,'src/core/ram-demo.asm')
    copy(ROOT/'LICENSE','LICENSE')
    copy(ROOT/'tools/installer/flash_model.py','tests/flash_model.py')
    # A small BSD-licensed emulator closure makes CPU checks offline/repeatable.
    py65=ROOT/'BUILD/v1.30/local/test-deps';py816=ROOT/'BUILD/test-deps-816'
    for name in ('py65/__init__.py','py65/devices/__init__.py','py65/devices/mpu6502.py','py65/devices/mpu65c02.py',
                 'py65/utils/__init__.py','py65/utils/conversions.py','py65/utils/devices.py'):
        copy(py65/name,'tests/vendor/'+name)
    copy(py65/'py65-1.2.0.dist-info/LICENSE.txt','tests/vendor/PY65-LICENSE.txt')
    copy(py816/'py65816/devices/mpu65c816.py','tests/vendor/py65816/devices/mpu65c816.py')
    copy(py816/'LICENSE','tests/vendor/PY65816-LICENSE.txt')
    for name in ('tests/vendor/py65816/__init__.py','tests/vendor/py65816/devices/__init__.py'):
        (out/name).write_text('',encoding='ascii')
    baseline={}
    for name,file in (('STR8N-F-BOOT-4096.bin',BASE/'payload/f-offline-component.bin'),
                      ('STR8N-F-CONFIG-RAM.bin',CFG/'payload/2609-CONFIG-RAM.bin'),
                      ('STR8N-F-OPAQUE-RAM.bin',BASE/'payload/ram-installer-offline.bin'),
                      ('STR8N-F-DEMO-RAM.bin',ROOT/'output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-ready/b15-F-DEMO-RAM.bin')):
        raw=file.read_bytes();baseline[name]=dict(bytes=len(raw),sha256=sha(raw))
    (out/'baseline.json').write_text(json.dumps(dict(identity='b15 direct-source extraction',compatibility='PR04',generation='8000000F',
        firmware_identity_unchanged=True,artifacts=baseline),indent=2)+'\n',encoding='utf-8')
    (out/'ORIGIN.json').write_text(json.dumps(dict(parent_project='https://github.com/95westus/STR8-N',
        extraction='Qualified derived b15 assembler sources and explicit include closure; no private board data',
        generated_symbol_and_image_includes='Regenerated/checked by the independent build; retained for auditability',
        third_party='BSD emulator files retain separate license notices',files=origins),indent=2)+'\n',encoding='utf-8')
    print('EXTRACTED',len(origins),'explicit source/license files;',out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)
