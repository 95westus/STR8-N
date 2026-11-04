"""Retarget the private read-only PB helper; never build installed firmware."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha

def build():
    out=ROOT/'BUILD/SRAM-reader-current-r2';out.mkdir(exist_ok=False);stage=out/'source';stage.mkdir()
    old=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source'
    source=(old/'sram-bench.asm').read_text()
    start=source.index('Q_WRITE:\n');end=source.index('Q_READ:\n',start)
    source=source[:start]+'Q_WRITE:\n        JMP Q_BAD_FRAME\n'+source[end:]
    (stage/'sram-bench.asm').write_text(source)
    for name in ('str8n-v2-public.inc','workbench-layout.inc','workbench-interface.inc','program-layout.inc'):
        shutil.copyfile(old/name,stage/name)
    provider=(REPO/'monitors/candidates/program-sp1-g00000002-wide-r5/STR8N-PROGRAM-SP1-6B00.bin').read_bytes()
    manifest=json.loads((REPO/'monitors/candidates/program-sp1-g00000002-wide-r5/manifest.json').read_text())
    assert sha(provider)==manifest['artifact']['sha256']
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(ROOT/'BUILD/program-sp1-g2-wide-r5/staging/program-provider.map').read_text(),re.M)}
    f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f)==json.loads((REPO/'F_FREEZE.json').read_text())['sha256']
    crc=binascii.crc_hqx(f,65535)
    values=dict(BENCH_F_LO=crc&255,BENCH_F_HI=crc>>8,BENCH_PV_HI=provider[-2],BENCH_PV_LO=provider[-1],
        BENCH_TRANSFER=sy['SP_TRANSFER'],BENCH_LIMIT=0,BENCH_ALLOW_BYTES=0)
    (stage/'sram-bench-params.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in values.items()))
    (stage/'sram-bench-allow.inc').write_text('        DB 0\n')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
        assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:raise RuntimeError('Helper assembly failed; see build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
    memory=cells(stage/'sram-bench.s19');body=bytearray(memory[a] for a in range(0x200,sy['Q_END']))
    pos=sy['Q_IMAGE_CRC']-0x200;body[pos:pos+2]=binascii.crc_hqx(body[:pos],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(body,65535)==0 and len(body)<0x1000
    name='SRAM-READ-ONLY-CURRENT-RAM.bin';(out/name).write_bytes(body)
    record=dict(filename=name,sha256=sha(body),bytes=len(body),provider_sha256=sha(provider),
        F_sha256=sha(f),installed_firmware_builds=0,helper_build_passes=1,write_command='refused; no compiled write allowance',
        prior_attempt='r1 stopped before assembly: missing transitive workbench-interface.inc include',status='BUILD_ONLY_PENDING_LIVE_READ')
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':build()
