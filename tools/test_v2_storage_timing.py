"""Execute RAM timer probe against cycle-driven timer and real SPI pins."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-storage'
import json
from test_v2_spi_resident import Memory,k,OUT
BODY=(OUT/'timing/probe.bin').read_bytes()

class TimedMemory(Memory):
    def __init__(self):
        super().__init__();self.timer_start=0;self.timer_value=65535;self.timer_low=255;self.ram[0x7FCE]=0x80
    def __getitem__(self,a):
        if isinstance(a,int) and a in (0x7FC8,0x7FC9):
            value=(self.timer_value-(self.cpu.processorCycles-self.timer_start))&65535
            return value&255 if a==0x7FC8 else value>>8
        return super().__getitem__(a)
    def __setitem__(self,a,v):
        if a==0x7FC8:self.timer_low=v;return
        if a==0x7FC9:self.timer_value=self.timer_low|(v<<8);self.timer_start=self.cpu.processorCycles;return
        super().__setitem__(a,v)

def main():
    m=TimedMemory();cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu;m.spi.cpu=cpu;k.model.run(cpu,lambda:k.model.waiting(cpu),30000000)
    m.ram[0x2000:0x2000+len(BODY)]=BODY
    from test_v2_spi_prototype import memory_request
    from test_v2_spi_resident import call
    memory_request(m,op=1,address=0x18000,count=1,buffer=0x4000);assert call(cpu,0x66A6)==0
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),30000000)
    m.ram[0x4000:0x5000]=b'\x55'*4096
    for n in (1,32,64,256,1024,4096):
        m.ram[0x6200:0x6204]=bytes((0,0,n&255,n>>8));before=cpu.processorCycles
        out=k.model.command(cpu,b'G 2000\r',40000000);assert m.ram[0x6214]==0 and b'~' in out
        measured=int.from_bytes(m.ram[0x6210:0x6214],'little');assert measured>0 and measured<cpu.processorCycles-before
        assert m.spi.devices[0].data[0x18000:0x18000+n]==b'\x55'*n
        print('PASS timer/SPI',n,measured,'cycles',flush=True)
    (OUT/'timing/model-check.json').write_text(json.dumps(dict(passed=True,firmware_artifacts=k.REPORT['artifacts'],worker_modified=False),indent=2)+'\n')

if __name__=='__main__':main()
