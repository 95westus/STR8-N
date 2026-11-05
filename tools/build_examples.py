"""Build attributed Microchess and OSI BASIC above frozen F; no board access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build import cells, s19

ROOT = Path(__file__).resolve().parents[1]
F_SHA = '8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
sha = lambda data: hashlib.sha256(data).hexdigest()


def command(args, cwd):
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True)
    with (cwd/'build.log').open('a', encoding='utf-8') as log:
        log.write(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)


def outside(text, fn):
    return ''.join(part if i % 2 else fn(part)
                   for i, part in enumerate(re.split(r'''("[^"]*"|'[^']*')''', text)))


def microchess(out):
    source = ROOT/'examples/microchess'
    stage = out/'microchess'; stage.mkdir()
    readable = (source/'microchess-readable.asm').read_text(encoding='ascii')
    code = []
    for line in readable.splitlines():
        if line.startswith(';') or line.startswith('ORG '):
            continue
        line = re.sub(r'^(\w+) = ', r'\1 EQU ', line)
        line = re.sub(r'\b(?:BYTE|TEXT)\b', 'DB', line)
        code.append(('' if ':' in line or ' EQU ' in line else ' ')+line)
    (stage/'chess.asm').write_text(' MODULE CHESS\n CODE\n'+'\n'.join(code)+
                                 '\nCHESS_END:\n ENDMOD\n END\n', encoding='ascii')
    command([shutil.which('wdc02as'), '-G','-L','-S','-W','chess.asm'], stage)
    command([shutil.which('wdcln'), '-g','-s','-t','-c0200','-hm19','-j',
             '-o','chess.s19','chess.obj'], stage)
    symbols = {name: int(value,16) for value,name in re.findall(
        r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (stage/'chess.map').read_text(), re.M)}
    memory = cells(stage/'chess.s19')
    body = bytes(memory[a] for a in range(0x200, symbols['CHESS_END']))
    (out/'microchess-ram.bin').write_bytes(body)
    (out/'microchess-ram.s19').write_bytes(s19(body, 0x200, 0x200))
    assert b'(c) 1976-2005 Peter Jennings' in body
    # Split real instruction source to fit the unchanged 6144-byte ASM buffer.
    # External references become checked EQU addresses from the reference map.
    lines = [line for line in readable.splitlines()
             if line and not line.startswith(';') and not line.startswith('ORG ')]
    names = re.findall(r'^(\w+)\s*(?:=|:)', '\n'.join(lines), re.M)
    alphabet = 'BCDEFGHIJKLMNOPQRSTUVWZ'
    compact = list(alphabet)+[a+b for a in alphabet for b in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    mapping = dict(zip(names, compact))
    def rename(line):
        return outside(line, lambda text: re.sub(r'(?<![$\w])[A-Z_][A-Z_0-9]*\b',
                       lambda m: mapping.get(m[0],m[0]), text))
    parts = []
    # Greedy groups ending just before a global label, each at most 200 lines.
    boundaries = [0]
    for i, line in enumerate(lines):
        if i-boundaries[-1] >= 170 and re.match(r'^\w+:',line):
            boundaries.append(i)
    boundaries.append(len(lines))
    origin = 0x200
    for n, (first, last) in enumerate(zip(boundaries,boundaries[1:]), 1):
        chunk = lines[first:last]
        local = set(re.findall(r'^(\w+)\s*(?:=|:)', '\n'.join(chunk), re.M))
        refs = set()
        for line in chunk:
            outside(line, lambda text: refs.update(re.findall(r'(?<![$\w])[A-Z_][A-Z_0-9]*\b',text)) or text)
        external = sorted((refs & set(names))-local)
        prefix = [f'; (c) 1976-2005 Peter Jennings; LICENSE.txt', f'ORG ${origin:04X}']
        prefix += [f'{mapping[name]}=${symbols[name]:X}' for name in external]
        text = prefix+[rename(line) for line in chunk]
        packed = sum(len(line)+4 for line in text)
        assert packed <= 6144, (n,packed)
        assert all(len(line) <= 120 for line in text)
        name = f'microchess-part{n}.asm'
        (out/name).write_text('\n'.join(text)+'\n',encoding='ascii',newline='\n')
        end = symbols[re.match(r'^(\w+):', lines[last])[1]] if last<len(lines) else symbols['CHESS_END']
        parts.append(dict(file=name,origin=f'{origin:04X}',end_exclusive=f'{end:04X}',packed_bytes=packed))
        origin=end
    # AP/02 B1:8000 loader copies the assembled game to RAM, then runs it.
    from example_images import ap02
    for cpu in (2,0x16):
        (out/f'microchess-ap02-b1-8000-cpu{cpu:02x}.bin').write_bytes(ap02(body,cpu=cpu))
    return dict(bytes=len(body),sha256=sha(body),load='0200',entry='0200',
                end=f'{0x1ff+len(body):04X}',parts=parts,symbols=symbols)


def basic(out, cc65):
    source=ROOT/'examples/osi-basic';stage=out/'osi-basic';shutil.copytree(source/'vendor',stage)
    pins=json.loads((source/'UPSTREAM.json').read_text())
    if set(pins['files'])!={p.name for p in (source/'vendor').iterdir() if p.is_file()}:
        raise ValueError('Unexpected BASIC vendor source inventory')
    for name,digest in pins['files'].items():
        if sha((source/'vendor'/name).read_bytes())!=digest:
            raise ValueError('Changed pinned BASIC source: '+name)
    defines=(stage/'defines_osi.s').read_text()
    for name, target in [('MONRDKEY','IO_GETC'),('MONCOUT','IO_PUTC'),('MONISCNTC','IO_CHECK'),
                          ('LOAD','IO_UNAVAILABLE'),('SAVE','IO_UNAVAILABLE')]:
        defines=re.sub(r'^'+name+r'\s*:=.*$',name+' := '+target,defines,flags=re.M)
    (stage/'defines_osi.s').write_text(defines,encoding='utf-8')
    init=(stage/'init.s').read_text()
    begin=init.index('.ifndef CONFIG_CBM_ALL\n        lda     #<QT_MEMORY_SIZE')
    end=init.index('L40FA:\n',begin)
    init=init[:begin]+'''        lda #<$6700
        sta LINNUM
        lda #>$6700
        sta LINNUM+1
'''+init[end:]
    begin=init.index('L4106:\n');end=init.index('L4136:\n',begin)
    init=init[:begin]+'L4106:\n'+init[end:]
    (stage/'init.s').write_text(init,encoding='utf-8')
    (stage/'osi_iscntc.s').write_text('''; Public Foundation poll through the adapter.
.segment "CODE"
ISCNTC:
    jsr IO_CHECK
    cmp #3
    bne RET2
    clc
; Fall through to BASIC STOP with Z=1 and C=0.
''',encoding='ascii')
    shutil.copyfile(source/'adapter.s',stage/'adapter.s')
    (stage/'main.s').write_text('.include "msbasic.s"\n.include "adapter.s"\n',encoding='ascii')
    def tool(name):
        for file in (Path(cc65)/'bin'/(name+'.exe'),Path(cc65)/'bin'/name):
            if file.is_file():return file
        raise FileNotFoundError('Missing external '+name)
    ca=tool('ca65');ld=tool('ld65')
    command([ca,'-I',Path(cc65)/'asminc','-D','osi','-g','-o','basic.o','main.s'],stage)
    command([ld,'-C',source/'str8n.cfg','-o','basic.bin','-Ln','labels.txt','basic.o'],stage)
    body=(stage/'basic.bin').read_bytes();assert len(body)<=8192
    symbols={name:int(value,16) for value,name in re.findall(r'^al ([0-9A-Fa-f]+) \.(\w+)$',(stage/'labels.txt').read_text(),re.M)}
    assert symbols['ENTRY']==0x8000
    image=body.ljust(8192,b'\xff')
    (out/'osi-basic-opaque-b0-8000.bin').write_bytes(image)
    for index,address in enumerate((0x8000,0x9000)):
        (out/f'osi-basic-b0-{address:04x}.bin').write_bytes(image[index*4096:(index+1)*4096])
    return dict(bytes=len(body),image_bytes=len(image),sha256=sha(image),bank=0,entry='8000',
                sectors=['8000','9000'],owner_RAM='0300-66FF',adapter_RAM='0200-0202',symbols=symbols)


def build(out, cc65):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==F_SHA
    upstream=json.loads((ROOT/'examples/microchess/UPSTREAM.json').read_text())
    assert sha((ROOT/'examples/microchess/Microchess6502-upstream.txt').read_bytes())==upstream['upstream_sha256']
    report=dict(schema=1,Microchess=microchess(out),OSI_BASIC=basic(out,cc65),
                F_rebuilt=False,Foundation_sha256=F_SHA,board_access=False,status='BUILD_ONLY')
    report['source_sha256']={p.relative_to(ROOT).as_posix():sha(p.read_bytes())
        for p in sorted((ROOT/'examples').rglob('*')) if p.is_file()}
    report['source_sha256']['tools/build_examples.py']=sha(Path(__file__).read_bytes())
    report['source_sha256']['tools/example_images.py']=sha((ROOT/'tools/example_images.py').read_bytes())
    (out/'EXAMPLES.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('Microchess','OSI_BASIC')},indent=2))
    return report


def export_tested(build, out):
    build,out=Path(build).resolve(),Path(out).resolve()
    report=json.loads((build/'EXAMPLES.json').read_text())
    for cpu in ('65c02','65c816-e'):
        tested=json.loads((build/f'tests-examples-{cpu}.json').read_text())
        if not tested['passed'] or len(tested.get('actual_DEV_ASM',[]))!=4:
            raise ValueError('Missing actual DEV ASM/example qualification: '+cpu)
        for name,digest in tested['example_payload_sha256'].items():
            if sha((build/name).read_bytes())!=digest:raise ValueError('Changed tested example: '+name)
    out.mkdir(parents=True,exist_ok=False)
    for source in sorted((ROOT/'examples').rglob('*')):
        if source.is_file():
            if source.suffix not in ('.asm','.s','.cfg','.json','.md','.txt'):
                raise ValueError('Unexpected example source type: '+str(source))
            dest=out/source.relative_to(ROOT/'examples');dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
    payload=out/'payload';payload.mkdir()
    for source in sorted(build.glob('*')):
        if source.is_file() and source.suffix in ('.bin','.s19'):
            shutil.copyfile(source,payload/source.name)
    for part in report['Microchess']['parts']:
        shutil.copyfile(build/part['file'],out/'microchess'/part['file'])
    (out/'tools').mkdir();shutil.copyfile(ROOT/'tools/example_images.py',out/'tools/example_images.py')
    for name in ('EXAMPLES.json','tests-examples-65c02.json','tests-examples-65c816-e.json'):
        shutil.copyfile(build/name,out/name)
    artifacts={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
               for p in sorted(out.rglob('*')) if p.is_file()}
    manifest=dict(schema=1,status='CPU_MODEL_VERIFIED_HARDWARE_PENDING',artifacts=artifacts,
                  F_rebuilt=False,Foundation_sha256=F_SHA,board_access=False,
                  manual_install_only=True,source_inputs=report['source_sha256'])
    (out/'EXAMPLES-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Exported verified example files:',len(artifacts))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cc65',type=Path,help='Installed cc65 root with bin/ and asminc/')
    parser.add_argument('--export-tested',type=Path,help='Export an existing build with both passing CPU reports')
    args=parser.parse_args()
    if args.export_tested:export_tested(args.export_tested,args.out)
    elif args.cc65:build(args.out,args.cc65)
    else:parser.error('Choose --cc65 for a build, or --export-tested for packaging')
