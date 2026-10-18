"""Rebuild the separate bf1 RAM helper from extracted source; no serial access."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();assert not out.exists() and len(str(out))<=65
    source=HERE/'release/candidates/batchfix-route-r1';ref=json.loads((HERE/'helper-reference.json').read_text())
    out.mkdir(parents=True);stage=out/'s';stage.mkdir()
    for name in ('reservation.asm','str8n-v2-eq.inc','reservation-links.inc'):shutil.copyfile(source/'source'/name,stage/name)
    assembler=shutil.which('wdc02as');linker=shutil.which('wdcln');assert assembler and linker
    logs=[]
    for command in [[assembler,'-G','-L','-S','-W','-I',str(stage),'reservation.asm'],[linker,'-g','-s','-t','-c3000','-hm19','-j','-o','reservation.s19','reservation.obj']]:
        r=subprocess.run(command,cwd=stage,capture_output=True,text=True);logs.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'build.log.json').write_text(json.dumps(logs,indent=2));assert r.returncode==0,(r.stdout,r.stderr)
    cells={}
    for line in (stage/'reservation.s19').read_text().splitlines():
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':
            address=int.from_bytes(raw[1:3],'big')
            for n,v in enumerate(raw[3:-1],address):assert n not in cells;cells[n]=v
    assert set(cells)==set(range(0x3000,0x3000+ref['bytes']))
    data=bytes(cells[n] for n in sorted(cells));assert hashlib.sha256(data).hexdigest()==ref['binary_sha256']
    (out/'reservation.bin').write_bytes(data);(out/'build-report.json').write_text(json.dumps(dict(passed=True,bytes=len(data),binary_sha256=ref['binary_sha256'],board_access=False,installation_permitted=False),indent=2)+'\n');print('PASS helper reproduced:',len(data),'bytes')
if __name__=='__main__':main()
