"""Execute selected compact boot layout, detailed queries and preservation."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-compact-boot')
import json
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_local_time import record
from test_v2_storage import cmd

def main():
    meta=json.loads((OUT/'build.json').read_text());assert meta['compact_boot_local']
    checks=[]
    for offset,wanted in ((-300,b'RTCC: Fri 2026-10-09 15:11:04 (-05:00)'),(0,b'RTCC: Fri 2026-10-09 20:11:04 (+00:00)'),(345,b'RTCC: Sat 2026-10-10 01:56:04 (+05:45)')):
        cpu,m=fresh(primary=layout());m.bus.rtc_regs[:9]=bytes.fromhex('84 11 20 2D 09 10 26 80 12')
        if offset:m.banks[3][0x1C20:0x1C40]=record(offset)
        before=snapshot(m);scratch=bytes(m.ram[0x200:0x6500]);boot(cpu);out=bytes(m.tx)
        lines=[line for line in out.split(b'\r\n') if line.startswith(b'RTCC:')]
        assert lines==[wanted],lines
        assert b'; trim' not in out and b'RTCC: EUI' not in out and b'RTCC: UTC' not in out
        assert snapshot(m)==before and bytes(m.ram[0x200:0x6500])==scratch
        if offset==-300:
            (OUT/'compact-boot-preview.txt').write_bytes(out)
            time=cmd(cpu,m,b'TIME\r')
            assert b'RTCC: UTC Fri 2026-10-09 20:11:04' in time
            assert b'RTCC: Local Fri 2026-10-09 15:11:04 (-05:00)' in time
            assert b'RTCC: Trim -18 steps:' in time and snapshot(m)==before
            edu=(OUT/'edu/edu.bin').read_bytes();m.ram[0x2000:0x2000+len(edu)]=edu
            detail=cmd(cpu,m,b'G 2000\r')
            assert b'RTCC: EUI 54:10:EC:B6:64:AF' in detail and snapshot(m)==before
            cmd(cpu,m,b'Q\r')
            clock=(OUT/'clock/clock.bin').read_bytes();m.ram[0x2000:0x2000+len(clock)]=clock
            start=cmd(cpu,m,b'G 2000\r')
            assert b'54:10:EC:B6:64:AF' in start
            identity=cmd(cpu,m,b'EUI\r');assert b'54:10:EC:B6:64:AF' in identity and snapshot(m)==before
            cmd(cpu,m,b'Q\r')
        checks.append(wanted.decode())
    cpu,m=fresh(off=True);before=snapshot(m);boot(cpu)
    assert b'RTCC:' not in m.tx and b'SSRAM:' not in m.tx and not m.bus.accesses and not m.spi.frames and snapshot(m)==before
    checks.append('EDU OFF remains device-free; TIME/CLOCK/EUI detailed output retained')
    report=dict(passed=True,checks=checks,artifacts=meta['artifacts'],status_asset_sha256=meta['status_asset_sha256'],local_asset_sha256=meta['local_asset_sha256'],clock_sha256=meta['clock_sha256'],board_access=False,boards_flashed=False)
    (OUT/'compact-boot-test-results.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS compact local boot, date rollover, full queries/EUI and preserved hardware/storage')

if __name__=='__main__':main()
