"""Execute UTC weekday formatting in cold status and explicit TIME."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-combined-display')
import json
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_storage import cmd

def main():
    meta=json.loads((OUT/'build.json').read_text());assert meta['weekday_display']
    cpu,m=fresh(primary=layout());before=snapshot(m);boot(cpu)
    assert b'RTCC: UTC Thu 2026-10-08 19:53:15' in m.tx,bytes(m.tx[-600:])
    assert snapshot(m)==before
    for n,day in enumerate(('Mon','Tue','Wed','Thu','Fri','Sat','Sun'),1):
        m.bus.rtc_regs[3]=(m.bus.rtc_regs[3]&0xF8)|n;before=snapshot(m)
        out=cmd(cpu,m,b'TIME\r')
        assert f'RTCC: UTC {day} 2026-10-08 19:53:15'.encode() in out,out
        assert snapshot(m)==before
    # Actual date rollover example with the device's Friday weekday.
    m.bus.rtc_regs[:7]=bytes.fromhex('A0 55 02 2D 09 10 26');before=snapshot(m)
    out=cmd(cpu,m,b'TIME\r');assert b'RTCC: UTC Fri 2026-10-09 02:55:20' in out,out
    assert snapshot(m)==before
    (OUT/'weekday-test-results.json').write_text(json.dumps(dict(passed=True,artifacts=meta['artifacts'],
        all_seven_weekdays=True,cold_and_time=True,hardware_preserved=True,board_access=False),indent=2)+'\n')
    print('PASS boot/TIME weekday, all seven RTC weekday values, UTC midnight date example and hardware preservation')

if __name__=='__main__':main()
