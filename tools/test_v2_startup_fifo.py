"""Instruction-level FIFO drain bounds, stale data and fresh-input handoff."""
import json
from test_v2_status import fresh,layout,OUT
from test_v2_spi_resident import k
from test_v2_storage import cmd

META=json.loads((OUT/'build.json').read_text());B=META['boot'];checks=[]
def run(cpu,stop):k.model.run(cpu,stop,30000000)

def main():
    assert META['startup_fifo_drain_limit']==1024
    for size in (0,1,16,255,256,1023,1024,1025,8192):
        cpu,m=fresh(primary=layout());stale=(b'AB\x1b\r'*((size+3)//4))[:size]
        m.rx.extend(stale);before=[bytes(x) for x in m.banks]
        run(cpu,lambda:cpu.pc==B['BOOT_FIFO_DRAIN'])
        for address in (0xFD,0xFA,0xF9,0xF8,0xF2,0xF1):m.ram[address]=0xA5
        run(cpu,lambda:cpu.pc==B['BOOT_STARTUP_DOTS'])
        assert bytes(m.rx)==stale[min(size,1024):],size
        assert not m.tx and not m.events and [bytes(x) for x in m.banks]==before
        assert all(m.ram[a]==0 for a in (0xFD,0xFA,0xF9,0xF8,0xF2,0xF1))
    checks.append('0 through 8192 pending bytes: drain stops at empty or exactly 1024 reads, with no output or flash mutation')
    print('PASS',checks[-1],flush=True)
    for key,page in ((b'A',0xA0),(b'B',0xB0),(b'\x1b',None)):
        cpu,m=fresh(primary=layout());m.rx.extend(b'B\rA\x1b')
        run(cpu,lambda:cpu.pc==B['BOOT_STARTUP_DOTS']);assert not m.rx
        m.rx.extend(key)
        run(cpu,lambda:k.model.waiting(cpu) or (cpu.pc==B['BOOT_RECOVERY_WINDOW'] and not m.rx))
        if page is None:
            assert cpu.pc==B['BOOT_RECOVERY_WINDOW'] and b'Enter default [3s]: ' in m.tx
            # No second drain between the dots and chooser may swallow this B.
            m.rx.extend(b'B');run(cpu,lambda:k.model.waiting(cpu));assert m.ram[0x7D30]==0xB0
        else:assert k.model.waiting(cpu) and m.ram[0x7D30]==page
        cmd(cpu,m,b'M 3E20 01 03 00\r');assert bytes(m.ram[0x3E20:0x3E23])==b'\x01\x03\0'
    checks.append('stale A/B/ESC discarded; fresh A/B accepted after drain; fresh ESC retains next menu B; RAM edit preserved')
    print('PASS',checks[-1],flush=True)
    cpu,m=fresh(primary=layout());m.usb=False
    run(cpu,lambda:cpu.pc==B['BOOT_STARTUP_DOTS']);assert not m.tx
    checks.append('disconnected USB reaches input window without waiting');print('PASS',checks[-1],flush=True)
    (OUT/'startup-fifo-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts']),indent=2)+'\n')

if __name__=='__main__':main()
