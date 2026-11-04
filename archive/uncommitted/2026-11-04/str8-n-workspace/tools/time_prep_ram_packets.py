"""Bounded CPU-RAM fault fixtures and exact relocated live candidates."""
import json,re,binascii
from pathlib import Path
import install_2512_native_utilities as d
t=d.t;ROOT=t.ROOT

class Code:
    def __init__(self,base):self.base=base;self.b=bytearray();self.labels={};self.fix=[]
    def emit(self,*b):self.b.extend(b)
    def imm(self,op,n):self.emit(op,n)
    def absolute(self,op,a):self.emit(op,a&255,a>>8)
    def label(self,n):self.labels[n]=self.base+len(self.b)
    def branch(self,op,n):self.emit(op,0);self.fix.append((len(self.b)-1,n))
    def done(self):
        for i,n in self.fix:
            v=self.labels[n]-(self.base+i+1);assert -128<=v<=127;(self.b)[i]=v&255
        return bytes(self.b)

def symbols(p):return {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',Path(p).read_text(),re.M)}
def artifact(folder,name):
    p=ROOT/folder;mf=json.loads((p/'manifest.json').read_text());a=(p/name).read_bytes();assert t.sha(a)==mf['artifacts'][name]['sha256'];return a

def core(which):
    folder=ROOT/('BUILD/mon-gF-time-r1' if which=='new' else 'BUILD/mon-gE-settings-r1')
    mf=json.loads((folder/'manifest.json').read_text());n=next(n for n,v in mf['artifacts'].items() if v['variant']=='RAM');b=(folder/n).read_bytes();assert t.sha(b)==mf['artifacts'][n]['sha256'];return b,symbols(folder/'RAM/mona.map')

def direct_packet(body,origin,stub):
    a=bytearray(b'\xff'*0x5A00);a[origin-0x200:origin-0x200+len(body)]=body
    a[:3]=bytes.fromhex('4C 00 1F');a[0x1D00:0x1D00+len(stub)]=stub
    return a

def time_packet(which,frames):
    body,sy=core(which);body=bytearray(body)
    # Same linked MR_SAMPLE/decoder; only READ transport and fixture pin loads
    # differ. The physical live trial uses the completely unpatched candidate.
    for old,new in ((0x7FCF,0x51F0),(0x7FC3,0x51F1),(0x7FCB,0x51F2)):
        for op in (0xAD,0x8D):body=body.replace(bytes((op,old&255,old>>8)),bytes((op,new&255,new>>8)))
    needle=bytes((0x20,sy['MR_READ']&255,sy['MR_READ']>>8));assert body.count(needle)==2;body=body.replace(needle,bytes.fromhex('20 00 18'))
    c=Code(0x1800);c.absolute(0xAD,0x6A93);c.imm(0xC9,9);c.branch(0xD0,'second');c.absolute(0xEE,0x5080)
    c.imm(0xA0,10);c.emit(0xB1,0xE6);c.branch(0xD0,'error');c.imm(0xA0,0);c.label('copy');c.emit(0xB1,0xE6);c.absolute(0x99,0x6AB0);c.emit(0xC8);c.imm(0xC0,9);c.branch(0xD0,'copy');c.branch(0x80,'good')
    c.label('second');c.imm(0xA0,9);c.emit(0xB1,0xE6);c.absolute(0x8D,0x6AB0);c.imm(0xA0,11);c.emit(0xB1,0xE6);c.branch(0xD0,'error')
    c.absolute(0xAD,0x5080);c.imm(0xC9,3);c.branch(0xB0,'good');c.emit(0x18,0xA5,0xE6,0x69,16,0x85,0xE6)
    c.label('good');c.emit(0xA9,0,0x38,0x60);c.label('error');c.emit(0x18,0x60);read=c.done();assert len(read)<128
    c=Code(0x1F00);c.emit(0x78,0xD8,0xA2,0xFF,0x9A,0xA9,0,0x85,0xE6,0xA9,0x50,0x85,0xE7);c.absolute(0x20,sy['MR_SAMPLE']);c.absolute(0x8D,0x1A00);c.emit(0x08,0x68);c.absolute(0x8D,0x1A01)
    c.absolute(0xAD,0x5080);c.absolute(0x8D,0x1A02);c.imm(0xA2,0);c.label('result');c.absolute(0xBD,0x6A90);c.absolute(0x9D,0x1A10);c.emit(0xE8);c.imm(0xE0,0x30);c.branch(0x90,'result');c.absolute(0x4C,0x7E67)
    a=direct_packet(body,0x200,c.done());a[0x1600:0x1600+len(read)]=read
    assert len(frames)<=3
    for n,frame in enumerate(frames):assert len(frame)==12;a[0x4E00+n*16:0x4E00+n*16+12]=frame
    a[0x4E80]=0;a[0x4FF0:0x4FF3]=bytes((0x81,0,0));return bytes(a)

def details(which):
    if which=='new':return artifact('BUILD/status-autoprep-r1','STATUS-RAM.bin'),json.loads((ROOT/'BUILD/status-autoprep-r1/RAM/symbols.json').read_text())
    return artifact('BUILD/status-g1-RAM-r1','STATUS-3400.bin'),symbols(ROOT/'BUILD/status-g1-RAM-r1/status-details/status-details.map')

def sram_packet(which,*,fixture=None):
    body,sy=details(which);body=bytearray(body)
    if fixture is not None:
        for offset in (0,2,0xB,0xC,0xD,0xE):
            for op in (0xAD,0x8D):body=body.replace(bytes((op,offset+0xC0,0x7F)),bytes((op,offset,0x5A)))
        first=body.index(bytes.fromhex('AD 00 5A'),sy['MS_SRAM_READ']-0x3400);body[first:first+3]=bytes.fromhex('20 00 18')
        at=body.index(bytes((0xA9,5,0x20,sy['MS_SPI_COMMAND']&255,sy['MS_SPI_COMMAND']>>8)),first)
        body[at:at+5]=bytes.fromhex('4C 30 18 EA EA')
    c=Code(0x1F00);c.emit(0x78,0xD8,0xA2,0xFF,0x9A)
    if fixture is None:
        for n,address in enumerate((0x7FC2,0x7FCB,0x7FCC,0x7FCE,0x7FCD)):c.absolute(0xAD,address);c.absolute(0x8D,0x1A80+n)
    c.absolute(0x20,sy['MS_SRAM_READ']);c.emit(0x08,0x68);c.absolute(0x8D,0x1A00)
    if fixture is None:
        c.imm(0xA2,0);c.label('primary');c.absolute(0xBD,0x6A40);c.absolute(0x9D,0x1A10);c.emit(0xE8);c.imm(0xE0,64);c.branch(0x90,'primary')
        for n,address in enumerate((0x7FC2,0x7FCB,0x7FCC,0x7FCE,0x7FCD)):c.absolute(0xAD,address);c.absolute(0x8D,0x1A90+n)
    else:
        for n,address in enumerate((0x5A10,0x5A12)):c.absolute(0xAD,address);c.absolute(0x8D,0x1A01+n)
        c.imm(0xA2,0);c.label('regs');c.absolute(0xBD,0x5A00);c.absolute(0x9D,0x1A10);c.emit(0xE8);c.imm(0xE0,16);c.branch(0x90,'regs')
    c.absolute(0x4C,0x7E67);a=direct_packet(body,0x3400,c.done())
    if fixture is not None:
        regs=bytearray(32);regs[0]=0xA5;regs[0xD]=0x18;regs[0x11]=1
        for offset,value in fixture.items():regs[offset]=value
        a[0x5800:0x5820]=regs
        c=Code(0x1800);c.absolute(0xEE,0x5A10);c.absolute(0xAD,0x5A11);c.branch(0xF0,'uncleared');c.absolute(0xAD,0x5A0D);c.imm(0x29,0xE7);c.absolute(0x8D,0x5A0D);c.label('uncleared');c.absolute(0xAD,0x5A00);c.emit(0x60);reader=c.done();assert len(reader)<=0x30
        a[0x1600:0x1600+len(reader)]=reader;c=Code(0x1830);c.emit(0xA9,1);c.absolute(0x8D,0x5A12);c.emit(0x38);c.absolute(0x4C,sy['MS_SRAM_RESTORE']);a[0x1630:0x1630+len(c.done())]=c.done()
    return bytes(a)

def live_packet():
    body,sy=core('new');body=bytearray(body)
    old=bytes.fromhex('64 E2 A9 AC 85 E3');assert body.count(old)==1;body=body.replace(old,bytes.fromhex('64 E2 A9 30 85 E3'))
    gate=sy['MS_GATE']-0x200;assert body[gate:gate+20]==bytes.fromhex('DA8D007D2048782008ACA8688D007D2048789860');body[gate+9]=0x30
    at=sy['MS_EXTENTS']-0x200;body[at:at+16]=bytes.fromhex('00 20 C0 00 C0 20 C0 00 00 30 00 04 00 34 AA 05')
    a=bytearray(b'\xff'*(0x39AA-0x200));a[:len(body)]=body
    for name,address in [('STATUS-text-2000.bin',0x2000),('STATUS-text-20C0.bin',0x20C0),('STATUS-3000.bin',0x3000)]:
        b=artifact('BUILD/status-g1-RAM-r1',name);assert a[address-0x200:address-0x200+len(b)]==b'\xff'*len(b);a[address-0x200:address-0x200+len(b)]=b
    b=artifact('BUILD/status-autoprep-r1','STATUS-RAM.bin');a[0x3200:0x3200+len(b)]=b
    assert len(a)==14250;return bytes(a)
