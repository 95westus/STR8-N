"""Execute beta6 banner for healthy, unusable, absent and corrupt clocks."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-banner')
import hashlib
import json
import re
from pathlib import Path

import test_v2_rtc_kernel as kernel

OUT = kernel.fw.OUT


def boot(banks=None,setup=None,usb=True,keys=b''):
    m = kernel.Memory(banks,usb)
    if setup:
        setup(m)
    m.rx.extend(keys)
    cpu = kernel.model.MPU(memory=m,pc=0xF004)
    m.cpu = cpu
    kernel.model.run(cpu,lambda:kernel.model.waiting(cpu),12000000)
    return cpu,m


def main():
    checks = []
    for keys in (b'',b'A\r',b'B\r'):
        cpu,m = boot(keys=keys)
        output = bytes(m.tx)
        if kernel.REPORT.get('weekday_display'):
            assert re.search(rb'UTC (Mon|Tue|Wed|Thu|Fri|Sat|Sun) 2026-',output)
            output=re.sub(rb'(UTC )(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ',rb'\1',output)
        assert b'UTC 2026-12-31 23:59:58' in output,output[-200:]
        normalized=output.replace(b'RTCC: EUI unavailable\r\n',b'')
        if kernel.REPORT.get('status_banner'):
            assert b'816N-VEC\r\n\r\nRAM $0200-$64FF\r\n\r\nEDU ON\r\n\r\nRTCC: UTC 2026-' in normalized
            assert m.ram[0x7D0F:0x7D11]==b'\x06\xEF'
        else:
            assert b'816N-VEC\r\nUTC 2026-' in normalized
            assert m.ram[0x7D0F:0x7D11]==b'\x07\x89'
        assert not m.bus.writes and not m.events
        before = len(m.bus.accesses)
        kernel.model.command(cpu,b'D 2000\r',4000000)
        assert len(m.bus.accesses)==before, 'Ordinary prompt must not read RTC'
        cpu.pc = 0x7E67
        start = len(m.tx)
        kernel.model.run(cpu,lambda:kernel.model.waiting(cpu),12000000)
        if kernel.REPORT.get('quiet_monitor_return'):
            assert b'UTC ' not in m.tx[start:] and len(m.bus.accesses)==before
        else:assert b'UTC 2026-' in m.tx[start:]
        assert not m.bus.writes
    checks.append('UTC on default/A/B boot; HOLD follows configured quiet return; ordinary prompts do not poll RTC')
    print('PASS',checks[-1],flush=True)
    for label,setup,expected in (
        ('stopped',lambda m:(m.bus.rtc_regs.__setitem__(0,0x58),m.bus.rtc_regs.__setitem__(3,0x08)),b'RTC stopped - use R CLOCK'),
        ('invalid',lambda m:m.bus.rtc_regs.__setitem__(4,0x32),b'RTC time invalid - use R CLOCK'),
        ('no slave',lambda m:m.bus.devices.pop(0x6F),b'RTC unavailable'),
        ('stuck',lambda m:setattr(m.bus,'stuck','scl'),b'RTC unavailable')):
        cpu,m = boot(setup=setup)
        if kernel.REPORT.get('eui_binding'):
            expected={b'RTC stopped - use R CLOCK':b'RTCC: Time stopped - use R CLOCK',b'RTC time invalid - use R CLOCK':b'RTCC: Time invalid - use R CLOCK',b'RTC unavailable':b'RTCC: Time unavailable'}[expected]
        assert expected in m.tx and b'UTC 2026-' not in m.tx,(label,bytes(m.tx[-200:]))
        assert b'B3>' in m.tx and not m.bus.writes and not m.events
    checks.append('stopped/invalid/NACK/stuck bus have bounded status lines and retain normal prompt without writes')
    print('PASS',checks[-1],flush=True)
    cpu,m = boot(setup=lambda m:m.bus.rtc_regs.__setitem__(3,0x3A))
    event = bytes(m.bus.rtc_regs[0x18:0x20])
    assert m.bus.rtc_regs[3]&0x10 and not m.bus.writes
    assert m.ram[0x66DC] and m.ram[0x66F0:0x66F8]==event
    checks.append('banner READ preserves latched power-fail data and captures evidence in RAM')
    print('PASS',checks[-1],flush=True)
    original = [bytes(b) for b in m.banks]
    for label in ('missing component','bad component','missing E','bad E'):
        banks = [bytearray(b) for b in original]
        if label=='missing component': banks[3][:4096]=bytes([255])*4096
        elif label=='bad component': banks[3][0x901]^=1
        elif label=='missing E': banks[3][0x6000:0x7000]=bytes([255])*4096
        else: banks[3][0x6F20]^=1
        cpu,absent = boot(banks)
        if kernel.REPORT.get('status_banner') and label in ('missing component','bad component'):
            assert absent.ram[0x7D0F:0x7D11]==b'\x06\xEF' and absent.ram[0x7D2A]==0
            assert b'RAM $0200-$66FF' in absent.tx and b'EDU ON' in absent.tx and b'RTCC: unavailable' in absent.tx
        else:assert absent.ram[0x7D10]==0
        assert b'UTC ' not in absent.tx and b'RTC unavailable' not in absent.tx
        assert b'B3>' in absent.tx and not absent.bus.accesses
    # Valid beta5 component has no private banner header. No call into its FF tail.
    banks = [bytearray(b) for b in original]
    banks[3][:4096]=(Path(__file__).resolve().parents[1]/'BUILD/v2-rtc-kernel/str8n-rtc-component-8000-8fff.bin').read_bytes()
    cpu,old = boot(banks)
    assert old.ram[0x7D07]==(0 if kernel.REPORT.get('provider_format',1)!=1 else 3) and not old.bus.accesses
    assert old.ram[0x7D2A if kernel.REPORT.get('status_banner') else 0x7D10]==0
    # Warm reentry after E replacement cannot use a stale private banner pointer.
    old.banks[3][0x6000:0x7000]=(Path(__file__).resolve().parents[1]/'BUILD/v2-rtc-kernel/str8n-v2-recovery-e000-efff.bin').read_bytes()
    old.ram[0x7D0F:0x7D11]=b'\x07\x89'
    cpu.pc=0x7E67
    kernel.model.run(cpu,lambda:kernel.model.waiting(cpu),12000000)
    assert old.ram[0x7D10]==0 and not old.bus.accesses
    checks.append('missing/corrupt software and valid older E/component omit line and cannot invoke stale/untrusted banner code')
    print('PASS',checks[-1],flush=True)
    # No connected console: transport output stays bounded and leaves an unattended monitor usable.
    cpu,headless = boot(usb=False)
    assert not headless.bus.writes and not headless.events
    checks.append('headless boot remains bounded; no RTC setting, acknowledgment or flash writes')
    print('PASS',checks[-1],flush=True)
    meta = json.loads((OUT/'build.json').read_text())
    for name,digest in meta['artifacts'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
    (OUT/'banner-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=meta['artifacts']),indent=2)+'\n')


if __name__=='__main__':
    main()
