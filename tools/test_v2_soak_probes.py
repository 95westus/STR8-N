"""Check the narrow RTC SRAM RAM diagnostic before hardware writes."""
import hashlib,json
from pathlib import Path
from test_v2_i2c import Devices
from test_v2_rtc import MPU
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/beta23-soak-probes'

def main():
    meta=json.loads((OUT/'build.json').read_text());body=(OUT/'rtc-sram/rtc-sram.bin').read_bytes();assert hashlib.sha256(body).hexdigest()==meta['rtc-sram']['sha256']
    m=Devices();m.rtc_regs.extend(bytes((i*19+3)&255 for i in range(64)));m.regs=m.rtc_regs;m.devices[0x6F]=m.rtc_regs
    m.ram[0x4000:0x4000+len(body)]=body;m.ram[0x7D27]=1;m.ram[0x7D07]=1
    original=bytes(m.rtc_regs);pins=(m.ddr,m.latch);checks=[]
    def call(op,address,count,data=None):
        m.ram[0x3000:0x3005]=bytes((op,address,count,0xFF,0))
        if data:m.ram[0x3100:0x3100+len(data)]=data
        cpu=MPU(memory=m,pc=0x4000)
        for _ in range(1000000):
            if cpu.pc==0x7E67:break
            cpu.step()
        else:raise AssertionError('Diagnostic timeout')
        return m.ram[0x3003],m.ram[0x3004],bytes(m.ram[0x3100:0x3100+count])
    for address in (0x20,0x30,0x40,0x50):
        status,done,backup=call(1,address,16);assert status==0 and done==16 and backup==original[address:address+16]
        pattern=bytes((address+i)^0xA5 for i in range(16));assert call(2,address,16,pattern)[:2]==(0,16)
        assert call(1,address,16)[2]==pattern
        assert call(2,address,16,backup)[:2]==(0,16) and call(1,address,16)[2]==backup
        assert bytes(m.rtc_regs)==original and m.ddr==pins[0] and (m.latch&m.ddr)==(pins[1]&pins[0])
    checks.append('All four 16-byte RTC SRAM chunks write/read/restore; registers and pins unchanged')
    for args in ((2,0x1F,1),(2,0x60,1),(2,0x50,17),(2,0x5F,2),(2,0x20,0),(3,0x20,1)):
        accesses=len(m.accesses);assert call(*args)[0]==9 and len(m.accesses)==accesses and bytes(m.rtc_regs)==original
    checks.append('Invalid ranges/counts/operations refuse before bus access')
    m.ram[0x7D27]=2;accesses=len(m.accesses);assert call(2,0x20,16)[0]==0x80 and len(m.accesses)==accesses
    checks.append('EDU OFF refuses before bus access')
    (OUT/'test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,probe_sha256=meta['rtc-sram']['sha256']),indent=2)+'\n');print('PASS RTC SRAM bounds, actual I2C bit model, restoration and EDU guard')

if __name__=='__main__':main()
