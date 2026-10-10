"""Force fixed F recovery, query wear and return through both frozen slots."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/beta23-storage-models')
import json
from test_v2_status import fresh,boot,layout,snapshot,OUT,META
from test_v2_storage import cmd

def main():
    checks=[]
    for slot in ('A','B'):
        cpu,m=fresh(primary=layout());m.rx.extend(b'S');before=snapshot(m);boot(cpu)
        assert b'FIXED F RECOVERY' in m.tx and b'REC> ' in m.tx
        assert snapshot(m)==before
        text=cmd(cpu,m,b'W\r');assert b'REC> ' in text and snapshot(m)==before
        text=cmd(cpu,m,(slot+'\r').encode());assert b'B3> ' in text
        assert snapshot(m)==before and m.ram[0x7D04:0x7D0C]==b'SV\x01\x0f\0\x65\xff\x64'
        assert m.ram[0x66AE:0x66B0]==b'\x01\0'
        assert b'RTCC: UTC' in cmd(cpu,m,b'TIME\r') and snapshot(m)==before
        checks.append('S recovery / read-only W / '+slot+' return / services / retained flash, SRAM, RTC, EEPROM')
    (OUT/'fixed-recovery-test-results.json').write_text(json.dumps(dict(passed=True,artifacts=META['artifacts'],checks=checks,model_only=True),indent=2)+'\n')
    print('PASS forced fixed F recovery, wear query and A/B return with complete snapshot preservation')

if __name__=='__main__':main()
