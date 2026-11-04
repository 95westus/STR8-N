"""Both CPU/console models: help/absent image, raw backup, valid readback/run."""
import argparse,json
from pathlib import Path
import test_b07
from build_b11 import HELP

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    core,_=test_b07.load_core();core.GENERATION=0x8000000b;rows=[]
    def passed(cpu,port,case):rows.append(dict(cpu=cpu,port=port,case=case,passed=True))
    def fresh(cpu,port):
        h=core.Machine(build,cpu,opaque=True);h.recovery()
        h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
        return h
    for cpu in ('65c02','65c816-e'):
        for port in (1,2):
            for ending in (b'\r',b'\n',b'\r\n'):
                h=fresh(cpu,port);ram=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0])
                out=h.port_command(port,b'?'+ending)
                assert HELP in out and out.endswith(b'REC> ') and b'REFUSED' not in out
                for key in (b'R',b'V'):
                    out=h.port_command(port,key+ending)
                    assert b'REFUSED: no valid RAM image\r\n' in out and b'timeout' not in out
                assert h.m.ram[h.b['RL_VALID']]==0 and bytes(h.m.ram[0x200:0x6500])==ram
                assert bytes(h.m.ram[:0xe0])==zp and not h.m.events
                passed(cpu,port,'help-and-invalid-RV-'+ending.hex())
            h=fresh(cpu,port);body=bytes(range(256))*64;h.m.ram[0x2000:0x6000]=body
            out=h.port_command(port,b'D\r')
            expected=body+core.crc(body).to_bytes(2,'little')
            assert expected in out and out.endswith(b'REC> ') and not h.m.events
            assert bytes(h.m.ram[0x2000:0x6000])==body
            passed(cpu,port,'D-16384-raw-bytes-plus-little-endian-CRC')
            h=fresh(cpu,port)
            body=bytes([0x4c,h.b['BOOT_MENU']&255,h.b['BOOT_MENU']>>8])+bytes(range(256))*4
            h.port_command(port,b'L\r',b'SEND HEADER+BIN\r\n')
            out=h.port_command(port,core.header(body)+body);assert b'LOADED;' in out
            assert HELP in h.port_command(port,b'?\r') and h.m.ram[h.b['RL_VALID']]==1
            out=h.port_command(port,b'V\r');assert body+core.crc(body).to_bytes(2,'little') in out
            out=h.port_command(port,b'R\r');assert out.endswith(b'REC> ') and b'REFUSED' not in out
            assert not h.m.events
            passed(cpu,port,'help-retains-valid-image-V-raw-CRC-and-R-runs')
            h.port_command(port,b'L\r',b'SEND HEADER+BIN\r\n');h.port_command(port,b'\x03')
            for key in (b'R\r',b'V\r'):
                assert b'REFUSED: no valid RAM image\r\n' in h.port_command(port,key)
            assert not h.m.events
            passed(cpu,port,'cancel-invalidates-image-specific-RV-refusal')
    result=dict(passed=True,hardware=False,serial_access=False,checks=len(rows),failures=0,cases=rows,
        checker_sha256=core.sha(Path(__file__).read_bytes()),F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes()))
    (build/'b11-help-tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b11 help/raw/diagnostic groups',len(rows),flush=True)

if __name__=='__main__':main()
