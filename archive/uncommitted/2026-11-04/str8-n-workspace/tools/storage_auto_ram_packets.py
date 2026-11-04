"""CPU-RAM probes and live-NO previews for the installed-storage candidate."""
import json
from pathlib import Path
from time_prep_ram_packets import Code
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/storage-installed-auto-r1'


def frame(tests=None,command=None):
    worker=(BUILD/'FLASH-RECORD-6B00.bin').read_bytes()
    sy=json.loads((BUILD/'symbols.json').read_text())['flash-record']
    a=bytearray(b'\xff'*0x1A00);a[:3]=bytes.fromhex('4C 00 10');a[0x100:0x900]=worker
    c=Code(0x1000);c.emit(0x78,0xD8,0xA2,0);c.label('copy')
    for i in range(8):c.absolute(0xBD,0x300+i*256);c.absolute(0x9D,0x6B00+i*256)
    c.emit(0xE8);c.branch(0xD0,'copy')
    def store(addr,value):c.emit(0xA9,value);c.absolute(0x8D,addr)
    def area(on,bank,first,end):
        for i,v in enumerate((on,bank,first&255,first>>8,end&255,end>>8)):store(0x6A29+i,v)
        store(sy['FR_BANK'],0);store(sy['FR_AUTO'],1)
    def word(addr,value):store(addr,value&255);store(addr+1,value>>8)
    if tests is not None:
        for n,test in enumerate(tests):
            area(*test['area']);word(sy['FR_NEXT'],0x9000)
            if 'record' in test:
                word(sy['V2_FLASH_PTR'],test['record'][0]);word(sy['FR_RECORD_END'],test['record'][1])
            if 'end' in test:word(sy['FR_END'],test['end'])
            c.absolute(0x20,sy[test['call']]);c.emit(0x08,0x68);c.absolute(0x8D,0x1A00+n*4)
            c.absolute(0xAD,sy['FR_NEXT']);c.absolute(0x8D,0x1A01+n*4)
            c.absolute(0xAD,sy['FR_NEXT']+1);c.absolute(0x8D,0x1A02+n*4)
    else:
        assert command is not None
        area(1,0,0x9000,0xA000)
        c.absolute(0xAD,0x7FA0);c.absolute(0x8D,0x1BFE)
        c.emit(0xA2,0,0xA0,0x1B);c.absolute(0x20,sy['FR_COMMAND'])
        c.absolute(0xAD,0x1BFE);c.absolute(0x8D,0x7FA0)
        a[0x1900:0x1900+len(command)+1]=command+b'\0'
    c.absolute(0x4C,0x7E67);code=c.done();assert len(code)<=0xA00,len(code)
    a[0xE00:0xE00+len(code)]=code
    return bytes(a)


def cases():
    tests=[]
    for name,area,carry,next_addr in [
        ('valid',(1,0,0x9000,0xB000),1,0x9000),('disabled',(0,0,0x9000,0xB000),0,0x8000),
        ('bank-mismatch',(1,1,0x9000,0xB000),0,0x8000),('inverted',(1,0,0xB000,0x9000),0,0x8000),
        ('below-flash',(1,0,0x7FFF,0x9000),0,0x8000),('past-arena',(1,0,0x9000,0xE001),0,0x8000),
        ('full-arena',(1,0,0x8000,0xE000),1,0x8000),('one-byte',(1,0,0x9000,0x9001),1,0x9000)]:
        tests.append(dict(name=name,area=area,carry=carry,next=next_addr,call='FA_SETUP'))
    for name,record,carry,next_addr in [
        ('ends-at-AREA',(0x8500,0x9000),1,0x9000),('crosses-AREA-start',(0x8500,0x9001),0,0x9000),
        ('first-record',(0x9000,0x9018),1,0x9018),('ends-at-limit',(0xAFFF,0xB000),1,0xB000),
        ('crosses-limit',(0xAFFF,0xB001),0,0x9000),('after-AREA',(0xB000,0xB100),1,0x9000),
        ('before-AREA',(0x8000,0x8018),1,0x9000),('page-carry',(0x90FF,0x9100),1,0x9100)]:
        tests.append(dict(name=name,area=(1,0,0x9000,0xB000),record=record,carry=carry,next=next_addr,call='FA_RECORD'))
    for end,carry in ((0xB000,1),(0xB001,0),(0xA918,1)):
        tests.append(dict(name=f'fits-{end:04X}',area=(1,0,0x9000,0xB000),end=end,carry=carry,next=0x9000,call='FA_FITS'))
    return tests
