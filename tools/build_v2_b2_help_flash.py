"""Build permanent B3:C help; no firmware rebuild or device access."""
import hashlib
import json
from pathlib import Path
import shutil
import build_v2_config as assembler
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-b2-help-flash'
SOURCES = ROOT / 'tools/v2-apps'
NAME = 'str8n-v2-b2-help-c000-cfff'
START, HANDLER, STUB = 0xC000, 0xC300, 0x7400


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    assembler.OUT = OUT
    (OUT / 'help-flash-tests.json').unlink(missing_ok=True)
    includes = (ROOT / 'src/v2-b2', OUT)
    def assemble(name, start, source):
        expanded = OUT / (name + '-expanded.asm')
        expanded.write_text(long_branches(source.read_text()), encoding='ascii')
        return assembler.assemble(name, start, shutil.which('wdc02as'),
            shutil.which('wdcln'), source_file=expanded, include_dirs=includes)
    handler, hs = assemble('help-flash-handler', HANDLER,
        SOURCES / 'str8n-v2-b2-help-overlay.asm')
    assert hs['HELP_ENTRY'] == HANDLER and hs['HELP_END'] <= 0xD000
    (OUT / 'help-flash-addresses.inc').write_text(
        f'FLASH_HANDLER EQU ${HANDLER:04X}\nFLASH_STUB EQU ${STUB:04X}\n')
    init, symbols = assemble('help-flash-init', START,
        SOURCES / 'str8n-v2-b2-help-flash.asm')
    assert symbols['FLASH_INIT_END'] <= HANDLER
    assert set(init) == set(range(START, symbols['FLASH_INIT_END']))
    assert set(handler) == set(range(HANDLER, hs['HELP_END']))
    memory = {**init, **handler}
    # Own the whole sector: zero-filled gaps cannot be mistaken for erased
    # RTS storage even if the owner later enables B3:C in a storage mask.
    sector = bytes(memory.get(a, 0) for a in range(START, 0xD000))
    assert b'\xff'*24 not in sector
    binary = OUT / (NAME + '.bin')
    binary.write_bytes(sector)
    lines = [assembler.record('0', 0, b'B2 permanent H: B3 C sector only')]
    lines += [assembler.record('1', a, sector[a-START:a-START+32])
              for a in range(START, 0xD000, 32)]
    lines.append(assembler.record('9', START))
    target = OUT / (NAME + '.s19')
    target.write_text('\n'.join(lines)+'\n', encoding='ascii')
    loaded, entry = assembler.read_s19(target)
    assert entry == START and bytes(loaded[a] for a in range(START,0xD000)) == sector
    metadata = dict(name=NAME, bank=3, sector='C', entry=START, handler=HANDLER,
        autoload_entry=symbols['AUTO_ENTRY'], autoload_command='K AUTO +H',
        initializer_bytes=len(init), handler_bytes=len(handler),
        code_text_bytes=len(memory), sector_bytes=4096,
        handler_end_exclusive=hs['HELP_END'],
        unused_sector_bytes=4096-len(memory), unused_fill_byte=0,
        trampoline_start=STUB,
        trampoline_bytes=3, trampoline_hex=bytes((0x4C,HANDLER & 255,HANDLER >> 8)).hex(),
        application_ram_bytes=0, overlay_ram_bytes=0,
        core_bytes_added=0, e_carrier_bytes_added=0,
        boot_command='C 1 3 C000 40',
        binary_sha256=hashlib.sha256(sector).hexdigest(),
        s19_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        initializer_symbols=symbols, handler_symbols=hs,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), SOURCES/'str8n-v2-b2-help-flash.asm',
                      SOURCES/'str8n-v2-b2-help-overlay.asm')})
    (OUT / 'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(target, f'{len(memory)} code/text bytes; three manager RAM bytes; zero app/overlay/core bytes')


if __name__ == '__main__':
    main()
