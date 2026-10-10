"""Execute the resident SPI gateway, integrity checks, ownership and lifecycle."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-spi-resident')
import json,hashlib
from test_v2_journal import Memory as BaseMemory,k,EQ
from test_v2_spi_prototype import Memory as PinMemory,raw_request,memory_request
OUT=k.fw.OUT;META=k.REPORT

class Memory(BaseMemory):
    def __init__(self,**spi):
        super().__init__();self.spi=PinMemory(**spi);self.spi.ram=self.ram;self.spi.banks=self.banks
        self.ram[0x7FCB]=0 # VIA reset ACR; base monitor fixture uses RAM filler here.
        self.ram[0x7FCE]=0x80 # Reset IER: no enabled VIA IRQs; reads have bit 7 set.
    def __getitem__(self,a):
        if isinstance(a,int) and a in (0x7FC0,0x7FC2,0x7FCC,0x7FCD):return self.spi[a]
        return super().__getitem__(a)
    def __setitem__(self,a,v):
        if isinstance(a,int) and a in (0x7FC0,0x7FC2):self.spi[a]=v;return
        super().__setitem__(a,v)

def boot(missing_main=False,**options):
    m=Memory(**options);cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu;m.spi.cpu=cpu
    if missing_main:m.banks[3][4096:8192]=bytes([255])*4096
    k.model.run(cpu,lambda:k.model.waiting(cpu),20000000);return cpu,m

def call(cpu,entry,bank=3):
    m=cpu.memory;pcr=(m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[bank];m[0x7FEC]=pcr
    cpu.p=0x28|cpu.UNUSED;sp=cpu.sp;cpu.stPushWord(0x01FF);cpu.pc=entry
    lowest=cpu.sp
    for _ in range(6000000):
        if cpu.pc==0x0200:break
        lowest=min(lowest,cpu.sp);cpu.step()
    else:raise AssertionError(hex(cpu.pc))
    m.deepest_stack=max(getattr(m,'deepest_stack',0),sp-lowest)
    assert cpu.sp==sp and m.ram[0x7FEC]==pcr and (cpu.p&0x0C)==8
    assert bool(cpu.p&cpu.CARRY)==(cpu.a==0)
    return cpu.a

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=boot();assert m.ram[0x7D04:0x7D0C]==b'SV\x01\x0f\0\x65\xff\x64'
    assert m.ram[0x6646:0x664D]==b'SP\x01\x01\x4c\xb8\x66'
    assert m.ram[0x66A2:0x66A9]==b'SM\x01\x01\x4c\xa9\x66' and m.ram[0x66AE]==META.get('managed_default',0)
    if META.get('status_banner'):
        assert m.spi.frames and all(f['device']==0 for f in m.spi.frames)
    else:assert not m.spi.frames and not m.spi.io_writes
    assert m.ram[0x200:0x6500]==bytes([0x5A])*0x6300
    flash=[bytes(b) for b in m.banks];ee=bytes(m.bus.ee);calendar=bytes(m.bus.rtc_regs)
    for bank in range(4):
        raw_request(m,tx=b'abc',rx=4);result=call(cpu,0x664A,bank)
        assert result==0 and m.ram[0x6659:0x665B]==b'\x03\x04',(bank,result,m.ram[0x6650:0x6660].hex(),m.ram[0x6664],m.spi.port_pcr,m.ram[0x7FCB],m.spi.io_writes[-4:])
        assert m.spi.frames[-1]['device']==1
        memory_request(m,op=0,count=0);before=bytes(m.spi.devices[0].data);assert call(cpu,0x66A6,bank)==0
        assert bytes(m.spi.devices[0].data)==before and m.ram[0x665B:0x665F]==bytes((0,0,2,0x81))
        for address,count in ((0xFFFE,64),(0x10000,64),(0x1FFFF,1)):
            pattern=bytes((i^0xA5) for i in range(count));m.ram[0x2200:0x2200+count]=pattern
            if META.get('managed_default'):
                memory_request(m,op=2,address=address,count=count);assert call(cpu,0x66A6,bank)==6
            m.ram[0x66AE]=0 # Test fixture acts as the privileged manager.
            memory_request(m,op=2,address=address,count=count);assert call(cpu,0x66A6,bank)==0
            m.ram[0x66AE]=META.get('managed_default',0)
            memory_request(m,address=address,count=count,buffer=0x2400);assert call(cpu,0x66A6,bank)==0
            assert m.ram[0x2400:0x2400+count]==pattern
        assert not m.ram[0x6660] and not m.ram[0x6669] and not m.ram[EQ['J_LOCK']]
    assert [bytes(b) for b in m.banks]==flash and bytes(m.bus.ee)==ee and bytes(m.bus.rtc_regs)==calendar
    passed('software-only discovery; merged public SPI/SRAM entries work in all banks; probe restores data; 17-bit boundaries; flash/RTC/EEPROM intact')
    for busy in (0x6660,0x6669,EQ['J_LOCK']):
        m.ram[busy]=1;raw_request(m,tx=b'12');m.ram[0x6658:0x6660]=bytes(range(8));before=bytes(m.ram[0x6650:0x6660]);n=len(m.spi.frames)
        assert call(cpu,0x664A)==8 and bytes(m.ram[0x6650:0x6660])==before and len(m.spi.frames)==n and m.ram[busy]==1
        m.ram[busy]=0
    raw_request(m,device=0,tx=b'\x05',rx=1);n=len(m.spi.frames);assert call(cpu,0x664A)==6 and len(m.spi.frames)==n
    m.ram[0x66AE]=1;memory_request(m,op=2,address=0,count=1);assert call(cpu,0x66A6)==6
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    assert m.ram[0x66AE]==1 and m.ram[0x6646:0x664A]==b'SP\x01\x01'
    assert bool(m.ram[0x6664]&4)==bool(META.get('status_banner') and not META.get('quiet_monitor_return'))
    assert m.ram[0x7D0A:0x7D0C]==b'\xff\x64'
    passed('busy refusal preserves active outputs/locks; raw SRAM denied; managed writes denied; HOLD preserves policy and reservation while invalidating SPI cache')
    # New CRC cache must cover the entire main prefix and preserve parent buses.
    for fault in ('missing','corrupt'):
        cpu,m=boot();n=len(m.spi.frames);m.ram[0x6664]&=~4
        if fault=='missing':m.banks[3][4096:8192]=bytes([255])*4096
        else:m.banks[3][META['spi_symbols']['SPI_HANDLE']-0x8000]^=1
        memory_request(m,op=0,count=0);assert call(cpu,0x66A6)==(0x80 if fault=='missing' else 0x81)
        assert len(m.spi.frames)==n and m.ram[0x7D07]==3 and not m.ram[EQ['J_DESC']]
        assert call(cpu,0x6504)==0
    cpu,m=boot();n=len(m.spi.frames);m.ram[0x6664]=2;m.banks[3][0xD80]^=1
    memory_request(m,op=0,count=0);assert call(cpu,0x66A6)==0x81 and len(m.spi.frames)==n
    passed('first-use integrity covers main prefix and whole helper sector; absent/corrupt SPI main cannot invoke code or disable valid RTC')
    cpu,m=boot(missing_main=True);assert m.ram[0x7D07]==3 and m.ram[0x7D0A:0x7D0C]==b'\xff\x64' and not m.spi.frames
    memory_request(m,op=0,count=0);assert call(cpu,0x66A6)==0x80 and call(cpu,0x6504)==0
    # Actual RAM NMI handler attempts reentry during the resident byte loop.
    cpu,m=boot();m.ram[0x7E00:0x7E02]=b'\0\4'
    m.ram[0x400:0x40D]=bytes.fromhex('48 DA 5A 20 4A 66 8D 20 04 7A FA 68 40')
    raw_request(m,tx=bytes(range(16)),rx=16,flags=1,wp=0x2200,rp=0x2200)
    cpu.stPushWord(0x01FF);cpu.pc=0x664A;injected=False
    for _ in range(6000000):
        if cpu.pc==0x200:break
        if not injected and cpu.pc==META['spi_symbols']['SP_BIT_LOOP']:cpu.nmi();injected=True
        cpu.step()
    else:raise AssertionError(hex(cpu.pc))
    assert injected and cpu.a==0 and m.ram[0x420]==8 and m.spi.frames[-1]['tx']==list(range(16))
    passed('cold missing SPI main retains RTC/I2C/RAM bounds; actual RAM NMI reentry refuses without damaging the active duplex transaction')
    for options in (dict(present=False),dict(stuck='low'),dict(stuck='high'),dict(ignore_writes=True)):
        cpu,m=boot(**options);memory_request(m,op=0,count=0);assert call(cpu,0x66A6)==7
    cpu,m=boot();m.bus.devices.pop(0x6F);memory_request(m,op=0,count=0);assert call(cpu,0x66A6)==0
    passed('missing/stuck/failed SRAM refuses usability safely; SRAM transport does not require responding RTC hardware')
    maximum_stack=0
    for mode in (0,0x80):
        cpu,m=boot(mode=mode);memory_request(m,op=0,count=0);before=bytes(m.spi.devices[0].data)
        assert call(cpu,0x66A6)==0 and m.spi.devices[0].mode==mode and bytes(m.spi.devices[0].data)==before
        maximum_stack=max(maximum_stack,m.deepest_stack)
    assert maximum_stack<=16,maximum_stack
    cpu,m=boot();raw_request(m,tx=bytes(range(64)),rx=64,flags=1,wp=0x2200,rp=0x2200)
    assert call(cpu,0x664A)==0 and m.spi.frames[-1]['tx']==list(range(64))
    # Alternating the buses must rebind shared thunks/scratch correctly.
    for _ in range(3):
        m.ram[0x2100]=0x10;m.ram[0x6650:0x6658]=bytes((0x3C,1,0,0x21,1,0,0x24,4))
        assert call(cpu,0x6514)==0 and m.ram[0x2400:0x2404]==bytes(range(0x10,0x14))
        memory_request(m,address=0x10000,count=64);assert call(cpu,0x66A6)==0
        assert call(cpu,0x6504)==0
    # Runnable example reads by default and supports caller-prepared WRITE.
    example=OUT/'example';em=json.loads((example/'build.json').read_text());body=(example/'example.bin').read_bytes()
    m.ram[0x2000:0x2000+len(body)]=body;data=k.model.command(cpu,b'G 2000\r',20000000)
    assert b'SM: 00' in data and m.ram[0x2300:0x2310]==m.spi.devices[0].data[0x10000:0x10010]
    prepared=bytes((2,0,0,0,1,0,0x23,16,0,0,0,0,0,0,0,0));m.ram[0x2400:0x2410]=prepared;m.ram[0x2300:0x2310]=bytes(range(16))
    prior=bytes(m.spi.devices[0].data[0x10000:0x10010]);data=k.model.command(cpu,b'G 2003\r',20000000)
    if META.get('managed_default'):
        assert b'SM: 06' in data and bytes(m.spi.devices[0].data[0x10000:0x10010])==prior
    else:assert b'SM: 00' in data and m.spi.devices[0].data[0x10000:0x10010]==bytes(range(16))
    passed('mode restoration fits stack budget; duplex and alternating I2C/RTC/SRAM preserve scratch ownership; linked example READ/prepared WRITE works')
    report=dict(passed=True,checks=checks,artifacts=META['artifacts'],spi_sizes=META['spi_sizes'],max_stack_bytes=maximum_stack,example_sha256=em['sha256'],hardware_tested=False,board_writes=False)
    (OUT/'spi-resident-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
