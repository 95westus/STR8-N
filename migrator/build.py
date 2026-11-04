"""Build the unrendered NFM1 RAM template once; never opens a device."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def fnv(data):
    value = 2166136261
    for byte in data:
        value = (value ^ byte) * 16777619 & 0xffffffff
    return value


def long_branches(source):
    """Avoid iterative builds: expand relative branches before assembly."""
    inverse = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
                   BMI='BPL', BPL='BMI', BVC='BVS', BVS='BVC')
    rows, count = [], 0
    for row in source.splitlines():
        match = re.fullmatch(r'\s*(BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS|BRA)\s+(\w+)\s*', row)
        if not match:
            rows.append(row)
        elif match[1] == 'BRA':
            rows.append('        JMP '+match[2])
        else:
            count += 1
            label = 'NFM_LONG_'+str(count)
            rows.extend(('        '+inverse[match[1]]+' '+label,
                         '        JMP '+match[2], label+':'))
    return '\n'.join(rows)+'\n'


def s19(data, entry, start=0x2000):
    def row(kind, address, body=b''):
        raw = bytes((len(body)+3,))+address.to_bytes(2, 'big')+body
        return 'S'+kind+(raw+bytes((255-(sum(raw)&255),))).hex().upper()
    return ('\n'.join([row('0', 0, b'STR8N-F NFM1 RAM template')]+
        [row('1', start+n, data[n:n+32]) for n in range(0, len(data), 32)]+
        [row('9', entry)])+'\n').encode('ascii')


def read_s19(path):
    result = {}
    for line in path.read_text().splitlines():
        raw = bytes.fromhex(line[2:])
        assert line[:2] in ('S0', 'S1', 'S9')
        assert len(raw) == raw[0]+1 and sum(raw)&255 == 255
        if line.startswith('S1'):
            for address, value in enumerate(raw[3:-1], int.from_bytes(raw[1:3], 'big')):
                assert address not in result
                result[address] = value
    return result


def recovery_loader(template):
    """Generate a backwards memmove wrapper for F's raw-L entry at 0200.

    Fixed instruction encoding is checked structurally; no CPU model is run.
    The destination is above the overlapping source, so copying every source
    byte in descending address order cannot overwrite an unread source byte.
    """
    template = bytes(template)
    if len(template) != 8192:
        raise ValueError('NFM1 recovery loader requires exactly 8192 bytes')
    blob = 0x200+32*13+3
    loader, rows = bytearray(), ['        MODULE NF_RECOVERY_LOADER', '        CODE']
    for page in range(31, -1, -1):
        source, destination = blob+page*256, 0x2000+page*256
        loader += b'\xa2\xff\xbd'+source.to_bytes(2, 'little')
        loader += b'\x9d'+destination.to_bytes(2, 'little')+b'\xca\xe0\xff\xd0\xf5'
        rows += ['        LDX #$FF', f'COPY_{page}: LDA BLOB+${page*256:04X},X',
                 f'        STA ${destination:04X},X', '        DEX',
                 '        CPX #$FF', f'        BNE COPY_{page}']
    loader += b'\x4c\x00\x20'
    rows += ['        JMP $2000', 'BLOB:']
    for offset in range(0, len(template), 16):
        rows.append('        DB '+','.join(f'${v:02X}' for v in template[offset:offset+16]))
    rows += ['LOADER_END:', '        ENDMOD', '        END']
    assert len(loader) == blob-0x200
    assert loader[-3:] == b'\x4c\x00\x20'
    # Each page contains its own descending X loop; verify all encoded windows.
    source_order = []
    for step, page in enumerate(range(31, -1, -1)):
        code = loader[step*13:(step+1)*13]
        source, destination = int.from_bytes(code[3:5], 'little'), int.from_bytes(code[6:8], 'little')
        assert code[:3] == b'\xa2\xff\xbd' and code[5] == 0x9d
        assert code[8:] == b'\xca\xe0\xff\xd0\xf5'
        assert source == blob+page*256 and destination == 0x2000+page*256
        assert source+255 < 0x6500 and 0x2000 <= destination <= 0x3f00
        source_order.extend(range(source+255, source-1, -1))
    assert source_order == list(range(blob+8191, blob-1, -1))
    assert blob < 0x2000 and 0x200+len(loader)+len(template) <= 0x6500
    result = bytes(loader)+template
    assert result[blob-0x200:] == template
    return result, '\n'.join(rows)+'\n'


def build(out, assembler=None, linker=None):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory')
    assembler = assembler or shutil.which('wdc02as')
    linker = linker or shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC wdc02as and wdcln must be on PATH')
    out.mkdir(parents=True)
    source = (ROOT/'nf-migrate.asm').read_text()
    (out/'nf-migrate.asm').write_text(long_branches(source), encoding='ascii', newline='\n')
    logs = []
    for command in ([assembler, '-G', '-L', '-S', '-W', 'nf-migrate.asm'],
                    [linker, '-g', '-s', '-t', '-c2000', '-hm19', '-j',
                     '-o', 'nf-migrate.s19', 'nf-migrate.obj']):
        result = subprocess.run(command, cwd=out, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=result.returncode,
                         stdout=result.stdout, stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n', encoding='utf-8')
        if result.returncode:
            raise RuntimeError('WDC build failed; inspect build-log.json')
    symbols = {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', (out/'nf-migrate.map').read_text(), re.M)}
    memory = read_s19(out/'nf-migrate.s19')
    assert symbols['ENTRY_65C02'] == 0x2000 and symbols['ENTRY_65C816'] == 0x2010
    assert symbols['MIG_END'] <= 0x3000, 'Code overlaps per-run plan'
    assert set(memory) == set(range(0x2000, symbols['MIG_END']))
    template = bytearray(8192)
    for address, value in memory.items():
        template[address-0x2000] = value
    assert template[0x1000:0x1100] == bytes(256)
    assert template[-4:] == bytes(4)
    (out/'template.bin').write_bytes(template)
    (out/'template.s19').write_bytes(s19(template, 0x2000))
    (out/'template-816.s19').write_bytes(s19(template, 0x2010))
    recovery, recovery_source = recovery_loader(template)
    (out/'template-recovery.bin').write_bytes(recovery)
    (out/'template-recovery.s19').write_bytes(s19(recovery, 0x200, start=0x200))
    (out/'template-recovery.asm').write_text(recovery_source, encoding='ascii', newline='\n')
    manifest = dict(schema=1, status='unrendered-template-refuses-execution',
        build_passed=True, execution_qualified=False, hardware_access=False,
        serial_access=False, CPU_simulations=0, source_sha256=hashlib.sha256(
            source.encode()).hexdigest(), template_sha256=hashlib.sha256(template).hexdigest(),
        bytes=len(template), code_bytes=symbols['MIG_END']-0x2000,
        load_start=0x2000, load_end=0x3fff, entry_65c02=0x2000, entry_65c816=0x2010,
        plan_address=0x3000, plan_bytes=256, self_hash_address=0x3ffc,
        self_hash_algorithm='FNV1a32 little endian over 2000-3FFB',
        staging_start=0x4000, staging_end=0x4fff, scratch_start=0x6000, scratch_end=0x601f,
        zero_page_start=0xe0, zero_page_end=0xe9, stack='emulation page 0100-01FF; native caller 0700 not uploaded',
        flash_id='SST39SF010A BF/B5', flash_bank=3,
        allowed_orders=[['F'], ['D', 'C'], ['F', 'D', 'C']],
        operations_always_erase=True, journal_commit_address='sector start + 00FF, value 00, programmed last',
        console='FT245 USB only', no_implicit_flash_bank_backup=True,
        recovery_loader=dict(bytes=len(recovery), start=0x200, entry=0x200,
            destination_start=0x2000, destination_end=0x3fff,
            copy_order='32 descending pages, X=FF down through 00 per page',
            sha256=hashlib.sha256(recovery).hexdigest(),
            structural_address_check=True, CPU_simulations=0,
            unrendered_template_refuses=True),
        limit='Static build only; no CPU/hardware acceptance or migration authorization')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (out/'symbols.json').write_text(json.dumps(symbols, indent=2)+'\n', encoding='utf-8')
    print('PASS NFM1 unrendered template build:', manifest['code_bytes'],
          'code bytes; no execution/hardware qualification', flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--assembler')
    parser.add_argument('--linker')
    args = parser.parse_args()
    build(args.out, args.assembler, args.linker)
