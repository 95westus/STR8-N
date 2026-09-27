"""Build the stock WDCMONv2 RAM migration installer for the exact a22 F top."""
import hashlib
import shutil
import subprocess
from pathlib import Path

import build_v2_a22 as a22

ROOT = a22.ROOT
BUILD = ROOT / 'BUILD/v2-alpha22-wdcmon-ram'
SOURCE = ROOT / 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm'
NAME = 'str8n-v2-alpha22-wdcmonv2-install-2000'


def run(*args):
    subprocess.run(args, cwd=BUILD, check=True)


def main():
    top = (a22.OUT / f'{a22.STEM}-f000-ffff.bin').read_bytes()
    if len(top) != 4096 or top[:4] != b'SN\x02\x00':
        raise ValueError('a22 top identity invalid')
    BUILD.mkdir(parents=True, exist_ok=True)
    candidate = BUILD / f'{a22.STEM}-f000-ffff.bin'
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
        '-DSTR8_V2_RC1=1', '-DSTR8_V2_A22=1', str(local_source))
    s19 = BUILD / (NAME + '.s19')
    run('wdcln', '-g', '-s', '-t', '-hm19', '-j', '-o', str(s19),
        str(local_source.with_suffix('.obj')))
    lines = s19.read_text(encoding='ascii').splitlines()
    lines[-1] = 'S9032000DC'
    s19.write_text('\n'.join(lines) + '\n', encoding='ascii')
    run('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'tools/wdcmonv2/check_wdcmonv2_install.ps1'),
        '-SourcePath', str(SOURCE), '-S19Path', str(s19),
        '-MapPath', str(s19.with_suffix('.map')),
        '-TopBinPath', str(candidate), '-CandidateBinPath', str(candidate),
        '-VersionText', '2.0a22', '-V2Signature')
    run('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'tools/wdcmonv2/start_wdcmonv2_ram.ps1'),
        '-ImagePath', str(s19), '-ValidateOnly')
    print(f'{s19}: F SHA-256 {hashlib.sha256(top).hexdigest()}')


if __name__ == '__main__':
    main()
