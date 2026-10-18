"""Execute exact beta26 A / retained beta25 B images from the physical backup."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-beta26')
import argparse
import json

from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_storage import cmd, service
from test_v2_spi_resident import k
import deploy_v2_beta26 as deploy


def main(root):
    meta = deploy.build_audit()
    plan = deploy.read(root/'upgrade/plan.json')
    expected = [(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
    prior = (root/'prior-verified/b3.bin').read_bytes()
    assert expected[3][0x3000:0x4000] == prior[0x3000:0x4000]
    checks = []
    def start(key=None, fault=None):
        cpu, memory = fresh()
        memory.banks = [bytearray(b) for b in expected]
        memory.spi.banks = memory.banks
        memory.bus.ee[0xF2:0xF8] = memory.banks[3][0x1C08:0x1C0E]
        if fault:
            offset = 0x2000+(31 if fault == 'commit' else 20 if fault == 'cookie' else 400)
            memory.banks[3][offset] ^= 1
        k.model.run(cpu, lambda:cpu.pc == meta['boot']['BOOT_STARTUP_DOTS'], 30000000)
        if key:
            memory.rx.extend(key)
        boot(cpu)
        return cpu, memory
    for key, page, version in [(None,0xA0,b'2.0b26'), (b'B',0xB0,b'2.0b25')]:
        cpu, memory = start(key)
        assert memory.ram[0x7D30] == page and b'STR8-N '+version in memory.tx
        assert b'Battery age unknown' in memory.tx
        before = snapshot(memory)
        text = cmd(cpu, memory, b'VERSION\r')
        assert b'STR8-N '+version in text, text
        assert b'MONITOR A gen 00000026 VALID default' in text
        assert b'MONITOR B gen 00000025 VALID' in text
        assert snapshot(memory) == before
        assert b'(-05:00)' in cmd(cpu, memory, b'TIME\r')
        text = cmd(cpu, memory, b'R CLOCK\r')
        assert b'CLOCK 1.8' in text and b'Battery age unknown' in text
        assert b'Battery age unknown' in cmd(cpu, memory, b'BATTERY\r')
        for command, wanted in [(b'STATUS', b'RTC registers (raw):'), (b'HISTORY',b'No saved event'),
                                 (b'EUI',b'EUI:'), (b'OFFSET',b'-05:00')]:
            text = cmd(cpu, memory, command+b'\r')
            assert wanted in text, (command,text)
        cmd(cpu, memory, b'Q\r')
        assert b'B0:8' in cmd(cpu, memory, b'W\r')
        apps = cmd(cpu, memory, b'APPS\r')
        assert apps.endswith(b'B3> ') and b'\xff' not in apps and b'Bad cmd' not in apps,apps
        assert snapshot(memory) == before and not memory.events
        checks.append(('default beta26 A' if page == 0xA0 else 'retained beta25 B')+
            ': VERSION, TIME, CLOCK/BATTERY/status/history/identity, W, APPS and flash/device preservation')
        print('PASS',checks[-1],flush=True)
    # Exercise real storage service 5, not a VERSION alias. The new sealed
    # helper's erased padding and remainder of D must never be an AUTO target.
    memory.banks[2][:0x4800] = bytes(0x4800)
    memory.banks[2][-4:] = b'\xff'*4
    memory.banks[2][0x1000:0x1100] = b'\xff'*256
    memory.ram[0x7D2C] = 2
    memory.ram[0x7D2D:0x7D2F] = (56).to_bytes(2,'little')
    assert service(cpu,memory,5) == (0,0x90,True)
    memory.banks[2][0x1000:0x1100] = bytes(256)
    before = snapshot(memory)
    result = service(cpu,memory,5)
    assert result[0] == 0 and not result[2],result  # X is unspecified on refusal.
    assert snapshot(memory) == before and not memory.events
    checks.append('AUTO service 5 finds permitted erased RAM-program space; reserved C800-DFFF/padding never returned; VERSION service 7 distinct')
    print('PASS',checks[-1],flush=True)
    for fault in ('commit','cookie','crc'):
        cpu, memory = start(fault=fault)
        assert memory.ram[0x7D30] == 0xB0 and b'STR8-N 2.0b25' in memory.tx
        assert bytes(memory.banks[3][0x3000:0x4000]) == prior[0x3000:0x4000]
        assert not memory.events
    checks.append('uncommitted/incompatible/corrupt beta26 automatically falls back to exact preserved beta25 B')
    print('PASS',checks[-1],flush=True)
    report = dict(passed=True, checks=checks, artifacts=meta['artifacts'],
        expected_hashes=plan['expected_hashes'], fallback_sha256=plan['fallback_sha256'],
        parent_functional_build_sha256=meta['battery_parent_build_sha256'],
        board_access=False, boards_flashed=False)
    (root/'upgrade/beta26-test-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    main(parser.parse_args().root.resolve())
