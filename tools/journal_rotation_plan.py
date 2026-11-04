"""Forecast native append/peer rotation for a reviewed write plan; no hardware."""
import binascii
from native_journal_room import valid_snapshot,classify_journal

def reserve(bank3,index):
    if not 0<=index<32:raise ValueError('Counter index0..31 required')
    status=classify_journal(bank3)
    if status['kind']!='valid-snbt':raise ValueError('Unambiguous valid SNBT required')
    rows=[(int.from_bytes(bank3[i+8:i+12],'little'),i,bank3[i:i+256]) for i in range(0x4000,0x6000,256) if valid_snapshot(bank3[i:i+256])]
    seq,off,raw=max(rows)
    if off&0xf00==0xf00:raise ValueError('Unresolved intent; inspect before planning')
    image=bytearray(bank3);row=bytearray(raw);writes=[];erases=[]
    def inc(n):
        p=0x40+3*n;count=int.from_bytes(row[p:p+3],'little')
        if count==0xffffff:raise ValueError('Counter saturated')
        row[p:p+3]=(count+1).to_bytes(3,'little')
    def append(where,kind):
        sequence=int.from_bytes(row[8:12],'little')
        if sequence==0xffffffff:raise ValueError('Sequence saturated')
        if image[where:where+256]!=b'\xff'*256:raise ValueError('Destination not blank')
        row[8:12]=(sequence+1).to_bytes(4,'little')
        row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little')
        row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little')
        if not valid_snapshot(row):raise ValueError('Planned row invalid')
        image[where:where+256]=row
        writes.append(dict(page=f'{where+0x8000:04X}',sequence=sequence+1,kind=kind))
    inc(index);sector=off&0xf000;peer=sector^0x1000;dest=off+256
    while dest<sector+0xf00 and image[dest:dest+256]!=b'\xff'*256:dest+=256
    if dest>=sector+0xf00:
        if image[peer:peer+4096]!=b'\xff'*4096:
            if dest!=sector+0xf00:raise ValueError('Intent position uncertain')
            inc(28 if peer==0x4000 else 29)
            append(dest,'peer-erase-intent')
            image[peer:peer+4096]=b'\xff'*4096
            erases.append('B3:C' if peer==0x4000 else 'B3:D')
        dest=peer
    append(dest,'target-erase-reservation')
    return bytes(image),dict(counter_index=index,journal_appends=writes,journal_sector_erases=erases)
