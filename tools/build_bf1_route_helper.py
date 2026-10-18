"""Source-build a separate RAM reservation helper; frozen payloads are read-only."""
import argparse,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release/beta35'))
from build import read_s19
sha=lambda b:hashlib.sha256(b).hexdigest()
MANIFEST_SHA='5612d0121df646728b64057df53de1c6faa2c8f324ee7cb16679b8341c261aed'

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    out=a.out.resolve();assert not out.exists() and len(str(out))<=65
    mfpath=ROOT/'BUILD/v2-beta35-candidate/migrator/manifest.json';assert sha(mfpath.read_bytes())==MANIFEST_SHA
    mf=json.loads(mfpath.read_text());source=ROOT/'release/candidates/batchfix-route-r1/source/reservation.asm'
    eq=ROOT/'release/beta35/source/migration/str8n-v2-eq.inc'
    provenance=json.loads((ROOT/'release/beta35/source-provenance.json').read_text())
    assert sha(eq.read_bytes())==provenance['source/migration/str8n-v2-eq.inc']['sha256']
    out.mkdir(parents=True);stage=out/'asm';stage.mkdir();shutil.copyfile(source,stage/'reservation.asm');shutil.copyfile(eq,stage/eq.name)
    needed=['MIG_HASH_RANGE','V2W_SELECT','V2W_BYTE','V2W_POLL','V2W_TIMEOUT']
    links={n:mf['symbols'].get(n,mf['worker'].get(n)) for n in needed};assert all(v is not None for v in links.values())
    (stage/'reservation-links.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in links.items()))
    assembler=shutil.which('wdc02as');linker=shutil.which('wdcln');assert assembler and linker
    logs=[]
    for command in [[assembler,'-G','-L','-S','-W','-I',str(stage),'reservation.asm'],
        [linker,'-g','-s','-t','-c3000','-hm19','-j','-o','reservation.s19','reservation.obj']]:
        r=subprocess.run(command,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (stage/'build.log.json').write_text(json.dumps(logs,indent=2)+'\n');assert r.returncode==0,(r.stdout,r.stderr)
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(stage/'reservation.map').read_text(),re.M)}
    cells=read_s19(stage/'reservation.s19');assert set(cells)==set(range(0x3000,symbols['R_END'])) and symbols['R_END']<=0x3300
    data=bytes(cells[i] for i in range(0x3000,symbols['R_END']));(out/'reservation.bin').write_bytes(data)
    result=dict(passed=True,source_only=True,entry=0x3000,bytes=len(data),binary_sha256=sha(data),symbols=symbols,
        links=links,frozen_manifest_sha256=MANIFEST_SHA,source_sha256=sha(source.read_bytes()),eq_sha256=sha(eq.read_bytes()),
        builder_sha256=sha(Path(__file__).read_bytes()),toolchain_sha256={Path(x).name:sha(Path(x).read_bytes()) for x in (assembler,linker)},
        model_qualified=False,installer_integrated=False,installation_permitted=False,release_qualified=False)
    (out/'build-report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS separate RAM helper build:',len(data),'bytes; model qualification pending')

if __name__=='__main__':main()
