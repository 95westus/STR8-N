"""Inspect an actual SS1/SS2 SPI SRAM capture for PROGRAM ownership and scope."""
import argparse,binascii,hashlib,json
from pathlib import Path

def inspect(data):
    if len(data)!=131072:raise ValueError('Complete131072-byte capture required')
    u16=lambda b:int.from_bytes(b,'little')
    h=data[:64]
    if h[:2]!=b'SS' or h[2] not in (1,2) or h[3:5]!=b'\x08\x08' or h[62]!=0 or h[63]!=0xa5 or binascii.crc_hqx(h[:62],65535):
        raise ValueError('Primary SS1/SS2 header not admitted')
    pages=u16(h[5:7])
    if pages not in (64,128,192,256):raise ValueError('Unsupported PROGRAM boundary')
    if h[2]==1:
        if h[:60]!=b'SS\x01\x08\x08\x00\x01\x00'+bytes(52):raise ValueError('Legacy SS1 fields differ')
    elif h[7] or not int.from_bytes(h[8:12],'little') or any(h[12:60]):raise ValueError('SS2 generation/reserved fields differ')
    used=set(range(8));records=[];free=[];latest={}
    for slot in range(8):
        address=64*(slot+1);r=data[address:address+64]
        if r[63]!=0xa5:
            free.append(dict(slot=slot,address=f'{address:04X}',all_zero=not any(r),all_FF=r==b'\xff'*64));continue
        if r[:4]!=b'SP\x01\x00' or r[62] or any(r[32:60]) or binascii.crc_hqx(r[:62],65535):raise ValueError(f'Slot{slot} header invalid')
        rawname=r[16:32];name=rawname.split(b'\x00',1)[0]
        if not name or rawname!=name.ljust(16,b'\x00') or any(not(48<=c<=57 or 65<=c<=90 or c in (45,95)) for c in name):raise ValueError(f'Slot{slot} name invalid')
        load,length,entry,seq=u16(r[4:6]),u16(r[6:8]),u16(r[8:10]),u16(r[10:12]);kind=r[15]
        if not seq or kind not in (1,2):raise ValueError(f'Slot{slot} state invalid')
        item=dict(slot=slot,directory_address=f'{address:05X}',name=name.decode('ascii'),sequence=seq,kind=kind,
                  load=f'{load:04X}',length=length,entry=f'{entry:04X}',page=r[14])
        if kind==1:
            if load<0x200 or not length or load+length>0x6700 or (entry and not load<=entry<load+length):raise ValueError(f'Slot{slot} RAM bounds invalid')
            extent=set(range(r[14],r[14]+(length+255)//256))
            if r[14]<8 or max(extent)>=pages or used&extent:raise ValueError(f'Slot{slot} PROGRAM bounds/overlap invalid')
            used|=extent;payload=data[r[14]*256:r[14]*256+length]
            item['payload_CRC_valid']=binascii.crc_hqx(payload,65535)==u16(r[12:14])
            item.update(payload_address=f'{r[14]*256:05X}',payload_end=f'{r[14]*256+length-1:05X}',
                        payload_sha256=hashlib.sha256(payload).hexdigest())
        elif length or r[14]:raise ValueError(f'Slot{slot} tombstone invalid')
        records.append(item);old=latest.get(item['name'])
        if old is None or seq>old['sequence']:latest[item['name']]=item
        elif seq==old['sequence']:old['ambiguous']=True
    if any(r.get('ambiguous') for r in latest.values()):raise ValueError('Ambiguous latest same-name sequence')
    return dict(format=f'SS{h[2]}',boundary=f'{pages*256:05X}',generation=int.from_bytes(h[8:12],'little'),
                sha256=hashlib.sha256(data).hexdigest(),records=records,latest=latest,free_slots=free,
                free_pages=[f'{p:02X}' for p in range(8,pages) if p not in used],WORKSPACE_start=f'{pages*256:05X}',
                hardware_access=False,format_performed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);a=p.parse_args();print(json.dumps(inspect(a.capture.read_bytes()),indent=2))
