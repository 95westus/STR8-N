"""Build the read-only NFA1 archive helper; never opens a device."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import build as migration

ROOT = Path(__file__).resolve().parent


def build(out, assembler=None, linker=None):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory')
    assembler = assembler or shutil.which('wdc02as')
    linker = linker or shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC wdc02as and wdcln must be on PATH')
    out.mkdir(parents=True)
    source = (ROOT/'nf-archive.asm').read_text()
    engine = (ROOT/'nf-migrate.asm').read_text()
    # Reuse the exact already built project FT245/FNV code; no ROM/flash helper.
    fnv = engine[engine.index('HASH_RANGE:\n'):engine.index('\nSELECT_BANK:\n')]
    ft245 = engine[engine.index('POLL_BYTE:\n'):engine.index('\nPRINT_DEST:\n')]
    for name, body in (('archive-fnv.inc', fnv), ('archive-ft245.inc', ft245)):
        assert not re.search(r'\b(?:UNLOCK|ERASE_RAW|PROGRAM_RAW|WAIT_FLASH|IDENTIFY_FLASH)\b', body)
        prefix = 'NFA_FNV_' if name == 'archive-fnv.inc' else 'NFA_FT_'
        (out/name).write_text(migration.long_branches(body).replace('NFM_LONG_', prefix),
                              encoding='ascii', newline='\n')
    # The full read-only closure must contain no write through a flash pointer.
    closure = '\n'.join((source, fnv, ft245))
    assert not re.search(r'\b(?:STA|STX|STY|STZ)\s+\(', closure)
    assert '$D555' not in closure and '$AAAA' not in closure
    assert not any(name in closure for name in ('PIA_CRA', 'FLASH_DATA', 'FLASH_ERROR'))
    (out/'nf-archive.asm').write_text(migration.long_branches(source), encoding='ascii', newline='\n')
    logs = []
    for command in ([assembler, '-G', '-L', '-S', '-W', 'nf-archive.asm'],
                    [linker, '-g', '-s', '-t', '-c2000', '-hm19', '-j',
                     '-o', 'nf-archive.s19', 'nf-archive.obj']):
        result = subprocess.run(command, cwd=out, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=result.returncode,
                         stdout=result.stdout, stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n', encoding='utf-8')
        if result.returncode:
            raise RuntimeError('WDC archive build failed; inspect build-log.json')
    symbols = {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', (out/'nf-archive.map').read_text(), re.M)}
    memory = migration.read_s19(out/'nf-archive.s19')
    assert symbols['ENTRY_65C02'] == 0x2000 and symbols['ENTRY_65C816'] == 0x2010
    assert symbols['ARCHIVE_END'] < 0x3000
    assert set(memory) == set(range(0x2000, symbols['ARCHIVE_END']))
    template = bytearray(8192)
    for address, value in memory.items():
        template[address-0x2000] = value
    template[-4:] = migration.fnv(template[:-4]).to_bytes(4, 'little')
    assert migration.fnv(template[:-4]) == int.from_bytes(template[-4:], 'little')
    (out/'archive.bin').write_bytes(template)
    (out/'archive.s19').write_bytes(migration.s19(template, 0x2000))
    (out/'archive-816.s19').write_bytes(migration.s19(template, 0x2010))
    recovery, recovery_source = migration.recovery_loader(template)
    (out/'archive-recovery.bin').write_bytes(recovery)
    (out/'archive-recovery.s19').write_bytes(migration.s19(recovery, 0x200, start=0x200))
    (out/'archive-recovery.asm').write_text(recovery_source, encoding='ascii', newline='\n')
    manifest = dict(schema=1, status='read-only-helper-not-execution-qualified',
        build_passed=True, execution_qualified=False, hardware_access=False,
        serial_access=False, CPU_simulations=0,
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        shared_engine_source_sha256=hashlib.sha256(engine.encode()).hexdigest(),
        shared_fnv_sha256=hashlib.sha256(fnv.encode()).hexdigest(),
        shared_ft245_sha256=hashlib.sha256(ft245.encode()).hexdigest(),
        archive_sha256=hashlib.sha256(template).hexdigest(), bytes=len(template),
        code_bytes=symbols['ARCHIVE_END']-0x2000, entry_65c02=0x2000, entry_65c816=0x2010,
        ram_first=0x2000, ram_last=0x3fff, scratch='6000-6011', zero_page='E0-E9',
        emulation_stack='0100-01FF', vendor_native_stack_0700_not_uploaded=True,
        flash_commands=False, flash_ID_commands=False, SPI_RTC_EEPROM_EDU_commands=False,
        io_writes=['7FE0 FT control', '7FE1 FT data', '7FE2/7FE3 directions', '7FEC bank PCR'],
        passes=2, banks_per_pass=4, bank_bytes=32768, trailer='FNV1a32 little endian',
        ready='ARCHIVER READY; G then Enter> ', confirm='G\r',
        header='ARCHIVE B{bank} PASS {pass}\r\n',
        completed='ARCHIVE COMPLETE; PRESS PHYSICAL RESET\r\n',
        final_bank=3, requires_physical_reset=True,
        recovery_loader=dict(bytes=len(recovery), entry=0x200,
            sha256=hashlib.sha256(recovery).hexdigest(), structural_address_check=True),
        limits=['No device/CPU acceptance yet', 'WDC startup after physical RESET is not qualified by this helper',
                'Helper issues no SPI/RTC/EDU writes; vendor startup behavior is separate',
                'Host must escrow owner RAM/ZP before uploading; restoration is a later explicit step'])
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (out/'symbols.json').write_text(json.dumps(symbols, indent=2)+'\n', encoding='utf-8')
    print('PASS read-only NFA1 helper build:', manifest['code_bytes'],
          'code bytes; no execution/hardware qualification', flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--assembler')
    parser.add_argument('--linker')
    args = parser.parse_args()
    build(args.out, args.assembler, args.linker)
