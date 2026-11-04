"""Read BASE1's fixed FI locator and bounded identity record from a 4K F BIN."""
import argparse
import binascii
import json
from pathlib import Path


def decode(image):
    image=bytes(image)
    if len(image)!=4096 or image[:4]!=b'SN\x02\0':raise ValueError('Not a 4096-byte N/F image')
    if image[0x3c:0x3e]!=b'FI':raise ValueError('F identity locator absent')
    address=int.from_bytes(image[0x3e:0x40],'little')
    offset=address-0xf000
    if not 0<=offset<=0xfe0-64:raise ValueError('Identity pointer outside F payload')
    row=image[offset:offset+64]
    if row[:5]!=b'NFI1\x40' or row[6]!=1:raise ValueError('Unsupported identity format/length')
    if binascii.crc_hqx(row[:62],0xffff)!=int.from_bytes(row[62:64],'little'):
        raise ValueError('Identity CRC mismatch')
    def text(where):
        field=row[where:where+8]
        if 0 not in field:raise ValueError('Unterminated identity field')
        return field.split(b'\0')[0].decode('ascii')
    return dict(product=text(12),F_version=text(20),F_generation=f'{int.from_bytes(row[8:12],"little"):08X}',
                profile=text(28),private_contract=row[36:40].decode('ascii'),public_ABI_major=row[5],
                descriptor_address=f'{address:04X}',descriptor_bytes=64,
                RAM_signature=f'{int.from_bytes(row[40:42],"little"):04X}',
                reset=f'{int.from_bytes(row[42:44],"little"):04X}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path)
    args=parser.parse_args();print(json.dumps(decode(args.image.read_bytes()),indent=2))
