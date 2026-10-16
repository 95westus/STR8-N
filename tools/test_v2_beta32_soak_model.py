"""Run the new soak's console/RAM/reset workload on exact retained images.

Writes only an owner-local report; never rebuilds the sealed candidate.
"""
import os
import re
import time

os.environ['STR8_RTC_BUILD'] = 'BUILD/v2-beta32-candidate'
import run_v2_beta32_soak as soak
from atomic_json import publish
from test_v2_status import fresh, boot, snapshot
from test_v2_sram_store import console


def main():
    plan, array = soak.audit()
    root = soak.ROOT / 'output/qualification/beta32-soak-model' / str(time.time_ns())
    root.mkdir(parents=True)
    cpu, memory = fresh()
    memory.banks = [bytearray((soak.REFERENCE / f'upgrade/post-reset-b{i}.bin').read_bytes()) for i in range(4)]
    memory.spi.banks = memory.banks
    memory.spi.devices[0].data[:] = array
    memory.fast = True
    status = (soak.REFERENCE / 'retained/devices-after/status.txt').read_bytes()
    memory.bus.rtc_regs[:9] = bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)', status)[1].decode())
    eeprom = (soak.REFERENCE / 'retained/devices-after/eeprom-0.bin').read_bytes()
    memory.bus.ee[:128] = eeprom[:128]
    # Probe layout: 00-7F, then FF, then F0-F7 (including factory EUI).
    memory.bus.ee[0xFF] = eeprom[128]
    memory.bus.ee[0xF0:0xF8] = eeprom[129:137]
    boot(cpu)
    assert b'STR8-N 2.0b32' in memory.tx, bytes(memory.tx[-1200:])
    print('PASS linked model initial beta32 boot', flush=True)

    class ModelLink:
        pending = bytearray()

        def send(self, data):
            self.pending.extend(console(cpu, memory, data, limit=100000000))

        def until(self, token):
            offset = self.pending.find(token)
            assert offset >= 0, (token, self.pending[-1200:])
            end = offset + len(token)
            result = bytes(self.pending[:end])
            del self.pending[:end]
            return result

        def command(self, text, prompt=soak.PROMPT):
            self.send(text.encode() + b'\r')
            return self.until(prompt)

        def dump(self, first, last, prompt=soak.PROMPT):
            return bytes(memory.banks[memory.ram[0xF3]][a - 0x8000] if a >= 0x8000 else memory[a] for a in range(first, last + 1))

        def write_ram(self, address, data, prompt=soak.PROMPT):
            # Inject CPU RAM as the existing guarded soak model does. Host
            # fault tests and the physical soak cover serial short writes;
            # replaying 416 monitor-edit commands adds no storage coverage.
            assert address == 0x0200 and len(data) == 256
            memory.ram[address:address + len(data)] = data

    link = ModelLink()
    original = snapshot(memory)
    checks = []
    # One console cycle; R compatibility also has sealed beta30–32 coverage
    # and alternates in the live soak. Avoid repeating unchanged suites here.
    for iteration in range(1):
        for group in ('clock', 'monitor', 'apps', 'batch', 'ram', 'reset'):
            out = root / f'{iteration}-{group}'
            out.mkdir()
            soak.guards(link)
            result = soak.unit(link, group, out, plan, array, iteration)
            soak.guards(link)
            assert snapshot(memory) == original and not memory.events, group + ' changed persistent storage'
            checks.append(dict(iteration=iteration, group=group, result=result))
            print('PASS linked model', iteration, group, flush=True)
    publish(root / 'report.json', dict(passed=True, board_access=False, build_sha256=soak.BUILD_HASH,
                                      runner_sha256=soak.sha((soak.ROOT / 'tools/run_v2_beta32_soak.py').read_bytes()),
                                      checks=checks, persistent_storage_unchanged=True))
    print('PASS exact beta32 soak console workload, RAM restoration and J3; report', root, flush=True)


if __name__ == '__main__':
    main()
