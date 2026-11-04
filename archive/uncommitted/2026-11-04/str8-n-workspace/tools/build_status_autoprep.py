"""Build changed STATUS details for RAM/ROM; reuse unchanged core and text."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches

def run():
    out=ROOT/'BUILD/status-autoprep-r1';out.mkdir(exist_ok=False)
    freeze=json.loads((REPO/'F_FREEZE.json').read_text());assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    artifacts={};logs=[]
    for variant,base,prior in [('ROM',0xFA50,ROOT/'BUILD/status-g1-r4'),('RAM',0x3400,ROOT/'BUILD/status-g1-RAM-r1')]:
        stage=out/variant;stage.mkdir()
        for n in ('str8n-v2-public.inc','status-interface.inc','status-text.inc'):
            shutil.copyfile(prior/'status-details'/n,stage/n)
        for n in ('status-details.asm','status-mon-sram.inc'):
            s=(REPO/'monitors/status'/n).read_text()
            s=re.sub(r'^\s*SAY (\w+)\s*$',lambda m:f'        LDX #<{m[1]}\n        LDY #>{m[1]}\n        JSR ST_PRINT',s,flags=re.M)
            s,_=conservative_branches(s,'status_details_'+n.replace('.','_').replace('-','_')+'_')
            (stage/n).write_text(s)
        for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','status-details.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{base:04X}','-hm19','-j','-o','status-details.s19','status-details.obj']):
            p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(variant=variant,command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(out/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'status-details.map').read_text(),re.M)}
        m=cells(stage/'status-details.s19');body=bytes(m[a] for a in range(base,sy['SD_END']));assert len(body)<=1448
        image=body.ljust(1448,b'\xff');image+=binascii.crc_hqx(image,65535).to_bytes(2,'big');assert binascii.crc_hqx(image,65535)==0
        name=f'STATUS-{variant}.bin';(out/name).write_bytes(image);(stage/'symbols.json').write_text(json.dumps(sy,indent=2))
        artifacts[name]=dict(bytes=len(image),linked_bytes=len(body),free_bytes=1448-len(body),sha256=sha(image));print(variant,len(body),'bytes;free',1448-len(body),flush=True)
    report=dict(component='Guarded automatic SRAM preparation',artifacts=artifacts,F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,
        source_sha256={n:sha((REPO/'monitors/status'/n).read_bytes()) for n in ('status-details.asm','status-mon-sram.inc')},
        unchanged_core_and_text_reused=True,build_passes=1,RAM_ROM_distinct_bindings=True)
    (out/'manifest.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':run()
