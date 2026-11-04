"""Assemble two complete ordered ES1 read-console exports; never opens a port."""
import argparse,hashlib,json,re
from pathlib import Path

SIZE=131072


def parse(raw):
    text=raw.decode('ascii').replace('\r','');blocks=text.split('EDU RO> R ')[1:]
    assert len(blocks)==SIZE//64,'Need exactly 2048 R replies in each dedicated pass log'
    result=bytearray();modes=set()
    for n,block in enumerate(blocks):
        lines=block.splitlines();command=re.fullmatch(r'([0-9A-F]{5}) 40',lines[0])
        assert command and int(command[1],16)==n*64,'Missing, duplicate or unordered address'
        status=re.fullmatch(r'STATUS COMPLETED MODE: 00 40 (00|40|80)',lines[1]);assert status,'Read failed or count/mode differs'
        assert re.fullmatch(r'(?:[0-9A-F]{2} ){64}',lines[2]),'Missing or malformed payload bytes'
        result.extend(bytes.fromhex(lines[2]));modes.add(int(status[1],16))
    assert len(result)==SIZE and len(modes)==1,'Incomplete array or mode changed'
    return bytes(result),modes.pop()


def selftest():
    data=bytes((n*37+(n>>8)*11)&255 for n in range(SIZE))
    lines=[f'EDU RO> R {a:05X} 40\r\nSTATUS COMPLETED MODE: 00 40 40\r\n'+''.join(f'{v:02X} ' for v in data[a:a+64])+'\r\n' for a in range(0,SIZE,64)]
    raw=''.join(lines).encode();assert parse(raw)==(data,0x40)
    bad=[b''.join(line.encode() for line in lines[:-1]),raw.replace(b'00040 40',b'00000 40',1),
         raw.replace(b'00 40 40',b'01 40 40',1),raw.replace(b'00 40 40',b'00 3F 40',1),
         raw.replace(b'00 40 40',b'00 40 80',1),raw.replace(b'00 25 ',b'00 ',1)]
    for value in bad:
        try:parse(value)
        except (AssertionError,IndexError):pass
        else:raise AssertionError('Incomplete or corrupt export accepted')
    return dict(passed=True,checks=7,hardware=False,serial_access=False,bytes=SIZE,
                cases=['complete independent byte oracle','missing tail','duplicate address','error status','short count','mode changed','short payload'])


def assemble(first,second,out):
    a,mode=parse(Path(first).read_bytes());b,other=parse(Path(second).read_bytes())
    assert a==b and mode==other,'Independent full exports or modes differ'
    out=Path(out).resolve();assert not out.exists();out.mkdir(parents=True)
    for n,data in ((1,a),(2,b)):(out/f'SRAM-pass{n}-131072.bin').write_bytes(data)
    sha=lambda data:hashlib.sha256(data).hexdigest()
    info=dict(passed=True,bytes=SIZE,sha256=sha(a),mode=f'{mode:02X}',identical=True,presence_proven=False,
        parser_only=True,serial_access=False,SRAM_writes=False,
        console_inputs={str(Path(path).resolve()):sha(Path(path).read_bytes()) for path in (first,second)})
    (out/'backup.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8');return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--first',type=Path);parser.add_argument('--second',type=Path);parser.add_argument('--out',type=Path)
    args=parser.parse_args();print(json.dumps(selftest() if args.self_test else assemble(args.first,args.second,args.out),indent=2))
