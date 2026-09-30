"""Build the guarded a24 E repair from the previously verified board E/F image."""
from pathlib import Path
import hashlib
import json
import shutil
import build_v2_a24 as a24

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / 'output/qualification/board-2205-a23-2026-09-27/b3-after.bin'
OUT = ROOT / 'BUILD/v2-alpha24-board-update'
NAME = 'str8n-v2-alpha24-e-update-2000'

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    prior = PRIOR.read_bytes()
    if len(prior) != 8192 or sha(prior[4096:]) != '24d0d9f2c7f619aece4d608b706c1a9b862b69c3bc2a411fe7dcc79fc1d36fa0':
        raise ValueError('Prior verified a23 E/F image mismatch')
    old = prior[:4096]
    if sha(old) != 'cdaaf02e0a4fa943379cffa87e92d90c90722613e1419c5bd0be90a0eb9164ac':
        raise ValueError('Prior verified E image mismatch')
    built = (a24.OUT / f'{a24.STEM}-e000-efff.bin').read_bytes()
    new = old[:0x800] + built[0x800:0xf00] + old[0xf00:]
    if new == old:
        raise ValueError('No E relink detected')
    stage = OUT / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    a24.include_bytes(stage / 'e-old-image.inc', old)
    a24.include_bytes(stage / 'e-new-image.inc', new)
    worker = json.loads((a24.OUT / 'build.json').read_text())['worker']
    (stage / 'e-worker-addresses.inc').write_text(''.join(
        f'{name:24} EQU     ${worker[name]:04X}\n' for name in ('V2W_SNAPSHOT', 'V2W_MUTATE')))
    old_out = a24.OUT
    try:
        a24.OUT = OUT
        memory, sym = a24.assemble(NAME, 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'),
                                   source_file=a24.SOURCE / 'str8n-v2-e-repair-2000.asm',
                                   include_dirs=(stage,))
    finally:
        a24.OUT = old_out
    if sym['START'] != 0x2000 or sym['E_END'] >= 0x6900:
        raise ValueError('E updater layout changed')
    if bytes(memory[a] for a in range(sym['E_NEW'], sym['E_NEW']+4096)) != new:
        raise ValueError('New E embed mismatch')
    if bytes(memory[a] for a in range(sym['E_OLD'], sym['E_OLD']+4096)) != old:
        raise ValueError('Old E embed mismatch')
    lines = [a24.record('0', 0, b'STR8-N 2.0a24 E update')]
    lines.extend(a24.record('1', addr, bytes(memory[a] for a in range(addr, min(addr+32, sym['E_END']))))
                 for addr in range(0x2000, sym['E_END'], 32))
    lines.append(a24.record('9', 0x2000))
    path = OUT / f'{NAME}.s19'
    path.write_text('\n'.join(lines)+'\n')
    parsed, entry = a24.read_s19(path)
    if parsed != memory or entry != 0x2000:
        raise ValueError('E updater S19 mismatch')
    (OUT / 'old-e.bin').write_bytes(old)
    (OUT / 'candidate-e.bin').write_bytes(new)
    print(json.dumps({'old_e':sha(old),'new_e':sha(new),'changed_bytes':sum(x!=y for x,y in zip(old,new)),
                      'updater':str(path),'updater_sha256':sha(path.read_bytes())}, indent=2))

if __name__ == '__main__': main()
