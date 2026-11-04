"""b15 raw-loader regression plus pre-payload Ctrl-C and literal payload 03."""
import argparse
import json
import sys
from pathlib import Path
from test_b14_core import load_core
from test_b14_raw import start, feed
import build_b15

HERE=Path(__file__).resolve().parent


def fresh(build,cpu):
    core,_=load_core();core.GENERATION=0x8000000f
    h=core.Machine(build,cpu,opaque=True);h.recovery()
    h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    return h


def cancellation_tests(build):
    rows=[]
    def passed(cpu,port,case,**detail):
        rows.append(dict(cpu=cpu,port=port,case=case,passed=True,**detail))
        print('PASS',cpu,port,case,detail,flush=True)
    for cpu in ('65c02','65c816-e'):
        for port in (1,2):
            for ending in (b'\r',b'\n',b'\r\n'):
                for source_port in (port,3-port):
                    h=fresh(build,cpu)
                    ram=bytes(h.m.ram[0x200:0x7800]);zp=bytes(h.m.ram[:0xe0]);flash=tuple(map(bytes,h.m.banks))
                    start(h,port,ending)
                    tx=h.m.tx if source_port==1 else h.m.acia_tx;n=len(tx)
                    (h.m.rx if source_port==1 else h.m.acia_rx).append(3)
                    h.run(lambda:len(tx)>n and bytes(tx).endswith(b'REC> '))
                    assert bytes(h.m.ram[0x200:0x7800])==ram
                    assert bytes(h.m.ram[:0xe0])==zp and tuple(map(bytes,h.m.banks))==flash and not h.m.events
                    assert h.m.ram[h.b['DC_BINARY']]==0
                    assert b'SEND BIN' not in tx[n:]
                    out=h.port_command(source_port,b'?\r')
                    assert build_b15.HELP in out
                    # A second load must have no stale ownership or timer state.
                    start(h,source_port)
                    body=b'\x4c\x00\x02\x03\r\n';feed(h,source_port,body)
                    h.run(lambda:h.c.pc==0x200)
                    assert bytes(h.m.ram[0x200:0x206])==body and not h.m.events
                    passed(cpu,port,'cancel-ready-'+ending.hex()+f'-from-{source_port}-then-reload')
            # Only enabled ports can cancel. Data from the other console stays
            # untouched when the current runtime mode selects one console.
            h=fresh(build,cpu);h.port_command(port,f'C{port}\r'.encode())
            start(h,port);other=h.m.acia_rx if port==1 else h.m.rx;other.append(3)
            h.fast_idle=False;polls=0
            def waiting():
                nonlocal polls
                if h.c.pc==h.b['B14_FIRST']:polls+=1
                return polls==100
            h.run(waiting);assert bytes(other)==b'\x03'
            (h.m.rx if port==1 else h.m.acia_rx).append(3)
            h.run(lambda:h.c.pc==h.b['BOOT_MENU'])
            assert bytes(other)==b'\x03' and not h.m.events
            passed(cpu,port,'disabled-console-cannot-cancel')
            # The optional command-LF lookahead can capture a first non-LF byte
            # before SEND BIN; a captured 03 must take the same cancel path.
            h=fresh(build,cpu);ram=bytes(h.m.ram[0x200:0x7800])
            tx=h.m.tx if port==1 else h.m.acia_tx;n=len(tx)
            (h.m.rx if port==1 else h.m.acia_rx).extend(b'L\r\x03')
            h.run(lambda:len(tx)>n and bytes(tx).endswith(b'REC> '))
            assert b'SEND BIN\r\n' in tx[n:] and bytes(h.m.ram[0x200:0x7800])==ram and not h.m.events
            passed(cpu,port,'optional-LF-probe-pending-Ctrl-C-cancels')
            # Once byte zero has arrived, all later 03 bytes are payload.
            for body in (b'\x00\x03',b'\x4c\x00\x02'+bytes([3])*256,bytes(range(256))):
                h=fresh(build,cpu);start(h,port);feed(h,port,body)
                h.run(lambda:h.c.pc==0x200)
                assert bytes(h.m.ram[0x200:0x200+len(body)])==body and not h.m.events
            passed(cpu,port,'payload-Ctrl-C-remains-literal',cases=3)
            if port==2:
                h=fresh(build,cpu);start(h,port);ram=bytes(h.m.ram[0x200:0x6500])
                h.m.acia_error=4;h.m.acia_rx.append(3)
                h.run(lambda:h.c.pc==h.b['BOOT_MENU'])
                assert b'REFUSED: receive error' in h.m.acia_tx
                assert bytes(h.m.ram[0x200:0x6500])==ram and not h.m.events
                passed(cpu,port,'receive-error-precedes-Ctrl-C-cancel')
        h=fresh(build,cpu);h.m.ft_tx_blocked=True;start(h,2)
        h.m.acia_rx.append(3);h.run(lambda:bytes(h.m.acia_tx).endswith(b'REC> '))
        assert h.m.ram[h.b['DC_BINARY']]==0 and not h.m.events
        passed(cpu,2,'blocked-FT-output-still-cancels-from-ACIA')
    core,_=load_core()
    core.save(build/'b15-cancel.json',dict(passed=True,checks=len(rows),failures=0,hardware=False,serial_access=False,
        cases=rows,checker_sha256=core.sha(Path(__file__).read_bytes()),F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes())))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    x=p.parse_args();build=x.build.resolve()
    # Preserve the b14 checker and its receipts. The only removed assertion
    # was that a leading 03 is data; the new tests above cover its replacement.
    source=(HERE/'test_b14_raw.py').read_text()
    source=source.replace('from build_b14 import HELP,FT_POLLS,AC_POLLS','from build_b15 import HELP,FT_POLLS,AC_POLLS')
    source=source.replace('0x8000000e','0x8000000f').replace('for first in [0,3,10,13,255]:','for first in [0,10,13,255]:')
    source=source.replace("f'b14-raw{suffix}.json'","f'b15-raw{suffix}.json'")
    sys.argv=[__file__,'--build',str(build)]
    exec(compile(source,str(HERE/'test_b14_raw.py'),'exec'),dict(__file__=__file__,__name__='__main__'))
    cancellation_tests(build)


if __name__=='__main__':main()
