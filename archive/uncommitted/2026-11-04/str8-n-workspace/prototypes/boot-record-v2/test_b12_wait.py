"""Linked-CPU first-byte waiting, cancellation, ownership and binary checks."""
import argparse
import json
from pathlib import Path
import test_b12_core as test_b07


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    args=p.parse_args();build=args.build.resolve();core,adaptation=test_b07.load_core()
    core.GENERATION=0x8000000c;rows=[]
    def passed(cpu,port,case,**details):
        rows.append(dict(cpu=cpu,port=port,case=case,passed=True,**details));print('PASS',cpu,port,case,flush=True)
    def fresh(cpu,port,ending=b'\r'):
        h=core.Machine(build,cpu,opaque=True);h.recovery()
        h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
        h.port_command(port,b'L'+ending,b'SEND HEADER+BIN\r\n')
        h.run(lambda:h.c.pc==h.b['B10_WAIT_FIRST'])
        return h
    def enter(h,port,data):
        return h.port_command(port,data)
    for cpu in ('65c02','65c816-e'):
        for port in (1,2):
            h=fresh(cpu,port);original=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0])
            output=bytes(h.m.tx),bytes(h.m.acia_tx);stack=h.c.sp;polls=0
            def enough():
                nonlocal polls
                if h.c.pc==h.b['B10_WAIT_FIRST']:polls+=1
                return polls>70000
            h.run(enough,limit=8_000_000)
            assert h.c.sp==stack and (bytes(h.m.tx),bytes(h.m.acia_tx))==output
            assert bytes(h.m.ram[0x200:0x6500])==original and bytes(h.m.ram[:0xe0])==zp and not h.m.events
            out=enter(h,port,b'\x03')
            assert b'REFUSED' not in out and out.endswith(b'REC> ') and h.m.ram[h.b['RL_VALID']]==0
            h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
            assert h.c.sp==253 and h.m.ram[0x7c2b]==0, (h.c.sp,h.m.ram[0x7c2b])
            passed(cpu,port,'over-old-65536-poll-wait-then-Ctrl-C',actual_empty_polls=polls-1,no_RAM_or_flash_write=True)
            for ending in (b'\r',b'\n',b'\r\n'):
                h=fresh(cpu,port,ending);original=bytes(h.m.ram[0x200:0x6500])
                for _ in range(8):
                    out=enter(h,port,b'\x03');assert b'REFUSED' not in out
                    h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE']);assert h.c.sp==253
                    h.port_command(port,b'L'+ending,b'SEND HEADER+BIN\r\n')
                    h.run(lambda:h.c.pc==h.b['B10_WAIT_FIRST'])
                body=bytes(range(256))*16
                out=enter(h,port,core.header(body)+body)
                assert b'LOADED;' in out and h.m.ram[h.b['RL_VALID']]==1
                assert bytes(h.m.ram[0x2000:0x3000])==body and bytes(h.m.ram[0x200:0x2000])==original[:0x1e00]
                assert bytes(h.m.ram[0x3000:0x6500])==original[0x2e00:] and not h.m.events
                passed(cpu,port,'cancel8-then-4096-byte-all-values-'+ending.hex(),payload_03_preserved=True)
            for partial,label in ((b'R','partial-header'),(core.header(b'\x03'*16)+b'\x03','partial-payload')):
                h=fresh(cpu,port);out=enter(h,port,partial)
                assert b'REFUSED' in out and h.m.ram[h.b['RL_VALID']]==0 and not h.m.events
                passed(cpu,port,label+'-still-times-out-and-invalidates-run')
            h=fresh(cpu,port);body=b'\x03\0\xff';packet=core.header(body)+body
            assert packet[8]==3
            out=enter(h,port,packet)
            assert b'LOADED;' in out and bytes(h.m.ram[0x2000:0x2003])==body and not h.m.events
            passed(cpu,port,'03-in-remaining-header-and-payload-is-data')
            h=fresh(cpu,port);other=h.m.acia_rx if port==1 else h.m.rx
            other.extend(b'\x03bad')
            for _ in range(32):
                h.c.step()
            assert bytes(other)==b'\x03bad' and h.m.ram[h.b['RL_VALID']]==0
            out=enter(h,port,core.header(b'\x03\0\xff\r\n')+b'\x03\0\xff\r\n')
            assert b'LOADED;' in out and not h.m.events
            passed(cpu,port,'other-console-Ctrl-C-not-binary-input')
    result=dict(passed=True,checks=len(rows),failures=0,cases=rows,hardware=False,serial_access=False,
        device_or_network_attempts=core.ATTEMPTS,checker_sha256=core.sha(Path(__file__).read_bytes()),
        F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes()),
        prototype_report_sha256=core.sha((build/'prototype-report.json').read_bytes()),
        component_hashes={p.name:core.sha(p.read_bytes()) for p in (build/'payload').glob('*-offline*.bin')})
    (build/'b12-wait-tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b12 wait groups',len(rows),flush=True)


if __name__=='__main__':main()
