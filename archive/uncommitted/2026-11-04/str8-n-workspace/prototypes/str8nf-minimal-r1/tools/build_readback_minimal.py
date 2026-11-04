"""Build MIN1 owner-RAM/ZP readback/restore service only; no F rebuild."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from build import cells, s19, save
from build_system import long_branches

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory')
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC tools required')
    out.mkdir(parents=True)
    core = out/'s/core'
    shutil.copytree(ROOT/'src', out/'s')
    symbols = {}

    def link(name, start, end):
        logs = []
        for command in ([assembler, '-G', '-L', '-S', '-W', '-I', str(core), name+'.asm'],
                        [linker, '-g', '-s', '-t', f'-c{start:04X}', '-hm19', '-j',
                         '-o', name+'.s19', name+'.obj']):
            process = subprocess.run(command, cwd=core, capture_output=True, text=True)
            logs.append(dict(command=command, returncode=process.returncode,
                             stdout=process.stdout, stderr=process.stderr))
            save(core/(name+'.log.json'), logs)
            if process.returncode:
                raise RuntimeError('WDC failed; inspect '+str(core/(name+'.log.json')))
        sy = {n: int(v, 16) for v, n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
                      (core/(name+'.map')).read_text(), re.M)}
        memory = cells(core/(name+'.s19'))
        assert set(memory) == set(range(start, sy[end]))
        symbols[name] = sy
        return bytes(memory[a] for a in range(start, sy[end]))

    prefix = ('        MODULE MIN1_READBACK\n        INCLUDE "str8n-v2-eq.inc"\n'
              '        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n'
              '        INCLUDE "boot-symbols.inc"\n        CODE\n')
    (core/'readback-service.asm').write_text(long_branches(prefix+
        (core/'mon-absent-service.inc').read_text()+'\n        ENDMOD\n        END\n'))
    raw = link('readback-service', 0x6800, 'MS_END')
    loader = 'MS_BOOTSTRAP:\n        SEI\n        CLD\n'
    for n in range(len(raw)):
        loader += f'        LDA MS_BLOB+{n}\n        STA ${0x6800+n:04X}\n'
    loader += '        JMP $6800\nMS_BLOB:\n'
    for n in range(0, len(raw), 16):
        loader += ' DB '+','.join(f'${value:02X}' for value in raw[n:n+16])+'\n'
    (core/'readback-loader.asm').write_text(prefix+loader+
        'MS_LOAD_END:\n        ENDMOD\n        END\n')
    data = link('readback-loader', 0x200, 'MS_LOAD_END')
    assert 0x6800+len(raw) < 0x7800 and 0x200+len(data) <= 0x6500
    payload = out/'payload'
    payload.mkdir()
    name = 'STR8N-F-READBACK-RAM.bin'
    (payload/name).write_bytes(data)
    (payload/name.replace('.bin','.s19')).write_bytes(s19(data,0x200,0x200))
    save(out/'symbols.json',symbols)
    manifest = dict(passed=True, execution_qualified=False, hardware_access=False,
        CPU_simulations=0, F_rebuilt=False, assembly_builds=1,
        modules=['readback-service','readback-loader'],
        prompt='RAM SERVICE MIN1> ', owner_RAM='0200-66FF',owner_ZP='00-DF',
        artifacts={name:dict(bytes=len(data),sha256=sha(data),address='0200',entry='0200')},
        service=dict(address='6800',bytes=len(raw),sha256=sha(raw)),
        source_sha256=sha((ROOT/'src/core/mon-absent-service.inc').read_bytes()),
        producer_sha256=sha(Path(__file__).read_bytes()))
    save(out/'manifest.json',manifest)
    print('PASS MIN1 readback/restore build;',len(data),'loader bytes;',len(raw),'service bytes; no F rebuild')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.out)
