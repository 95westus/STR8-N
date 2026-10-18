"""Exact-preimage RAM fixture/restore for physical recovery qualification."""
import argparse,json,shutil
from pathlib import Path
import migrate_v2 as u
import beta4_migration as m

BUILD=u.ROOT/'BUILD/v2-beta25-b24g34'

def prepare(root,source,final=None):
    root.mkdir(parents=True,exist_ok=False);prior_source=source/'prior-verified' if (source/'prior-verified').exists() else source
    shutil.copytree(prior_source,root/'prior-verified')
    prior=u.read(root/'prior-verified/manifest.json');assert prior['board']=='2604' and prior['repeat_verified']
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and u.sha(b)==prior['banks'][i]['sha256']
    target=[bytearray(b) for b in banks] if final is None else [bytearray((final/f'b{i}.bin').read_bytes()) for i in range(4)]
    if final is None:target[3][:0x7000]=b'\xff'*0x7000
    assert target[:3]==banks[:3] and target[3][0x7000:]==banks[3][0x7000:],'Only B3:8-E may change'
    meta=u.read(BUILD/'build.json');assert banks[3][0x7000:]==(BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    order=[(3,s) for s in (12,8,9,14,10,11,13)]
    mf=u.read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    expected=[bytearray(b) for b in banks];payloads=[]
    for n,(bank,sector) in enumerate(order):
        i=(sector-8)*4096;data=bytearray(target[bank][i:i+4096]);address=0
        if sector in (10,11) and m.slot_valid(data,sector<<4):data[31]=0xFF;address=(sector<<12)+31
        row=bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*n)));cells[mf['banks']+n]=bank;cells[mf['commits']+n]=4 if address else 0
        cells.update(dict(enumerate(address.to_bytes(2,'little')+b'\0\0',mf['commit_addresses']+4*n)))
        expected[bank][i:i+4096]=data
        if address:expected[bank][address-0x8000]=0
        payloads.append(data)
    assert expected==target
    out=root/'upgrade';out.mkdir();installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board='2604',version='2.0b25',generation=37,test_fixture='restore' if final else 'F-only',target_build=str(BUILD.relative_to(u.ROOT)),prior_directory='prior-verified',
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[u.sha(b) for b in banks],expected_hashes=[u.sha(b) for b in target],
        installer_sha256=u.sha(installer),build_sha256=u.sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=u.sha((BUILD/'migrator/manifest.json').read_bytes()),
        storage_update=True,commit_records=[],no_sram_format=True,fixed_f_preserved=True,erase_attempts=order)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(target):(out/f'expected-b{i}.bin').write_bytes(b)
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    print('PREPARED 2604',plan['test_fixture'],'seven B3 sectors; F/B0/B1/B2 preserved',flush=True)

def audit(root):
    plan=u.read(root/'upgrade/plan.json');meta=u.read(BUILD/'build.json');assert plan['board']=='2604' and plan['fixed_f_preserved']
    assert u.sha((BUILD/'build.json').read_bytes())==plan['build_sha256'] and u.sha((BUILD/'migrator/manifest.json').read_bytes())==plan['template_manifest_sha256']
    for n,h in meta['artifacts'].items():assert u.sha((BUILD/n).read_bytes())==h
    assert u.read(root/'upgrade/model-check.json')['fixed_f_and_other_banks_preserved']
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','install'));p.add_argument('--root',required=True,type=Path);p.add_argument('--source',type=Path);p.add_argument('--final',type=Path);a=p.parse_args()
    if a.stage=='prepare':prepare(a.root,a.source,a.final)
    else:u.deploy.BUILD=BUILD;u.deploy.audit=lambda:audit(a.root);u.deploy.install(a.root,'2604')
