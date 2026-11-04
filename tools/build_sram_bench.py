"""Build a qualification-only SRAM restore tool from exact backed-up blocks."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha
from program_format import inspect
from mona_branches import conservative_branches

def build(out,snapshot,provider_manifest,duplicate_slot=None):
    out=Path(out).resolve();snapshot=Path(snapshot).resolve();pvpath=Path(provider_manifest).resolve()
    if out.exists() or not out.is_relative_to(ROOT.parents[1]/'output/qualification'):raise ValueError('Fresh private qualification directory required')
    memory=snapshot.read_bytes();layout=inspect(memory)
    slots=[s['slot'] for s in layout['free_slots']]
    if slots!=[0,1,2,3,4] or any(f'{p:02X}' not in layout['free_pages'] for p in [0x90,0x91,0x92,0x93,0xa0]):
        raise ValueError('Review actual slot/page scope before building this target-specific restorer')
    blocks=sorted([64*(s+1) for s in slots]+[0x9000+n*64 for n in range(4)]+[0x9100,0x9200,0x9300,0xa000])
    retirement=None
    if duplicate_slot is not None:
        victim=next(r for r in layout['records'] if r['slot']==duplicate_slot)
        if victim['kind']!=1 or not victim['payload_CRC_valid'] or layout['latest'][victim['name']]['slot']==duplicate_slot:
            raise ValueError('Only a superseded committed valid payload may be retired')
        copies=[r for r in layout['records'] if r['slot']!=duplicate_slot and r['kind']==1 and r['payload_CRC_valid']
                and r['length']==victim['length'] and r['payload_sha256']==victim['payload_sha256']]
        if not copies:raise ValueError('No retained exact payload copy')
        address=64*(duplicate_slot+1);blocks=sorted(blocks+[address])
        retirement=dict(slot=duplicate_slot,directory_address=f'{address:04X}',commit_address=f'{address+63:04X}',
                        original_commit='A5',retired_commit='00',retained_slots=[r['slot'] for r in copies],
                        payload_sha256=victim['payload_sha256'],payload_bytes_unchanged=True)
    pv=json.loads(pvpath.read_text());provider=(pvpath.parent/pv['artifact']['filename']).read_bytes()
    assert sha(provider)==pv['artifact']['sha256'] and binascii.crc_hqx(provider,65535)==0
    sym={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(pvpath.parent/'staging/program-provider.map').read_text(),re.M)}
    f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();freeze=json.loads((ROOT/'F_FREEZE.json').read_text());assert sha(f)==freeze['sha256']
    out.mkdir(parents=True);stage=out/'source';stage.mkdir()
    for name in ['sram-bench.asm']:
        src=ROOT/'tools/qualification'/name;s,_=conservative_branches(src.read_text(),'QB_LONG_');(stage/name).write_text(s)
    for name in ['workbench-layout.inc','workbench-interface.inc','program-layout.inc']:shutil.copyfile(ROOT/'monitors/src'/name,stage/name)
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    crc=binascii.crc_hqx(f,65535)
    params=dict(BENCH_F_LO=crc&255,BENCH_F_HI=crc>>8,BENCH_PV_HI=provider[-2],BENCH_PV_LO=provider[-1],
                BENCH_TRANSFER=sym['SP_TRANSFER'],BENCH_LIMIT=(int(layout['boundary'],16)//256)&255,BENCH_ALLOW_BYTES=len(blocks)*2)
    (stage/'sram-bench-params.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in params.items()))
    table=b''.join(a.to_bytes(2,'little') for a in blocks)
    (stage/'sram-bench-allow.inc').write_text('        DB '+','.join(f'${v:02X}' for v in table)+'\n')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
        r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('WDC failed; inspect '+str(out/'build-log.json'))
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
    m=cells(stage/'sram-bench.s19');assert set(m)==set(range(0x200,sy['Q_END'])) and sy['Q_END']<0x2000
    body=bytearray(m[a] for a in range(0x200,sy['Q_END']));offset=sy['Q_IMAGE_CRC']-0x200
    body[offset:offset+2]=binascii.crc_hqx(body[:offset],65535).to_bytes(2,'big');assert binascii.crc_hqx(body,65535)==0
    name='2512-PRIVATE-SRAM-RESTORE-RAM.bin';(out/name).write_bytes(body)
    original={f'{a:04X}':dict(sha256=sha(memory[a:a+64])) for a in blocks}
    for a in blocks:(out/f'original-{a:04X}.bin').write_bytes(memory[a:a+64])
    result=dict(board='2512',snapshot_sha256=sha(memory),provider_sha256=sha(provider),artifact=dict(filename=name,bytes=len(body),sha256=sha(body)),
                allowed_64_byte_writes=[f'{a:04X}' for a in blocks],blocks=original,source_sha256=sha(src.read_bytes()),
                primary_layout_unchanged=True,WORKSPACE_writes=False,flash_writes=False,mode_writes=False,hardware_access=False,
                build_passes=1,assembler_linker_invocations=2,duplicate_retirement=retirement)
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--provider-manifest',type=Path,required=True)
    p.add_argument('--duplicate-slot',type=int)
    a=p.parse_args();build(a.out,a.snapshot,a.provider_manifest,a.duplicate_slot)
