"""Check the compact F candidate's static layout and component bindings.

This reads existing files only. It does not assemble, emulate, open a serial
port, or establish execution/hardware qualification.
"""
import argparse
import binascii
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'validation/v0.2.0-reference'
F_NAME = 'STR8N-F-BOOT-4096.bin'
sha = lambda data: hashlib.sha256(data).hexdigest()
crc = lambda data: binascii.crc_hqx(data, 0xffff)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def s19_bytes(path):
    """Decode/check the component S0/S1/S9 format, including every checksum."""
    memory = {}
    entry = None
    for row in path.read_text(encoding='ascii').splitlines():
        if not row:
            continue
        if not re.fullmatch(r'S[019][0-9A-Fa-f]+', row):
            raise ValueError('Unsupported S-record in ' + path.name)
        raw = bytes.fromhex(row[2:])
        if len(raw) != raw[0]+1 or sum(raw) & 255 != 255:
            raise ValueError('S-record checksum/count mismatch in ' + path.name)
        address = int.from_bytes(raw[1:3], 'big')
        if row[1] == '1':
            for offset, value in enumerate(raw[3:-1]):
                where = address+offset
                if where in memory:
                    raise ValueError('Overlapping S-record in ' + path.name)
                memory[where] = value
        elif row[1] == '9':
            if entry is not None or len(raw) != 4:
                raise ValueError('Invalid duplicate/length S9 in ' + path.name)
            entry = address
    if not memory or entry is None:
        raise ValueError('Missing component bytes or entry in ' + path.name)
    start = min(memory)
    if set(memory) != set(range(start, max(memory)+1)):
        raise ValueError('Noncontiguous S-record in ' + path.name)
    return start, entry, bytes(memory[a] for a in range(start, max(memory)+1))


def retained_boot_rows(path):
    """Ignore comments/labels and only the explicitly retired patch padding.

    The four FF bytes before the fixed F040 table are deliberately retained.
    DB FB,EA CPU-mode pairs and all timing instructions remain significant.
    """
    rows = []
    after_reset = False
    discarded = []
    for original in path.read_text(encoding='utf-8').splitlines():
        text = original.split(';', 1)[0].strip()
        if text.startswith('BOOT_RESET:'):
            after_reset = True
        text = re.sub(r'^\w+:\s*', '', text).strip()
        if not text:
            continue
        normalized = re.sub(r'\s+', ' ', text).upper()
        normalized = re.sub(r'\s*,\s*', ',', normalized)
        patch_bytes = re.fullmatch(r'DB (\$[0-9A-F]{2})(?:,\1)*', normalized)
        patch_fill = re.fullmatch(
            r'DS B14_(?:MAIN_BASE\+106-B14_MAIN_END|INIT_BASE\+99-B14_INIT_END),\$FF',
            normalized)
        if after_reset and ((patch_bytes and patch_bytes[1] in ('$FF', '$EA')) or patch_fill):
            discarded.append(normalized)
            continue
        rows.append(normalized.replace('"PR04"', '"PR05"'))
    return rows, discarded


def check(build):
    build = Path(build).resolve()
    report = dict(
        passed=False, scope='Static file, layout, symbol and dependency checks only',
        execution_qualified=False, CPU_simulations=0, hardware_access=False,
        serial_access=False, assembly_builds=1,
        build=build.relative_to(ROOT).as_posix() if build.is_relative_to(ROOT) else str(build),
        reference='validation/v0.2.0-reference', checks=[])

    def require(name, condition, **details):
        report['checks'].append(dict(name=name, passed=bool(condition), **details))
        if not condition:
            raise ValueError(name)

    try:
        manifest = read_json(build/'manifest.json')
        system = read_json(build/'system-manifest.json')
        symbols = read_json(build/'symbols.json')
        system_symbols = read_json(build/'system-symbols.json')
        old_manifest = read_json(REFERENCE/'firmware/manifest.json')
        old_system = read_json(REFERENCE/'firmware/system-manifest.json')
        old_symbols = read_json(REFERENCE/'firmware/symbols.json')
        f = (build/'payload'/F_NAME).read_bytes()
        old_f = (REFERENCE/'firmware/payload'/F_NAME).read_bytes()
        old_declared = old_manifest['artifacts'][F_NAME]
        require('Preserved release F reference', len(old_f) == 4096 and
                sha(old_f) == old_declared['sha256'] ==
                '1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8')
        boot = symbols['boot']
        old_boot = old_symbols['boot']
        compiled = {item['module']: item for item in manifest['compiled']}
        old_compiled = {item['module']: item for item in old_manifest['compiled']}
        require('F extent and reclaimed bytes', len(f) == 4096 and
                compiled['boot']['bytes'] == 3581 and boot['BOOT_END'] == 0xfdfd and
                old_compiled['boot']['bytes'] == 3669 and old_boot['BOOT_END'] == 0xfe55 and
                old_boot['BOOT_END']-boot['BOOT_END'] == 88)
        require('Single usable tail and reserved vector padding',
                0xffe0-boot['BOOT_END'] == 483 and
                f[boot['BOOT_END']-0xf000:0xfe4] == b'\xff'*(0xffe4-boot['BOOT_END']))
        require('Fixed F03C reserve', f[0x3c:0x40] == old_f[0x3c:0x40] == b'\xff'*4)
        fixed = ('BOOT_API_LINE', 'BOOT_API_HEX_WORD', 'BOOT_API_HEX_BYTE',
                 'BOOT_RESERVED', 'BOOT_API_PROMOTE', 'BOOT_API_READ', 'BOOT_API_CFG',
                 'BOOT_ERASE_ENTRY', 'BOOT_API_W', 'BOOT_API_UPDATE',
                 'BOOT_WEAR_DESCRIPTOR', 'BOOT_RESET')
        fixed += tuple('BOOT_SR_'+str(n) for n in range(19))
        require('Fixed ROM facade symbols', all(boot[n] == old_boot[n] for n in fixed)
                and boot['BOOT_API_PROMOTE'] == 0xf039, symbols=len(fixed))
        require('Signature and hardware vectors unchanged',
                f[:4] == old_f[:4] == b'SN\x02\0' and f[0xfe4:] == old_f[0xfe4:]
                and f[0xffc:0xffe] == b'\x04\xf0')
        require('All worker/vector RAM symbols unchanged',
                all(symbols[k] == old_symbols[k] for k in ('worker', 'vectors')))

        blobs = {}
        for module, label, count in (('worker', 'BOOT_WORKER_IMAGE', 1000),
                                     ('vectors', 'BOOT_VECTOR_IMAGE', 196)):
            start = boot[label]-0xf000
            old_start = old_boot[label]-0xf000
            blob = f[start:start+count]
            require('Embedded '+module+' unchanged', blob == old_f[old_start:old_start+count]
                    and len(blob) == compiled[module]['bytes'] == count and
                    sha(blob) == compiled[module]['sha256'] == old_compiled[module]['sha256'])
            blobs[module] = blob
        for label in ('BOOT_XCE', 'BOOT_XCE_RESTORE'):
            require(label+' CPU-mode pair retained',
                    f[boot[label]-0xf000:boot[label]-0xf000+2] == b'\xfb\xea')
        rows, discarded = retained_boot_rows(ROOT/'src/core/str8n-v2-boot.asm')
        old_rows, old_discarded = retained_boot_rows(REFERENCE/'src/core/str8n-v2-boot.asm')
        require('Boot instructions/data retained except retired padding and PR05',
                rows == old_rows and not discarded and bool(old_discarded),
                retired_padding_directives=len(old_discarded))
        require('Address arithmetic structure retained',
                rows.count('JMP BOOT_START_CHOICES+3') == 1 and
                rows.count('CMP BOOT_COMPAT_DATA-$14,Y') == 1 and
                f[boot['BOOT_START_CHOICES']-0xf000] == 0x4c and
                f[boot['BOOT_COMPAT_DATA']-0xf000:boot['BOOT_COMPAT_DATA']-0xf000+4] == b'PR05')

        artifacts = dict(manifest['artifacts'], **system['artifacts'])
        expected_names = set(old_manifest['artifacts']) | set(old_system['artifacts'])
        require('Complete eighteen-component set', len(artifacts) == 18 and
                set(artifacts) == expected_names)
        payloads = {}
        for name, record in artifacts.items():
            data = (build/'payload'/name).read_bytes()
            address, entry, decoded = s19_bytes((build/'payload'/name).with_suffix('.s19'))
            require('BIN/S19/manifest '+name, len(data) == record['bytes'] and
                    sha(data) == record['sha256'] and decoded == data and
                    address == int(record['address'], 16) and entry == int(record['entry'], 16))
            payloads[name] = data
        require('Core/system manifest binding',
                system['core_manifest_sha256'] == sha((build/'manifest.json').read_bytes()))
        actual_source = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
                         for p in sorted((ROOT/'src').rglob('*')) if p.is_file()}
        require('Current source bindings', manifest['source'] == actual_source and
                system['sources'] == actual_source)
        require('Candidate scope metadata', manifest.get('candidate') is True and
                system.get('candidate') is True and
                manifest.get('execution_qualified') is False and
                system.get('execution_qualified') is False and
                system['generation'] == '8000000F')

        f_crc = crc(f)
        require('Candidate F CRC', f_crc == 0x79a7, crc=f'{f_crc:04X}', sha256=sha(f))
        for name, prefix, module in (('maint-ro-params.inc', 'MA', 'maint'),
                                     ('edu-client-params.inc', 'EC', 'es1-client'),
                                     ('edu-sram-params.inc', 'ES', 'es1')):
            text = (build/'s/core'/name).read_text()
            sy = system_symbols[module]
            require('Exact F guard '+name,
                    re.search(prefix+r'_F_CRC_LO EQU \$A7\b', text) is not None and
                    re.search(prefix+r'_F_CRC_HI EQU \$79\b', text) is not None and
                    sy[prefix+'_F_CRC_LO'] | sy[prefix+'_F_CRC_HI'] << 8 == f_crc)
        guard_bytes = b''.join(address.to_bytes(2, 'little') + len(blobs[module]).to_bytes(2, 'little') +
                               crc(blobs[module]).to_bytes(2, 'little')
                               for module, address in (('worker', 0x7800), ('vectors', 0x7e20)))
        for module, filename, label, immutable in (
                ('maint', 'STR8N-F-MAINT-RO-RAM.bin', 'MA_GUARD_TABLE', 'MA_IMM_END'),
                ('es1-client', 'STR8N-F-EDU-SRAM-RAM.bin', 'EC_GUARDS', 'EC_IMM_END')):
            sy = system_symbols[module]
            data = payloads[filename]
            offset = sy[label]-0x200
            require('RAM guard and image seal '+module,
                    data[offset:offset+12] == guard_bytes and
                    crc(data[:sy[immutable]-0x200]) == 0)

        for flavor in ('BASE', 'VX1'):
            for page in ('A', 'B'):
                name = f'STR8N-F-MON-{flavor}-{page}.bin'
                data = payloads[name]
                require('Monitor compatibility/generation/CRC '+flavor+' '+page,
                        data[20:24] == b'PR05' and data[8:12] == bytes.fromhex('0F000080') and
                        int.from_bytes(data[18:20], 'little') == crc(data[:18]+data[32:]))
        for address in (0x8000, 0x9000):
            module = f'flash-{address:04x}'
            sy = system_symbols[module]
            data = payloads[f'STR8N-F-FLASH-{address:04X}-RAM.bin']
            image = payloads[f'STR8N-F-FLASH-{address:04X}.bin']
            offset = sy['BM_CODE_CRC']-0x200
            require('FLASH guard/seal/ROM body '+module,
                    sy['BM_F_CRC_LO'] | sy['BM_F_CRC_HI'] << 8 == f_crc and
                    int.from_bytes(data[offset:offset+2], 'little') == crc(data[:sy['BM_CODE_END']-0x200]) and
                    image[128:128+len(data)] == data)
        es = payloads['STR8N-F-ES1-8.bin']
        ec = payloads['STR8N-F-EDU-SRAM-RAM.bin']
        header_offset = system_symbols['es1-client']['EC_EXPECTED_HEADER']-0x200
        require('ES1 sector seal and client expected header',
                crc(es) == 0 and ec[header_offset:header_offset+64] == es[:64] and
                es[16:20] == bytes.fromhex('0F000080'))
        vx = payloads['STR8N-F-VX1-E.bin']
        vx_sy = system_symbols['vx1']
        def vx_bytes(label, size):
            offset = vx_sy[label]-0xe000
            return vx[offset:offset+size]
        require('VX1 exact F identity/generation/release/seal', crc(vx) == 0 and
                vx_sy['F_CRC_LO'] | vx_sy['F_CRC_HI'] << 8 == f_crc and
                vx_bytes('VX_F_IDENTITY', 32) == hashlib.sha256(f).digest() and
                vx_bytes('VX_F_GENERATION', 4) == bytes.fromhex('0F000080') and
                vx_bytes('VX_F_RELEASE_TEXT', 16) == b'2.0proto b15c1'.ljust(16, b'\0'))
        for name in ('STR8N-F-DEMO-RAM.bin', 'STR8N-F-VERSION-RAM.bin'):
            declared = old_manifest['artifacts'].get(name, old_system['artifacts'].get(name))
            require('Public-only component unchanged '+name, sha(payloads[name]) == declared['sha256'])
        report.update(passed=True, old_boot_bytes=3669, boot_bytes=3581,
                      reclaimed_bytes=88, usable_free_bytes=483,
                      usable_free_range='FDFD-FFDF', vector_padding_range='FFE0-FFE3',
                      reserved_facade_bytes=4, F_sha256=sha(f), F_crc=f'{f_crc:04X}',
                      private_compatibility='PR05', generation='8000000F',
                      component_count=len(artifacts))
    except (AssertionError, KeyError, OSError, ValueError) as error:
        report['error'] = str(error)
    destination = build/'layout-check.json'
    destination.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    if not report['passed']:
        raise ValueError('Static layout check failed: '+report['error']+'; see '+str(destination))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT/'build/fcompact-r1')
    args = parser.parse_args()
    result = check(args.build)
    print(f"PASS {len(result['checks'])} static checks; 88 bytes reclaimed, 483 usable tail bytes; "
          'no execution or hardware qualification')
