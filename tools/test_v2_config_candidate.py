"""Alpha24-derived F-pocket regression; host model only."""
import hashlib
import json
import sys
import build_v2_config as firmware
sys.modules['build_v2'] = firmware
sys.modules['build_v2_a24'] = firmware
sys.modules['build_v2_a23'] = firmware
import test_v2_a24_regression as regression


def check_beta1_extension_compatibility():
    """Existing E images use these direct calls in addition to the public ABI."""
    report = json.loads((firmware.OUT / 'build.json').read_text())
    expected = {
        'V2_HEX_WORD': 0xF371, 'V2_HEX_BYTE': 0xF375,
        'V2_SKIP_SPACES': 0xF364, 'V2_PRINT_ADDR': 0xF5AF,
        'V2_PUTC': 0x7BBF, 'V2_HEX_OUT': 0x7EB4, 'V2_NEWLINE': 0x7ECA,
        'V2_BAD_HEX': 0xF1EF, 'V2_BAD_RANGE': 0xF1F3,
        'V2_PROTECTED': 0xF1F7, 'V2_PROMPT': 0xF120, 'V2_MESSAGE': 0xF18D,
        'V2_FLASH_FAILED': 0xF594, 'V2_FLASH_DONE': 0xF58F,
        'V2_CONFIRM': 0xF5B9, 'V2_PRINT': 0xF9ED, 'V2_READ_LINE': 0xF969,
        'V2_CHECK_CANCEL': 0x7B52, 'V2_SR_ERROR_TEXT': 0x21,
        'V2_CANCELLED': 0xF19E,
        'V2W_READ': 0x7930, 'V2W_SNAPSHOT': 0x797A, 'V2W_MUTATE': 0x79A3,
    }
    for name, address in expected.items():
        assert report['resident'][name] == address, f'Installed S/R binding moved: {name}'
    # Exact E identity means the following S/R regression also exercises the
    # previously shipped binary, not merely an extension relinked for this F.
    image = (firmware.OUT / f'{firmware.STEM}-e000-efff.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == (
        '8a684bdb84ebb0d9cf5e925abc65a6d99db8736e3ffe14de6a24a17f53d139a6'
    ), 'Beta 1 E image changed'
    print('PASS: installed beta 1 S/R bindings and exact E image', flush=True)


def check_relocated_boot_delay():
    """Execute real opcodes: startup tests normally fast-forward this loop."""
    report = json.loads((firmware.OUT / 'build.json').read_text())
    worker = report['worker']
    image, _ = firmware.read_s19(firmware.OUT / 'asm/str8n-v2-worker.s19')
    memory = bytearray(65536)
    for address, value in image.items():
        memory[address] = value
    cpu = regression.boot.BaseMPU(memory=memory, pc=worker['V2W_BOOT_DELAY'])
    cpu.y = 0xA7
    for _ in range(200_000):
        if cpu.pc == worker['V2W_BOOT_DELAY_DONE']:
            break
        cpu.step()
    else:
        raise AssertionError('Boot delay did not terminate')
    assert cpu.processorCycles == 329_217, 'Boot delay timing changed'
    assert cpu.y == 0xA7, 'Boot delay clobbered Y'
    print('PASS: relocated boot delay retains 329217 cycles before RTS and Y', flush=True)


def check_board_query_states():
    """Both fixed facades retain their results after moving the query to RAM."""
    boot = regression.boot
    for resident in range(4):
        cpu, mem = boot.boot(resident)
        for caller in range(4):
            boot.select_flash_bank(mem, caller)
            entries = [boot.VSYM['STR8V2_RAM_BOARD_QUERY']]
            if caller == resident:
                entries.append(boot.SYM['STR8V2_BOARD_QUERY'])
            for detected_cpu in (0x02, 0x16):
                mem.ram[boot.SYM['V2_CPU']] = detected_cpu
                for console in (0, 1, 0xFF):
                    mem.ram[boot.SYM['V2_CONSOLE']] = console
                    for carry in (0, cpu.CARRY):
                        for entry in entries:
                            cpu.p = (cpu.p & ~cpu.CARRY) | carry
                            changes = len(mem.bank_changes)
                            boot.call_public(cpu, entry)
                            expected = (1, detected_cpu, 0x11 if console == 0 else 1)
                            assert (cpu.a, cpu.x, cpu.y) == expected
                            assert cpu.p & cpu.CARRY
                            assert mem.bank == caller and len(mem.bank_changes) == changes
    print('PASS: ROM/RAM board query, both CPU IDs, console states and incoming carry', flush=True)


if __name__ == '__main__':
    check_beta1_extension_compatibility()
    check_relocated_boot_delay()
    check_board_query_states()
    regression.main()
    (firmware.OUT / 'a24-regression.json').replace(firmware.OUT / 'config-regression.json')
