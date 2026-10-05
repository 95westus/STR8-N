"""Build an independent L-loadable H module; never rebuild or alter firmware."""
import hashlib
import json
from pathlib import Path
import shutil
import build_v2_config as assembler
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-b2-help'
SOURCES = ROOT / 'tools/v2-apps'
NAME = 'str8n-v2-b2-help-2000'


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    assembler.OUT = OUT
    for stale in ('help-tests.json',):
        (OUT / stale).unlink(missing_ok=True)
    includes = (ROOT / 'src/v2-b2', OUT)
    def assemble(name, start, source):
        expanded = OUT / (name + '-expanded.asm')
        expanded.write_text(long_branches(source.read_text()), encoding='ascii')
        return assembler.assemble(name, start, shutil.which('wdc02as'),
            shutil.which('wdcln'), source_file=expanded, include_dirs=includes)
    pinned, symbols = assemble('help-overlay', 0x5800,
        SOURCES / 'str8n-v2-b2-help-overlay.asm')
    end = symbols['HELP_END']
    assert end <= 0x6000 and set(pinned) == set(range(0x5800, end))
    data = bytes(pinned[a] for a in range(0x5800, end))
    (OUT / 'help-overlay.bin').write_bytes(data)
    (OUT / 'help-image.inc').write_text(
        f'PINNED_ENTRY EQU ${symbols["HELP_ENTRY"]:04X}\nPINNED_END EQU ${end:04X}\n')
    (OUT / 'help-bytes.inc').write_text('\n'.join(
        ' DB ' + ','.join(f'${b:02X}' for b in data[i:i+24])
        for i in range(0, len(data), 24)) + '\n')
    memory, loader = assemble(NAME, 0x2000,
        SOURCES / 'str8n-v2-b2-help-2000.asm')
    app_end = loader['APP_END']
    assert app_end <= 0x5800 and set(memory) == set(range(0x2000, app_end))
    lines = [assembler.record('0', 0, b'B2 optional H extension')]
    lines += [assembler.record('1', a, bytes(memory[x]
        for x in range(a, min(a+32, app_end)))) for a in range(0x2000, app_end, 32)]
    lines.append(assembler.record('9', 0x2000))
    target = OUT / (NAME + '.s19')
    target.write_text('\n'.join(lines) + '\n', encoding='ascii')
    assert assembler.read_s19(target) == (memory, 0x2000)
    (OUT / 'manifest.json').write_text(json.dumps({
        'name': NAME, 'entry': 0x2000, 'load_bytes': app_end-0x2000,
        'overlay_start': 0x5800, 'overlay_end_exclusive': end,
        'overlay_bytes': len(data), 'handler': symbols['HELP_ENTRY'],
        'core_bytes_added': 0, 'e_carrier_bytes_added': 0,
        's19_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'overlay_sha256': hashlib.sha256(data).hexdigest(),
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), SOURCES / 'str8n-v2-b2-help-overlay.asm',
                      SOURCES / 'str8n-v2-b2-help-2000.asm')},
    }, indent=2) + '\n')
    print(target, f'{app_end-0x2000} load bytes; {len(data)} pinned RAM bytes; zero ROM bytes')


if __name__ == '__main__':
    main()
