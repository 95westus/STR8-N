"""Run the linked v2 host suites against the a23 firmware and reset model."""
import json

# Importing this installs the a23 build/model under the legacy test-suite
# module names, including the longer a22/a23 reset wait.
import test_v2_a23_sr as sr
import test_v2_boot as boot
import test_v2_acia_probe as acia
import test_v2_b3_migration as migration
import test_v2_monitor as monitor
import test_v2_load as load
import test_v2_flash as flash
import test_v2_config as config
import test_v2_interrupt_probe as interrupt
import test_v2_a23_f_size as f_size


def main():
    suites = (boot, acia, migration, monitor, load, flash, config, interrupt,
              sr, f_size)
    passed = []
    for module in suites:
        module.main()
        passed.append(module.__name__)
        print('SUITE PASS:', module.__name__, flush=True)
    (sr.a23.OUT / 'a23-regression.json').write_text(
        json.dumps({'passed': passed, 'board_tested': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
