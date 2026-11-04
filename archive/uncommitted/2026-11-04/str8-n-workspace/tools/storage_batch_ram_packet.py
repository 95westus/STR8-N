"""RAM transport for the storage BATCH candidate, with no NVM writer fixture."""
import binascii, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'release/str8nf-v0.2.0/tools'))
from storage_compact import compact
from named_edu_ram_packet import Code


def packet(body,kernel,route,queue,*,program=None):
    assert route in (3,4) and 0<=len(queue)<=34
    assert program is None or program==bytes.fromhex('A9 47 8D FF 18 4C 67 7E')
    packed=compact(body);first=0x1AC0;rest=packed[first:]
    assert len(kernel)<=0x140 and len(rest)<=0xD00 and 0x2000+len(body)<=0x5400
    a=bytearray(b'\xff'*0x6300);a[:3]=bytes.fromhex('4C 00 1F')
    a[0x100:0x100+len(kernel)]=kernel
    a[0x240:0x240+min(first,len(packed))]=packed[:first]
    a[0x5600:0x5600+len(rest)]=rest
    c=Code();c.emit(0x78,0xD8,0xA2,0xFF,0x9A,0xA2,0);c.label('kernel')
    c.emit(0xBD,0,3,0x9D,0,0x68,0xBD,0,4,0x9D,0,0x69,0xE8);c.branch(0xD0,'kernel')
    c.emit(0xA2,0);c.label('save')
    c.emit(0xBD,0,0,0x9D,0,2,0xBD,0,0x6A,0x9D,0,3,0xE8);c.branch(0xD0,'save')
    def store(c,addr,value):c.emit(0xA9,value,0x8D,addr&255,addr>>8)
    values={0xE0:0x40,0xE1:4,0xE2:0,0xE3:0x20,0x670B:0,0x670C:0x20,0x6708:3}
    for addr,value in ((0x6709,0x2000+len(body)),(0x670F,0x5800+len(rest)),(0x670D,binascii.crc_hqx(body,65535))):
        values[addr]=value&255;values[addr+1]=value>>8
    for addr,value in values.items():store(c,addr,value)
    c.emit(0x20,0,0x68,0xA2,0);c.label('contexts')
    c.emit(0xBD,0,2,0x9D,0,0x5C,0xBD,0,3,0x9D,0,0x5D,0xE8);c.branch(0xD0,'contexts')
    c.emit(0x4C,0,0x54);prefix=c.finish();assert len(prefix)<=256
    a[0x1D00:0x1D00+len(prefix)]=prefix
    c=Code();c.emit(0xA2,0x2F);c.label('clear')
    c.emit(0x9E,0xD0,0x6A,0xCA);c.branch(0x10,'clear')
    c.emit(0xA2,7);c.label('area');c.emit(0x9E,0x28,0x5D,0xCA);c.branch(0x10,'area')
    for i,value in enumerate(queue):store(c,0x6AD0+i,value)
    for addr,value in ((0x6AF3,len(queue)),(0x6AF6,route+2),(0x6AF7,3),(0x6AF8,2),(0x7DF9,0xB7 if queue else 0),(0x5B02,route),(0x6770,0)):
        store(c,addr,value)
    if program is not None:
        for i,value in enumerate(program):store(c,0x1000+i,value)
        store(c,0x18FF,0)
    c.emit(0x4C,0,0x20);tail=c.finish();assert len(tail)<=0x400
    a[0x5200:0x5200+len(tail)]=tail
    return bytes(a)
