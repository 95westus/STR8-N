"""Offline S19 join and RAM-to-AP/02 example packaging. No serial or flash IO."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re


def records(data):
    memory={};entry=None
    for line in data.splitlines():
        line=line.strip().upper()
        if not line:continue
        if entry is not None or not re.fullmatch(rb'S[019][0-9A-F]+',line):
            raise ValueError('Expected S0/S1 data followed by one final S9')
        row=bytes.fromhex(line[2:].decode('ascii'))
        if len(row)<4 or len(row)!=row[0]+1 or sum(row)&255!=255:
            raise ValueError('S-record count/checksum mismatch')
        address=int.from_bytes(row[1:3],'big');body=row[3:-1]
        if line[1]==ord('1'):
            if not body or not 0x200<=address<=address+len(body)-1<=0x66ff:
                raise ValueError('S1 destination outside owner RAM')
            for offset,value in enumerate(body,address):
                if offset in memory:raise ValueError('Overlapping S1 records')
                memory[offset]=value
        elif line[1]==ord('9'):
            if body:raise ValueError('S9 must not contain data')
            entry=address
    if not memory or entry is None:raise ValueError('Missing S1 data or final S9')
    return memory,entry


def s19(body,load,entry):
    def record(kind,address,data=b''):
        row=bytes((len(data)+3,))+address.to_bytes(2,'big')+data
        return b'S'+str(kind).encode()+(row+bytes(((~sum(row))&255,))).hex().upper().encode()+b'\r\n'
    return b''.join(record(1,load+i,body[i:i+24]) for i in range(0,len(body),24))+record(9,entry)


def ap02(body,*,load=0x200,entry=0x200,base=0x8000,cpu=0,name='UCHESS'):
    if not body or load&255 or not 0x200<=load<=entry<load+len(body)<=0x6700:
        raise ValueError('Use a page-aligned owner-RAM load and entry within its bytes')
    if base not in range(0x8000,0xf000,0x1000) or cpu not in (0,2,0x16):
        raise ValueError('Invalid flash base or CPU; native 816 is unsupported')
    if not re.fullmatch(r'[A-Z][A-Z0-9_-]{0,10}',name):raise ValueError('Use a short uppercase AP name')
    pages=(len(body)+255)//256
    if load+pages*256>0x6700:raise ValueError('Page copy crosses owner-RAM limit')
    loader=bytearray((0x78,0xd8))
    for page in range(pages):
        loader+=bytes((0xa2,0,0xbd,0,0,0x9d,0,load//256+page,0xe8,0xd0,0xf7))
    loader+=b'\x4c'+entry.to_bytes(2,'little')
    for page in range(pages):
        offset=4+page*11
        loader[offset+1:offset+3]=(base+32+len(loader)+page*256).to_bytes(2,'little')
    payload=bytes(loader)+body.ljust(pages*256,b'\xff')
    if len(payload)+32>4096:raise ValueError('RAM image and loader do not fit one sector')
    header=bytearray(32);header[:8]=b'AP\x02 PR05'
    header[8:10]=(32+len(payload)).to_bytes(2,'little');header[10:12]=(base+32).to_bytes(2,'little')
    header[14:16]=bytes((1,cpu));header[16:16+len(name)]=name.encode('ascii')
    header[28:30]=binascii.crc_hqx(header[:28],65535).to_bytes(2,'little')
    header[30:32]=binascii.crc_hqx(payload,65535).to_bytes(2,'little')
    return (bytes(header)+payload).ljust(4096,b'\xff')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    j=sub.add_parser('join-s19');j.add_argument('files',type=Path,nargs='+')
    j.add_argument('--entry',type=lambda x:int(x,16),default=0x200)
    j.add_argument('--expect',type=Path);j.add_argument('--out',type=Path,required=True)
    a=sub.add_parser('ap02');a.add_argument('--ram',type=Path,required=True)
    for flag,default in [('load',0x200),('entry',0x200),('base',0x8000)]:
        a.add_argument('--'+flag,type=lambda x:int(x,16),default=default)
    cpus={'shared':0,'65c02':2,'65c816-e':0x16}
    a.add_argument('--cpu',choices=cpus,default='shared',
                   help='Shared requires the updated AP/02 dispatcher')
    a.add_argument('--name',default='UCHESS');a.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    if args.command=='join-s19':
        memory={}
        for file in args.files:
            chunk,_=records(file.read_bytes())
            if memory.keys() & chunk.keys():raise ValueError('Parts overlap')
            memory.update(chunk)
        load=min(memory);end=max(memory)+1
        if set(memory)!=set(range(load,end)) or args.entry not in memory:raise ValueError('Gap or missing entry')
        body=bytes(memory[i] for i in range(load,end))
        if args.expect and body!=args.expect.read_bytes():raise ValueError('Assembled bytes differ from the reference')
        (args.out/'program.bin').write_bytes(body);(args.out/'program.s19').write_bytes(s19(body,load,args.entry))
    else:
        body=ap02(args.ram.read_bytes(),load=args.load,entry=args.entry,base=args.base,
                  cpu=cpus[args.cpu],name=args.name)
        (args.out/'program-ap02-sector.bin').write_bytes(body)
    manifest={'operation':args.command,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
              'board_access':False,'F_rebuilt':False,'status':'OFFLINE_ONLY_NO_INSTALLATION'}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
