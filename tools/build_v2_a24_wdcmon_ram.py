"""Build the WDCMONv2 RAM installer for the exact alpha24 F sector.

This is an offline artifact build. It does not connect to a board.
"""
import hashlib
import json
import shutil
import subprocess

import build_v2_a24 as a24


ROOT = a24.ROOT
BUILD = ROOT / 'BUILD/v2-alpha24-wdcmon-ram'
SOURCE = ROOT / 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm'
NAME = 'str8n-v2-alpha24-wdcmonv2-install-2000'


def run(*args):
    subprocess.run(args, cwd=BUILD, check=True)


def main():
    top = (a24.OUT / f'{a24.STEM}-f000-ffff.bin').read_bytes()
    if len(top) != 4096 or top[:4] != b'SN\x02\x00':
        raise ValueError('alpha24 F image identity invalid')
    if top[0xFFC:0xFFE] == b'\xff\xff':
        raise ValueError('alpha24 RESET vector is erased')
    BUILD.mkdir(parents=True, exist_ok=True)
    candidate = BUILD / f'{a24.STEM}-f000-ffff.bin'
    candidate.write_bytes(top)
    fnv = 2166136261
    for byte in top:
        fnv = ((fnv ^ byte) * 16777619) & 0xffffffff
    (BUILD / 'str8n-v2-rc1-wdcmonv2-install-image.inc').write_text(''.join(
        f'W2I_CANDIDATE_FNV{n}      EQU             ${((fnv >> (8*n)) & 255):02X}\n'
        for n in range(4)), encoding='ascii')
    local_source = BUILD / SOURCE.name
    shutil.copyfile(SOURCE, local_source)
    run('wdc02as', '-G', '-L', '-S', '-W', '-I', str(BUILD),
        '-DSTR8_V2_RC1=1', '-DSTR8_V2_A24=1', '-DSTR8_V2_A24_UNIFIED=1', str(local_source))
    s19 = BUILD / (NAME + '.s19')
    run('wdcln', '-g', '-s', '-t', '-hm19', '-j', '-o', str(s19),
        str(local_source.with_suffix('.obj')))
    lines = s19.read_text(encoding='ascii').splitlines()
    lines[-1] = 'S9032000DC'
    s19.write_text('\n'.join(lines) + '\n', encoding='ascii')
    linked, entry = a24.read_s19(s19)
    if entry != 0x2000 or min(linked) != 0x2000 or max(linked) >= 0x4000 \
            or set(linked) != set(range(0x2000, max(linked) + 1)):
        raise ValueError('alpha24 installer is outside its dense $2000-$3FFF RAM window')
    code = bytes(linked[address] for address in range(0x2000, max(linked) + 1))
    if not code.startswith(bytes.fromhex('38 FB 78')):
        raise ValueError('unified entry must use SEC/$FB before 8-bit code')
    for marker in (b'WDCMONV2 -> STR8-N 2.0a24',
                   b'TYPE INSTALL STR8-N 2.0a24> ',
                   b'INSTALL STR8-N 2.0A24'):
        if marker not in code:
            raise ValueError(f'alpha24 installer missing linked marker {marker!r}')
    run('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'tools/wdcmonv2/check_wdcmonv2_install.ps1'),
        '-SourcePath', str(SOURCE), '-S19Path', str(s19),
        '-MapPath', str(s19.with_suffix('.map')),
        '-TopBinPath', str(candidate), '-CandidateBinPath', str(candidate),
        '-VersionText', a24.VERSION, '-V2Signature', '-Unified02And816Entry')
    run('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'tools/wdcmonv2/start_wdcmonv2_ram.ps1'),
        '-ImagePath', str(s19), '-ValidateOnly')
    report = {
        'version': a24.VERSION, 'entry': '2000',
        'candidate_f_sha256': hashlib.sha256(top).hexdigest(),
        'candidate_f_fnv1a': f'{fnv:08X}',
        'installer_s19_sha256': hashlib.sha256(s19.read_bytes()).hexdigest(),
        'board_tested': False,
    }
    (BUILD / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{s19}: F SHA-256 {report["candidate_f_sha256"]}')


if __name__ == '__main__':
    main()
