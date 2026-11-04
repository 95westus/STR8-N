"""Measure linked empty-poll cycles; derive nominal three-second budgets."""
import argparse,json
from pathlib import Path
import test as core
from test_boot_startup import timed_step,check_instruction_timing

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    rows=[]
    for cpu in ['65c02','65c816-e']:
        for port in [1,2]:
            results={}
            for n in [1,256,65536]:
                h=core.Machine(build,cpu,opaque=True);check_instruction_timing(type(h.c))
                h.m.ram[h.b['DC_BINARY']]=port;h.m.ram[h.b['DC_NEXT']]=port
                h.c.pc=h.b['B14_IDLE'];h.c.x=((n-1)%256+1)%256;h.c.y=(((n-1)//256)%256+1)%256
                h.m.ram[h.b['B14_TICKS']]=(n-1)//65536+1
                start=h.c.processorCycles
                while h.c.pc!=h.b['B14_RUN']:timed_step(h.c,h.m[h.c.pc])
                results[n]=h.c.processorCycles-start
            base=(results[256]-11)//256
            def cycles(n):return base*n+4*((n+255)//256)+8*((n+65535)//65536)-1
            assert all(results[n]==cycles(n) for n in results),(cpu,port,base,results)
            n=24_000_000//base
            while cycles(n)<24_000_000:n+=1
            while cycles(n-1)>=24_000_000:n-=1
            rows.append(dict(cpu=cpu,port=port,base_empty_poll_cycles=base,measured=results,
                             polls=n,cycles=cycles(n),seconds=cycles(n)/8_000_000))
            print(rows[-1],flush=True)
    (build/'b14-timer-calibration.json').write_text(json.dumps(dict(passed=True,hardware=False,cases=rows),indent=2)+'\n')

if __name__=='__main__':main()
