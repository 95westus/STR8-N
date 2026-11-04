"""Build only the changed MIN1 OPAQUE tool; reuse the frozen PR05 components.

No F/worker/vector rebuild, CPU model, serial access or installation occurs.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from build import cells, s19, save

ROOT = Path(__file__).resolve().parents[1]
F_SHA = 'ccb923340528a0764102fc270e39dd07c95a76569e19c4f60169e081712164d3'
sha = lambda data: hashlib.sha256(data).hexdigest()


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory')
    current = ROOT/'firmware/minimal-manifest.json'
    if current.exists():
        declared = json.loads(current.read_text())['artifacts']
    else:
        core_manifest = json.loads((ROOT/'firmware/manifest.json').read_text())
        system = json.loads((ROOT/'firmware/system-manifest.json').read_text())
        declared = dict(core_manifest['artifacts'], **system['artifacts'])
    reuse = ('STR8N-F-BOOT-4096.bin', 'STR8N-F-CONFIG-RAM.bin',
             'STR8N-F-DEMO-RAM.bin', 'STR8N-F-READBACK-RAM.bin')
    for name in reuse:
        data = (ROOT/'firmware/payload'/name).read_bytes()
        if len(data) != declared[name]['bytes'] or sha(data) != declared[name]['sha256']:
            raise ValueError('Changed frozen input: '+name)
    f = (ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    if len(f) != 4096 or sha(f) != F_SHA:
        raise ValueError('F is frozen for this release checkpoint')
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC assembler/linker must be on PATH')
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src', out/'s')
    payload = out/'payload'
    payload.mkdir()
    artifacts = {}
    for name in reuse:
        for suffix in ('.bin', '.s19'):
            shutil.copyfile((ROOT/'firmware/payload'/name).with_suffix(suffix),
                            (payload/name).with_suffix(suffix))
        artifacts[name] = dict(declared[name], reused_without_rebuild=True)
    core = out/'s/core'
    logs = []
    for command in ([assembler, '-G', '-L', '-S', '-W', '-I', str(core), 'ram-installer.asm'],
                    [linker, '-g', '-s', '-t', '-c0200', '-hm19', '-j',
                     '-o', 'ram-installer.s19', 'ram-installer.obj']):
        process = subprocess.run(command, cwd=core, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=process.returncode,
                         stdout=process.stdout, stderr=process.stderr))
        save(core/'ram-installer.log.json', logs)
        if process.returncode:
            raise RuntimeError('WDC failed; inspect '+str(core/'ram-installer.log.json'))
    symbols = {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$', (core/'ram-installer.map').read_text(), re.M)}
    memory = cells(core/'ram-installer.s19')
    end = symbols['INSTALLER_END']
    if not 0x200 < end <= 0x6500 or set(memory) != set(range(0x200, end)):
        raise ValueError('OPAQUE RAM extent mismatch')
    data = bytes(memory[address] for address in range(0x200, end))
    name = 'STR8N-F-OPAQUE-RAM.bin'
    (payload/name).write_bytes(data)
    (payload/name.replace('.bin', '.s19')).write_bytes(s19(data, 0x200, 0x200))
    artifacts[name] = dict(bytes=len(data), sha256=sha(data), address='0200', entry='0200',
                           reused_without_rebuild=False)
    save(out/'opaque-symbols.json', symbols)
    manifest = dict(passed=True, profile='MIN1', candidate=True, execution_qualified=False,
        hardware_access=False, CPU_simulations=0, assembly_builds=1,
        rebuilt_modules=['OPAQUE'], F_rebuilt=False, F_sha256=F_SHA,
        layout=json.loads((ROOT/'layout.json').read_text()), artifacts=artifacts,
        source={p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
                for p in sorted((ROOT/'src').rglob('*')) if p.is_file()},
        producer_sha256=sha(Path(__file__).read_bytes()))
    save(out/'minimal-manifest.json', manifest)
    print('PASS MIN1: OPAQUE rebuilt once;', len(data), 'bytes; F and other RAM tools reused')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.out)
