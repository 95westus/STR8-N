"""Build only the high-RAM S19 overlay and its disposable raw-BIN launcher."""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_mona import ROOT, cells, sha
from mona_branches import conservative_branches


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh build directory')
    freeze = json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == freeze['sha256']
    assert all(sha((ROOT/n).read_bytes()) == h for n,h in freeze['sources'].items())
    out.mkdir(parents=True)
    source = ROOT/'monitors/native/s19-loader.asm'
    body, branches = conservative_branches(source.read_text(), 'SL_LONG_')
    (out/source.name).write_text(body, encoding='utf-8')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc', out/'str8n-v2-public.inc')
    logs = []
    for command in (
        [shutil.which('wdc02as'), '-G','-L','-S','-W',source.name],
        [shutil.which('wdcln'), '-g','-s','-t','-c6B00','-hm19','-j','-o','s19-loader.s19','s19-loader.obj'],
    ):
        assert command[0]
        p = subprocess.run(command, cwd=out, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:
            raise RuntimeError('Build failed; inspect build-log.json')
    symbols = {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (out/'s19-loader.map').read_text(), re.M)}
    memory = cells(out/'s19-loader.s19')
    raw = bytes(memory[a] for a in range(0x6B00,symbols['SL_END']))
    assert len(raw) <= 1534
    image = raw.ljust(1534,b'\xff')
    image += binascii.crc_hqx(image,65535).to_bytes(2,'big')
    assert binascii.crc_hqx(image,65535) == 0 and image[:8] == b'SL\x01\x06PR05'
    # The ROM L packet borrows0200-08FF. Its caller runs at7400, so an S1
    # may subsequently replace that entire owner-RAM region safely.
    launcher = bytearray(bytes.fromhex('78 D8 A2 00'))
    loop = len(launcher)
    for page in range(6):
        launcher += bytes([0xBD,0,(3+page),0x9D,0,(0x6B+page)])
    launcher += bytes.fromhex('BD C0 02 9D 00 74 E8 D0')
    launcher += bytes([(loop-(len(launcher)+1))&255])
    launcher += bytes.fromhex('4C 00 74')
    assert len(launcher) <= 0xC0
    launcher = launcher.ljust(0xC0,b'\xff')+bytes.fromhex('20 08 6B 4C 67 7E')
    packet = bytes(launcher).ljust(256,b'\xff')+image
    artifacts = {}
    for name, data in (('S19-LOADER-6B00.bin',image), ('STR8N-S19-RAM.bin',packet)):
        (out/name).write_bytes(data)
        artifacts[name] = dict(bytes=len(data),sha256=sha(data))
    report = dict(component='S19 RAM loader',status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',
        artifacts=artifacts,linked_bytes=len(raw),free_bytes=1534-len(raw),
        source_sha256={str(source.relative_to(ROOT)):sha(source.read_bytes())},
        code='6B00-70FF',state='7500-7506',record_buffer='7700-77FB',
        application_destinations='0200-66FF',records='S0/S1/S9; S9 never executes',
        F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,build_passes=1,branches=branches)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('linked_bytes','free_bytes','artifacts')},indent=2))
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    build(a.out)
