"""Bit-level VIA/23LCV1024 model adapted from the earlier SPI prototype tests.

Independent peripheral model, no runtime/device/old-build imports. Unlike a
presence probe this model deliberately permits a stuck-low READ to look valid.
"""
class SRAM:
    def __init__(self,mode=0x40):
        self.data=bytearray((i*37+(i>>8)*11)&255 for i in range(131072));self.mode=mode
        self.writes=[];self.mode_writes=[]
    def start(self):self.command=None;self.address=0;self.addr_left=0
    def advance(self):
        if self.mode==0x40:self.address=(self.address+1)&0x1ffff
        elif self.mode==0x80:self.address=(self.address&~31)|((self.address+1)&31)
    def receive(self,value):
        if self.command is None:self.command=value;self.addr_left=3 if value in (2,3) else 0
        elif self.addr_left:self.address=(self.address<<8|value)&0x1ffff;self.addr_left-=1
        elif self.command==1:self.mode_writes.append(value);self.mode=value
        elif self.command==2:self.writes.append((self.address,value));self.data[self.address]=value;self.advance()
        elif self.command==3:self.advance()
    def output(self):
        if self.command==5:return self.mode
        if self.command==3 and not self.addr_left:return self.data[self.address]
        return 255


class VIA:
    def __init__(self,mode=0x40,present=True,stuck=None):
        self.ddr=0;self.latch=255;self.pcr=0;self.acr=0;self.ifr=0;self.ier=0x80;self.clear_flags=True
        self.chip=SRAM(mode) if present else None;self.stuck=stuck
        self.selected=None;self.bit=self.value=0;self.miso=1;self.outbyte=255
        self.frames=[];self.writes=[];self.reads=[];self.port_reads=0
    def levels(self):return (~self.ddr|self.latch)&15
    def read(self,a):
        self.reads.append(a)
        if a==0x7fc2:return self.ddr
        if a==0x7fcc:return self.pcr
        if a==0x7fcb:return self.acr
        if a==0x7fcd:return self.ifr
        if a==0x7fce:return self.ier
        assert a==0x7fc0,f'Unexpected VIA read {a:04X}'
        self.port_reads+=1
        if self.clear_flags:self.ifr&=~0x18
        value=(self.latch&self.ddr)|(255&~self.ddr)
        bit=self.miso if self.stuck is None else int(self.stuck=='high')
        return value&~32|(32 if bit else 0)
    def write(self,a,v):
        assert a in (0x7fc0,0x7fc2),f'Unexpected VIA write {a:04X}'
        before=self.levels();self.writes.append((a,v))
        if a==0x7fc0:self.latch=v
        else:self.ddr=v
        after=self.levels()
        for dev,mask in ((0,4),(1,8)):
            if before&mask and not after&mask:
                assert self.selected is None,'Two selected peripherals'
                self.selected=dev;self.frames.append(dict(device=dev,tx=[],clocks=0,edges=[]))
                self.bit=self.value=0;self.outbyte=255;self.miso=1
                if dev==0 and self.chip:self.chip.start()
            if not before&mask and after&mask:self.selected=None;self.miso=1
        if self.selected is not None:
            if (before^after)&1:self.frames[-1]['edges'].append((self.cpu.processorCycles,bool(after&1)))
            if not before&1 and after&1:
                self.frames[-1]['clocks']+=1;self.value=self.value<<1|((after>>1)&1);self.bit+=1
                if self.bit==8:
                    self.frames[-1]['tx'].append(self.value)
                    if self.selected==0 and self.chip:self.chip.receive(self.value)
            elif before&1 and not after&1:
                if self.bit==8:
                    self.bit=self.value=0
                    self.outbyte=self.chip.output() if self.selected==0 and self.chip else 255
                self.miso=(self.outbyte>>(7-self.bit))&1


def attach(h,**options):
    via=VIA(**options);via.cpu=h.c
    class MemoryWithVIA(type(h.m)):
        def __getitem__(self,a):
            if isinstance(a,int) and 0x7fc0<=a<=0x7fcf:return via.read(a)
            return super().__getitem__(a)
        def __setitem__(self,a,v):
            if isinstance(a,int) and 0x7fc0<=a<=0x7fcf:return via.write(a,v)
            return super().__setitem__(a,v)
    h.m.__class__=MemoryWithVIA;h.via=via;return via
