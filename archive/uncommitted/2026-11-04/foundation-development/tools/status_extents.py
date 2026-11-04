"""STATUS's sealed strings occupy explicit bundle extents, never free padding."""
import binascii,hashlib,json
from pathlib import Path

TEXT_EXTENTS=((0x40,192),(0x240,192))
CODE_EXTENTS=((0x2C00,1024),(0x7A50,1450))


def assert_preserved(before,after):
    """Compare all four STATUS allocations in complete B2 bank images."""
    if len(before)!=32768 or len(after)!=32768:raise ValueError('Complete B2 images required')
    for offset,size in TEXT_EXTENTS+CODE_EXTENTS:
        if before[offset:offset+size]!=after[offset:offset+size]:
            raise ValueError(f'STATUS allocation changed at B2:{0x8000+offset:04X}')


def preserve_text(bundle,status_manifest):
    path=Path(status_manifest).resolve();manifest=json.loads(path.read_text())
    assert not manifest.get('RAM_trial',False),'ROM STATUS manifest required'
    result=bytearray(bundle)
    for offset,size in TEXT_EXTENTS:
        address=f'{0x8000+offset:04X}'
        name,info=next((n,v) for n,v in manifest['artifacts'].items() if v['address']==address)
        data=(path.parent/name).read_bytes()
        assert len(data)==size and hashlib.sha256(data).hexdigest()==info['sha256']
        assert binascii.crc_hqx(data,65535)==0
        if bundle[offset:offset+size] not in (b'\xff'*size,data):
            raise ValueError('STATUS extent collides with bundle code/data at'+address)
        result[offset:offset+size]=data
    for offset,(a,b) in enumerate(zip(bundle,result)):
        assert a==b or any(start<=offset<start+size for start,size in TEXT_EXTENTS)
    return bytes(result)
