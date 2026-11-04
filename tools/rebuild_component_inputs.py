"""Rebuild Foundation helpers and CLOCK from checked-in source; never assemble F."""
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build import cells
from build_base1 import build as build_helpers
from build_native_apps import normalized, sealed
from mona_branches import conservative_branches

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()


def clock_source(out):
    """Generate native return ABI and CLOCK staging from the ordinary source tree."""
    out.mkdir(parents=True, exist_ok=False)
    sources = {}
    for folder in ('src/core', 'src/include', 'monitors/native'):
        for path in (ROOT/folder).iterdir():
            if path.suffix not in ('.asm', '.inc'):
                continue
            target = out/path.name
            if target.exists() and folder == 'src/include' and '../include/' not in target.read_text():
                continue
            data = path.read_bytes()
            sources[path.relative_to(ROOT).as_posix()] = sha(data)
            target.write_text(data.decode('utf-8-sig'), encoding='utf-8', newline='\n')
    for name in ('batch-interface.inc', 'monitor-ui.inc'):
        path = ROOT/'monitors/src'/name
        sources[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
        shutil.copyfile(path, out/name)
    path = ROOT/'monitors/src/workbench-monitor-ui.inc'
    sources[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    ui = path.read_text()
    ui = ui[ui.index('W_UI_EXPECTED EQU'):ui.index('W_UI_ERROR:')]
    a, b = ui.index('W_UI_CALL:'), ui.index('W_UI_CHECK:')
    ui = ui[:a]+ui[b:]
    ui = re.sub(r'EQU \$663([0-8])', r'EQU $5B1\1', ui)
    (out/'native-ui-check.inc').write_text(ui)
    for path in out.glob('*.inc'):
        text, _ = conservative_branches(normalized(path.read_text()), 'NI_'+re.sub(r'\W', '_', path.name)+'_')
        path.write_text(text, encoding='utf-8', newline='\n')
    logs = []
    def link(name, origin, end):
        path = out/(name+'.asm')
        text = re.sub(r'^\s*XDEF\s+.*$', '', path.read_text(), flags=re.M)
        text, _ = conservative_branches(normalized(text), name.upper().replace('-', '_')+'_LONG_')
        path.write_text(text, encoding='utf-8', newline='\n')
        assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
        if not assembler or not linker:
            raise RuntimeError('WDC02AS and WDCLN must be on PATH')
        for command in ([assembler, '-G', '-L', '-S', '-W', name+'.asm'],
                        [linker, '-g', '-s', '-t', f'-c{origin:04X}', '-hm19', '-j', '-o', name+'.s19', name+'.obj']):
            result = subprocess.run(command, cwd=out, capture_output=True, text=True)
            logs.append(dict(command=command, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
            (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n')
            if result.returncode:
                raise RuntimeError('Source reconstruction failed; see '+str(out/'build-log.json'))
        symbols = {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (out/(name+'.map')).read_text(), re.M)}
        memory = cells(out/(name+'.s19'))
        if set(memory) != set(range(origin, symbols[end])):
            raise ValueError('Noncontiguous reconstructed module: '+name)
        return bytes(memory[a] for a in range(origin, symbols[end])), symbols
    ret, symbols = link('native-return', 0x5e00, 'NR_END')
    if len(ret) > 510:
        raise ValueError('Native return code exceeds its original allocation')
    (out/'native-api.inc').write_text(f'NR_CALL EQU ${symbols["NR_CALL"]:04X}\n')
    clock, symbols = link('clock', 0x2000, 'APP_END')
    if symbols['APP_END'] >= 0x5b00:
        raise ValueError('CLOCK code exceeds its original allocation')
    header = bytearray(b'\xff'*32)
    header[:8] = b'RP'+bytes((1,0))+b'PR05'
    header[8:10] = len(clock).to_bytes(2,'little')
    header[10:12] = (0x2000).to_bytes(2,'little')
    header[12:14] = (0x2000).to_bytes(2,'little')
    header[14:18] = (1).to_bytes(4,'little')
    image = sealed(bytes(header)+clock, 3*4096)
    return image, sources


def rebuild(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    lock = json.loads((ROOT/'components/inputs/LOCK.json').read_text())
    expected = {row['path']:row for row in lock['reconstructed_inputs'] if row['rebuild_recipe']=='tools/rebuild_component_inputs.py'}
    mapping, witness = {}, []
    def record(name, path):
        key = 'components/inputs/accepted-base1/'+name
        row = expected[key]
        data = path.read_bytes()
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('Reconstructed input differs from qualified bytes: '+name)
        mapping[name] = path
        witness.append(dict(input=name, bytes=len(data), sha256=sha(data),
                            file=path.relative_to(out).as_posix(), result='EXACT_MATCH'))
    helpers = out/'helpers'
    build_helpers(helpers)
    helper_manifest = json.loads((helpers/'base1-manifest.json').read_text())
    if helper_manifest['F_rebuilt']:
        raise ValueError('Foundation must remain frozen')
    for component in ('CONFIG', 'OPAQUE', 'MAP', 'READBACK', 'DEMO'):
        filename = f'STR8N-F-{component}-RAM.bin'
        record('foundation/firmware/payload/'+filename, helpers/'payload'/filename)
    staging = out/'clock-source'
    clock, clock_sources = clock_source(staging)
    for index, address in enumerate((0xb000, 0xc000, 0xd000)):
        name = f'native/payload/B2-{address:04X}.bin'
        path = out/('B2-'+f'{address:04X}'+'.bin')
        path.write_bytes(clock[index*4096:(index+1)*4096])
        record(name, path)
    if set(expected) != {'components/inputs/accepted-base1/'+name for name in mapping}:
        raise ValueError('Incomplete source reconstruction')
    receipt = dict(schema=1, inputs=witness, F_rebuilt=False, F_sha256=helper_manifest['F_sha256'],
                   helper_source=helper_manifest['source'], clock_source=clock_sources,
                   complete_source_only_build=False, board_access=False)
    (out/'SOURCE-RECONSTRUCTION.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return mapping, staging, receipt
