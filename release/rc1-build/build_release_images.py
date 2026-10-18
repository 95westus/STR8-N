"""Compose all rc1 user BINs from the clean build and credited UCHESS record."""
import argparse,hashlib,json
from pathlib import Path
from build_full_image import compose
def main():
    p=argparse.ArgumentParser();p.add_argument('--payload',required=True,type=Path);p.add_argument('--reference',required=True,type=Path);p.add_argument('--uchess-record',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    ref=json.loads(a.reference.read_text());raw,_=compose(a.payload,ref);image=bytearray(raw[32768:]);record=a.uchess_record.read_bytes()
    assert len(record)==1463 and record[:4]==b'SR\1?' and record[8:24]==b'UCHESS'.ljust(16,b'\0') and image[:len(record)]==b'\xff'*len(record)
    assert b'Microchess Copyright 1976 Peter Jennings benlo.com' in record
    image[:len(record)]=record;a.out.mkdir(parents=True,exist_ok=False)
    files={'str8n-2.0rc1-apps-str8n-only.bin':bytes(image)}
    for name,offset,size in [('boot-core-b3',0x10000,32768),('monitor-a',0x12000,4096),('monitor-b',0x13000,4096),('b3-f000-ffff',0x17000,4096)]:files[f'str8n-2.0rc1-{name}.bin']=bytes(image[offset:offset+size])
    for name,body in files.items():(a.out/name).write_bytes(body)
    (a.out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in sorted(files.items())))
    print('PASS five source-derived rc1 firmware BINs; B0/vendor code excluded')
if __name__=='__main__':main()
