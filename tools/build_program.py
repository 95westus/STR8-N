"""Build only the PROGRAM provider; no F rebuild, CPU model or board access."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha
from mona_branches import conservative_branches

def build(out,generation=3):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);stage=out/'staging';stage.mkdir()
    files=['program-provider.asm','program-layout.inc','program-layout-check.inc','program-spi.inc','workbench-layout.inc','workbench-interface.inc','batch-interface.inc','monitor-ui.inc']
    sources={}
    for name in files:
        p=ROOT/'monitors/src'/name;sources['monitors/src/'+name]=sha(p.read_bytes())
        body=p.read_text()
        if name not in ('program-layout.inc','workbench-layout.inc','workbench-interface.inc'):
            body,_=conservative_branches(body,'SP_LONG_'+name.replace('.','_').replace('-','_')+'_')
        (stage/name).write_text(body,encoding='utf-8',newline='\n')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','program-provider.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c6B00','-hm19','-j','-o','program-provider.s19','program-provider.obj']):
        r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('WDC failed; inspect '+str(out/'build-log.json'))
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'program-provider.map').read_text(),re.M)}
    m=cells(stage/'program-provider.s19');assert set(m)==set(range(0x6b00,symbols['SP_END']))
    body=bytes(m[a] for a in range(0x6b00,symbols['SP_END']))
    assert len(body)<=3326,'Provider exceeds its CRC trailer at77FE'
    assert body[:8]==b'SP\x01\x0dPR05'
    image=body+b'\xff'*(3326-len(body));image+=binascii.crc_hqx(image,65535).to_bytes(2,'big')
    assert binascii.crc_hqx(image,65535)==0
    name='STR8N-PROGRAM-SP1-6B00.bin';(out/name).write_bytes(image)
    report=dict(component='PROGRAM provider',generation=f'{generation:08X}',status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',
                artifact=dict(filename=name,sha256=sha(image),bytes=len(image),linked_bytes=len(body),free_bytes=3326-len(body)),
                source_sha256=sources,entries={k:f'{symbols[k]:04X}' for k in ['API','SP_READ64','W_SPI_GUARD']},
                origin='6B00',end_exclusive='7800',F_rebuilt=False,CPU_simulations=0,build_passes=1,assembler_linker_invocations=len(logs),
                wide_restore='SW/1/1 op6=load-only, op7=run; 0200-66FF; resident tail after copying; pre-copy CRC and per-chunk cancellation',
                wide_store='op8=Store, op9=preview; original0200-66FF source; internal request69D0; caller must not load WB over source first',
                batch_registration='BT/1/2 PR05 entry prefix; public HOLD return; wide load-only must be final',
                format='SS1/SS2 primary; SP/01 slots, CRC/commit last; no format/delete/reclaim',
                writes='PROGRAM directory0040-023F or payload0800-boundary only; no mode write or WORKSPACE write')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['artifact'],indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--generation',type=lambda s:int(s,0),default=3);a=p.parse_args();build(a.out,a.generation)
