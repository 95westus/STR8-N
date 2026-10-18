"""Build a temporary shared CPU/ABI observation helper without firmware changes."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();assert not out.exists() and len(str(out))<65
    out.mkdir(parents=True);s=out/'s';s.mkdir();source=ROOT/'tools/qualification/bf1_cpu_mode_probe.asm';shutil.copyfile(source,s/'mode.asm')
    assembler=shutil.which('wdc02as');linker=shutil.which('wdcln');assert assembler and linker;logs=[]
    for cmd in [[assembler,'-G','-L','-S','-W','mode.asm'],[linker,'-g','-s','-t','-c2000','-hm19','-j','-o','mode.s19','mode.obj']]:
        r=subprocess.run(cmd,cwd=s,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'build.log.json').write_text(json.dumps(logs,indent=2));assert r.returncode==0,(r.stdout,r.stderr)
    cells={};entry=None
    for line in (s/'mode.s19').read_text().splitlines():
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255;addr=int.from_bytes(raw[1:3],'big')
        if line[1]=='1':
            for n,v in enumerate(raw[3:-1],addr):assert n not in cells;cells[n]=v
        elif line[1]=='9':entry=addr
    symbols={name:int(v,16) for v,name in re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$',(s/'mode.map').read_text(),re.M)}
    entry=symbols['START'];assert entry==0x2000 and set(cells)==set(range(0x2000,max(cells)+1)) and max(cells)<0x2100
    data=bytes(cells[n] for n in sorted(cells));(out/'mode.bin').write_bytes(data)
    raw=bytes([3])+entry.to_bytes(2,'big');record='S9'+(raw+bytes([255-(sum(raw)&255)])).hex().upper()
    (out/'mode.s19').write_text('\n'.join(line for line in (s/'mode.s19').read_text().splitlines() if not line.startswith('S9'))+'\n'+record+'\n')
    assert data[symbols['CPU816']-entry:symbols['CPU816']-entry+3]==bytes.fromhex('38fbea')
    (out/'report.json').write_text(json.dumps(dict(passed=True,entry=entry,bytes=len(data),binary_sha256=sha(out/'mode.bin'),s19_sha256=sha(out/'mode.s19'),source_sha256=sha(source),symbols=symbols,temporary_RAM_only=True,firmware_modified=False,enters_native_mode=False),indent=2)+'\n');print('PASS temporary shared CPU-mode probe:',len(data),'bytes')
if __name__=='__main__':main()
