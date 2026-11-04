"""Standalone CPU/NOR tests with synthetic banks; never imports a port adapter."""
import argparse,binascii,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests/vendor'),str(ROOT/'tools')]
from py65.devices.mpu65c02 import MPU as CPU02
from py65816.devices.mpu65c816 import MPU as CPU816
from flash_model import Memory as NOR
from oip import crc,header

REC=b'REC> '
CFG=b'RAM CONFIG ? B C I W Q> '
OI=b'INSTALLER I Q> '


def snapshot(target='S',mask=0,seq=7):
    row=bytearray(b'\xff'*256);row[:8]=b'SNBT\x01\x20\0'+target.encode();row[8:12]=seq.to_bytes(4,'little')
    row[12:18]=bytes((30,mask,8,8,8,8));row[18:22]=(0x8000000f).to_bytes(4,'little');row[22:30]=bytes(8)
    config=bytearray((1,0,1,7,0xf0,30,0,ord('P'),0xa0,15,0,0,0x80,0xa5,0,0));a=b=0
    for v in config[:14]:a=(a+v)&255;b=(b+a)&255
    config[14:]=bytes((a,b));row[32:48]=config
    for n in range(32):row[64+3*n:67+3*n]=(100+n).to_bytes(3,'little')
    row[160:164]=b'\xff'*4;row[30:32]=crc(row[:30]).to_bytes(2,'little');row[252:254]=crc(row[:252]).to_bytes(2,'little');row[255]=0
    return bytes(row)


def latest(banks):
    rows=[]
    for off in range(0x4000,0x6000,256):
        r=bytes(banks[3][off:off+256])
        if r[:6]==b'SNBT\x01\x20' and r[255]==0 and crc(r[:30])==int.from_bytes(r[30:32],'little') and crc(r[:252])==int.from_bytes(r[252:254],'little'):rows.append(r)
    return max(rows,key=lambda r:int.from_bytes(r[8:12],'little')) if rows else None


class Memory(NOR):
    def __init__(self,banks):super().__init__(banks);self.acia_tx=bytearray();self.attempts={}
    def __getitem__(self,a):
        if a in (0x7f80,0x7f81):return 0
        return super().__getitem__(a)
    def __setitem__(self,a,v):
        if a==0x7f80:self.acia_tx.append(v&255)
        super().__setitem__(a,v)
    def mutated(self,kind,address,value):
        assert self.cpu.pc<0x8000
        assert self.bank==3 and 0xc000<=address<0xe000 or self.bank<3 and address&0xf000==0x9000
        if kind=='erase' and self.bank<3:
            r=latest(self.banks);index=self.bank*8+1
            self.attempts[index]=self.attempts.get(index,0)+1
            assert int.from_bytes(r[64+3*index:67+3*index],'little')==100+index+self.attempts[index]
        self.events.append((kind,self.bank,address,value))


class Machine:
    def __init__(self,build,cpu,target='S',mask=0,journal=True):
        self.build=build;self.sy=json.loads((build/'symbols.json').read_text());self.b=self.sy['boot'];self.w=self.sy['worker'];self.cpu=cpu
        banks=[bytearray(b'\xff'*32768) for _ in range(4)]
        for bank in banks:bank[:3]=b'\x4c\x00\x80'
        banks[3][-4096:]=(build/'payload/STR8N-F-BOOT-4096.bin').read_bytes()
        if journal:banks[3][0x4000:0x4100]=snapshot(target,mask)
        self.m=Memory(banks);self.c=(CPU02 if cpu=='65c02' else CPU816)(memory=self.m,pc=0xf004);self.m.cpu=self.c
        self.c.p=0x34;self.c.sp=255
        if cpu!='65c02':self.c.mode=1;self.c.dpr=self.c.dbr=self.c.pbr=0
    def run(self,stop,limit=4000000):
        c,m=self.c,self.m
        for _ in range(limit):
            if stop():return
            if c.pc==self.b['BOOT_DRAIN_BEGIN'] and not m.rx:
                c.a=c.x=c.y=0;c.p=(c.p&~0xc2)|2|(m[0x7fe0]&0x40);m.ram[self.b['BR_TICKS']]=0;c.pc=self.b['BOOT_DRAIN_DONE'];continue
            if c.pc==self.w['V2W_BOOT_DELAY_OUTER']:c.pc=self.w['V2W_BOOT_DELAY_DONE'];continue
            if c.pc==self.w['V2W_ACIA_DELAY_OUTER']:
                c.a=0;c.p=(c.p&~0x82)|2;c.pc=self.w['V2W_ACIA_SEND']+14;continue
            if c.pc==self.b['J_CRC_BYTE'] and m.bank==3:
                addr=self.b['J_CRC'];hi=(m.ram[addr+1]^c.a);lo=m.ram[addr];a=hi;carry=0
                for bit in range(8):
                    carry=hi>>7;hi=((hi<<1)|(lo>>7))&255;lo=(lo<<1)&255
                    if carry:lo^=0x21;hi^=0x10;a=hi
                m.ram[addr:addr+2]=bytes((lo,hi));c.a=a;c.x=0;c.p=(c.p&~0x83)|2|carry;c.pc=(c.stPopWord()+1)&65535;continue
            op=m[c.pc]
            if self.cpu=='65c02' and op&15==15:
                pc=c.pc;bit=bool(m[m[pc+1]]&(1<<((op>>4)&7)));take=bit if op&128 else not bit;d=m[pc+2];c.pc=(pc+3+((d if d<128 else d-256) if take else 0))&65535
            else:c.step()
        raise AssertionError(('timeout',self.cpu,hex(c.pc),bytes(m.tx[-160:])))
    def recovery(self):self.run(lambda:bytes(self.m.tx).endswith(REC))
    def command(self,body,prompt):
        n=len(self.m.tx);self.m.rx.extend(body);self.run(lambda:len(self.m.tx)>n and bytes(self.m.tx).endswith(prompt));return bytes(self.m.tx[n:])
    def load(self,name,prompt):
        image=(self.build/'payload'/name).read_bytes();self.m.ram[0x200:0x200+len(image)]=image
        self.c.pc=0x200;self.c.sp=255;n=len(self.m.tx);self.run(lambda:len(self.m.tx)>n and bytes(self.m.tx).endswith(prompt))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build,out=args.build.resolve(),args.out.resolve();assert not out.exists();out.mkdir(parents=True);cases=[]
    def passed(cpu,name):cases.append(dict(passed=True,cpu=cpu,case=name));print('PASS',cpu,name,flush=True)
    for cpu in ('65c02','65c816-e'):
        for bank in range(4):
            h=Machine(build,cpu,str(bank),15);h.run(lambda:h.c.pc==0x8000);assert h.m.bank==bank and not h.m.events;passed(cpu,f'saved-default-boots-B{bank}')
            h=Machine(build,cpu,mask=15);h.recovery();h.command(b'C1\r',REC);h.m.rx.extend(str(bank).encode()+b'\r');h.run(lambda:h.c.pc==0x8000)
            assert h.m.bank==bank and not h.m.events;passed(cpu,f'manual-selection-boots-B{bank}')
        h=Machine(build,cpu,journal=False);h.recovery();h.command(b'C1\r',REC);h.command(b'L\r',b'SEND BIN\r\n')
        assert h.command(b'\x03',REC).endswith(REC) and not h.m.events;passed(cpu,'F-only-no-journal-no-MON-recovery-and-Ctrl-C')
        h=Machine(build,cpu);h.recovery();h.command(b'C1\r',REC);h.load('STR8N-F-CONFIG-RAM.bin',CFG);old=latest(h.m.banks)
        assert b'OK' in h.command(b'B 1 9000\r',CFG);assert b'OK' in h.command(b'C 1\r',CFG)
        r=latest(h.m.banks);assert r[7]==ord('1') and r[13]==2 and r[14:18]==bytes((8,9,8,8)) and r[64:252]==old[64:252]
        assert all(event[0]!='erase' for event in h.m.events);passed(cpu,'CONFIG-enable-entry-default-without-erase-or-wear-reset')
        h=Machine(build,cpu);h.recovery();h.command(b'C1\r',REC);h.load('STR8N-F-OPAQUE-RAM.bin',OI);body=bytes(range(256))*16;before=list(map(bytes,h.m.banks))
        h.command(b'I\r',b'SEND OIP1 HEADER\r\n');h.command(header(0,0x90,body,crc(b'\xff'*4096)),b'SEND 4096\r\n')
        assert b'OK: verified sector' in h.command(body,OI);assert bytes(h.m.banks[0][0x1000:0x2000])==body
        count=len(h.m.events);h.command(b'I\r',b'SEND OIP1 HEADER\r\n');h.command(header(0,0x90,body,crc(body)),b'SEND 4096\r\n')
        assert b'OK: identical; no erase' in h.command(body,OI) and len(h.m.events)==count
        h.command(b'I\r',b'SEND OIP1 HEADER\r\n');raw=h.command(header(0,0x90),OI)
        assert raw==b'READ SECTOR+CRC\r\n'+body+crc(body).to_bytes(2,'little')+b'\r\nOK: read\r\n'+OI
        restore=b'\xff'*4096;h.command(b'I\r',b'SEND OIP1 HEADER\r\n');h.command(header(0,0x90,restore,crc(body)),b'SEND 4096\r\n');h.command(restore,OI)
        assert bytes(h.m.banks[0])==before[0] and list(map(bytes,h.m.banks[1:3]))==before[1:3]
        assert bytes(h.m.banks[3][:0x4000])==before[3][:0x4000] and bytes(h.m.banks[3][0x6000:])==before[3][0x6000:]
        assert int.from_bytes(latest(h.m.banks)[67:70],'little')==103
        passed(cpu,'opaque-install-read-noop-restore-durable-wear-and-unrelated-banks')
        (out/(cpu+'-console.bin')).write_bytes(bytes(h.m.tx))
        for sector in (0xa0,0xb0,0xc0,0xd0,0xf0):
            try:header(3,sector)
            except ValueError:pass
            else:raise AssertionError('Host accepted a protected sector')
        passed(cpu,'host-protected-B3-AB-CD-F-targets-refused')
        h=Machine(build,cpu);h.recovery();h.command(b'C1\r',REC);h.load('STR8N-F-OPAQUE-RAM.bin',OI)
        before=list(map(bytes,h.m.banks));bad=bytearray(header(0,0x90));bad[6:8]=bytes((3,0xc0));bad[-2:]=crc(bad[:-2]).to_bytes(2,'little')
        h.command(b'I\r',b'SEND OIP1 HEADER\r\n');reply=h.command(bad,b'LOCKED: RESET required\r\n')
        assert b'REFUSED' in reply and not h.m.events and list(map(bytes,h.m.banks))==before
        passed(cpu,'device-protected-journal-header-refuses-before-mutation')
    (out/'qualification.json').write_text(json.dumps(dict(passed=True,checks=len(cases),hardware=False,serial_access=False,
        cases=cases,limits=['Synthetic banks/counters only','USB model; polling/delay and CRC shortcuts; no new timing/physical claim','No new stable-release acceptance claim']),indent=2)+'\n',encoding='utf-8')
    print('PASS',len(cases),'standalone CPU/NOR groups; no hardware',flush=True)


if __name__=='__main__':main()
