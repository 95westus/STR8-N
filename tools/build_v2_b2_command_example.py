"""Build an educational H+X B3:C image; never touch firmware or a device."""
import hashlib
import json
import shutil
from pathlib import Path
import build_v2_b2_help_flash as help_module
import build_v2_config as assembler
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-b2-command-example'
SOURCES = ROOT / 'tools/v2-apps'
NAME = 'str8n-v2-b2-h-x-c000-cfff'
ENTRY, HANDLER, STUB = 0xC700, 0xCA00, 0x7403


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'command-example-tests.json').unlink(missing_ok=True)
    # Build H in a private output directory, leaving its normal artifacts alone.
    help_module.OUT = OUT / 'base-help'
    help_module.main()
    base_meta = json.loads((help_module.OUT / 'manifest.json').read_text())
    sector = bytearray((help_module.OUT / (help_module.NAME + '.bin')).read_bytes())
    assert base_meta['handler_end_exclusive'] <= ENTRY
    (OUT / 'asm').mkdir(exist_ok=True)
    assembler.OUT = OUT
    (OUT / 'command-x-addresses.inc').write_text(
        f'FLASH_HANDLER EQU ${HANDLER:04X}\nFLASH_STUB EQU ${STUB:04X}\n')
    def assemble(name, start, source):
        expanded = OUT / (name + '-expanded.asm')
        expanded.write_text(long_branches(source.read_text()), encoding='ascii')
        return assembler.assemble(name, start, shutil.which('wdc02as'),
            shutil.which('wdcln'), source_file=expanded,
            include_dirs=(ROOT / 'src/v2-b2', OUT))
    handler, handler_symbols = assemble('command-x-handler', HANDLER,
        SOURCES / 'str8n-v2-b2-command-x.asm')
    with (OUT/'command-x-addresses.inc').open('a') as inc:
        inc.write(f'NAMED_HELLO EQU ${handler_symbols["HELLO_ENTRY"]:04X}\n'
                  f'NAMED_ECHO EQU ${handler_symbols["ECHO_ENTRY"]:04X}\n')
    init, init_symbols = assemble('command-x-init', ENTRY,
        SOURCES / 'str8n-v2-b2-command-x-init.asm')
    assert init_symbols['FLASH_INIT_END'] <= HANDLER
    assert handler_symbols['X_END'] <= 0xD000
    for memory, start, end in ((init, ENTRY, init_symbols['FLASH_INIT_END']),
                             (handler, HANDLER, handler_symbols['X_END'])):
        assert set(memory) == set(range(start, end))
        for address, byte in memory.items():
            assert sector[address-0xC000] == 0
            sector[address-0xC000] = byte
    assert b'\xff'*24 not in sector
    binary = OUT / (NAME + '.bin')
    binary.write_bytes(sector)
    lines = [assembler.record('0', 0, b'B2 educational H+X B3:C')]
    lines += [assembler.record('1', address, sector[address-0xC000:address-0xC000+32])
              for address in range(0xC000, 0xD000, 32)]
    lines.append(assembler.record('9', ENTRY))
    s19 = OUT / (NAME + '.s19')
    s19.write_text('\n'.join(lines)+'\n', encoding='ascii')
    memory, entry = assembler.read_s19(s19)
    assert entry == ENTRY and bytes(memory[a] for a in range(0xC000, 0xD000)) == sector
    metadata = dict(entry=ENTRY, handler=HANDLER, stub=STUB,
        autoload_entries=dict(H=base_meta['autoload_entry'], X=init_symbols['AUTO_ENTRY']),
        autoload_commands=['K AUTO +X', 'K AUTO +H'],
        initializer_bytes=len(init), handler_bytes=len(handler),
        x_code_text_bytes=len(init)+len(handler),
        total_code_text_bytes=base_meta['code_text_bytes']+len(init)+len(handler),
        sector_bytes=4096, x_manager_ram_bytes=3, total_h_x_manager_ram_bytes=6,
        application_ram_bytes=0, overlay_ram_bytes=0,
        core_bytes_added=0, e_carrier_bytes_added=0,
        boot_command='C 1 3 C700 40', initializer_symbols=init_symbols,
        handler_symbols=handler_symbols,
        s19_sha256=hashlib.sha256(s19.read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(sector).hexdigest())
    (OUT / 'manifest.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(s19, f'X: {len(init)+len(handler)} flash bytes, 3 manager RAM bytes')


if __name__ == '__main__':
    main()
