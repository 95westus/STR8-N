"""Run a24 host regression; physical 816 execution remains a separate gate."""
import hashlib
import json
import sys

import build_v2_a24 as firmware
sys.modules['build_v2'] = firmware
# Reuse S/R cases with the a24 image and its FT245-only startup contract.
sys.modules['build_v2_a23'] = firmware
import test_v2_a23_sr as sr
import test_v2_a24_console as console
import test_v2_boot as boot
import test_v2_monitor as monitor
import test_v2_load as load
import test_v2_flash as flash
import test_v2_config as config
import test_v2_interrupt_probe as interrupt


def main():
    receipt = firmware.OUT / 'a24-regression.json'
    receipt.unlink(missing_ok=True)
    passed = []
    for check in (boot.check_boot_and_input, boot.check_handoffs,
                  boot.check_vectors, boot.check_image_and_instructions,
                  boot.check_capability_abi, boot.check_v135_roundtrip,
                  boot.check_compact_messages):
        check()
        passed.append(check.__name__)
        print('PASS:', passed[-1], flush=True)
    boot.check_ram_abi_all_banks(acia_enabled=False)
    passed.append('FT245 RAM ABI across all resident/caller banks')
    for suite in (console, monitor, load, flash, config, interrupt):
        suite.main()
        passed.append(suite.__name__)
        print('SUITE PASS:', passed[-1], flush=True)
    sr.main(cold_start_check=console.main)
    passed.append('S/R/T, absent extension, and no-USB autostart')
    receipt.write_text(json.dumps({
        'version': firmware.VERSION, 'passed': passed,
        'image_sha256': hashlib.sha256(boot.IMAGE).hexdigest(),
        'physical_hardware_tested': False,
        'native_816_execution_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
