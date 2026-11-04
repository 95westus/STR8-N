"""Relink only E and pack gate/worker into existing BANK MAINT padding."""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil
import subprocess
from build_mona import ROOT, cells, sha
from mona_branches import conservative_branches


def build(out, transfer, support, maint,reuse_dispatch=None):
    out,transfer,support,maint=map(lambda p:Path(p).resolve(),(out,transfer,support,maint))
    if out.exists():raise ValueError('Fresh output directory required')
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    tm=json.loads((transfer/'manifest.json').read_text());mm=json.loads((maint/'manifest.json').read_text())
    def artifact(folder,manifest,name):
        data=(folder/name).read_bytes();assert sha(data)==manifest['artifacts'][name]['sha256'];return data
    worker=artifact(transfer,tm,'FLASH-RECORD-6B00.bin')
    gate=artifact(transfer,tm,'FLASH-TRANSFER-GATE-7300.bin')
    flash=artifact(transfer,tm,'FLASH-S19-flash.bin')
    bank=bytearray(artifact(maint,mm,'BANK-MAINT-g00000001-flash.bin'))
    assert len(worker)==2048 and len(gate)==1024
    assert int.from_bytes(bank[8:10],'little')+32<=0x2380
    assert bank[0x2380:-2]==b'\xff'*(len(bank)-0x2380-2)
    bank[0x2380:0x2780]=gate  # A380-A77F
    bank[0x27C0:0x2FC0]=worker  # A7C0-AFBF; leave RP's own CRC separate
    bank[-2:]=binascii.crc_hqx(bank[:-2],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(bank,65535)==0
    out.mkdir(parents=True)
    stage=out/'staging';stage.mkdir()
    prior=support/'staging/E'
    for path in prior.iterdir():
        if path.suffix in ('.asm','.inc'):shutil.copyfile(path,stage/path.name)
    changed=('services.asm','service-flash-transfer.inc')
    loader_len=len(re.findall(r'\$[0-9A-Fa-f]{2}',(prior/'service-load-image.inc').read_text()))
    assert 256<loader_len<=512
    for name in changed:
        text=(ROOT/'monitors/src'/name).read_text()
        text=text.replace('"WORKBENCH_GENERATION_BYTES"','$0D,$00,$00,$00')
        text=text.replace('SERVICE_LOADER_TAIL',str(loader_len-256))
        text,_=conservative_branches(text,'FT_E_'+name.replace('.','_').replace('-','_')+'_')
        (stage/name).write_text(text)
    logs=[]
    prior_E=None
    if reuse_dispatch:
        prior_E=Path(reuse_dispatch).resolve();old_E=json.loads((prior_E/'manifest.json').read_text())
        assert old_E['source_sha256']=={'monitors/src/'+n:sha((ROOT/'monitors/src'/n).read_bytes()) for n in changed}
        assert old_E['support_source_sha256']=={p.name:sha(p.read_bytes()) for p in prior.iterdir() if p.suffix in ('.inc','.asm')}
    commands=[] if prior_E else ([shutil.which('wdc02as'),'-G','-L','-S','-W','services.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-cE000','-hm19','-j','-o','services.s19','services.obj'])
    for cmd in commands:
        assert cmd[0];r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('Build failed; inspect build-log.json')
    if prior_E:
        old_image=(prior_E/'FLASH-DISPATCH-E.bin').read_bytes()
        assert sha(old_image)==old_E['artifacts']['FLASH-DISPATCH-E.bin']['sha256']
        body=old_image[:old_E['E_linked_bytes']]
    else:
        symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'services.map').read_text(),re.M)}
        memory=cells(stage/'services.s19');body=bytes(memory[a] for a in range(0xE000,symbols['S_END']))
    assert len(body)<=4094, f'E body {len(body)} exceeds sector'
    image=body.ljust(4094,b'\xff');image+=binascii.crc_hqx(image,65535).to_bytes(2,'big')
    artifacts={}
    for name,data in (('FLASH-DISPATCH-E.bin',image),('BANK-MAINT-with-transfer.bin',bytes(bank)),('FLASH-S19-flash.bin',flash)):
        (out/name).write_bytes(data);artifacts[name]=dict(bytes=len(data),sha256=sha(data))
    report=dict(status='BUILD_ONLY_NOT_INSTALLED',F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,
        source_sha256={'monitors/src/'+n:sha((ROOT/'monitors/src'/n).read_bytes()) for n in changed},
        support_source_sha256={p.name:sha(p.read_bytes()) for p in prior.iterdir() if p.suffix in ('.inc','.asm')},
        transfer_manifest=str(transfer/'manifest.json'),artifacts=artifacts,E_linked_bytes=len(body),E_free_bytes=4094-len(body),
        BANK_MAINT_body_unchanged=True,MON_A_B_unchanged=True,PROGRAM_WB_STATUS_CLOCK_unchanged=True,
        source_allocations=['B1:A380-A77F gate','B1:A7C0-AFBF high records'],
        image_targets=['B1:A','B2:E','B2:F','B3:E'],
        native_routes=['S19','STORE/S P','STORE/S 0|1','RESTORE/R 0|1 name [L]','R FLASH; BANK 0|1; I first last'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS E body {len(body)}, free{4094-len(body)}; existing BANK MAINT body unchanged; no F rebuild')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('out','transfer','support','maint'):p.add_argument('--'+name,required=True)
    p.add_argument('--reuse-dispatch')
    a=p.parse_args();build(a.out,a.transfer,a.support,a.maint,a.reuse_dispatch)
