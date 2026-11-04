"""Known large owner-RAM sources; transport packet never exceeds raw BIN cap."""
from time_prep_ram_packets import Code


def source_packet(program=False):
    first,pages=(0x4700,32) if program else (0x4E00,25)
    expected=bytearray(bytes((i&255)^0xA5 for i in range(pages*256)) if program else b'\xff'*(pages*256))
    patches={}
    if program:
        head=bytes.fromhex('80 08 42 54 01 02 50 52 30 35 A9 4C 8D FF 18 4C 67 7E')
        patches.update({i:v for i,v in enumerate(head)})
        tail=b'LARGE-RETURN-G4!';assert len(tail)==16
    else:
        head=b'AUTO-LARGE-G4!!!';tail=b'END-AUTO-G4!!!!!'
        assert len(head)==len(tail)==16
        patches.update({i:v for i,v in enumerate(head)})
    patches.update({len(expected)-16+i:v for i,v in enumerate(tail)})
    for i,v in patches.items():expected[i]=v
    c=Code(0x1000);c.emit(0x78,0xD8,0xA2,0xFF,0x9A,0x64,0xE0,0xA9,first>>8,0x85,0xE1,0xA2,pages,0xA0,0)
    c.label('fill');c.emit(*(bytes.fromhex('98 49 A5') if program else bytes.fromhex('A9 FF')))
    c.emit(0x91,0xE0,0xC8);c.branch(0xD0,'fill');c.emit(0xE6,0xE1,0xCA);c.branch(0xD0,'fill')
    for i,v in patches.items():c.emit(0xA9,v);c.absolute(0x8D,first+i)
    c.absolute(0x9C,0x7DF9);c.absolute(0x4C,0x7E67)
    code=c.done();assert len(code)<0xE00
    a=bytearray(b'\xff'*0x1E00);a[:3]=bytes.fromhex('4C 00 10');a[0xE00:0xE00+len(code)]=code
    return bytes(a),bytes(expected)
