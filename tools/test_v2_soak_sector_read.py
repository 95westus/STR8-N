"""Exercise the linked sector reader across every bank/sector and invalid input."""
import hashlib,json
from pathlib import Path
from test_v2_rtc import MPU

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/beta23-soak-probes'
BITS=(0xCC,0xCE,0xEC,0xEE)

class Memory:
    def __init__(self,body,pcr):
        self.ram=bytearray(65536);self.ram[0x4000:0x4000+len(body)]=body
        self.ram[0x7FEC]=pcr;self.writes=[];self.reads=[]
        self.banks=[bytes(((i*13)^(i>>8)^(b*71))&255 for i in range(32768)) for b in range(4)]
    def __getitem__(self,a):
        if a>=0x8000:
            b=BITS.index(self.ram[0x7FEC]&0xEE);self.reads.append((b,a))
            return self.banks[b][a-0x8000]
        return self.ram[a]
    def __setitem__(self,a,v):
        assert a<0x8000,'Flash write attempted'
        assert a==0x7FEC or 0x100<=a<0x200 or 0x2000<=a<0x3000 or 0x3002<=a<=0x3005 or 0x4000<=a<0x4100,hex(a)
        self.writes.append(a);self.ram[a]=v

def main():
    meta=json.loads((OUT/'build.json').read_text())['sector-read']
    body=(OUT/'sector-read/sector-read.bin').read_bytes()
    assert hashlib.sha256(body).hexdigest()==meta['sha256']
    cases=0
    for initial in (0xCC,0xDF,0xEC,0xFF):
        for bank in range(4):
            for page in range(0x80,0x100,0x10):
                m=Memory(body,initial);m.ram[0x3000:0x3004]=bytes((bank,page,255,255))
                cpu=MPU(memory=m,pc=0x4000);cpu.p=0x28;flags=cpu.p;sp=cpu.sp
                for _ in range(50000):
                    if cpu.pc==0x7E67:break
                    cpu.step()
                else:raise AssertionError('Sector reader timeout')
                assert m.ram[0x2000:0x3000]==m.banks[bank][(page-0x80)*256:(page-0x70)*256]
                assert m.ram[0x3002:0x3004]==b'\0\x10' and m.ram[0x7FEC]==initial
                assert m.ram[0x3004:0x3006]==bytes((initial,initial))
                assert cpu.sp==sp and cpu.p&~cpu.BREAK==flags&~cpu.BREAK
                assert m.reads==[(bank,a) for a in range(page*256,page*256+4096)]
                cases+=1
    for bank,page in ((4,0x80),(255,0x80),(0,0x70),(3,0x81),(2,0xFF)):
        m=Memory(body,0xFF);m.ram[0x3000:0x3004]=bytes((bank,page,255,255));cpu=MPU(memory=m,pc=0x4000)
        for _ in range(100):
            if cpu.pc==0x7E67:break
            cpu.step()
        assert cpu.pc==0x7E67 and m.ram[0x3002:0x3004]==b'\x09\0'
        assert not m.reads and 0x7FEC not in m.writes
    report=dict(passed=True,sha256=meta['sha256'],valid_cases=cases,invalid_cases=5,checks=['all banks and sectors byte-exact','complete PCR, flags and stack restored','no flash/peripheral writes except bank selection','invalid inputs refuse before bank access'])
    (OUT/'sector-read-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS sector reader:',cases,'valid cases, 5 refusals')

if __name__=='__main__':main()
