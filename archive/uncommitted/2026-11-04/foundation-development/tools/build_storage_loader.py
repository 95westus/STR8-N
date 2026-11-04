"""Build only the extended native loader; preserve F and existing apps."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_native_apps import ROOT,normalized,sealed,sha
from build import cells
from mona_branches import conservative_branches

def build(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    paths=[p.relative_to(ROOT).as_posix() for p in (ROOT/'src/include').glob('*.inc')]+['src/core/vectors-symbols.inc','src/core/boot-symbols.inc']
    sources={}
    for n in paths:
        p=ROOT/n;sources[n]=sha(p.read_bytes());(out/p.name).write_bytes(p.read_bytes())
    p=ROOT/'monitors/native/native-loader.asm';sources[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    source,branches=conservative_branches(normalized(p.read_text()),'NL_STORAGE_LONG_')
    (out/p.name).write_text(source)
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','native-loader.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c7000','-hm19','-j','-o','native-loader.s19','native-loader.obj']):
        assert cmd[0];r=subprocess.run(cmd,cwd=out,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('Loader build failed; see build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(out/'native-loader.map').read_text(),re.M)}
    memory=cells(out/'native-loader.s19');raw=bytes(memory[a] for a in range(0x7000,sy['NL_END']))
    image=sealed(raw,1024);assert image[:8]==b'NL\x01\x05PR05'
    names={}
    def emit(name,body):
        (out/name).write_bytes(body);names[name]=dict(bytes=len(body),sha256=sha(body))
    emit('NATIVE-LOADER-storage-7000.bin',image)
    for kind,label in ((3,'SRAM'),(4,'WORK')):
        # Raw probe exercises absent/wrong-kind flash admission before install.
        prefix=bytes.fromhex('78 D8 A2 00 BD 00 03 9D 00 70 BD 00 04 9D 00 71 BD 00 05 9D 00 72 BD 00 06 9D 00 73 E8 D0 E5 A9')+bytes([kind])+bytes.fromhex('4C 08 70')
        emit(f'NATIVE-LOADER-probe-{label}-RAM.bin',prefix.ljust(256,b'\xFF')+image)
    r=dict(status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',source_sha256=sources,artifacts=names,
        linked_bytes=len(raw),free_bytes=1022-len(raw),header='NL 01 05 PR05',kinds=['CLOCK','FLASH','MAINT','SRAM','WORK'],
        storage_image='One RP/1 kind3 image at B1:B-D for both storage menus; target review required',
        F_sha256=freeze['sha256'],F_rebuilt=False,build_passes=1,CPU_simulations=0,hardware_access=False,branches=branches)
    (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ('linked_bytes','free_bytes','header')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out)
