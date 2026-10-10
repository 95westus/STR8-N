"""Backup-bound beta15 -> beta17 recipes, with no DEMO/DEMO2 installation."""
import argparse,hashlib,json
from pathlib import Path
import beta4_migration as m
from build_v2_spi_resident import merge_identity_tail
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-storage';OLD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def records(image):
    i=0
    while i+24<=0x6000:
        h=image[i:i+24];n=int.from_bytes(h[6:8],'little');load=int.from_bytes(h[4:6],'little')
        if h[:3]==b'SR\x01' and h[3] in (63,255) and n and 0x200<=load and load+n<=0x6700 and i+24+n<=0x6000:
            yield i,h[8:24].rstrip(b'\0').decode('ascii'),n,load,h[3];i+=24+n
        else:i+=1

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=('2512','2205','2609'));a=p.parse_args()
    prior=read(a.root/'prior/manifest.json');assert prior['repeat_verified'] and prior['board']==a.board
    banks=[(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(a.root/f'prior/b{i}-repeat.bin').read_bytes() and sha(b)==prior['banks'][i]['sha256']
    meta=read(BUILD/'build.json');check=read(BUILD/'storage-candidate-check.json');assert check['passed'] and check['artifacts']==meta['artifacts']
    source=((0,'str8n-rtc-component-8000-8fff.bin'),(0x1000,'str8n-journal-9000-9fff.bin'),(0x2000,'str8n-v2-recovery-slot-a0.bin'),(0x3000,'str8n-v2-recovery-slot-b0.bin'),(0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin'))
    for offset,name in source:
        n=3072 if offset==0x1000 else 4096;assert banks[3][offset:offset+n]==(OLD/name).read_bytes()[:n],name
    assert banks[1][:8192]==(OLD/'str8n-maint-1.7-b1-8000-9fff.bin').read_bytes()
    assert banks[1][8192:12288]==b'\xff'*4096,'MAINT third sector occupied'
    final=[bytearray(b) for b in banks];removed=[];moved=[]
    mm=read(BUILD/'maint/manifest.json');final[1][:12288]=(BUILD/mm['storage_file']).read_bytes();b2=final[2]
    paths={'SRAM':('store/sram.bin',0x2000),'WORK':('workspace/workspace.bin',0x3000),'EDU':('edu/edu.bin',0x4600)}
    found=set()
    for i,name,n,load,marker in records(banks[2]):
        if name in paths:
            path,offset=paths[name];assert name not in found and marker==63 and i==offset and bytes(b2[i+24:i+24+n])==(OLD/path).read_bytes(),name
            b2[i:i+24+n]=b'\xff'*(24+n);found.add(name)
        elif name in ('DEMO','DEMO2'):
            b2[i:i+24+n]=b'\xff'*(24+n);removed.append(dict(name=name,address=0x8000+i,bytes=24+n))
        elif name=='SDEMO' and i==0x2E80:
            body=bytes(b2[i:i+24+n]);target=0x2F80;assert n==6 and b2[target:target+len(body)]==b'\xff'*len(body)
            b2[i:i+len(body)]=b'\xff'*len(body);b2[target:target+len(body)]=body;moved.append(dict(name=name,old=0x8000+i,new=0x8000+target))
    assert found==set(paths)
    for name,address,path,start in (('SRAM',0xA000,'store/sram.bin',0x4000),('WORK',0xB000,'workspace/workspace.bin',0x5000),('EDU',0xC580,'edu/edu.bin',0x2000)):
        body=(BUILD/path).read_bytes();r=b'SR\x01\x3F'+start.to_bytes(2,'little')+len(body).to_bytes(2,'little')+name.encode().ljust(16,b'\0')+body;i=address-0x8000
        assert b2[i:i+len(r)]==b'\xff'*len(r),('overlap',name);b2[i:i+len(r)]=r
    assert b2[0x4800:0x5000]==b'\xff'*2048,'Shared asset overlap'
    b2[0x4800:0x5000]=(BUILD/'boot-status/asset.bin').read_bytes()
    final[3][:4096]=(BUILD/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    final[3][4096:8192]=merge_identity_tail(banks[3][4096:8192],(BUILD/'str8n-journal-9000-9fff.bin').read_bytes())
    for page,name in ((14,'str8n-v2-recovery-e000-efff.bin'),(11,'str8n-v2-recovery-slot-b0.bin'),(10,'str8n-v2-recovery-slot-a0.bin')):final[3][(page-8)*4096:(page-7)*4096]=(BUILD/name).read_bytes()
    order=[(1,8),(1,9),(1,10),(2,10),(2,11),(2,12)]
    for page in (8,9):
        if final[3][(page-8)*4096:(page-7)*4096]!=banks[3][(page-8)*4096:(page-7)*4096]:order.append((3,page))
    order.extend(((3,14),(3,11),(3,10)));order.insert(0,(3,12));assert len(order)<=16
    j=m.journal(banks[3]);assert j is not None;cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg) and cfg[13]==(0xA5 if a.board=='2512' else 0)
    if cfg[7]==ord('P'):cfg[9:13]=meta['generation'].to_bytes(4,'little')
    cfg[14:]=m.config_sum(cfg);counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for b,s in order:idx=b*8+s-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[3][0x7000:]==banks[3][0x7000:] and final[3][0x1C00:0x2000]==banks[3][0x1C00:0x2000]
    assert not [r for r in records(final[2]) if r[1] in ('DEMO','DEMO2')]
    mf=read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    stage=[bytearray(b) for b in final];pending=((1,0x8003),(2,0xA003),(2,0xB003),(2,0xC583))
    for b,address in pending:stage[b][address-0x8000]=255
    commits={(1,10):[0x8003],(2,10):[0xA003],(2,12):[0xB003,0xC583]};expected=[bytearray(b) for b in banks];payload=[];commit_records=[]
    for i,(b,s) in enumerate(order):
        offset=(s-8)*4096;data=bytes(stage[b][offset:offset+4096]);row=bytes((s<<4,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos,v in enumerate(row,mf['table']+9*i):cells[pos]=v
        addresses=commits.get((b,s),[]);cells[mf['banks']+i]=b;cells[mf['commits']+i]=b+1 if addresses else 0
        for slot in range(2):
            value=addresses[slot] if slot<len(addresses) else 0;cells[mf['commit_addresses']+4*i+slot*2]=value&255;cells[mf['commit_addresses']+4*i+slot*2+1]=value>>8
        expected[b][offset:offset+4096]=data
        for address in addresses:expected[b][address-0x8000]=63;commit_records.append(dict(bank=b,address=address-3))
        payload.append(data)
    assert expected==final
    out=a.root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,version=meta['version'],generation=meta['generation'],steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),config=cfg.hex(),counts_before=before,counts_after=counts,storage_update=True,banner_update=True,journal_update=False,clock_update=False,clock_build=str(BUILD/'clock'),clock_sha256=read(BUILD/'clock/build.json')['sha256'],commit_records=commit_records,removed_records=removed,moved_records=moved,no_sram_format=True,edu_mode='OFF' if a.board=='2512' else 'ON')
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(final):(out/f'expected-b{b}.bin').write_bytes(data)
    print('PREPARED',a.board,len(order),'guarded sectors; DEMO/DEMO2 omitted; four complete records committed last')

if __name__=='__main__':main()
