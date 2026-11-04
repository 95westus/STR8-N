"""Bank/FT245/AMD behavior inherited from the qualified recovery model."""
from collections import deque

class Memory:
    def __init__(self, banks=None, usb=True):
        self.ram = bytearray(b'\x5a'*0x8000)
        self.banks = [bytearray(b'\xff'*0x8000) for _ in range(4)]
        assert banks is not None, 'Explicit model bank fixture required'
        self.banks = [bytearray(b) for b in banks]
        self.bank = 3
        self.ram[0x7fec] = 0
        self.ram[0x7fe0] = 0x0c
        self.ram[0x7fe3] = 0
        self.rx,self.tx = deque(),bytearray()
        self.usb = usb
        self.cpu = None
        self.unlock = 0
        self.busy = None
        self.events = []
        self.cut_after = None
        self.fault = None
        self.programmed = set()

    def __getitem__(self,a):
        if isinstance(a,slice): return [self[x] for x in range(*a.indices(65536))]
        if a>=0x8000:
            if self.busy:
                assert self.cpu.pc<0x8000, f'ROM fetch while flash busy: {self.cpu.pc:04X}'
                bank,target,value,ticks = self.busy
                assert self.bank==bank
                if ticks:
                    if self.fault!='timeout': self.busy=bank,target,value,ticks-1
                    return value^0x80
                self.busy=None
            return self.banks[self.bank][a-0x8000]
        if a==0x7fe0:
            return (self.ram[a]&~0x23)|(0 if self.rx else 2)|(0 if self.usb else 0x20)
        if a==0x7fe1 and not self.ram[0x7fe3]: return self.rx[0] if self.rx else 0
        return self.ram[a]

    def __setitem__(self,a,v):
        v &= 255
        if a<0x8000:
            old=self.ram[a]; self.ram[a]=v
            if a==0x7fec:
                assert v&0xee in (0xcc,0xce,0xec,0xee), f'Invalid flash-bank PCR mode: {v:02X}'
                self.bank=(0 if v&0x0e==0x0c else 1)|(0 if v&0xe0==0xc0 else 2)
            elif a==0x7fe0 and not old&8 and v&8 and self.rx: self.rx.popleft()
            elif a==0x7fe3 and v==255 and self.ram[0x7fe0]&4: self.tx.append(self.ram[0x7fe1])
            return
        assert self.cpu.pc<0x8000, f'Flash mutation from ROM {self.cpu.pc:04X}'
        if self.unlock==3:
            key=(self.bank,a)
            assert key not in self.programmed, f'Byte reprogrammed before erase: {key}'
            assert self.banks[self.bank][a-0x8000]==255, f'Programming non-erased byte: {key}'
            self.programmed.add(key)
            self.banks[self.bank][a-0x8000]=v
            self.busy=(self.bank,a,v,2)
            self.unlock=0
            self.mutated('program',a,v)
        elif a==0xd555 and v==0xf0:
            self.unlock=0; self.busy=None
        elif self.unlock in (0,4) and a==0xd555 and v==0xaa: self.unlock+=1
        elif self.unlock in (1,5) and a==0xaaaa and v==0x55: self.unlock+=1
        elif self.unlock==2 and a==0xd555 and v in (0xa0,0x80): self.unlock=3 if v==0xa0 else 4
        elif self.unlock==6 and v==0x30:
            base=a&0xf000
            self.banks[self.bank][base-0x8000:base-0x8000+4096]=b'\xff'*4096
            self.programmed={k for k in self.programmed if k[0]!=self.bank or k[1]&0xf000!=base}
            if self.fault=='erase_verify': self.banks[self.bank][base-0x8000+17]=0
            self.busy=(self.bank,a,255,2)
            self.unlock=0
            self.mutated('erase',base,255)
        else: raise AssertionError(f'Bad flash command {self.unlock}: {a:04X}={v:02X}')

    def mutated(self,kind,address,value):
        raise NotImplementedError('Installer model supplies erase-accounting checks')
