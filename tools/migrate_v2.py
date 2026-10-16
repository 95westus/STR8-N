"""Source-aware, exact-backup migration. Hardware operations select one FTDI ID.

Legacy beta1 is identified but deliberately requires a separate conversion:
it has no inactive slot or bootable legacy fallback in the A/B layout.
"""
import argparse, hashlib, json, binascii
from pathlib import Path
import beta4_migration as m
import update_v2_beta24 as deploy

ROOT=deploy.ROOT
read=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
CATALOG=('v2-beta4','v2-compact-boot','v2-board-name','v2-startup-keys','v2-startup-fifo','v2-beta25','v2-beta25-b23','v2-beta25-b24g34')

def identify(banks,active):
    assert len(banks)==4 and all(len(b)==32768 for b in banks)
    f=banks[3][0x7000:]; legacy=m.LEGACY_F.get(sha(f)) or m.LEGACY_F.get(sha(f[:0xFD0]+b'\xff'*16+f[0xFE0:]))
    if legacy:
        return dict(version=legacy[0],route='legacy-conversion-required',inactive_slot=False,
                    bootable_source_fallback=False,conversion_tool='tools/beta4_migration.py',
                    execution_qualified=False,reason='Legacy layout requires conversion; inactive-only update is unavailable')
    assert active in (0xA0,0xB0)
    off=(active-0x80)*256;slot=banks[3][off:off+4096]
    assert m.slot_valid(slot,active),'Active monitor is not valid'
    core=[];monitor=[]
    for name in CATALOG:
        folder=ROOT/'BUILD'/name
        if not (folder/'build.json').exists():continue
        meta=read(folder/'build.json')
        if f==(folder/'str8n-v2-recovery-f000-ffff.bin').read_bytes():core.append((folder,meta))
        if slot==(folder/f'str8n-v2-recovery-slot-{active:02x}.bin').read_bytes():monitor.append((folder,meta))
    for folder,meta in monitor:
        for corefolder,cm in core:
            if meta['boot_compatibility']==cm['boot_compatibility'] and meta['boot']['BOOT_SLOT_CHECK']==cm['boot']['BOOT_SLOT_CHECK']:
                return dict(version=meta['version'],generation=meta['generation'],source_build=str(folder.relative_to(ROOT)),
                    core_build=str(corefolder.relative_to(ROOT)),route='inactive-monitor',active_page=active,
                    inactive_page=active^0x10,bootable_source_fallback=True,abi_token=meta['boot_compatibility'])
    raise ValueError('Unregistered core/active-monitor pair; no writes permitted')

def prepare(root,board,build):
    root=Path(root);prior=read(root/'prior-verified/manifest.json')
    state=read(root/'initial-state.json');assert prior['repeat_verified'] and prior['board']==board
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==prior['banks'][i]['sha256']
    source=identify(banks,state['active_page'])
    if source['route']!='inactive-monitor':raise ValueError(source['reason'])
    old=ROOT/source['source_build'];oldmeta=read(old/'build.json');active=source['active_page'];inactive=source['inactive_page']
    if build is None:
        names=('v2-beta25-b4-unified',) if source['version']=='2.0b4' else ('v2-beta25-b23','v2-beta25-b24-unified','v2-beta25-b24g34')
        candidates=[ROOT/'BUILD'/n for n in names]
        build=next((p for p in candidates if (p/'build.json').exists() and read(p/'build.json')['boot_compatibility']==source['abi_token']),None)
        if build is None:raise ValueError('Source recognized; build and qualify a target for this ABI before migration')
    build=Path(build).resolve();meta=read(build/'build.json')
    if source['version']==meta['version'] and source['generation']>=meta['generation']:raise ValueError('Active monitor already at target; preserve fallback without writes')
    assert meta['generation']>source['generation'],'Target must be newer than the active monitor'
    assert meta['boot_compatibility']==source['abi_token'] and meta['boot']['BOOT_SLOT_CHECK']==oldmeta['boot']['BOOT_SLOT_CHECK']
    # Selecting the retained fallback does not make an already-installed target
    # old again. Refuse a redundant rewrite of that target and its shared core.
    installed=((3,(inactive-0x80)*256,f'str8n-v2-recovery-slot-{inactive:02x}.bin',4096),
        (3,0x6000,'str8n-v2-recovery-e000-efff.bin',4096),(3,0x7000,'str8n-v2-recovery-f000-ffff.bin',4096),
        (3,0,'str8n-rtc-component-8000-8fff.bin',4096),(3,0x1000,'str8n-journal-9000-9fff.bin',3072),
        (1,0,meta['maintenance_storage_file'],12288),(2,0x4800,'boot-status/asset.bin',meta['status_asset_bytes']),
        (2,0x6000,'local-display/asset.bin',meta['local_asset_bytes']))
    if all(banks[b][i:i+n]==(build/name).read_bytes()[:n] for b,i,name,n in installed):
        raise ValueError('Target already installed in inactive slot; preserve fallback and boot/promote the target')
    conversion={}
    if source['version']=='2.0b4':
        from migrate_v2_beta4 import convert
        final,order,commits,conversion=convert(banks,build,ROOT)
        for offset,name in ((0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin'),((inactive-0x80)*256,f'str8n-v2-recovery-slot-{inactive:02x}.bin')):
            final[3][offset:offset+4096]=(build/name).read_bytes()
        order.extend((3,s) for s in (8,9,14,15) if final[3][(s-8)*4096:(s-7)*4096]!=banks[3][(s-8)*4096:(s-7)*4096])
        order.append((3,inactive>>4));order.insert(0,(3,12));assert len(order)<=read(build/'migrator/manifest.json')['max_sectors']
    else:
        final=[bytearray(b) for b in banks]
        # Exact registered source ranges; retain all board-specific tails and data.
        for offset,name,size in ((0,'str8n-rtc-component-8000-8fff.bin',4096),(0x1000,'str8n-journal-9000-9fff.bin',3072)):
            assert banks[3][offset:offset+size]==(build/name).read_bytes()[:size],name
        for offset,name in ((0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin'),((inactive-0x80)*256,f'str8n-v2-recovery-slot-{inactive:02x}.bin')):
            if offset==0x6000:
                assert banks[3][offset:offset+4096] in ((old/name).read_bytes(),(build/name).read_bytes()),'Unregistered shared E; preserve custom native-app metadata'
            final[3][offset:offset+4096]=(build/name).read_bytes()
        for offset,name in ((0x4800,'boot-status/asset.bin'),(0x6000,'local-display/asset.bin')):
            before=(old/name).read_bytes();after=(build/name).read_bytes()
            assert banks[2][offset:offset+len(before)]==before,name
            if len(after)>len(before):assert banks[2][offset+len(before):offset+len(after)]==b'\xff'*(len(after)-len(before))
            final[2][offset:offset+len(after)]=after
        before=(old/oldmeta['maintenance_storage_file']).read_bytes();after=(build/meta['maintenance_storage_file']).read_bytes()
        # A mixed source may already use the target shared MAINT.
        assert banks[1][:len(before)]==before or banks[1][:len(after)]==after,'Unregistered shared MAINT'
        assert len(after)==12288;final[1][:len(after)]=after
        order=[]
        if final[1]!=banks[1]:order.extend(((1,10),(1,9),(1,8)))
        for bank,sector in ((2,12),(2,13),(2,14),(3,14),(3,15)):
            i=(sector-8)*4096
            if final[bank][i:i+4096]!=banks[bank][i:i+4096]:order.append((bank,sector))
        order.append((3,inactive>>4));order.insert(0,(3,12));assert len(order)<=16
        commits={(1,8):[0x8003]} if (1,8) in order else {}
    journal=m.journal(banks[3]);assert journal
    cfg=bytearray(journal[8:24]);assert cfg[14:]==m.config_sum(cfg)
    if source['version']=='2.0b4':
        m.clean_config(bytes(cfg)) # Validate the published startup schema without rewriting it.
        assert not(cfg[1] and cfg[6]==0 and 0x6500<=int.from_bytes(cfg[3:5],'little')<0x6700), 'Autostart overlaps new service RAM'
        assert cfg[13] in (0,0xA5), 'Unknown reserved configuration tag'
    cfg[7]=ord('P');cfg[8]=inactive;cfg[9:13]=meta['generation'].to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)];beforecounts=counts[:]
    for bank,sector in order:
        idx=bank*8+sector-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(journal[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    start=(active-0x80)*256
    assert final[3][start:start+4096]==banks[3][start:start+4096] and final[0]==banks[0]
    mf=read(build/'migrator/manifest.json');assert mf.get('mixed_commit_values'),'Use qualified mixed-commit template'
    cells,entry=m.read_s19(build/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    expected=[bytearray(b) for b in banks];payloads=[];records=[]
    for i,(bank,sector) in enumerate(order):
        offset=(sector-8)*4096;data=bytearray(final[bank][offset:offset+4096])
        addresses=commits.get((bank,sector),[])
        assert len(addresses)<=2
        for address in addresses:
            data[address-0x8000-offset]=0xFF;records.append(dict(bank=bank,address=address-3))
        if (bank,sector)==(3,inactive>>4):
            addresses=[(inactive<<8)+31];data[31]=0xFF
        row=bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=bank;cells[mf['commits']+i]=bank+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),mf['commit_addresses']+4*i)))
        expected[bank][offset:offset+4096]=data
        for address in addresses:expected[bank][address-0x8000]=0 if bank==3 else 63
        payloads.append(data)
    assert expected==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=board,version=meta['version'],generation=meta['generation'],source=source,source_generation=source['generation'],
        target_build=str(build.relative_to(ROOT)),prior_directory='prior-verified',steps=[dict(bank=b,sector=s) for b,s in order],
        prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),
        build_sha256=sha((build/'build.json').read_bytes()),config=cfg.hex(),counts_before=beforecounts,counts_after=counts,
        storage_update=True,commit_records=records,no_sram_format=True,active_fallback=chr(active//16-10+65),
        updated_slot=chr(inactive//16-10+65),fallback_sha256=sha(banks[3][start:start+4096]),
        monitor_commit=dict(bank=3,address=(inactive<<8)+31,value=0),initial_f_install_power_loss_safe=False)
    plan.update(conversion)
    plan['template_manifest_sha256']=sha((build/'migrator/manifest.json').read_bytes())
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    print('PREPARED',board,source['version'],'->',meta['version'],'fallback',plan['active_fallback'],'updated',plan['updated_slot'],len(order),'sectors',flush=True)

def audit(root,build):
    meta=read(build/'build.json');plan=read(root/'upgrade/plan.json')
    assert not plan.get('model_only'), 'Projected model fixtures cannot be installed'
    if plan.get('layout_conversion'):
        kit=ROOT/'BUILD/v2-beta4/kit';m.validate_kit(kit)
        assert sha((kit/'manifest.json').read_bytes())==plan['published_kit_sha256']
    assert sha((build/'build.json').read_bytes())==plan['build_sha256']
    assert sha((build/'migrator/manifest.json').read_bytes())==plan['template_manifest_sha256']
    for n,h in meta['artifacts'].items():assert sha((build/n).read_bytes())==h,n
    f=bytearray((build/'str8n-v2-recovery-f000-ffff.bin').read_bytes());i=meta['boot']['BOOT_COMPAT_DATA']-0xF000
    assert int.from_bytes(f[i:i+4],'little')==meta['boot_compatibility']
    f[i:i+4]=bytes(4);assert binascii.crc32(f)&0xFFFFFFFF==meta['boot_identity_crc32']
    for page in ('a0','b0'):assert meta['monitors'][page]['BOOT_SLOT_CHECK']==meta['boot']['BOOT_SLOT_CHECK']
    for field,folder in (('local_asset_sha256','local-display'),('status_asset_sha256','boot-status')):assert sha((build/folder/'asset.bin').read_bytes())==meta[field]
    for name in ('f-only-bootstrap','f-only-fault','apps','time-local','startup-fifo','storage-transfer'):
        r=read(build/(name+'-test-results.json'));assert r['passed'] and r['artifacts']==meta['artifacts'],name
        for field in ('local_asset_sha256','status_asset_sha256','bootstrap_utility_sha256'):
            if field in r:assert r[field]==meta[field],(name,field)
    check=read(root/'upgrade/model-check.json');assert check['fallback_unchanged'] and check['monitor_commit_verified_last']
    mixed=root/'upgrade/mixed-slot-test-results.json'
    if not mixed.exists():mixed=build/'mixed-slot-test-results.json'
    result=read(mixed)
    assert result['passed'] and result['artifacts']==meta['artifacts'] and result['expected_hashes']==plan['expected_hashes']
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('inspect','prepare','audit','install'));p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--build',type=Path)
    a=p.parse_args();root=a.root.resolve()
    if a.stage=='inspect':print(json.dumps(identify([(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)],read(root/'initial-state.json')['active_page']),indent=2))
    elif a.stage=='prepare':prepare(root,a.board,a.build.resolve() if a.build else None)
    else:
        build=ROOT/read(root/'upgrade/plan.json')['target_build'];audit(root,build)
        if a.stage=='install':deploy.BUILD=build;deploy.audit=lambda:audit(root,build);deploy.install(root,a.board)
