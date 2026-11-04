"""Raw receive/autorun tests and unaccelerated idle timing on both CPUs/ports."""
import argparse,json
from pathlib import Path
from test_b14_core import load_core,empty_cycles
from build_b14 import HELP,FT_POLLS,AC_POLLS

def fresh(build,cpu):
    core,_=load_core();core.GENERATION=0x8000000e
    h=core.Machine(build,cpu,opaque=True);h.recovery()
    h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    return h

def start(h,port,ending=b'\r'):
    h.port_command(port,b'L'+ending,b'SEND BIN\r\n')
    h.run(lambda:h.c.pc==h.b['B14_FIRST'])

def feed(h,port,body):
    (h.m.rx if port==1 else h.m.acia_rx).extend(body)
    target=0x200+len(body)
    h.run(lambda:h.c.pc==h.b['B14_IDLE'] and int.from_bytes(h.m.ram[0xe2:0xe4],'little')==target)

def preservation(h,original,body):
    assert bytes(h.m.ram[0x200:0x200+len(body)])==body
    assert bytes(h.m.ram[0x200+len(body):0x6500])==original[len(body):]
    assert not h.m.events

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
    p.add_argument('--cpu',choices=['65c02','65c816-e']);p.add_argument('--timing',action='store_true')
    args=p.parse_args();build=args.build.resolve();rows=[]
    def passed(cpu,port,case,**kw):
        rows.append(dict(cpu=cpu,port=port,case=case,passed=True,**kw));print('PASS',cpu,port,case,flush=True)
    for cpu in ([args.cpu] if args.cpu else ['65c02','65c816-e']):
        for port in [1,2]:
            if args.timing:
                real=fresh(build,cpu);start(real,port);real.fast_idle=False
                original=bytes(real.m.ram[0x200:0x6500]);feed(real,port,b'\x4c\x00\x02'+bytes(range(256)))
                # Compare accelerated and real execution starting with exactly
                # the same CPU, RAM, queued input and output state.
                import copy
                fast=copy.deepcopy(real);fast.fast_idle=True
                begin=real.c.processorCycles
                real.run(lambda:real.c.pc==0x200);fast.run(lambda:fast.c.pc==0x200)
                duration=real.c.processorCycles-begin
                n=FT_POLLS if port==1 else AC_POLLS
                assert 24_000_000<=duration<=24_001_000,(cpu,port,duration)
                assert real.c.__dict__.keys()==fast.c.__dict__.keys()
                assert {k:v for k,v in real.c.__dict__.items() if k!='memory'}=={k:v for k,v in fast.c.__dict__.items() if k!='memory'}
                assert real.m.ram==fast.m.ram and real.m.banks==fast.m.banks
                assert real.m.tx==fast.m.tx and real.m.acia_tx==fast.m.acia_tx
                preservation(real,original,b'\x4c\x00\x02'+bytes(range(256)))
                assert real.m.ram[real.b['DC_BINARY']]==0
                passed(cpu,port,'full-three-second-idle-actual-instructions-and-exact-fast-model-equivalence',
                    cycles_until_run=duration,seconds_at_8MHz=duration/8_000_000,
                    empty_poll_cycles=empty_cycles(n,port),accelerated_instructions=False)
                continue
            for ending in [b'\r',b'\n',b'\r\n']:
                h=fresh(build,cpu);out=h.port_command(port,b'?'+ending)
                assert HELP in out and b'R=' not in out and b'CRC' not in out and b'RLP1' not in out
                for key in [b'R',b'r',b'D',b'd',b'V',b'v']:
                    assert b'REFUSED: command' in h.port_command(port,key+ending)
                passed(cpu,port,'help-and-removed-R-D-V-'+ending.hex())
                h=fresh(build,cpu);original=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0]);flash=tuple(map(bytes,h.m.banks))
                start(h,port,ending)
                # No timer starts before data; advance virtual elapsed time
                # and execute first-byte wait polls rather than invent EOF.
                h.c.processorCycles+=100_000_000;h.fast_idle=False
                polls=0
                def waiting():
                    nonlocal polls
                    if h.c.pc==h.b['B14_FIRST']:polls+=1
                    return polls==1025
                h.run(waiting);assert bytes(h.m.ram[0x200:0x6500])==original
                h.fast_idle=True;body=bytes(range(256))*16
                output=bytes(h.m.tx),bytes(h.m.acia_tx)
                feed(h,port,body)
                other=h.m.acia_rx if port==1 else h.m.rx;other.extend(b'R\rC1\r\x03\x00\xff')
                noise=bytes(other);h.run(lambda:h.c.pc==0x200)
                assert bytes(other)==noise and output==(bytes(h.m.tx),bytes(h.m.acia_tx))
                assert h.m.bank==3 and h.m.ram[h.b['DC_BINARY']]==0
                assert bytes(h.m.ram[:0xe0])==zp and tuple(map(bytes,h.m.banks))==flash
                preservation(h,original,body)
                passed(cpu,port,'indefinite-first-wait-4K-all-values-no-echo-other-port-untouched-'+ending.hex(),bytes=len(body))
            for first in [0,3,10,13,255]:
                h=fresh(build,cpu);start(h,port);body=bytes([first])+b'\x00\xff\r\n\x03'
                feed(h,port,body);h.run(lambda:h.c.pc==0x200)
                assert bytes(h.m.ram[0x200:0x200+len(body)])==body
                passed(cpu,port,f'first-byte-{first:02x}-is-data')
            h=fresh(build,cpu);start(h,port);feed(h,port,b'A')
            # The countdown has almost expired. A new byte must fully reload
            # it; this exercises the actual receive/reset branch at its edge.
            h.c.x=h.c.y=1;h.m.ram[h.b['B14_TICKS']]=1
            (h.m.rx if port==1 else h.m.acia_rx).append(ord('B'))
            h.run(lambda:h.c.pc==h.b['B14_IDLE'] and h.m.ram[0x201]==ord('B'))
            n=FT_POLLS if port==1 else AC_POLLS
            count=(h.c.x or 256)+256*((h.c.y or 256)-1)+65536*(h.m.ram[h.b['B14_TICKS']]-1)
            assert count==n;h.run(lambda:h.c.pc==0x200)
            passed(cpu,port,'last-byte-restarts-full-idle-budget')
            h=fresh(build,cpu);start(h,port);body=bytes(range(256))*99
            before=bytes(h.m.ram[0x6500:0x7800]);feed(h,port,body);h.run(lambda:h.c.pc==0x200)
            assert len(body)==0x6300 and bytes(h.m.ram[0x200:0x6500])==body and bytes(h.m.ram[0x6500:0x7800])==before
            passed(cpu,port,'exact-25344-byte-upper-bound-runs')
            h=fresh(build,cpu);start(h,port);before=bytes(h.m.ram[0x6500:0x7800])
            queue=h.m.rx if port==1 else h.m.acia_rx;queue.extend(body+b'X')
            h.run(lambda:h.c.pc==h.b['BOOT_MENU'])
            tx=h.m.tx if port==1 else h.m.acia_tx
            assert b'REFUSED: RAM range' in tx and bytes(h.m.ram[0x6500:0x7800])==before and not h.m.events
            assert h.c.pc!=0x200
            passed(cpu,port,'overflow-refuses-without-out-of-range-write-or-execution')
            if port==2:
                for error in [1,2,4]:
                    h=fresh(build,cpu);start(h,port);h.m.acia_error=error
                    h.m.acia_rx.append(0x4c);h.run(lambda:h.c.pc==h.b['BOOT_MENU'])
                    assert b'REFUSED: receive error' in h.m.acia_tx and not h.m.events
                    passed(cpu,port,'serial-error-refuses-'+str(error))
            h=fresh(build,cpu);h.m.ft_tx_blocked=True;start(h,2)
            body=b'\x4c\x00\x02'+bytes(range(256));feed(h,2,body);h.run(lambda:h.c.pc==0x200)
            assert bytes(h.m.ram[0x200:0x200+len(body)])==body and not h.m.events
            passed(cpu,port,'blocked-FT245-output-ACIA-load-and-autorun')
    core,_=load_core();suffix=('-timing-'+args.cpu) if args.timing else ''
    core.save(build/f'b14-raw{suffix}.json',dict(passed=True,checks=len(rows),failures=0,hardware=False,serial_access=False,
        cases=rows,checker_sha256=core.sha(Path(__file__).read_bytes()),F_sha256=core.sha((build/'payload/f-offline-component.bin').read_bytes())))

if __name__=='__main__':main()
