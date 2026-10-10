"""Execute SPI/SRAM opcodes against bit-level VIA/23LCV1024 models."""
import hashlib,json
from pathlib import Path
from test_v2_rtc import MPU
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-spi-phase2';META=json.loads((OUT/'build.json').read_text());S=META['symbols']
BODY=(OUT/'spi-prototype.bin').read_bytes()

class SRAM:
    def __init__(self,mode=0x40,size=131072,ignore_writes=False,ignore_restore=False):
        self.data=bytearray((i*37+(i>>8)*11)&255 for i in range(size));self.mode=mode
        self.writes=[];self.mode_writes=[];self.ignore_writes=ignore_writes;self.ignore_restore=ignore_restore
    def start(self):self.command=None;self.address=0;self.addr_left=0;self.reads=0
    def advance(self):
        if self.mode==0x40:self.address=(self.address+1)&0x1ffff
        elif self.mode==0x80:self.address=(self.address&~31)|((self.address+1)&31)
    def receive(self,value):
        if self.command is None:
            self.command=value;self.addr_left=3 if value in (2,3) else 0
        elif self.addr_left:
            self.address=(self.address<<8|value)&0x1ffff;self.addr_left-=1
        elif self.command==1:
            self.mode_writes.append(value);self.mode=value
        elif self.command==2:
            self.writes.append((self.address,value));index=self.address%len(self.data)
            if not self.ignore_writes and not (self.ignore_restore and len(self.writes)==2):self.data[index]=value
            self.advance()
        elif self.command==3:
            self.reads+=1;self.advance()
    def output(self):
        if self.command==5:return self.mode
        if self.command==3 and not self.addr_left:return self.data[self.address%len(self.data)]
        return 255

class Memory:
    def __init__(self,present=True,mode=0x40,stuck=None,**chip_options):
        self.ram=bytearray(65536);self.ram[0x3000:0x3000+len(BODY)]=BODY
        self.ram[0x6500:0x6700]=(ROOT/'BUILD/v2-rtc-trim/split/gateway.bin').read_bytes()
        self.ram[0x66C0:0x6700]=bytes([0x5A])*64
        self.banks=[bytearray([255])*32768 for _ in range(4)]
        self.banks[3][:4096]=(ROOT/'BUILD/v2-rtc-trim/str8n-rtc-component-8000-8fff.bin').read_bytes()
        for b in self.banks:b[-6:-4]=b'\0\4'
        self.ram[0x7E00:0x7E02]=b'\0\4'
        self.ddr=0;self.latch=255;self.port_pcr=0;self.ifr=0
        self.devices={0:SRAM(mode=mode,**chip_options)} if present else {}
        self.stuck=stuck;self.selected=None;self.bit=0;self.value=0;self.miso=1;self.outbyte=255
        self.frames=[];self.io_writes=[];self.port_reads=0
    def bank(self):return ((self.ram[0x7FEC]>>4)&2)|((self.ram[0x7FEC]>>1)&1)
    def levels(self):return (~self.ddr|self.latch)&15
    def __getitem__(self,a):
        if isinstance(a,slice):return self.ram[a]
        if a>=0x8000:return self.banks[self.bank()][a-0x8000]
        if a==0x7FC2:return self.ddr
        if a==0x7FCC:return self.port_pcr
        if a==0x7FCD:return self.ifr
        if a==0x7FC0:
            self.port_reads+=1;self.ifr&=~0x18
            value=(self.latch&self.ddr)|(255&~self.ddr)
            bit=self.miso if self.stuck is None else int(self.stuck=='high')
            return value&~32|(32 if bit else 0)
        return self.ram[a]
    def __setitem__(self,a,v):
        if isinstance(a,slice):self.ram[a]=v;return
        assert a<0x8000,'Flash mutation attempted'
        if a in (0x7FC0,0x7FC2):
            before=self.levels();self.io_writes.append((a,v))
            if a==0x7FC0:self.latch=v
            else:self.ddr=v
            after=self.levels()
            for dev,mask in ((0,4),(1,8)):
                if before&mask and not after&mask:
                    assert self.selected is None,'Two selected peripherals'
                    self.selected=dev;self.frames.append(dict(device=dev,tx=[],clocks=0,edges=[]));self.bit=self.value=0;self.outbyte=255;self.miso=1
                    if dev in self.devices:self.devices[dev].start()
                if not before&mask and after&mask:self.selected=None;self.miso=1
            if self.selected is not None:
                if (before^after)&1 and hasattr(self,'cpu'):self.frames[-1]['edges'].append((self.cpu.processorCycles,bool(after&1)))
                if not before&1 and after&1:
                    self.frames[-1]['clocks']+=1;self.value=self.value<<1|((after>>1)&1);self.bit+=1
                    if self.bit==8:
                        self.frames[-1]['tx'].append(self.value)
                        if self.selected in self.devices:self.devices[self.selected].receive(self.value)
                elif before&1 and not after&1:
                    if self.bit==8:
                        self.bit=self.value=0
                        self.outbyte=self.devices[self.selected].output() if self.selected in self.devices else (0xC0+len(self.frames[-1]['tx']))&255 if self.selected==1 else 255
                    self.miso=(self.outbyte>>(7-self.bit))&1
            return
        if a>=0x7F00:
            assert a==0x7FEC,f'Unexpected hardware write {a:04X}'
        self.ram[a]=v

def raw_request(m,device=1,tx=b'',rx=0,flags=0,wp=0x2100,rp=0x2200,filler=255,mode=0):
    m.ram[0x6650:0x6660]=bytes((device,flags,wp&255,wp>>8,len(tx),rp&255,rp>>8,rx,0,0,0,0,filler,mode,0,0))
    if 0x200<=wp and wp+len(tx)<=0x6500:m.ram[wp:wp+len(tx)]=tx

def memory_request(m,op=1,address=0,count=64,buffer=0x2200):
    m.ram[0x6650:0x6660]=bytes((op,0,address&255,address>>8&255,address>>16,buffer&255,buffer>>8,count,0,0,0,0,0,0,0,0))

def call(m,sram=False,flags=0x28,bank=3,nmi=False):
    m.ram[0x7FEC]=(0xCC,0xCE,0xEC,0xEE)[bank]|1
    before=(m.ddr,m.latch,m.ram[0x7FEC],bytes(m.ram[0x66C0:0x6700]));cpu=MPU(memory=m,pc=0x300B if sram else 0x3004)
    m.cpu=cpu;cpu.p=flags|cpu.UNUSED;cpu.sp=0xFD;cpu.stPushWord(0x01FF);minimum=cpu.sp;injected=False
    if nmi:
        m.ram[0x400:0x410]=bytes.fromhex('48 DA 5A 20 04 30 8D 20 04 7A FA 68 40 00 00 00')
    for steps in range(400000):
        if cpu.pc==0x200:break
        if nmi and not injected and cpu.pc==S['BIT_LOOP']:
            cpu.nmi();injected=True
        minimum=min(minimum,cpu.sp);cpu.step()
    else:raise AssertionError((hex(cpu.pc),m.ram[0x6650:0x6660].hex()))
    assert cpu.sp==0xFD and m.ram[0x7FEC]==before[2]
    assert (cpu.p&0x0C)==(flags&0x0C)
    assert (m.ddr==before[0]) and ((m.latch^before[1])&m.ddr)==0
    assert bytes(m.ram[0x66C0:0x6700])==before[3]
    assert not m.ram[0x6660] and not m.ram[0x6669]
    assert bool(cpu.p&cpu.CARRY)==(cpu.a==0)
    if nmi:assert injected and m.ram[0x420]==8
    return cpu.a,0xFD-minimum

def client(m,bulk=False,bank=3):
    image=(OUT/'spi-client.bin').read_bytes();m.ram[0x2000:0x2000+len(image)]=image
    m.ram[0x3E00:0x3E10]=m.ram[0x6650:0x6660]
    m.ram[0x3E20:0x3E23]=bytes((1,bank,0));m.ram[0x7FEC]=0xEE
    cpu=MPU(memory=m,pc=0x2003 if bulk else 0x2000);cpu.sp=0xFF
    for _ in range(8000000):
        if cpu.pc==0x7E67:break
        if cpu.pc in (0x7E6D,0x7E7C,0x7E7F):cpu.pc=(cpu.stPopWord()+1)&65535
        else:cpu.step()
    else:raise AssertionError(hex(cpu.pc))
    assert m.ram[0x3E33]==m.ram[0x3E34] and m.ram[0x7FEC]==0xEE
    return bytes(m.ram[0x3E10:0x3E20])

def main():
    assert hashlib.sha256(BODY).hexdigest()==META['sha256']
    assert hashlib.sha256((ROOT/'BUILD/v2-rtc-trim/split/provider.bin').read_bytes()).hexdigest()==META['provider_sha256']
    checks=[];max_stack=0
    def passed(message):checks.append(message);print('PASS',message,flush=True)
    for bank in range(4):
        m=Memory();raw_request(m,tx=b'123',rx=4);status,stack=call(m,bank=bank);assert status==0
        assert m.frames[-1]['tx']==list(b'123'+bytes([255])*4) and m.ram[0x6659:0x665B]==b'\x03\x04'
        raw_request(m,tx=bytes(range(64)),rx=64,flags=1,wp=0x22F0,rp=0x22F0)
        status,stack=call(m,bank=bank,nmi=True);assert status==0 and m.frames[-1]['tx']==list(range(64))
        assert m.ram[0x22F0:0x2330]==bytes([255])+bytes(range(0xC1,0x100));assert m.ram[0x6659:0x665B]==b'@@'
    passed('mode0 sequential and in-place duplex, byte counts, four caller banks and NMI busy reentry; stack/PCR/VIA/RTC output preserved')
    for wp,rp in ((0x2100,0x2200),(0x2200,0x2100),(0x2100,0x2140),(0x2140,0x2100)):
        m=Memory();raw_request(m,tx=bytes(range(64)),rx=64,flags=1,wp=wp,rp=rp);assert call(m)[0]==0
    for wp,rp in ((0x2100,0x2101),(0x2101,0x2100),(0x2100,0x213F),(0x213F,0x2100)):
        m=Memory();raw_request(m,tx=bytes(range(64)),rx=64,flags=1,wp=wp,rp=rp);assert call(m)[0]==9 and not m.io_writes
    invalid=[dict(device=2),dict(mode=3),dict(flags=2),dict(tx=b'',rx=0),dict(tx=bytes(65)),dict(rx=65),dict(wp=0x1FF),dict(wp=0x64FF,tx=b'12'),dict(rp=0x6500),dict(flags=1,tx=b'12',rx=1),dict(flags=1,tx=b'12',rx=2,wp=0x2200,rp=0x2201)]
    for change in invalid:
        m=Memory();args=dict(tx=b'12',rx=2);args.update(change);raw_request(m,**args)
        assert call(m)[0]==9 and not m.io_writes
    for field in (0x6660,0x6669):
        m=Memory();raw_request(m,tx=b'12');m.ram[field]=1;prior=bytes(m.ram[0x6650:0x6660]);cpu=MPU(memory=m,pc=0x3004);cpu.stPushWord(0x01FF)
        for _ in range(100):
            if cpu.pc==0x200:break
            cpu.step()
        assert cpu.a==8 and bytes(m.ram[0x6650:0x6660])==prior and not m.io_writes
    m=Memory();m.ram[0x3DF0]=1;raw_request(m,device=0,tx=b'\x05',rx=1);assert call(m)[0]==6 and not m.io_writes
    m=Memory();m.ram[0x7E01]=0x90;raw_request(m,tx=b'12');assert call(m,bank=0)[0]==0x82 and not m.io_writes
    for kind in ('pending','handshake','select','latching'):
        m=Memory();raw_request(m,tx=b'12')
        if kind=='pending':m.ifr=0x10
        if kind=='handshake':m.port_pcr=0x80
        if kind=='select':m.ddr=4;m.latch=0xFB
        if kind=='latching':m.ram[0x7FCB]=2
        assert call(m)[0]==1 and not m.io_writes
        if kind=='pending':assert m.ifr==0x10 and m.port_reads==0
    passed('invalid ranges/counts/modes/overlap, managed profile and busy refuse before pin changes; pending IRQ/handshake/select preserved')
    for mode in (0,0x40,0x80):
        for bank in range(4):
            m=Memory(mode=mode);chip=m.devices[0];before=bytes(chip.data)
            memory_request(m,op=0,count=0);status,stack=call(m,sram=True,bank=bank);max_stack=max(max_stack,stack)
            assert status==0 and bytes(chip.data)==before and chip.mode==mode,(mode,bank,status,chip.mode,chip.writes,m.ram[0x6650:0x6660].hex(),m.frames)
            assert m.ram[0x665B:0x665F]==bytes((0,0,2,0x81))
            for address,count in ((0,1),(0xFFFE,64),(0x10000,64),(0x1FFC0,64),(0x1FFFF,1)):
                data=bytes((i^0xA5)&255 for i in range(count));m.ram[0x2200:0x2200+count]=data
                memory_request(m,op=2,address=address,count=count);assert call(m,sram=True,bank=bank)[0]==0
                assert chip.data[address:address+count]==data and chip.mode==mode
                memory_request(m,address=address,count=count,buffer=0x2400);assert call(m,sram=True,bank=bank)[0]==0
                assert m.ram[0x2400:0x2400+count]==data and chip.mode==mode
    passed('explicit preserving probe; byte/page/sequential modes restored; SRAM read/write across 0FFFF/10000 and exact array/RAM limits in all banks')
    for opts in (dict(present=False),dict(stuck='low'),dict(stuck='high'),dict(ignore_writes=True),dict(ignore_restore=True)):
        m=Memory(**opts);memory_request(m,op=0,count=0);assert call(m,sram=True)[0]==7
    for address,count,buffer in ((0x20000,1,0x2200),(0x1FFFF,2,0x2200),(0,0,0x2200),(0,65,0x2200),(0,2,0x64FF)):
        m=Memory();memory_request(m,address=address,count=count,buffer=buffer);assert call(m,sram=True)[0]==9 and not m.io_writes
    passed('missing/stuck/ignored writes/restoration failures return unusable; array overflow and protected CPU buffers rejected without transfers')
    assert max_stack<=16,max_stack
    m=Memory();memory_request(m,address=0x10000,count=64,buffer=0x4000)
    result=client(m,bulk=True,bank=0);assert result[8]==0 and m.ram[0x4000:0x6000]==m.devices[0].data[0x10000:0x12000]
    m=Memory(present=False);memory_request(m,op=0,count=0);assert client(m)[8]==7
    passed('linked RAM client copies results before HOLD, preserves caller PCR and performs bounded 8KiB reads across the upper half; absent SRAM fails safely')
    m=Memory();raw_request(m,tx=bytes((0x55,0xAA))*32);assert call(m)[0]==0
    high=[];low=[]
    for (t,level),(next_t,next_level) in zip(m.frames[-1]['edges'],m.frames[-1]['edges'][1:]):
        if level!=next_level:(high if level else low).append(next_t-t)
    timing=dict(min_high_cycles=min(high),min_low_cycles=min(low),cpu_mhz_example=8,physical_scope_measured=False)
    assert min(high)>=20 and min(low)>=20,timing
    report=dict(passed=True,checks=checks,sha256=META['sha256'],provider_sha256=META['provider_sha256'],client_sha256=META['client']['sha256'],max_stack_bytes=max_stack,timing=timing,hardware_tested=False)
    (OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('STACK',max_stack,'bytes including caller return, without asynchronous NMI handler',flush=True)

if __name__=='__main__':main()
