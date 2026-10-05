"""Build the independent b2 manager command/service acceptance probe; no I/O."""
import hashlib
import json
from pathlib import Path
import shutil
import build_v2_config as assembler
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-b2-board-probes'
SOURCE = ROOT / 'tools/v2-apps/str8n-v2-b2-manager-test-2000.asm'
NAME = 'str8n-v2-b2-manager-test-2000'


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    expanded = OUT / 'manager-test-expanded.asm'
    expanded.write_text(long_branches(SOURCE.read_text()), encoding='ascii')
    assembler.OUT = OUT
    memory, symbols = assembler.assemble(NAME, 0x2000, shutil.which('wdc02as'),
        shutil.which('wdcln'), source_file=expanded, include_dirs=(ROOT/'src/v2-b2',))
    end = symbols['APP_END']
    assert end < 0x5800 and set(memory) == set(range(0x2000,end))
    lines = [assembler.record('0',0,b'B2 independent manager probe')]
    lines += [assembler.record('1',a,bytes(memory[x] for x in range(a,min(a+32,end))))
              for a in range(0x2000,end,32)]
    lines += [assembler.record('9',0x2000)]
    target = OUT/(NAME+'.s19')
    target.write_text('\n'.join(lines)+'\n', encoding='ascii')
    assert assembler.read_s19(target) == (memory,0x2000)
    (OUT/'manifest.json').write_text(json.dumps({'name':NAME,'bytes':end-0x2000,
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        's19_sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2)+'\n')
    print(target, end-0x2000, 'bytes')


if __name__ == '__main__':
    main()
