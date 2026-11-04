"""Build only the B0:9000 public-ABI test fixture, once. No F or device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def build(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Use a fresh output directory')
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    if not assembler or not linker:raise ValueError('WDC tools not found')
    out.mkdir(parents=True)
    source=ROOT/'examples/base1-b0-9000.asm'
    shutil.copyfile(source,out/'fixture.asm')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',out/'str8n-v2-public.inc')
    logs=[]
    for command in ([assembler,'-G','-L','-S','-W','fixture.asm'],
                    [linker,'-g','-s','-t','-c9000','-hm19','-j','-o','fixture.s19','fixture.obj']):
        result=subprocess.run(command,cwd=out,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
        if result.returncode:raise RuntimeError('Fixture build failed; inspect build-log.json')
    symbols={name:int(value,16) for value,name in re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$',(out/'fixture.map').read_text(),re.M)}
    memory={}
    for line in (out/'fixture.s19').read_text().splitlines():
        raw=bytes.fromhex(line[2:]);assert raw[0]+1==len(raw) and sum(raw)&255==255
        if line.startswith('S1'):
            address=int.from_bytes(raw[1:3],'big');memory.update((address+n,value) for n,value in enumerate(raw[3:-1]))
    assert symbols['START']==0x9000 and symbols['IMAGE_END']<=0xa000
    assert set(memory)==set(range(0x9000,symbols['IMAGE_END']))
    body=bytes(memory[a] for a in range(0x9000,symbols['IMAGE_END']))
    image=body.ljust(4096,b'\xff');(out/'BASE1-B0-9000-ACCEPT.bin').write_bytes(image)
    sha=lambda data:hashlib.sha256(data).hexdigest()
    report=dict(passed=True,source_sha256=sha(source.read_bytes()),image_sha256=sha(image),
        source_bytes=len(body),bytes=4096,bank=0,address='9000',entry='9000',
        mutable_RAM='6100-6103; system pointer E0-E1 and stack',uses_public_RAM_ABI_only=True,
        F_rebuilt=False,CPU_simulations=0,hardware_access=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    build(parser.parse_args().out)
