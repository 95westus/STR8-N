"""Prove a measured sample survives the monitor's later banner READ."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-rtc-banner'
import hashlib
import json
from pathlib import Path

import test_v2_rtc_kernel as kernel
from beta4_migration import read_s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'BUILD/v2-rtc-kernel/utc-client'


class Memory(kernel.Memory):
    def __setitem__(self,address,value):
        super().__setitem__(address,value)
        if address==0x7FE1 and value==ord('@'):
            self.bus.rtc_regs[0]=0xD9


def main():
    memory = Memory()
    cpu = kernel.model.MPU(memory=memory,pc=0xF004)
    memory.cpu = cpu
    kernel.model.run(cpu,lambda:kernel.model.waiting(cpu),12000000)
    cells,entry = read_s19(OUT/'rtc-sample-client.s19')
    for address,value in cells.items():
        memory.ram[address]=value
    output = kernel.model.command(cpu,b'G 2000\r',12000000)
    assert memory.ram[0x2449]==58 and memory.ram[0x66C9]==59
    assert b'UTC 2026-12-31 23:59:59' in output and not memory.bus.writes
    digest = hashlib.sha256(bytes(cells.values())).hexdigest()
    assert digest==json.loads((OUT/'sample-build.json').read_text())['sha256']
    (OUT/'sample-test-results.json').write_text(json.dumps(dict(passed=True,sha256=digest,
        sample_second=58,banner_second=59,clock_written=False,
        kernel_artifacts=kernel.REPORT['artifacts']),indent=2)+'\n')
    print('PASS measured sample survives later banner READ, including one-second rollover')


if __name__=='__main__':
    main()
