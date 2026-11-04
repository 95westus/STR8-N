"""Build the standalone boot/opaque tree with WDC tools; no parent-tree inputs."""
import argparse,binascii,hashlib,json,re,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def cells(path):
    result={}
    for line in path.read_text().splitlines():
        if not line:continue
        if not re.fullmatch(r'S[019][0-9a-fA-F]+',line):raise ValueError('Unsupported S-record')
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':
            for address,value in enumerate(raw[3:-1],int.from_bytes(raw[1:3],'big')):
                assert address not in result;result[address]=value
    return result


def db(path,data):path.write_text(''.join(' DB '+','.join(f'${b:02X}' for b in data[n:n+16])+'\n' for n in range(0,len(data),16)),encoding='ascii',newline='\n')


def s19(data,address,entry):
    def row(kind,where,body):
        raw=bytes([len(body)+3])+where.to_bytes(2,'big')+body
        return 'S'+kind+(raw+bytes([255-(sum(raw)&255)])).hex().upper()
    return ('\n'.join([row('0',0,b'STR8N-F component')]+[row('1',address+n,data[n:n+32]) for n in range(0,len(data),32)]+[row('9',entry,b'')])+'\n').encode()


def build(*args, **kwargs):
    raise ValueError('BASE1 F is frozen; use tools/build_base1.py for RAM components')


if __name__=='__main__':
    raise SystemExit('Use tools/build_base1.py --out NEW-DIRECTORY; F is reused unchanged')
