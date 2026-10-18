"""2609-only, exact-backup beta25 shared update plus one inactive monitor."""
import json,sys,hashlib,binascii
from pathlib import Path
import beta4_migration as m
import update_v2_beta24 as deploy

ROOT=deploy.ROOT;BUILD=ROOT/'BUILD/v2-beta25';OLD=ROOT/'BUILD/v2-startup-fifo'
BASE=ROOT/'output/qualification/beta25-2026-10-14';BOARD='2609'
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()

def audit():
    meta=read(BUILD/'build.json');assert (meta['version'],meta['generation'])==('2.0b25',37)
    for n,h in meta['artifacts'].items():assert sha((BUILD/n).read_bytes())==h,n
    for field,folder in (('local_asset_sha256','local-display'),('status_asset_sha256','boot-status')):
        assert sha((BUILD/folder/'asset.bin').read_bytes())==meta[field]
    for name in ('f-only-bootstrap','f-only-fault','apps','time-local','startup-fifo','storage-transfer','mixed-slot','mixed-identity'):
        r=read(BUILD/(name+'-test-results.json'));assert r['passed'] and r['artifacts']==meta['artifacts'],name
        for field in ('local_asset_sha256','status_asset_sha256','bootstrap_utility_sha256'):
            if field in r:assert r[field]==meta[field],(name,field)
    assert meta['boot_compatibility']==read(OLD/'build.json')['boot_compatibility']
    f=bytearray((BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes());offset=meta['boot']['BOOT_COMPAT_DATA']-0xF000
    assert int.from_bytes(f[offset:offset+4],'little')==meta['boot_compatibility']
    f[offset:offset+4]=bytes(4);assert binascii.crc32(f)&0xFFFFFFFF==meta['boot_identity_crc32']
    parent=bytearray((ROOT/'BUILD/v2-fix005/str8n-v2-recovery-f000-ffff.bin').read_bytes());parent[offset:offset+4]=bytes(4)
    assert f==parent,'beta25 F instruction bytes changed beyond the proven ABI token'
    assert read(BUILD/'mixed-slot-test-results.json')['expected_hashes']==read(BASE/BOARD/'upgrade/plan.json')['expected_hashes']
    return meta

def prepare():
    # Qualification can proceed in parallel; audit() is mandatory at install.
    meta=read(BUILD/'build.json');root=BASE/BOARD;p=read(root/'prior-verified/manifest.json')
    state=read(root/'initial-state.json');assert p['repeat_verified'] and p['board']==BOARD
    active=state['active_page'];inactive=state['inactive_page'];assert (active,inactive)==(0xA0,0xB0)
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==p['banks'][i]['sha256']
    for page in (active,inactive):
        image=banks[3][(page-0x80)*256:(page-0x80)*256+4096]
        assert image==(OLD/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
    assert banks[3][0x7000:]==(OLD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert banks[1][:12288]==(BUILD/meta['maintenance_storage_file']).read_bytes(), 'Existing MAINT must remain byte-identical'
    final=[bytearray(b) for b in banks]
    for offset,name in ((0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin'),
        ((inactive-0x80)*256,f'str8n-v2-recovery-slot-{inactive:02x}.bin')):
        if offset!=0x3000:assert banks[3][offset:offset+4096]==(OLD/name).read_bytes()
        final[3][offset:offset+4096]=(BUILD/name).read_bytes()
    for offset,name in ((0x4800,'boot-status/asset.bin'),(0x6000,'local-display/asset.bin')):
        before=(OLD/name).read_bytes();after=(BUILD/name).read_bytes();assert len(before)==len(after)
        assert banks[2][offset:offset+len(before)]==before
        final[2][offset:offset+len(after)]=after
    order=[(3,12),(2,12),(2,13),(2,14),(3,14),(3,15),(3,11)]
    journal=m.journal(banks[3]);assert journal;cfg=bytearray(journal[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7]=ord('P');cfg[8]=inactive;cfg[9:13]=meta['generation'].to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for bank,sector in order:
        index=bank*8+sector-8;assert counts[index]<0xFFFFFF;counts[index]+=1
    seq=int.from_bytes(journal[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[1]==banks[1]
    assert final[3][0x2000:0x3000]==banks[3][0x2000:0x3000]
    assert final[3][:0x2000]==banks[3][:0x2000] and final[3][0x5000:0x6000]==banks[3][0x5000:0x6000]
    mf=read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    # This installer has no SR-record commits. Its sole delayed commit is MI
    # byte 31, whose value is zero rather than the SR-record commit value 3F.
    start=mf['symbols']['MIG_RECORD_COMMIT'];matches=[a+1 for a in range(start,start+32) if cells.get(a)==0xA9 and cells.get(a+1)==0x3F]
    assert len(matches)==1;cells[matches[0]]=0
    expected=[bytearray(b) for b in banks];payloads=[]
    for i,(bank,sector) in enumerate(order):
        offset=(sector-8)*4096;data=bytearray(final[bank][offset:offset+4096]);commit=(bank,sector)==(3,11)
        if commit:data[31]=0xFF
        row=bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for a,v in enumerate(row,mf['table']+9*i):cells[a]=v
        cells[mf['banks']+i]=bank;cells[mf['commits']+i]=4 if commit else 0
        for a in range(mf['commit_addresses']+4*i,mf['commit_addresses']+4*i+4):cells[a]=0
        if commit:
            cells[mf['commit_addresses']+4*i]=0x1F;cells[mf['commit_addresses']+4*i+1]=0xB0
        expected[bank][offset:offset+4096]=data
        if commit:expected[3][0x301F]=0
        payloads.append(bytes(data))
    assert expected==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=BOARD,version=meta['version'],generation=37,source_generation=35,prior_directory='prior-verified',
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),config=cfg.hex(),
        counts_before=before,counts_after=counts,storage_update=True,commit_records=[],no_sram_format=True,
        active_fallback='A',updated_slot='B',fallback_sha256=sha(banks[3][0x2000:0x3000]),
        monitor_commit=dict(bank=3,address=0xB01F,value=0),initial_f_install_power_loss_safe=False)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    print('PREPARED 2609: shared changes + MON B; MON A/B0/B1 exact; slot B commit last',flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='audit':audit();print('PASS beta25 bound model audit')
    elif sys.argv[1]=='install':
        check=read(BASE/BOARD/'upgrade/model-check.json')
        assert check['fallback_unchanged'] and check['monitor_commit_verified_last']
        deploy.BUILD=BUILD;deploy.audit=audit;deploy.install(BASE/BOARD,BOARD)
    else:raise ValueError(sys.argv[1])
