"""Pack the pre-WB Store frontend into unused S19-overlay padding; F reused."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha
from build import db
from mona_branches import conservative_branches


def build(out,s19,provider):
    out,s19,provider=map(lambda p:Path(p).resolve(),(out,s19,provider))
    if out.exists():raise ValueError('Fresh output directory required')
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    sm=json.loads((s19/'manifest.json').read_text());pm=json.loads((provider/'manifest.json').read_text())
    sl=(s19/'S19-LOADER-6B00.bin').read_bytes();sp=(provider/pm['artifact']['filename']).read_bytes()
    assert sha(sl)==sm['artifacts']['S19-LOADER-6B00.bin']['sha256'] and sm['linked_bytes']<=512
    assert sha(sp)==pm['artifact']['sha256'] and pm['generation']=='00000003'
    out.mkdir(parents=True);sources={};logs=[]
    for path in ('src/include/str8n-v2-public.inc','src/core/worker-public-symbols.inc','src/core/boot-symbols.inc'):
        p=ROOT/path;sources[path]=sha(p.read_bytes());shutil.copyfile(p,out/p.name)
    (out/'store-provider-pin.inc').write_text(f'STORE_PROVIDER_CRC_HI EQU ${sp[-2]:02X}\nSTORE_PROVIDER_CRC_LO EQU ${sp[-1]:02X}\n')
    def assemble(name,origin,last):
        p=ROOT/f'monitors/native/{name}.asm';sources[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
        body,_=conservative_branches(p.read_text(),'STORE_LONG_'+name.replace('-','_')+'_')
        (out/p.name).write_text(body)
        for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W',p.name],
                        [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']):
            assert command[0];r=subprocess.run(command,cwd=out,capture_output=True,text=True)
            logs.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if r.returncode:raise RuntimeError('Build failed; see build-log.json')
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(out/(name+'.map')).read_text(),re.M)}
        memory=cells(out/(name+'.s19'))
        return bytes(memory[a] for a in range(origin,sy[last])),sy
    tail,ts=assemble('store-loader',0x6A30,'ST_END')
    assert len(tail)<=208, f'Store tail {len(tail)} bytes overlaps its provider at6B00'
    (out/'store-tail.inc').write_text(f'STORE_TAIL_BYTES EQU ${len(tail):02X}\n')
    db(out/'store-tail-bytes.inc',tail)
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(s19/'s19-loader.map').read_text(),re.M)}
    (out/'s19-pins.inc').write_text(f'STORE_S19_DRAIN EQU ${sy["SL_DRAIN"]:04X}\n')
    front,fs=assemble('store-front',0x6D00,'SF_END')
    assert len(front)<=1022,f'Store frontend {len(front)} exceeds existing overlay padding'
    overlay=sl[:512]+front.ljust(1022,b'\xff')
    overlay+=binascii.crc_hqx(overlay,65535).to_bytes(2,'big')
    assert len(overlay)==1536 and binascii.crc_hqx(overlay,65535)==0
    (out/'S19-STORE-6B00.bin').write_bytes(overlay)
    report=dict(status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',source_sha256=sources,
        F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,build_passes=1,
        S19_SHA256=sha(sl),PROGRAM_SHA256=sha(sp),tail_bytes=len(tail),front_bytes=len(front),
        free_bytes=1022-len(front),S19_code_unchanged=True,
        entries=dict(S19='6B08',STORE='6D08'),owner_RAM='0200-66FF untouched except requested S19 destinations',
        scratch='67C0 line,69D0 request,69F0 state,6A30-6AFF transient MON parser tail',
        PROGRAM_API='8=Store,9=preview; confirmed live YES; not BATCH',
        artifacts={'S19-STORE-6B00.bin':dict(bytes=len(overlay),sha256=sha(overlay))})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('tail_bytes','front_bytes','free_bytes','artifacts')},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--s19',type=Path,required=True);p.add_argument('--provider',type=Path,required=True)
    a=p.parse_args();build(a.out,a.s19,a.provider)
