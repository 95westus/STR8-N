"""Build the v2.0a22 RAM bank maintenance utility against its worker map."""
from pathlib import Path
import json
import shutil

import build_v2_a22 as a22


def main():
    report = json.loads((a22.OUT / 'build.json').read_text())
    stage = a22.OUT / 'bank-maint-asm'
    stage.mkdir(parents=True, exist_ok=True)
    (stage / 'bank-maint-worker.inc').write_text(''.join(
        f'{name:24} EQU     ${report["worker"][name]:04X}\n'
        for name in ('V2W_SELECT', 'V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')
    name = 'str8n-v2-bank-maint-2000'
    memory, symbols = a22.assemble(name, 0x2000, shutil.which('wdc02as'),
                                    shutil.which('wdcln'),
                                    source_file=a22.SOURCE / (name + '.asm'),
                                    include_dirs=(stage,))
    end = symbols['BM_END']
    if symbols['START'] != 0x2000 or end > 0x6900:
        raise ValueError('Bank maintenance image is outside application RAM')
    image = a22.dense_image(memory, 0x2000, end)
    lines = [a22.record('0', 0, b'STR8-N v2 bank maint')]
    lines.extend(a22.record('1', address, image[address-0x2000:address-0x2000+32])
                 for address in range(0x2000, end, 32))
    lines.append(a22.record('9', 0x2000))
    out = a22.OUT / (name + '.s19')
    out.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a22.read_s19(out)
    if parsed != memory or entry != 0x2000:
        raise ValueError('Bank maintenance S19 round trip failed')
    print(f'{out}: {len(image)} bytes')


if __name__ == '__main__':
    main()
