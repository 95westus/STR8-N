"""Build the unified b15 system and both board profiles from this tree alone."""
import argparse
import binascii
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import build as corebuild

ROOT = Path(__file__).resolve().parents[1]
GENERATION = 0x8000000F
crc = lambda data: binascii.crc_hqx(data, 0xffff)
sha = lambda data: hashlib.sha256(data).hexdigest()
save = corebuild.save


def long_branches(text, prefix='P_LONG_'):
    inverse = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
                   BMI='BPL', BPL='BMI', BVC='BVS', BVS='BVC')
    rows, number = [], 0
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS|BRA)\s+(\w+)\s*', line)
        if not match:
            rows.append(line)
        elif match[1] == 'BRA':
            rows.append('        JMP ' + match[2])
        else:
            number += 1
            skip = prefix + str(number)
            rows.extend(('        ' + inverse[match[1]] + ' ' + skip,
                         '        JMP ' + match[2], skip + ':'))
    return '\n'.join(rows) + '\n'


def monitor_slot(body, symbols, page, vectors):
    assert len(body) <= 3968
    slot = bytearray(b'\xff' * 4096)
    slot[:8] = b'MI\x01' + bytes((page, 3, 1, 0, 0))
    slot[8:12] = GENERATION.to_bytes(4, 'little')
    for offset, value in ((12, len(body)), (14, symbols['START']),
                          (16, symbols['V2_PROMPT_ENTRY'])):
        slot[offset:offset+2] = value.to_bytes(2, 'little')
    slot[20:24] = b'PR04'
    calls = ('V2_HEX_WORD', 'V2_HEX_BYTE', 'V2_SKIP_SPACES', 'V2_PRINT_ADDR',
             'V2_PUTC', 'V2_HEX_OUT', 'V2_NEWLINE', 'V2_BAD_HEX', 'V2_BAD_RANGE',
             'V2_PROTECTED', 'V2_PROMPT', 'V2_MESSAGE', 'V2_FLASH_FAILED',
             'V2_FLASH_DONE', 'V2_CONFIRM', 'V2_PRINT', 'V2_READ_LINE',
             'V2_CHECK_CANCEL', 'V2_CANCELLED', 'V2_M_EDIT')
    for n, name in enumerate(calls):
        slot[32+2*n:34+2*n] = symbols[name].to_bytes(2, 'little')
    slot[128:128+len(body)] = body
    stub = bytes.fromhex('48 DA 5A AD EC 7F 48 A9 01 20 48 78 4C 10 A0')
    init = bytes((0xa2, 14, 0xbd, 0x6c, page, 0x9d, 0x50, 0x7c, 0xca, 0x10, 0xf7))
    init += bytes((0xa9, vectors['V2V_DEFAULT'] & 255, 0x8d, 2, 0x7e,
                   0xa9, vectors['V2V_DEFAULT'] >> 8, 0x8d, 3, 0x7e))
    init += b''.join(bytes((0x9c, n, 0x7b)) for n in range(0xfc, 0x100))
    init += b'\x4c' + symbols['V2_RESET'].to_bytes(2, 'little')
    hook = bytes.fromhex('00 FF 4C') + symbols['V2_REENTER'].to_bytes(2, 'little')
    slot[72:128] = init + stub + hook
    slot[31] = 0
    slot[18:20] = crc(slot[:18] + slot[32:]).to_bytes(2, 'little')
    return slot


def footer(kind, page, release):
    row = bytearray(b'\xff' * 64)
    row[:8] = (b'MC' if kind == 'MON' else b'XC') + bytes((1, 1, 1, 64, page, 0))
    row[8:12] = GENERATION.to_bytes(4, 'little')
    row[12:28] = release.encode().ljust(16, b'\0')
    row[28:60] = bytes(32)
    return row


def normalized(image, monitor=False):
    data = bytearray(image)
    data[0xfdc:0xffc] = bytes(32)
    if monitor:
        data[18:20] = b'\0\0'
    else:
        data[-2:] = b'\0\0'
    data[31] = 0
    return hashlib.sha256(data).digest()


def build(out, assembler=None, linker=None):
    out = Path(out).resolve()
    corebuild.build(out, assembler, linker)
    core = out / 's/core'
    symbols = json.loads((out / 'symbols.json').read_text())
    compiled, artifacts = [], {}
    assembler = assembler or shutil.which('wdc02as')
    linker = linker or shutil.which('wdcln')

    def link(name, start, end, key=None):
        logs = []
        for command in ([assembler, '-G', '-L', '-S', '-W', '-I', str(core), name+'.asm'],
                        [linker, '-g', '-s', '-t', f'-c{start:04X}', '-hm19', '-j',
                         '-o', name+'.s19', name+'.obj']):
            result = subprocess.run(command, cwd=core, capture_output=True, text=True)
            logs.append(dict(command=command, returncode=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
            save(core/(name+'.log.json'), logs)
            if result.returncode:
                raise RuntimeError('WDC failed: '+name+'; inspect '+str(core/(name+'.log.json')))
        sy = {n: int(v, 16) for v, n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
              (core/(name+'.map')).read_text(), re.M)}
        memory = corebuild.cells(core/(name+'.s19'))
        assert set(memory) == set(range(start, sy[end]))
        body = bytes(memory[n] for n in range(start, sy[end]))
        symbols[key or name] = sy
        compiled.append(dict(module=key or name, bytes=len(body), sha256=sha(body)))
        return body, sy

    def emit(name, body, address, entry=None, role='RAM tool'):
        body = bytes(body)
        entry = address if entry is None else entry
        (out/'payload'/name).write_bytes(body)
        (out/'payload'/name.replace('.bin', '.s19')).write_bytes(corebuild.s19(body, address, entry))
        artifacts[name] = dict(bytes=len(body), sha256=sha(body), address=f'{address:04X}',
                               entry=f'{entry:04X}', role=role)

    template = (core/'monitor-template.asm').read_text()
    for flavor in ('base', 'vx1'):
        source = template
        if flavor == 'vx1':
            start = source.index('AP_TRY:')
            end = source.index('V2_SR_DISPATCH:', start)
            hooks = long_branches((core/'version-caps-mon.inc').read_text(), 'VX_LONG_')
            source = source[:start]+hooks+'\nAP_CHECK: CLC\n        RTS\n\n'+source[end:]
            start = source.index('B29_LEGACY_DISABLED:')
            end = source.index('B29_GATE_IMAGE:', start)
            source = source[:start] + source[end:]
            source = source.replace('V2_RESERVED2_ENTRY:     JMP     V2_RESERVED',
                                    'V2_RESERVED2_ENTRY:     JMP     VX_DISCOVER')
            source = source.replace('        INCLUDE "app-fixed-symbols.inc"',
                 '        INCLUDE "app-fixed-symbols.inc"\n        INCLUDE "version-caps-public.inc"')
        for page in (0xa0, 0xb0):
            name = f'monitor-{flavor}-{page:02x}'
            path = core/(name+'.asm')
            path.write_text(source.replace('V2_IMAGE_PAGE EQU $B0', f'V2_IMAGE_PAGE EQU ${page:02X}'))
            body, sy = link(name, page*256+128, 'V2_END')
            if flavor == 'vx1':
                inverse = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
                               BMI='BPL', BPL='BMI', BVC='BVS', BVS='BVC')
                for _ in range(8):
                    text = path.read_text()
                    def compact(m):
                        branch, label, dest = m.groups()
                        if label in sy and dest in sy and -128 <= sy[dest]-(sy[label]-3) <= 127:
                            return '        '+inverse[branch]+' '+dest+'\n'
                        return m[0]
                    updated = re.sub(r'        (BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS) (VX_LONG_\d+)\n        JMP (\w+)\n\2:\n', compact, text)
                    if updated == text:
                        break
                    path.write_text(updated)
                    body, sy = link(name, page*256+128, 'V2_END')
            slot = monitor_slot(body, sy, page, symbols['vectors'])
            if flavor == 'vx1':
                assert sy['V2_END'] <= page*256+0xfc0
                slot[0xfc0:] = footer('MON', page, '2.0proto b15vx1')
                slot[0xfdc:0xffc] = normalized(slot, True)
                slot[18:20] = crc(slot[:18]+slot[32:]).to_bytes(2, 'little')
            emit(f'STR8N-F-MON-{flavor.upper()}-{page >> 4:X}.bin', slot, page*256,
                 int.from_bytes(slot[14:16], 'little'), 'Optional monitor sector')

    raw, sy = link('version-caps-e000', 0xe000, 'VX_END', 'vx1')
    image = bytearray(raw)
    assert len(image) == 4096 and sy['VX_CODE_END'] < 0xefc0
    image[0xfc0:] = footer('EXT', 0, 'b15-vx1')
    image[-2:] = b'\0\0'
    image[0xfdc:0xffc] = normalized(image)
    image[-2:] = crc(image[:-2]).to_bytes(2, 'big')
    emit('STR8N-F-VX1-E.bin', image, 0xe000, sy['VX_QUERY'], 'Optional VERSION/CAPS sector')
    raw, _ = link('version-caps-client', 0x200, 'VQ_END', 'vx1-client')
    emit('STR8N-F-VERSION-RAM.bin', raw, 0x200)

    raw, sy = link('ram-maint-ro', 0x200, 'MA_END', 'maint')
    image = bytearray(raw)
    offset = sy['MA_IMAGE_CRC']-0x200
    image[offset:offset+2] = crc(image[:offset]).to_bytes(2, 'big')
    assert crc(image[:sy['MA_IMM_END']-0x200]) == 0
    emit('STR8N-F-MAINT-RO-RAM.bin', image, 0x200)

    raw, sy = link('edu-sram', 0x8040, 'ES_END', 'es1')
    image = bytearray(b'\xff'*4096)
    image[:4] = b'ES\x01\x40'
    for offset, label in ((4, 'ES_INIT'), (7, 'ES_QUERY'), (10, 'ES_READ'), (13, 'ES_PREP')):
        image[offset:offset+3] = b'\x4c'+sy[label].to_bytes(2, 'little')
    image[16:20] = GENERATION.to_bytes(4, 'little')
    image[20:24] = bytes((0, 0, 2, 1))
    image[24:32] = bytes((0, 0x65, 0, 1, 1, 32, 1, 0))
    image[64:64+len(raw)] = raw
    image[-2:] = crc(image[:-2]).to_bytes(2, 'big')
    emit('STR8N-F-ES1-8.bin', image, 0x8000, sy['ES_INIT'], 'Optional EDU/SRAM provider sector')
    raw, sy = link('edu-client', 0x200, 'EC_END', 'es1-client')
    image = bytearray(raw)
    offset = sy['EC_IMAGE_CRC']-0x200
    image[offset:offset+2] = crc(image[:offset]).to_bytes(2, 'big')
    emit('STR8N-F-EDU-SRAM-RAM.bin', image, 0x200)

    f = (out/'payload/STR8N-F-BOOT-4096.bin').read_bytes()
    source = long_branches((core/'bank-monitor.asm').read_text(), 'BM_LONG_')
    for address, allocation in ((0x8000, 4096), (0x9000, 8192)):
        name = f'flash-{address:04x}'
        layout_name = name+'-layout.inc'
        layout = core/layout_name
        layout.write_text(f'BM_HOME_FIRST EQU ${address >> 8:02X}\n'
            f'BM_HOME_AFTER EQU ${(address+allocation) >> 8:02X}\n'
            f'BM_F_CRC_LO EQU ${crc(f) & 255:02X}\nBM_F_CRC_HI EQU ${crc(f) >> 8:02X}\n')
        (core/(name+'.asm')).write_text(source.replace('bank-monitor-layout.inc', layout_name))
        raw, sy = link(name, 0x200, 'BM_END')
        body = bytearray(raw)
        body[sy['BM_CODE_CRC']-0x200:sy['BM_CODE_CRC']-0x200+2] = crc(body[:sy['BM_CODE_END']-0x200]).to_bytes(2, 'little')
        pages = (len(body)+255)//256
        layout.write_text(layout.read_text()+f'BM_COPY_PAGES EQU {pages}\nBM_HOME_ADDRESS EQU ${sy["BM_HOME"]:04X}\n')
        entry_name = name+'-entry'
        (core/(entry_name+'.asm')).write_text((core/'bank-monitor-entry.asm').read_text().replace('bank-monitor-layout.inc', layout_name))
        entry, _ = link(entry_name, address, 'BM_ROM_END')
        image = (entry.ljust(128, b'\xff')+body.ljust(pages*256, b'\xff')).ljust(allocation, b'\xff')
        assert len(image) == allocation and sy['BM_END'] < 0x2000
        emit(f'STR8N-F-FLASH-{address:04X}.bin', image, address, role='Optional opaque application')
        emit(f'STR8N-F-FLASH-{address:04X}-RAM.bin', body, 0x200)

    prefix = ('        MODULE UNIFIED_READBACK\n        INCLUDE "str8n-v2-eq.inc"\n'
              '        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n'
              '        INCLUDE "boot-symbols.inc"\n        CODE\n')
    (core/'readback-service.asm').write_text(long_branches(prefix+(core/'mon-absent-service.inc').read_text()+'\n        ENDMOD\n        END\n'))
    raw, sy = link('readback-service', 0x6800, 'MS_END')
    loader = 'MS_BOOTSTRAP:\n        SEI\n        CLD\n'
    for n in range(len(raw)):
        loader += f'        LDA MS_BLOB+{n}\n        STA ${0x6800+n:04X}\n'
    loader += '        JMP $6800\nMS_BLOB:\n'
    for n in range(0, len(raw), 16):
        loader += ' DB '+','.join(f'${v:02X}' for v in raw[n:n+16])+'\n'
    (core/'readback-loader.asm').write_text(prefix+loader+'MS_LOAD_END:\n        ENDMOD\n        END\n')
    image, _ = link('readback-loader', 0x200, 'MS_LOAD_END')
    emit('STR8N-F-READBACK-RAM.bin', image, 0x200)
    assert sy['MS_END'] < 0x7800 and len(image)+0x200 <= 0x6500

    baseline = json.loads((ROOT/'system-baseline.json').read_text())
    for name, expected in baseline['artifacts'].items():
        actual = artifacts[name]
        assert actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256'], 'System baseline mismatch: '+name
    assert set(artifacts) == set(baseline['artifacts'])
    save(out/'system-symbols.json', symbols)
    save(out/'system-manifest.json', dict(passed=True, hardware=False, serial_access=False,
         identity='Unified STR8N-F b15 source/build', generation='8000000F',
         core_manifest_sha256=sha((out/'manifest.json').read_bytes()),
         profiles=json.loads((ROOT/'profiles.json').read_text()), artifacts=artifacts,
         compiled=compiled, sources={p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
             for p in sorted((ROOT/'src').rglob('*')) if p.is_file()}))
    print('PASS unified system:', len(artifacts), 'additional payloads; both board profiles; no device access', flush=True)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--assembler')
    parser.add_argument('--linker')
    args = parser.parse_args()
    build(args.out, args.assembler, args.linker)
