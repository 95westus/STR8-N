"""CPU-RAM-only transport fixtures; no emulator or board I/O."""
import binascii,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'release/str8nf-v0.2.0/tools'))
from build_bank_features import compact


class Code:
    def __init__(self):self.a=bytearray();self.labels={};self.fix=[]
    def emit(self,*a):self.a.extend(a)
    def label(self,n):self.labels[n]=len(self.a)
    def branch(self,op,n):self.emit(op,0);self.fix.append((len(self.a)-1,n))
    def finish(self):
        for at,n in self.fix:
            delta=self.labels[n]-at-1;assert -128<=delta<=127;self.a[at]=delta&255
        return bytes(self.a)


def byte_writer(fail_after=None):
    c=Code()
    if fail_after is not None:c.emit(0xAD,0xFF,0x18,0xC9,fail_after);c.branch(0xB0,'bad')
    c.emit(0xA5,0xE5,0xC9,0x50);c.branch(0x90,'bad');c.emit(0xC9,0x54);c.branch(0xB0,'bad')
    c.emit(0xA5,0xF0,0x92,0xE4,0xD2,0xE4);c.branch(0xD0,'bad')
    c.emit(0xEE,0xFF,0x18,0x38,0x60);c.label('bad');c.emit(0x18,0x60)
    return c.finish()


def flash_reader():
    # Expose only synthetic B0:9000-903F at CPU1800-183F; all else reads FF.
    c=Code();c.emit(0xA0,0);c.label('loop');c.emit(0xA9,0xFF,0xA6,0xF3);c.branch(0xD0,'store')
    c.emit(0xA6,0xE3,0xE0,0x90);c.branch(0xD0,'store')
    c.emit(0x98,0x18,0x65,0xE2);c.branch(0xB0,'ff');c.emit(0xC9,0x40);c.branch(0xB0,'ff')
    c.emit(0xAA,0xBD,0,0x18);c.branch(0x80,'store');c.label('ff');c.emit(0xA9,0xFF)
    c.label('store');c.emit(0x99,0x80,0x7C,0xC8,0xC4,0xEA);c.branch(0x90,'loop');c.emit(0x60)
    return c.finish()


def packet(body,kernel,*,storage=False,metadata=None,source=None,fail_after=None):
    data=compact(body);first=0x1A00;rest=data[first:]
    assert len(kernel)<=0x130 and len(rest)<=0xD00 and len(body)<0x3800
    a=bytearray(b'\xff'*0x6300)
    a[:3]=bytes.fromhex('4C 00 1F')
    a[0x100:0x100+len(kernel)]=kernel
    a[0x300:0x300+min(first,len(data))]=data[:first]
    a[0x5600:0x5600+len(rest)]=rest
    bw=byte_writer(fail_after);assert len(bw)<=64;a[0x2A0:0x2A0+len(bw)]=bw
    fr=flash_reader();assert len(fr)<0xD0;a[0x230:0x230+len(fr)]=fr
    if metadata is not None:
        assert not storage and len(metadata)==1024;a[0x4E00:0x5200]=metadata;a[0x5200:0x5204]=b'PJ\x06\x01'
    if source is not None:
        assert len(source)==64;a[0x5280:0x52C0]=source
    c=Code();c.emit(0x78,0xD8,0xA2,0xFF,0x9A,0xA2,0);c.label('kernel')
    c.emit(0xBD,0,3,0x9D,0,0x68,0xBD,0,4,0x9D,0,0x69,0xE8);c.branch(0xD0,'kernel')
    c.emit(0xA2,0);c.label('savezp');c.emit(0xBD,0,0,0x9D,0,2,0xE8,0xE0,0xE0);c.branch(0x90,'savezp')
    c.emit(0xA2,0);c.label('savemon');c.emit(0xBD,0,0x6A,0x9D,0,3,0xE8);c.branch(0xD0,'savemon')
    def store(address,value):c.emit(0xA9,value,0x8D,address&255,address>>8)
    limit=0x2000+len(body);end=0x5800+len(rest);crc=binascii.crc_hqx(body,65535)
    for addr,v in ((0xE0,0),(0xE1,5),(0xE2,0),(0xE3,0x20),(0x670B,0),(0x670C,0x20),
                   (0x6708,3),(0x6709,limit&255),(0x670A,limit>>8),(0x670F,end&255),(0x6710,end>>8),
                   (0x670D,crc&255),(0x670E,crc>>8)):
        store(addr,v)
    c.emit(0x20,0,0x68,0xA2,0);c.label('context')
    c.emit(0xBD,0,2,0x9D,0,0x5C if storage else 0x64,0xBD,0,3,0x9D,0,0x5D if storage else 0x65,0xE8);c.branch(0xD0,'context')
    c.emit(0xA2,len(bw)-1);c.label('bw');c.emit(0xBD,0xA0,4,0x9D,0,0x19,0xCA);c.branch(0x10,'bw')
    c.emit(0x9C,0xFF,0x18,0xA2,len(fr)-1);c.label('fr');c.emit(0xBD,0x30,4,0x9D,0,0x1A,0xCA);c.branch(0x10,'fr')
    c.emit(0xA2,63);c.label('source');c.emit(0xBD,0x80,0x54,0x9D,0,0x18,0xCA);c.branch(0x10,'source')
    store(0x7D30,0xB0)
    c.emit(0x9C,0xF9,0x7D,0x9C,2,0x5B,0x9C,0x70,0x67,0x4C,0,0x20)
    prefix=c.finish();assert len(prefix)<=256,len(prefix)
    a[0x1D00:0x1D00+len(prefix)]=prefix
    return bytes(a)
