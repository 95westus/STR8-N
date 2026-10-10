"""Execute integrated beta5 discovery/protection and component lifecycle."""
import hashlib
import json
from pathlib import Path
import sys
import os

import build_v2_recovery as fw
ROOT = Path(__file__).resolve().parents[1]
fw.OUT = ROOT / os.environ.get('STR8_RTC_BUILD','BUILD/v2-rtc-kernel')
fw.SOURCE = fw.OUT / 'source'
fw.VERSION = json.loads((fw.OUT/'build.json').read_text())['version']
fw.MAINT_LABEL = 'MAINT'
import test_v2_recovery as model
from test_v2_i2c import Devices

REPORT = json.loads((fw.OUT / 'build.json').read_text())
BANNER = REPORT.get('banner_reads_rtc',False)
CAPABILITIES = REPORT.get('capabilities',3)


class Memory(model.Memory):
    def __init__(self, banks=None, usb=True):
        super().__init__(banks, usb)
        if banks is None:
            self.banks[3][:4096] = (fw.OUT / 'str8n-rtc-component-8000-8fff.bin').read_bytes()
            if REPORT.get('spi'):self.banks[3][4096:8192]=(fw.OUT/'str8n-journal-9000-9fff.bin').read_bytes()
            if REPORT.get('status_banner'):
                offset=REPORT['status_asset_address']-0x8000
                self.banks[2][offset:offset+REPORT['status_asset_bytes']]=(fw.OUT/'boot-status/asset.bin').read_bytes()
            if REPORT.get('local_time'):
                offset=REPORT['local_asset_address']-0x8000
                self.banks[2][offset:offset+REPORT['local_asset_bytes']]=(fw.OUT/'local-display/asset.bin').read_bytes()
            if REPORT.get('storage_services'):
                store=json.loads((fw.OUT/'store/build.json').read_text());body=(fw.OUT/'store/sram.bin').read_bytes()
                head=b'SR\x01\x3F'+store['entry'].to_bytes(2,'little')+len(body).to_bytes(2,'little')+b'SRAM'.ljust(16,b'\0')
                self.banks[2][0x2000:0x2000+len(head+body)]=head+body
            maintenance = fw.OUT / REPORT.get('maintenance_storage_file','str8n-maint-'+REPORT.get('maintenance_version','1.6')+'-b1-8000-9fff.bin')
            if maintenance.exists():
                body=maintenance.read_bytes();self.banks[1][:len(body)] = body
        self.bus = Devices()
        self.bus.ram = self.ram

    def __getitem__(self, a):
        if isinstance(a, int) and a in (0x7FC3, 0x7FCF):
            return self.bus[a]
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if isinstance(a, int) and a in (0x7FC3, 0x7FCF):
            self.bus[a] = v
            return
        super().__setitem__(a, v)


def boot(banks=None, keys=b''):
    mem = Memory(banks)
    mem.rx.extend(keys)
    cpu = model.MPU(memory=mem, pc=0xF004)
    mem.cpu = cpu
    model.run(cpu, lambda: model.waiting(cpu), 12000000)
    return cpu, mem


def app_call(cpu, addr, bank=0):
    mem = cpu.memory
    old = mem.ram[0x7FEC]
    mem[0x7FEC] = (old & 0x11) | (0xCC, 0xCE, 0xEC, 0xEE)[bank]
    original = mem.ram[0x7FEC]
    cpu.p |= cpu.INTERRUPT
    cpu.p &= ~cpu.DECIMAL
    cpu.stPushWord(0x01FF)
    cpu.pc = addr
    model.run(cpu, lambda: cpu.pc == 0x0200, 4000000)
    assert mem.ram[0x7FEC] == original
    result = cpu.a
    # Actual applications return to monitor with its public bank-safe HOLD.
    cpu.pc = 0x7E67
    model.run(cpu, lambda: model.waiting(cpu), 12000000)
    return result


def main():
    checks = []
    for keys in (b'', b'A\r', b'B\r'):
        cpu, mem = boot(keys=keys)
        assert mem.ram[0x7D04:0x7D0C] == b'SV\x01'+bytes((CAPABILITIES,))+b'\x00\x65\xFF\x64'
        assert mem.ram[0x6500:0x6504] == b'RG\x01\x04'
        assert mem.ram[0x6510:0x6514] == b'I2\x01\x01'
        expected=3 if BANNER else 0
        assert mem.ram[0x6664] in ((expected,expected|4) if REPORT.get('status_banner') else (expected,))
        assert bool(mem.bus.accesses)==BANNER and not mem.bus.writes
        assert mem.ram[0x0200:0x6500] == bytes([0x5A]) * 0x6300
        assert not mem.events
    checks.append('default/A/B boot publishes services/bounds; banner READ only' if BANNER else 'default/A/B boot publishes separate services and bounds without probing I2C')
    original = [bytes(b) for b in mem.banks]
    for fault in ('missing', 'corrupt'):
        banks = [bytearray(b) for b in original]
        if fault == 'missing':
            banks[3][:4096] = bytes([255]) * 4096
        else:
            banks[3][0x700] ^= 1
        cpu, absent = boot(banks)
        assert absent.ram[0x7D04:0x7D0C] == b'SV\x01\x00\x00\x00\xFF\x66'
        assert absent.ram[0x0200:0x6700] == bytes([0x5A]) * 0x6500
        assert not absent.bus.accesses and not absent.events
        assert b'B3>' in absent.tx
        assert b'6500: 12' in model.command(cpu, b'M 6500 12\rD 6500\r')
    checks.append('absent/corrupt component leaves full program RAM and normal monitor usable')
    for fault in ('missing', 'corrupt-tail'):
        banks = [bytearray(b) for b in original]
        if fault == 'missing':
            banks[3][0x6000:0x7000] = bytes([255]) * 4096
        else:
            banks[3][0x6F20] ^= 1
        cpu, absent = boot(banks)
        assert absent.ram[0x7D04] == 0 and absent.ram[0x7D0C] == 0
        assert absent.ram[0x0200:0x6700] == bytes([0x5A]) * 0x6500
        assert not absent.bus.accesses and not absent.events
        assert b'B3>' in absent.tx
        output = model.command(cpu, b'M 6500 12\rD 6500\r')
        assert b'SR unavailable' in output and b'6500: 5A' in output
    checks.append('absent E or corrupted second-half E fails before optional bootstrap; display/recovery remain usable and E-dependent commands refuse')
    cpu, mem = boot()
    protected = bytes(mem.ram[0x6500:0x6700])
    for command in (b'M 6500 12\r', b'M 64FF 12 34\r', b'G 6504\r'):
        assert b'Protected' in model.command(cpu, command), command
        assert mem.ram[0x6500:0x6700] == protected
    # A complete S1 spanning the reservation must be rejected atomically.
    line = fw.link.record('1', 0x64FF, bytes([1, 2])).encode()
    end = fw.link.record('9', 0x2000).encode()
    before = mem.ram[0x64FF]
    output = model.command(cpu, b'L\r' + line + b'\r\n' + end + b'\r\n')
    assert b'Protected' in output or b'Bad range' in output
    assert mem.ram[0x64FF] == before and mem.ram[0x6500:0x6700] == protected
    for command in (b'F 8000 00\r', b'I 8000 8FFF\r'):
        assert b'Protected' in model.command(cpu, command), command
    assert not mem.events
    checks.append('M/G/S19 and normal flash operations protect reserved RAM and RTC sector')
    for bank in range(4):
        cpu, mem = boot()
        assert app_call(cpu, 0x6504, bank) == 0
        expected=3 if BANNER and not REPORT.get('quiet_monitor_return') else 2
        assert mem.ram[0x7D07] == CAPABILITIES and mem.ram[0x6664] in ((expected,expected|4) if REPORT.get('status_banner') else (expected,))
        assert mem.ram[0x7D0C] == 255
    checks.append('first request activates RTC through each bank; HOLD preserves initialized state and invalidates code cache')
    cpu, mem = boot()
    mem.bus.rtc_regs[3] |= 0x10
    event = bytes(mem.bus.rtc_regs[0x18:0x20])
    mem.ram[0x66E9:0x66EB] = b'PA'
    assert app_call(cpu, 0x650D) == 0
    assert mem.ram[0x66DC] == 1 and mem.ram[0x66F0:0x66F8] == event
    assert app_call(cpu, 0x6507) == 0
    assert mem.ram[0x66DC] == 1 and mem.ram[0x66F0:0x66F8] == event
    mem.banks[3][0x800] ^= 1
    cpu.pc = 0x7E67
    model.run(cpu, lambda: model.waiting(cpu), 12000000)
    assert mem.ram[0x7D07] == 0 and mem.ram[0x7D0C] == 255
    assert mem.ram[0x7D0A:0x7D0C] == b'\xFF\x64'
    checks.append('outage capture survives monitor reentry/revalidation; invalidated component cannot free active RAM')
    cpu, mem = boot()
    start = [bytes(b) for b in mem.banks]
    assert b'MAINT' in model.command(cpu, b'T 1\r', 12000000)
    assert ('BANK MAINT '+REPORT.get('maintenance_version','1.6')).encode() in model.command(cpu, b'R MAINT\r', 16000000)
    service_ram = bytes(mem.ram[0x6500:0x6700])
    for command in (b'E 3 8\r', b'C R 6400 6401 R 6500\r'):
        result = model.command(cpu, command, 12000000)
        assert any(text in result for text in (b'INVALID', b'PROTECTED', b'CANCELED')), (command, result)
        assert b'Y?' not in result
        assert mem.ram[0x6500:0x6700] == service_ram
        assert [bytes(b) for b in mem.banks] == start
    result = model.command(cpu, b'M\r', 20000000)
    assert b'RTC/I2C' in result and b'6500-66FF services protected' in result
    model.command(cpu, b'Q\r', 16000000)
    assert b'B3>' in mem.tx[-100:]
    assert [bytes(b) for b in mem.banks] == start
    checks.append('relocated MAINT 1.6 runs, maps and protects RTC sector/service RAM, then returns safely')
    mem.ram[0x6200:0x6208] = b'RTC-PASS'
    assert b'Done' in model.command(cpu, b'S 2 8000 6200 6207 PROBE\r', 16000000)
    mem.ram[0x6200:0x6208] = bytes(8)
    assert b'Done' in model.command(cpu, b'R 2 PROBE L\r', 16000000)
    assert mem.ram[0x6200:0x6208] == b'RTC-PASS'
    before = bytes(mem.ram[0x6500:0x6700])
    result = model.command(cpu, b'S 2 9000 6500 6507 BAD\r', 16000000)
    assert b'Done' not in result and bytes(mem.ram[0x6500:0x6700]) == before
    checks.append('SAVE/TABLE/RESTORE remain usable and reject service-owned RAM')
    # Existing static MAINT artifact must retain its public calling contract.
    legacy = ROOT / 'BUILD/v2-beta4/kit/str8n-bank-maint-1.5-2000.s19'
    stream = b'L\r' + legacy.read_bytes().replace(b'\n', b'\r\n')
    model.command(cpu, stream, 16000000)
    assert b'BANK MAINT 1.5' in model.command(cpu, b'G 2000\r', 16000000)
    model.command(cpu, b'Q\r', 16000000)
    assert b'B3>' in mem.tx[-100:]
    checks.append('unchanged legacy MAINT 1.5 S19 still loads/runs/returns with the fixed public ABI')
    report = dict(passed=True, checks=checks, hardware_tested=False,
                  artifacts=REPORT['artifacts'])
    (fw.OUT / 'kernel-test-results.json').write_text(json.dumps(report, indent=2) + '\n')
    for text in checks:
        print('PASS', text, flush=True)


if __name__ == '__main__':
    main()
