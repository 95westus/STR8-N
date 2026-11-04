"""Build the commented AP/02 example once, without board access or an F build."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha

def build(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);stage=out/'staging';stage.mkdir()
    src=ROOT/'apps/examples/appdemo.asm';shutil.copyfile(src,stage/'appdemo.asm')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','appdemo.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c9020','-hm19','-j','-o','appdemo.s19','appdemo.obj']):
        r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('WDC failed; see build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'appdemo.map').read_text(),re.M)}
    m=cells(stage/'appdemo.s19');assert set(m)==set(range(0x9020,sy['APP_END']))
    code=bytes(m[a] for a in range(0x9020,sy['APP_END']));h=bytearray(32)
    h[:8]=b'AP\x02\x20PR05';h[8:10]=(32+len(code)).to_bytes(2,'little');h[10:12]=(0x9020).to_bytes(2,'little')
    h[14:16]=bytes([1,2]);h[16:23]=b'APPDEMO';h[28:30]=binascii.crc_hqx(h[:28],65535).to_bytes(2,'little')
    h[30:32]=binascii.crc_hqx(code,65535).to_bytes(2,'little');image=bytes(h)+code
    name='STR8N-APPDEMO-AP02-B0-9000.bin';(out/name).write_bytes(image)
    sector='STR8N-APPDEMO-AP02-B0-9-SECTOR.bin';(out/sector).write_bytes(image.ljust(4096,b'\xff'))
    result=dict(component='AP/02 public-ABI example',name='APPDEMO',bank=0,base='9000',entry='9020',bytes=len(image),
                image=dict(filename=name,sha256=sha(image)),sector=dict(filename=sector,sha256=sha(image.ljust(4096,b'\xff'))),
                source_sha256={'apps/examples/appdemo.asm':sha(src.read_bytes())},build_passes=1,assembler_linker_invocations=2,
                status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,CPU_simulations=0)
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out)
