"""Mixed-slot read paths with 2609's bound EUI/control/trim fixture."""
import json
from test_v2_beta25 import *

def main():
    checks=[]
    for page,key,version in ((0xA0,b'A',b'2.0b24'),(0xB0,b'B',b'2.0b25')):
        c,m=fresh(primary=layout());m.banks=[bytearray(b) for b in EXPECTED];m.spi.banks=m.banks
        binding=m.banks[3][0x1C00:0x1C20];assert binding[:2]==b'EI'
        m.bus.ee[0xF2:0xF8]=binding[8:14];m.bus.rtc_regs[7:9]=bytes((0x80,14))
        k.model.run(c,lambda:c.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000);m.rx.extend(key);boot(c)
        assert m.ram[0x7D30]==page and b'STR8-N '+version in m.tx
        before=snapshot(m);reply=cmd(c,m,b'R CLOCK\r');assert b', changed' not in reply and b', unbound' not in reply,reply
        reply=cmd(c,m,b'STATUS\r');assert b'80 0E ' in reply and b'Running: yes' in reply and b'Backup enabled: yes' in reply
        for command in (b'EUI\r',b'HISTORY\r',b'TRIM\r',b'OFFSET\r'):cmd(c,m,command)
        cmd(c,m,b'Q\r');assert snapshot(m)==before and not m.events and m.ram[0x7D30]==page
        checks.append(version.decode()+' bound identity/status/history/trim/offset and HOLD preserved')
        print('PASS',checks[-1],flush=True)
    (OUT/'mixed-identity-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],
        expected_hashes=PLAN['expected_hashes'],board_access=False,boards_flashed=False),indent=2)+'\n')

if __name__=='__main__':main()
