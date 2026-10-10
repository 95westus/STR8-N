"""Execute cold-boot integration and explicit-query scope on the candidate."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-spi-startup')
import json
from test_v2_status import fresh,boot,layout,snapshot,OUT,META

def invoke(cpu,entry):
    cpu.stPushWord(0x1FF);cpu.pc=entry
    for _ in range(3000000):
        if cpu.pc==0x200:return
        cpu.step()
    raise AssertionError('allocation timeout')

def main():
    checks=[]
    for enabled in (False,True):
        cpu,m=fresh(primary=layout());prior=snapshot(m);seen=[]
        def inject(c):
            if c.pc==META['status_symbols']['SPI_STARTUP_GUARD'] and not seen:
                m.spi.ifr=0x1A;m.ram[0x7FCE]=0x90 if enabled else 0x80
                seen.append(m.spi.port_reads)
            return False
        boot(cpu,inject)
        assert seen and snapshot(m)==prior
        if enabled:
            assert m.spi.ifr==0x1A and m.spi.port_reads==seen[0] and b'SSRAM: Unavailable' in m.tx
        else:
            assert m.spi.ifr==2 and b'SSRAM: PROGRAM payload 63488 bytes' in m.tx
            assert not m.spi.devices[0].writes
        checks.append('cold boot '+('enabled IRQ refused' if enabled else 'disabled flags cleared and allocation read without data writes'))
    # Explicit EDU/TIME status kinds must leave pending flags alone.
    cpu,m=fresh(primary=layout());boot(cpu)
    for kind in (1,2):
        m.spi.ifr=0x1A;m.ram[0x7FCE]=0x80
        m.ram[META['status_symbols']['KIND']]=kind
        reads=m.spi.port_reads;prior=snapshot(m)
        invoke(cpu,META['status_symbols']['ALLOCATION'])
        assert m.spi.ifr==0x1A and m.spi.port_reads==reads and snapshot(m)==prior
    checks.append('EDU/TIME explicit allocation queries leave pending flags untouched')
    report=dict(passed=True,checks=checks,artifacts=META['artifacts'],status_asset_sha256=META['status_asset_sha256'],board_access=False,boards_flashed=False)
    (OUT/'spi-startup-integration-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS', '; '.join(checks),flush=True)

if __name__=='__main__':main()
