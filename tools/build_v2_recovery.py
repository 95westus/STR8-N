"""Build the beta1-derived immutable-F, A/B monitor and wear journal candidate.

No serial access. Generated images reserve B3:A-D; never assume these are free.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import binascii
import re

import build_v2_config as link
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/v2-recovery'
OUT = ROOT / 'BUILD/v2-recovery'
VERSION = '2.0b3'
MAINT_LABEL = 'MAINT'
STEM = 'str8n-v2-recovery'
SR_CALLS = ('V2_HEX_WORD', 'V2_HEX_BYTE', 'V2_SKIP_SPACES', 'V2_PRINT_ADDR',
            'V2_PUTC', 'V2_HEX_OUT', 'V2_NEWLINE', 'V2_BAD_HEX',
            'V2_BAD_RANGE', 'V2_PROTECTED', 'V2_PROMPT', 'V2_MESSAGE',
            'V2_FLASH_FAILED', 'V2_FLASH_DONE', 'V2_CONFIRM', 'V2_PRINT',
            'V2_READ_LINE', 'V2_CHECK_CANCEL', 'V2_CANCELLED')


def crc(data):
    return binascii.crc_hqx(data, 0xffff)


def relax_branches(path, memory, symbols, assemble):
    """Shrink expanded branches, preserving fixed entry and descriptor slots."""
    opposite=dict(BEQ='BNE',BNE='BEQ',BCC='BCS',BCS='BCC',BPL='BMI',BMI='BPL',BVC='BVS',BVS='BVC')
    pattern=r'\s+(B[A-Z]{2}) (\w*LONG_\d+)\n\s+JMP (\w+)\n\2:'
    for _ in range(20):
        source=path.read_text()
        def relax(match):
            op,skip,target=match.groups()
            if skip not in symbols or target not in symbols:return match[0]
            distance=symbols[target]-(symbols[skip]-5+2)
            return '\n                        '+opposite[op]+' '+target if -128<=distance<=127 else match[0]
        compact=re.sub(pattern,relax,source)
        if compact==source:break
        path.write_text(compact)
        memory,symbols=assemble()
    return memory,symbols


def metadata(config=b'\xff'*16, counts=None, sequence=1):
    if len(config)!=16 or not 1<=sequence<=0xffffffff:
        raise ValueError('Metadata needs 16 config bytes and a nonzero 32-bit sequence')
    if counts is not None and (len(counts)!=32 or any(not 0<=v<=0xffffff for v in counts)):
        raise ValueError('Metadata needs 32 unsigned 24-bit counts')
    data = bytearray(b'\xff'*128)
    data[:8] = b'WC\x01\x00' + sequence.to_bytes(4, 'little')
    data[8:24] = config
    data[24:120] = b''.join(v.to_bytes(3, 'little') for v in (counts or [0]*32))
    data[120:122] = crc(data[:120]).to_bytes(2, 'little')
    data[127] = 0
    return bytes(data)


def slot_image(code, symbols, page, generation, compatibility=None):
    data = bytearray(b'\xff'*4096)
    data[:8] = b'MI\x01' + bytes([page, 3, 1, 0, 0])
    data[8:12] = generation.to_bytes(4, 'little')
    data[12:14] = len(code).to_bytes(2, 'little')
    data[14:16] = symbols['START'].to_bytes(2, 'little')
    data[16:18] = symbols['V2_PROMPT_ENTRY'].to_bytes(2, 'little')
    if compatibility is None:
        compatibility = json.loads((OUT/'build.json').read_text())['boot_compatibility']
    data[20:24] = compatibility.to_bytes(4,'little')
    for index, name in enumerate(SR_CALLS):
        data[32+2*index:34+2*index] = symbols[name].to_bytes(2, 'little')
    data[128:128+len(code)] = code
    data[18:20] = crc(data[:18]+data[32:]).to_bytes(2, 'little')
    data[31] = 0
    return bytes(data)


def emit(name, start, data, entry):
    (OUT / (name+'.bin')).write_bytes(data)
    lines = [link.record('0', 0, name.encode())]
    lines += [link.record('1', a, data[a-start:a-start+32])
              for a in range(start, start+len(data), 32)]
    lines += [link.record('9', entry)]
    path = OUT / (name+'.s19')
    path.write_text('\n'.join(lines)+'\n', encoding='ascii')
    memory, observed = link.read_s19(path)
    assert observed == entry and bytes(memory[a] for a in range(start, start+len(data))) == data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.generation < 0xffffffff:
        parser.error('generation must be 1..4294967294; never wrap')
    stage = OUT / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    (OUT/'build.json').unlink(missing_ok=True)
    (OUT/'test-results.json').unlink(missing_ok=True)
    # Expand branches in this candidate only. Historical source/builders stay frozen.
    for path in SOURCE.iterdir():
        if path.suffix in ('.asm', '.inc'):
            raw = path.read_text()
            if path.name not in ('str8n-v2-worker.asm', 'str8n-v2-flash-worker.inc',
                                 'str8n-v2-ram-console.inc', 'str8n-v2-vectors.asm'):
                raw = long_branches(raw).replace('BM_LONG_', path.stem.replace('-', '_')+'_LONG_')
            (stage/path.name).write_text(raw, encoding='ascii')
    link.OUT = OUT
    link.SOURCE = stage
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise SystemExit('WDC02AS and WDCLN must be on PATH')

    def assemble(name, start):
        inputs = OUT / 'inputs'
        inputs.mkdir(exist_ok=True)
        source = inputs / (name+'.asm')
        shutil.copyfile(stage/(name+'.asm'), source)
        return link.assemble(name, start, assembler, linker, source_file=source)

    wm, ws = assemble('str8n-v2-worker', 0x7800)
    worker = link.dense_image(wm, 0x7800, ws['V2W_END'])
    if len(worker) > 1024:
        raise ValueError('RAM worker exceeds 7800-7BFF')
    (stage/'worker-public-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in ws.items() if n.startswith('V2W_')))
    vm, vs = assemble('str8n-v2-vectors', 0x7e20)
    vectors = link.dense_image(vm, 0x7e20, vs['V2V_END'])
    if len(vectors) > 224 or vs['V2V_RAM_SIGNATURE'] != 0x7e60:
        raise ValueError('Vector reservation/ABI changed')
    (stage/'vectors-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in (ws|vs).items() if n.startswith(('V2W_','V2V_'))) + f'V2_VECTOR_SIZE EQU ${len(vectors):02X}\n')
    link.include_bytes(stage/'worker-image.inc', worker)
    link.include_bytes(stage/'vectors-image.inc', vectors)
    # Fixed source windows copy the exact worker, with an overlapping final page.
    offsets = list(range(0,len(worker)-255,256))
    if len(worker)%256: offsets.append(len(worker)-256)
    copy = [' LDX #0', 'BOOT_COPY_WORKER:']
    for off in offsets:
        copy += [f' LDA BOOT_WORKER_IMAGE+${off:04X},X', f' STA V2_WORKER+${off:04X},X']
    copy += [' INX', ' BNE BOOT_COPY_WORKER']
    (stage/'worker-copy.inc').write_text('\n'.join(copy)+'\n')
    # Fixed SR trampolines preserve an extension shared by separately linked slots.
    (stage/'sr-stubs.inc').write_text(''.join(f'BOOT_SR_{i}: PHX\n LDX #${i*2:02X}\n JMP BOOT_SR_ROUTE\n' for i in range(len(SR_CALLS))))
    (stage/'sr-monitor-symbols.inc').write_text(''.join(f'{n} EQU ${0xf040+6*i:04X}\n' for i,n in enumerate(SR_CALLS)))
    # Link the unrelaxed bootstrap lower first; it may exceed the F boundary.
    bm, bs = assemble('str8n-v2-boot', 0xe000)
    bm, bs = relax_branches(stage/'str8n-v2-boot.asm',bm,bs,lambda:assemble('str8n-v2-boot',0xe000))
    bm, bs = assemble('str8n-v2-boot',0xf000)
    boot = link.dense_image(bm, 0xf000, bs['BOOT_END'])
    if len(boot) > 0xfe0:
        raise ValueError(f'Fixed F boot exceeds hardware vectors: {len(boot)}')
    f = bytearray(b'\xff'*4096)
    f[:len(boot)] = boot
    hw = {0xffe4:'V2V_NATIVE_COP',0xffe6:'V2V_NATIVE_BRK',0xffe8:'V2V_NATIVE_ABORT',
          0xffea:'V2V_NATIVE_NMI',0xffee:'V2V_NATIVE_IRQ',0xfff4:'V2V_COP',
          0xfff8:'V2V_ABORT',0xfffa:'V2V_NMI',0xfffe:'V2V_IRQ_BRK'}
    for a,n in hw.items(): f[a-0xf000:a-0xf000+2] = vs[n].to_bytes(2,'little')
    f[0xffc:0xffe] = (0xf004).to_bytes(2,'little')
    compatibility = binascii.crc32(f) & 0xffffffff
    compat_offset = bs['BOOT_COMPAT_DATA']-0xf000
    f[compat_offset:compat_offset+4] = compatibility.to_bytes(4,'little')
    (stage/'boot-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in bs.items() if n.startswith('BOOT_') and v>=0xf000 and n!='BOOT_API_ERASE'))
    messages = json.loads((SOURCE/'str8n-v2-text.json').read_text())
    pool, ids = bytearray(), []
    prefix = next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    for i,m in enumerate(messages):
        raw = bytearray(m['text'].replace('{version}',VERSION).encode())
        if i < prefix: raw = raw[4:]
        raw[-1] |= 128
        pool.extend(raw)
        ids.append(f"{m['name']} EQU ${i:02X}\n")
    (stage/'text-ids.inc').write_text(''.join(ids))
    with (stage/'sr-monitor-symbols.inc').open('a') as stream:
        stream.write(f"V2_SR_ERROR_TEXT EQU ${next(i for i,m in enumerate(messages) if m['name']=='V2_SR_ERROR_TEXT'):02X}\n")
    link.include_bytes(stage/'text-image.inc', pool)
    (stage/'text-image.inc').write_text('V2_TEXT:\n'+(stage/'text-image.inc').read_text())
    slots, syms = {}, {}
    for page in (0xa0,0xb0):
        source = (stage/'str8n-v2.asm').read_text().replace('V2_IMAGE_PAGE EQU $A0',f'V2_IMAGE_PAGE EQU ${page:02X}')
        name = f'monitor-{page:02x}'
        (stage/(name+'.asm')).write_text(source)
        mem, sym = assemble(name,(page<<8)+128)
        mem,sym=relax_branches(stage/(name+'.asm'),mem,sym,lambda:assemble(name,(page<<8)+128))
        code = link.dense_image(mem,(page<<8)+128,sym['V2_END'])
        if len(code)>3968: raise ValueError(f'Monitor {page:02X} exceeds its sector: {len(code)}')
        slots[page] = slot_image(code,sym,page,args.generation,compatibility)
        syms[page] = sym
        emit(f'{STEM}-slot-{page:02x}',page<<8,slots[page],sym['START'])
    sm, ss = assemble('str8n-v2-sr',0xe800)
    # Relax expanded conditional branches using linked addresses. Shrinking
    # code only reduces other branch distances; fixed descriptor slots stay put.
    sm,ss=relax_branches(stage/'str8n-v2-sr.asm',sm,ss,lambda:assemble('str8n-v2-sr',0xe800))
    sr = link.dense_image(sm,0xe800,ss['SR_END'])
    if len(sr)>1792: raise ValueError('S/R/T exceeds E800-EEFF')
    e = bytearray(b'\xff'*4096); e[0x800:0x800+len(sr)] = sr
    emit(STEM+'-e000-efff',0xe000,e,0xf004)
    emit(STEM+'-f000-ffff',0xf000,f,0xf004)
    initial = metadata()
    # Initial provisioning puts one valid snapshot in C, D remains erased.
    cd = initial+b'\xff'*(8192-len(initial))
    emit(STEM+'-c000-dfff',0xc000,cd,0xf004)
    emit(STEM+'-a000-dfff',0xa000,slots[0xa0]+slots[0xb0]+cd,0xf004)
    report = dict(version=VERSION,base='codex/beta1-release (a9660bc)',generation=args.generation,
                  boot_compatibility=compatibility,
                  boot_bytes=len(boot),worker_bytes=len(worker),vector_bytes=len(vectors),sr_bytes=len(sr),
                  monitor_bytes={f'{p:02x}':syms[p]['V2_END']-((p<<8)+128) for p in syms},
                  boot=bs,worker=ws,vectors=vs,monitors={f'{p:02x}':s for p,s in syms.items()},sr=ss,
                  hardware_tested=False,application_ram_end=0x66ff,
                  artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob(STEM+'*.bin')},
                  source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()})
    (OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"{VERSION}: fixed F {len(boot)} bytes; worker {len(worker)}; monitors {report['monitor_bytes']}; SR {len(sr)}")
    print('Reserved: B3:A/B monitor slots, C/D metadata; application RAM ends $66FF. No board writes.')


if __name__=='__main__': main()
