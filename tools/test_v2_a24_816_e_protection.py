"""Confirm alpha24's normal I command protects the resident B3:E sector."""
import sys

import build_v2_a24 as firmware

sys.modules['build_v2'] = firmware
import test_v2_a24_console  # patches the FT245-only startup delay in the model
from test_v2_flash import boot_flash, send


def main():
    cpu, memory = boot_flash(3)
    memory.banks[3][0x6000:0x7000] = bytes(4096)
    before = [bytes(bank) for bank in memory.banks]
    output = send(cpu, b'I E000 EFFF\r')
    assert b'Protected' in output, output
    assert [bytes(bank) for bank in memory.banks] == before
    assert not memory.events
    print('PASS: I rejects resident B3:E before any flash write')


if __name__ == '__main__':
    main()
