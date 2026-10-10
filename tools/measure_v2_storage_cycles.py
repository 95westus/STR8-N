"""Measure warm resident SRAM service CPU cycles; modeled pins, no ports."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-storage'
import json
from test_v2_spi_resident import boot,k,call
from test_v2_spi_prototype import memory_request
from pathlib import Path
OUT=k.fw.OUT/'timing';OUT.mkdir(exist_ok=True)

def main():
    cpu,m=boot();memory_request(m,op=1,address=0x18000,count=1,buffer=0x4000);assert call(cpu,0x66A6)==0
    results=[]
    for fill in (0,0x55,0xFF):
        m.ram[0x4000:0x5000]=bytes([fill])*4096
        for size in (1,32,64,256,1024,4096):
            total=0;maximum=0
            for offset in range(0,size,64):
                n=min(64,size-offset);memory_request(m,op=2,address=0x18000+offset,count=n,buffer=0x4000+offset);m.ram[0x66AE]=0
                start=cpu.processorCycles;assert call(cpu,0x66A6)==0;cycles=cpu.processorCycles-start;m.ram[0x66AE]=1
                total+=cycles;maximum=max(maximum,cycles)
            results.append(dict(fill=fill,size=size,calls=(size+63)//64,cycles=total,max_call_cycles=maximum,ms_8MHz=total/8000))
    (OUT/'sram-cycle-model.json').write_text(json.dumps(dict(results=results,hardware=False),indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
