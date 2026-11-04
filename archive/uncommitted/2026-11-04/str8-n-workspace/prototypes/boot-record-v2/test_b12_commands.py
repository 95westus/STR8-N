"""Both CPUs/ports: removed D/V, help, verified load/run and console blockage."""
import argparse,json
from pathlib import Path
import test_b12_core
from build_b12 import HELP

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    core,_=test_b12_core.load_core();core.GENERATION=0x8000000c;rows=[]
    def passed(cpu,port,case):rows.append(dict(cpu=cpu,port=port,case=case,passed=True))
    def fresh(cpu):
        h=core.Machine(build,cpu,opaque=True);h.recovery();h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE']);return h
    for cpu in ('65c02','65c816-e'):
        for port in (1,2):
            for ending in (b'\r',b'\n',b'\r\n'):
                h=fresh(cpu);ram=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0])
                out=h.port_command(port,b'?'+ending);assert HELP in out and b'D=' not in out and b'V=' not in out
                assert b'REFUSED: no valid RAM image' in h.port_command(port,b'R'+ending)
                assert not h.m.events and bytes(h.m.ram[0x200:0x6500])==ram and bytes(h.m.ram[:0xe0])==zp
                passed(cpu,port,'help-and-no-image-R-'+ending.hex())
                for key in (b'D',b'd',b'V',b'v'):
                    out=h.port_command(port,key+ending)
                    assert out==key+b'\r\nREFUSED: command\r\nREC> ',repr(out)
                assert not h.m.events and bytes(h.m.ram[0x200:0x6500])==ram
                passed(cpu,port,'removed-uppercase-lowercase-DV-'+ending.hex())
            h=fresh(cpu);body=bytes([0x4c,h.b['BOOT_MENU']&255,h.b['BOOT_MENU']>>8])+bytes(range(256))*16
            original=bytes(h.m.ram[0x200:0x6500]);h.port_command(port,b'L\r',b'SEND HEADER+BIN\r\n')
            assert b'LOADED; R runs\r\n' in h.port_command(port,core.header(body)+body)
            assert bytes(h.m.ram[0x2000:0x2000+len(body)])==body
            for cmd in (b'?\r',b'D\r',b'V\r'):h.port_command(port,cmd)
            assert h.m.ram[h.b['RL_VALID']]==1 and bytes(h.m.ram[0x2000:0x2000+len(body)])==body
            assert h.port_command(port,b'R\r').endswith(b'REC> ')
            assert bytes(h.m.ram[0x200:0x2000])==original[:0x1e00] and bytes(h.m.ram[0x2000+len(body):0x6500])==original[0x1e00+len(body):]
            assert not h.m.events
            passed(cpu,port,'all-byte-4K-load-overwrites-authorized-RAM-removed-commands-preserve-image-R-runs')
            h.port_command(port,b'L\r',b'SEND HEADER+BIN\r\n');assert b'REFUSED' not in h.port_command(port,b'\x03')
            assert b'no valid RAM image' in h.port_command(port,b'R\r') and not h.m.events
            passed(cpu,port,'cancel-clears-run-permission')
            h=fresh(cpu);h.m.ft_tx_blocked=True;out=h.port_command(2,b'?\r')
            assert HELP in out and out.endswith(b'REC> ') and not h.m.events
            passed(cpu,port,'blocked-FT245-help-continues-on-ACIA')
    core.save(build/'b12-command-tests.json',dict(passed=True,hardware=False,serial_access=False,checks=len(rows),failures=0,cases=rows,
        checker_sha256=core.sha(Path(__file__).read_bytes()),F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes())))
    print('PASS b12 command groups',len(rows),flush=True)

if __name__=='__main__':main()
