"""Source-build separate beta35 A/B monitor variants; never edit the frozen kit.

The B variant must reproduce the sealed B payload exactly. The A variant only
changes the declared image page and linked origin, then seals the same ABI-1
monitor header at generation 47. Neither output authorizes installation.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'release/beta35'
sys.path.insert(0,str(SOURCE))
from build import SR_CALLS,db,read_s19,s19,crc
sha=lambda data:hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path);args=p.parse_args();out=args.out.resolve()
    assert not out.exists() and len(str(out))<=65,'Choose a new short output path'
    meta=json.loads((SOURCE/'release.json').read_text())
    provenance=json.loads((SOURCE/'source-provenance.json').read_text())
    for name,info in provenance.items():assert sha((SOURCE/name).read_bytes())==info['sha256'],name
    out.mkdir(parents=True);stage=out/'asm';shutil.copytree(SOURCE/'source/core',stage)
    shutil.copyfile(SOURCE/'source/batch/batch-gate.asm',stage/'batch-gate.asm')
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln');assert assembler and linker
    links=[];maps={}
    def assemble(name,address,end):
        log=[]
        for command in [[assembler,'-G','-L','-S','-W','-I',str(stage),name+'.asm'],
                        [linker,'-g','-s','-t',f'-c{address:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']]:
            r=subprocess.run(command,cwd=stage,capture_output=True,text=True)
            log.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            (stage/(name+'.log.json')).write_text(json.dumps(log,indent=2)+'\n')
            assert r.returncode==0,(name,r.stdout,r.stderr)
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(stage/(name+'.map')).read_text(),re.M)}
        cells=read_s19(stage/(name+'.s19'));assert set(cells)==set(range(address,sy[end]))
        body=bytes(cells[a] for a in range(address,sy[end]));maps[name]=sy
        links.append(dict(name=name,address=address,end=sy[end],bytes=len(body),sha256=sha(body)))
        return body,sy
    assemble('str8n-v2-worker',0x7800,'V2W_END')
    assemble('str8n-v2-vectors',0x7E20,'V2V_END')
    batch,_=assemble('batch-gate',0x7C90,'B29_GATE_END');assert len(batch)<=96
    db(stage/'batch-gate.inc',batch+b'\xEA'*(96-len(batch)))
    messages=json.loads((stage/'text.json').read_text());prefix=next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    pool=bytearray()
    for i,message in enumerate(messages):
        raw=bytearray(message['text'].replace('{version}','2.0b35').encode('ascii'))
        if i<prefix:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    db(stage/'text-image.inc',pool,'V2_TEXT:\n')
    base=(stage/'monitor-b0.asm').read_text();assert base.count('V2_IMAGE_PAGE EQU $B0')==1
    artifacts={}
    for page in (0xB0,0xA0):
        name=f'monitor-{page:02x}'
        (stage/(name+'.asm')).write_text(base.replace('V2_IMAGE_PAGE EQU $B0',f'V2_IMAGE_PAGE EQU ${page:02X}',1),encoding='ascii')
        body,symbols=assemble(name,(page<<8)+128,'V2_END');assert len(body)<=3968
        image=bytearray(b'\xff'*4096);image[:8]=b'MI\x01'+bytes([page,3,1,0,0]);image[8:12]=(47).to_bytes(4,'little')
        for offset,value in [(12,len(body)),(14,symbols['START']),(16,symbols['V2_PROMPT_ENTRY'])]:image[offset:offset+2]=value.to_bytes(2,'little')
        image[20:24]=meta['boot_compatibility'].to_bytes(4,'little')
        for i,n in enumerate(SR_CALLS):image[32+2*i:34+2*i]=symbols[n].to_bytes(2,'little')
        image[70:72]=symbols['V2_M_EDIT'].to_bytes(2,'little');image[128:128+len(body)]=body
        image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little');image[31]=0
        filename=f'str8n-v2-beta35-slot-{page:02x}.bin';(out/filename).write_bytes(image)
        (out/filename.replace('.bin','.s19')).write_bytes(s19(image,page<<8,0xF004))
        artifacts[filename]=dict(sha256=sha(image),bytes=len(image),page=page,generation=47)
        if page==0xB0:assert artifacts[filename]==dict(meta['expected']['str8n-v2-recovery-slot-b0.bin'],page=page,generation=47)
    assert maps['monitor-b0']['BOOT_SLOT_CHECK']==maps['monitor-a0']['BOOT_SLOT_CHECK']==0xF30D
    report=dict(version='2.0b35',generation=47,passed=True,source_only=True,binary_inputs=[],fresh_links=links,
        B_matches_frozen_payload=True,installation_permitted=False,model_qualified=False,
        original_candidate_build_sha256=meta['candidate_build_sha256'],artifacts=artifacts,
        source_files={n:i['sha256'] for n,i in provenance.items()},
        source_transform='Only V2_IMAGE_PAGE B0 -> A0 and linker origin B080 -> A080 for A variant',
        toolchain={Path(t).name:sha(Path(t).read_bytes()) for t in [assembler,linker]},
        builder_sha256=sha(Path(__file__).read_bytes()))
    (out/'symbols.json').write_text(json.dumps(maps,indent=2)+'\n')
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS 5 fresh links; B image byte-exact; separate A35 extension built, model qualification pending')


if __name__=='__main__':main()
