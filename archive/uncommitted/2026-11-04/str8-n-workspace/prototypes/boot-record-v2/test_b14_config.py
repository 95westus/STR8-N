"""Execute raw-loaded CONFIG and small BINs at 0200 with MON A/B absent."""
import argparse
from pathlib import Path
from test_b14_core import load_core
from test_b14_raw import fresh,start,feed

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    core,_=load_core();rows=[];prompt=b'CONFIG prototype I(blank only) W C target Q> '
    def passed(cpu,port,case):rows.append(dict(cpu=cpu,port=port,case=case,passed=True));print('PASS',cpu,port,case,flush=True)
    for cpu in ['65c02','65c816-e']:
        for port in [1,2]:
            h=fresh(build,cpu);start(h,port);body=(build/'payload/ram-config-offline.bin').read_bytes()
            before=bytes(h.m.ram[0x200+len(body):0x6500]);feed(h,port,body)
            h.run(lambda:bytes(h.m.tx).endswith(prompt) and bytes(h.m.acia_tx).endswith(prompt))
            assert h.m.banks[3][0x2000:0x4000]==b'\xff'*8192
            assert bytes(h.m.ram[0x200:0x200+len(body)])==body
            assert bytes(h.m.ram[0x200+len(body):0x6500])==before and not h.m.events
            assert b'OK' in h.port_command(port,b'I\r',prompt)
            assert b'UNKNOWN HISTORY' in h.port_command(port,b'W\r',prompt)
            # Blank initialization intentionally has no enabled opaque banks.
            assert b'REFUSED' in h.port_command(port,b'C 0\r',prompt)
            assert b'OK' in h.port_command(port,b'C S\r',prompt)
            assert h.call(h.b['BOOT_READ_RECORD']) and h.m.ram[0x6707]==ord('S')
            passed(cpu,port,'CONFIG-raw-0200-autoexec-blank-init-read-config-write-no-MON')
            h=fresh(build,cpu);start(h,3-port)
            # First data source owns BIN regardless of which port typed L.
            body=bytes([0xa9,0xa5,0x8d,0x6b,0x7c,0x4c,h.b['BOOT_MENU']&255,h.b['BOOT_MENU']>>8])
            feed(h,port,body);assert h.m.ram[h.b['DC_BINARY']]==port
            h.run(lambda:h.m.ram[0x7c6b]==0xa5 and bytes(h.m.tx).endswith(b'REC> '))
            assert bytes(h.m.ram[0x200:0x208])==body and not h.m.events
            passed(cpu,port,'first-data-port-claims-and-program-really-executes-at-0200-without-R')
            h=fresh(build,cpu);start(h,port);body=b'RLP1\x01\x01'+bytes(range(16))
            feed(h,port,body);h.run(lambda:h.c.pc==0x200)
            assert bytes(h.m.ram[0x200:0x200+len(body)])==body and not h.m.events
            passed(cpu,port,'RLP1-looking-bytes-are-ordinary-BIN-data')
            if port==2:
                h=fresh(build,cpu);start(h,port);body=bytes(range(256))*32
                now=h.c.processorCycles+1000
                h.m.acia_wire.extend((now+i*4167,v,0) for i,v in enumerate(body))
                h.run(lambda:h.c.pc==0x200)
                assert bytes(h.m.ram[0x200:0x2200])==body and h.m.acia_overruns==0 and not h.m.events
                passed(cpu,port,'ACIA-19200-paced-raw-8192-bytes-longer-than-three-seconds-no-early-run-or-overrun')
    core.save(build/'b14-config-execution.json',dict(passed=True,checks=len(rows),failures=0,hardware=False,serial_access=False,cases=rows,
        checker_sha256=core.sha(Path(__file__).read_bytes()),F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes())))

if __name__=='__main__':main()
