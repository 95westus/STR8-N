"""Execute CLOCK parsing, read-only paths, and confirmed SET against real code."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

import test_v2_rtc_kernel as kernel
from beta4_migration import read_s19
from build_v2_clock import OUT
OUT=Path(__file__).resolve().parents[1]/os.environ.get('STR8_CLOCK_BUILD','BUILD/v2-clock')
from test_v2_rtc import MPU as BareCPU

META = json.loads((OUT/'build.json').read_text())
CELLS, ENTRY = read_s19(OUT/'clock.s19')
SYM = META['symbols']


def parser(text):
    memory = [0]*65536
    for a,v in CELLS.items():
        memory[a] = v
    data = text.encode('ascii')
    memory[SYM['LINE']:SYM['LINE']+len(data)+1] = list(data)+[0]
    memory[SYM['LINE_LENGTH']] = len(data)
    cpu = BareCPU(memory=memory,pc=SYM['PARSE_SET'])
    cpu.stPushWord(0x1EFF)
    kernel.model.run(cpu,lambda:cpu.pc==0x1F00,5000)
    return bool(cpu.p&cpu.CARRY),bytes(memory[SYM['REQUEST']:SYM['REQUEST']+8])


def launch(cpu):
    for a,v in CELLS.items():
        cpu.memory.ram[a] = v
    return kernel.model.command(cpu,b'G 2000\r',12000000)


def main():
    assert hashlib.sha256((OUT/'clock.bin').read_bytes()).hexdigest()==META['sha256']
    assert hashlib.sha256((OUT/'clock.s19').read_bytes()).hexdigest()==META['s19_sha256']
    checks = []
    dates = []
    for year in range(2000,2100):
        for month,day in ((1,1),(2,28),(3,1),(12,31)):
            dates.append(datetime(year,month,day,23,59,59))
        if year%4==0:
            dates.append(datetime(year,2,29,0,0,0))
    for month in range(1,13):
        dates.append(datetime(2048,month,15,12,34,56))
    for value in dates:
        ok,request = parser('SET '+value.strftime('%Y-%m-%d %H:%M:%S'))
        expected = value.year.to_bytes(2,'little')+bytes((value.month,value.day,value.isoweekday(),value.hour,value.minute,value.second))
        assert ok and request==expected,(value,request,expected)
    for invalid in ('SET 1999-12-31 23:59:59','SET 2100-01-01 00:00:00',
        'SET 2025-02-29 00:00:00','SET 2026-04-31 00:00:00',
        'SET 2026-00-01 00:00:00','SET 2026-13-01 00:00:00',
        'SET 2026-01-00 00:00:00','SET 2026-01-01 24:00:00',
        'SET 2026-01-01 00:60:00','SET 2026-01-01 00:00:60',
        'SET 2026-01-01T00:00:00','SET 2026-01-01 00-00-00',
        'SET 2026-01-01 00:00:00X','SET 2026-01-01 00:00:0X'):
        assert not parser(invalid)[0],invalid
    checks.append(f'{len(dates)} independent calendar/weekday cases, leap/year-byte boundaries and malformed dates')
    print('PASS',checks[-1],flush=True)
    if 'HISTORY_CALL' in SYM:
        from test_v2_journal import boot
        cpu,m=boot()
    else:
        cpu,m = kernel.boot()
    for bank in range(4):
        kernel.model.command(cpu,f'B{bank}\r'.encode())
        output = launch(cpu)
        assert ('CLOCK '+META['version']).encode() in output and b'UTC 2026-' in output and b'CLOCK> ' in output
        # Monitor G enters the resident bank. Exercise the running RAM client's
        # calls with each caller bank, as a cooperating RAM application may do.
        m[0x7FEC] = (m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[bank]
        before = m.ram[0x7FEC]
        output = kernel.model.command(cpu,b'status\rtime\r?\r',16000000)
        assert b'Running: yes' in output and b'condition: unknown' in output
        assert m.ram[0x7FEC]==before
        assert not m.bus.writes
        assert b'B3>' in kernel.model.command(cpu,b'q\r',12000000)
    checks.append('read/status/help and public bank-safe return in all four overlays; no RTC writes')
    print('PASS',checks[-1],flush=True)
    launch(cpu)
    for response in (b'NO\r',b'Y\r',b'YES!\r',b'\x03',b'\x1b',b'YES'+b'X'*300+b'\r'):
        output = kernel.model.command(cpu,b'SET 2026-10-07 01:02:03\r'+response,16000000)
        assert b'Type YES to confirm' in output and b'Canceled' in output
        assert not m.bus.writes
    output = kernel.model.command(cpu,b'SET 2026-02-29 00:00:00\r',8000000)
    assert b'Invalid command/date' in output and b'confirm' not in output and not m.bus.writes
    kernel.model.command(cpu,b'Q\r',12000000)
    checks.append('invalid input, short/trailing confirmation, Ctrl-C, Escape and overflow cannot authorize SET')
    print('PASS',checks[-1],flush=True)
    m.bus.rtc_regs[3] |= 0x10
    evidence = bytes(m.bus.rtc_regs[0x18:0x20])
    control_trim = bytes(m.bus.rtc_regs[7:9])
    launch(cpu)
    output = kernel.model.command(cpu,b'SET 2048-02-29 12:34:56\rYES\r',16000000)
    assert b'Power-fail down/up' in output and b'SET completed' in output
    assert b'UTC 2048-02-29 12:34:56' in output
    assert m.bus.rtc_regs[:7]==bytes((0xD6,0x34,0x12,0x2E,0x29,0x02,0x48))
    assert bytes(m.bus.rtc_regs[7:9])==control_trim
    assert m.ram[0x66DC] and m.ram[0x66F0:0x66F8]==evidence
    assert all((device==0x6F and reg<=6) or ('HISTORY_CALL' in SYM and device==0x57 and reg<128) for device,reg,value in m.bus.writes)
    kernel.model.command(cpu,b'QUIT\r',12000000)
    checks.append('confirmed SET derives weekday, preserves control/trim, and archives outage before clearing it')
    print('PASS',checks[-1],flush=True)
    before = len(m.bus.writes)
    m.bus.rtc_regs[7] |= 0x10
    launch(cpu)
    output = kernel.model.command(cpu,b'SET 2026-10-07 00:00:00\r',12000000)
    assert b'Alarms enabled; SET refused' in output and b'Type YES' not in output
    assert len(m.bus.writes)==before
    kernel.model.command(cpu,b'Q\r',12000000)
    m.bus.rtc_regs[7] &= ~0x30
    m.bus.rtc_regs[0] &= ~0x80
    m.bus.rtc_regs[3] &= ~0x20
    output = launch(cpu)
    assert b'time not usable' in output and b'UTC 20' not in output
    output = kernel.model.command(cpu,b'S\r',12000000)
    assert b'Running: no' in output and b'Calendar valid: yes' in output
    kernel.model.command(cpu,b'Q\r',12000000)
    checks.append('stopped time is not displayed as usable; enabled alarms refuse SET without writes')
    print('PASS',checks[-1],flush=True)
    m.bus.devices.pop(0x6F)
    output = launch(cpu)
    error_prefix=b'RTCC: Error 02' if META['version'] in ('1.4','1.5') else b'RTC error 02'
    assert error_prefix in output and b'CLOCK> ' in output
    output = kernel.model.command(cpu,b'SET 2026-10-07 00:00:00\r',12000000)
    assert error_prefix in output and b'Type YES' not in output
    kernel.model.command(cpu,b'Q\r',12000000)
    accesses = len(m.bus.accesses)
    m.ram[0x7D07] = 0
    output = launch(cpu)
    software_message=b'RTCC: Services unavailable' if META['version'] in ('1.4','1.5') else b'RTC software unavailable'
    assert software_message in output and len(m.bus.accesses)==accesses
    kernel.model.command(cpu,b'S\r',12000000)
    assert len(m.bus.accesses)==accesses and not m.events
    kernel.model.command(cpu,b'Q\r',12000000)
    assert not m.events
    checks.append('absent RTC and absent software retain a usable prompt and make no data/flash writes')
    print('PASS',checks[-1],flush=True)
    report = dict(passed=True,checks=checks,sha256=META['sha256'],s19_sha256=META['s19_sha256'],
        kernel_artifacts=kernel.REPORT['artifacts'],physical_hardware_tested=False)
    (OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'core-test-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
