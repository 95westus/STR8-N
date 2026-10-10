"""Exercise reset-required messages and activation at the actual cold path."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-compact-boot')
import json
from test_v2_status import fresh,boot,layout,run_edu,snapshot,OUT,META
from test_v2_storage import cmd

def main():
    cpu,m=fresh(primary=layout());boot(cpu)
    assert b'RESET required:' not in m.tx
    text=run_edu(cpu,m,b'OFF\rY\r?\rQ\r')
    assert b'Saved; RESET required.' in text and b'EDU ON\r\nRESET required: OFF' in text,text
    assert m.ram[0x7D0A:0x7D0C]==b'\xff\x64' and m.ram[0x7D27]==1
    text=run_edu(cpu,m,b'?\rQ\r');assert b'RESET required: OFF' in text
    before=snapshot(m);cpu.pc=0x7E67;start=len(m.tx);boot(cpu)
    assert bytes(m.tx[start:])==b'\r\nB3> ' and m.ram[0x7D27]==1 and snapshot(m)==before
    cpu.pc=0xF004;start=len(m.tx);boot(cpu)
    assert m.ram[0x7D27]==2 and m.ram[0x7D0A:0x7D0C]==b'\xff\x66'
    text=run_edu(cpu,m,b'?\rQ\r');assert b'EDU OFF' in text and b'RESET required:' not in text
    text=run_edu(cpu,m,b'ON\rN\rQ\r');assert b'Saved; RESET required.' not in text and m.ram[0x7D28]==0xA5
    text=run_edu(cpu,m,b'ON\rY\r?\rQ\r')
    assert b'Saved; RESET required.' in text and b'EDU OFF\r\nRESET required: ON' in text
    assert m.ram[0x7D27]==2 and m.ram[0x7D0A:0x7D0C]==b'\xff\x66'
    cpu.pc=0xF004;boot(cpu);assert m.ram[0x7D27]==1 and m.ram[0x7D0A:0x7D0C]==b'\xff\x64'
    text=run_edu(cpu,m,b'?\rQ\r');assert b'RESET required:' not in text
    report=dict(passed=True,artifacts=META['artifacts'],status_asset_sha256=META['status_asset_sha256'],save_notice=True,pending_notice=True,both_mode_directions=True,hold_does_not_activate=True,cold_reset_activates=True,notice_cleared_when_active=True,cancellation_no_notice=True,board_access=False,boards_flashed=False)
    (OUT/'reset-notice-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS saved/pending reset notices, HOLD preservation, cold activation, notice clearance and canceled changes')

if __name__=='__main__':main()
