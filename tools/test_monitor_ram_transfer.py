"""Check RAM transfer limits, rejected commands and readback failure handling."""
from beta4_migration import Link

class Fixture:
    write_ram=Link.write_ram
    def __init__(self,fail=None,mismatch=False):
        self.commands=[];self.ram=bytearray(32768);self.fail=fail;self.mismatch=mismatch
    def command(self,text,prompt):
        self.commands.append(text)
        if len(self.commands)==self.fail:return b'Long line\r\nB3> '
        assert len(text)<=40
        fields=text.split();address=int(fields[1],16);data=bytes(int(v,16) for v in fields[2:])
        self.ram[address:address+len(data)]=data
        return b'\r\nB3> '
    def dump(self,first,last,prompt):
        body=bytes(self.ram[first:last+1])
        return bytes([body[0]^1])+body[1:] if self.mismatch else body

def main():
    for size in (0,1,8,16,17,64):
        f=Fixture();data=bytes(range(size));f.write_ram(0x2400,data)
        assert bytes(f.ram[0x2400:0x2400+size])==data
        assert all(len(line)<=30 for line in f.commands)
    for kwargs in ({'fail':1},{'fail':2},{'mismatch':True}):
        f=Fixture(**kwargs)
        try:f.write_ram(0x2400,bytes(range(24)))
        except IOError:pass
        else:raise AssertionError('failed transfer accepted')
        if f.fail:assert len(f.commands)==f.fail,'continued after command rejection'
    for address,data in ((0x7FFF,b'xx'),(0x8000,b'x'),(-1,b'x')):
        f=Fixture()
        try:f.write_ram(address,data)
        except ValueError:pass
        else:raise AssertionError('non-RAM staging accepted')
        assert not f.commands
    print('PASS short transfers, tail chunks, immediate refusal, readback mismatch and non-RAM boundaries')

if __name__=='__main__':main()
