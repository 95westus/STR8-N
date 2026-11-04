"""Pure OIP1 frame helpers. No port, implicit flash operation or board state."""
import binascii

def crc(data):return binascii.crc_hqx(bytes(data),65535)

def allowed(bank,sector):return bank in range(4) and sector in range(0x80,0x100,0x10) and (bank<3 or sector in (0x80,0x90,0xa0,0xb0,0xe0))

def header(bank,sector,payload=None,preimage_crc=0):
    if not allowed(bank,sector):raise ValueError('Protected/noncanonical target')
    if payload is not None and len(payload)!=4096:raise ValueError('Exactly 4096 payload bytes required')
    if not 0<=preimage_crc<=65535 or payload is None and preimage_crc:raise ValueError('Invalid preimage CRC')
    row=b'OIP1\x01'+bytes((int(payload is not None),bank,sector))+(4096).to_bytes(2,'little')+preimage_crc.to_bytes(2,'little')
    row+=(crc(payload) if payload is not None else 0).to_bytes(2,'little')+bytes(4)
    return row+crc(row).to_bytes(2,'little')


def main():
    import argparse,hashlib,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('read','replace'))
    parser.add_argument('--bank',type=int,required=True)
    parser.add_argument('--sector',type=lambda text:int(text,16),required=True,help='Full hex sector address, e.g. 9000')
    parser.add_argument('--before',type=Path,help='Verified 4096-byte target preimage; required for replace')
    parser.add_argument('--image',type=Path,help='4096-byte replacement; required for replace')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.sector&0xff or not allowed(args.bank,args.sector>>8):parser.error('Protected or noncanonical target')
    if args.out.exists():parser.error('Use a new output directory')
    if args.operation=='replace':
        if not args.before or not args.image:parser.error('replace requires --before and --image')
        before=args.before.read_bytes();payload=args.image.read_bytes()
        if len(before)!=4096 or len(payload)!=4096:parser.error('Both files must contain exactly 4096 bytes')
    else:
        if args.before or args.image:parser.error('read does not take --before or --image')
        before=payload=None
    frame=header(args.bank,args.sector>>8,payload,crc(before) if before is not None else 0)
    args.out.mkdir(parents=True);(args.out/'header.bin').write_bytes(frame)
    if payload is not None:(args.out/'payload.bin').write_bytes(payload)
    digest=lambda data:hashlib.sha256(data).hexdigest()
    receipt=dict(offline=True,serial_access=False,operation=args.operation,bank=args.bank,sector=f'{args.sector:04X}',
        header_sha256=digest(frame),preimage_sha256=digest(before) if before is not None else None,
        payload_sha256=digest(payload) if payload is not None else None,
        transfer='Send header only after SEND OIP1 HEADER; payload only after SEND 4096')
    (args.out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('Prepared',args.out,'(offline; no device opened)')


if __name__=='__main__':main()
