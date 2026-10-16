"""Exact-backup beta28 installation on 2512, retaining beta25 B and fixed F."""
import argparse,json
from pathlib import Path
import migrate_v2 as u
import update_v2_beta24 as deploy
m=u.m;ROOT=u.ROOT;BUILD=ROOT/'BUILD/v2-beta28-b23';read=u.read;sha=u.sha

def audit_build():
    meta=read(BUILD/'build.json');proof=read(BUILD/'profile-proof.json')
    assert proof['passed'] and proof['build_sha256']==sha((BUILD/'build.json').read_bytes())
    for n,h in meta['artifacts'].items():assert sha((BUILD/n).read_bytes())==h,n
    for n,key in [('boot-status','status'),('battery','battery'),('version','version'),('local-display','local')]:assert sha((BUILD/n/'asset.bin').read_bytes())==meta[key+'_asset_sha256']
    return meta

def prepare(root):
    meta=audit_build();manifest=read(root/'prior-verified/manifest.json');state=read(root/'initial-state.json')
    assert manifest['repeat_verified'] and manifest['board']=='2512' and state['active_page']==0xB0
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==manifest['banks'][i]['sha256']
    source=u.identify(banks,0xB0);assert source['source_build']==str(Path('BUILD/v2-beta25-b23'))
    old=ROOT/source['source_build'];om=read(old/'build.json')
    assert banks[3][0x7000:]==(BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert banks[3][0x6000:0x7000]==(old/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    for off,name,n in [(0,'str8n-rtc-component-8000-8fff.bin',4096),(4096,'str8n-journal-9000-9fff.bin',3072)]:assert banks[3][off:off+n]==(BUILD/name).read_bytes()[:n]
    # Recognize every byte that the expanded B2 allocation replaces. Refuse
    # opaque or newly saved content rather than silently overwriting it.
    recognized=bytearray(b'\xff'*32768)
    for off,name in [(0x2000,'store/sram.bin'),(0x3000,'workspace/workspace.bin'),(0x4580,'edu/edu.bin')]:
        body=(old/name).read_bytes();header=banks[2][off:off+24]
        assert header[:4]==b'SR\x01?' and int.from_bytes(header[6:8],'little')==len(body)
        recognized[off:off+24+len(body)]=header+body
    for off,name in [(0x4800,'boot-status/asset.bin'),(0x6000,'local-display/asset.bin')]:
        data=(old/name).read_bytes();recognized[off:off+len(data)]=data
    assert recognized==banks[2],'Unknown B2 data; no installation permitted'
    assert banks[1][:12288]==(old/om['maintenance_storage_file']).read_bytes()
    final=[bytearray(b) for b in banks];final[1][:12288]=b'\xff'*12288
    reference=(ROOT/'BUILD/v2-beta28/candidate/b2.bin').read_bytes()
    final[2][:]=reference;final[2][:0x5800]=(BUILD/'xip/utilities.bin').read_bytes()
    final[2][0x7800:]=(BUILD/'version/asset.bin').read_bytes()
    final[3][0x6000:0x7000]=(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    final[3][0x2000:0x3000]=(BUILD/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    order=[(3,12)]+[(2,s) for s in range(15,7,-1)]+[(3,14),(1,10),(1,9),(1,8),(3,10)]
    j=m.journal(banks[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xA0'+(40).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    before=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];counts=before[:]
    for b,s in order:
        idx=b*8+s-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[1][12288:]==banks[1][12288:]
    assert final[3][:0x2000]==banks[3][:0x2000] and final[3][0x3000:0x4000]==banks[3][0x3000:0x4000] and final[3][0x7000:]==banks[3][0x7000:]
    mf=read(BUILD/'migrator/manifest.json');assert mf['mixed_commit_values'] and len(order)<=mf['max_sectors']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    pending=[bytearray(b) for b in banks];payloads=[]
    for i,(b,s) in enumerate(order):
        off=(s-8)*4096;data=bytearray(final[b][off:off+4096]);addresses=[0xA01F] if (b,s)==(3,10) else []
        for a in addresses:data[a-0x8000-off]=0xFF
        row=bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=b;cells[mf['commits']+i]=b+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),mf['commit_addresses']+4*i)))
        pending[b][off:off+4096]=data
        for a in addresses:pending[b][a-0x8000]=0
        payloads.append(data)
    assert pending==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board='2512',version='2.0b28',generation=40,source=source,source_generation=37,target_build=str(BUILD.relative_to(ROOT)),prior_directory='prior-verified',steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),config=cfg.hex(),counts_before=before,counts_after=counts,storage_update=True,commit_records=[],fallback_sha256=sha(banks[3][0x3000:0x4000]),monitor_commit=dict(bank=3,address=0xA01F,value=0),no_sram_format=True,physical_reset_required=True,clock_flash_preserved=True,immutable_recovery_unchanged=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    print('PREPARED 2512 beta28 A, beta25 B retained, 14 sectors, CLOCK flash and fixed F preserved')

def audit(root):
    meta=audit_build();plan=read(root/'upgrade/plan.json')
    assert plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert plan['template_manifest_sha256']==sha((BUILD/'migrator/manifest.json').read_bytes())
    model=read(root/'upgrade/model-check.json');functional=read(root/'upgrade/beta28-board-test-results.json')
    assert model['passed'] and model['fallback_unchanged'] and model['monitor_commit_verified_last']
    assert functional['passed'] and functional['expected_hashes']==plan['expected_hashes'] and functional['build_sha256']==plan['build_sha256']
    for p in ['retained/sram-prior/report.json','retained/devices-before/report.json']:assert read(root/p)['passed']
    assert sha((root/'retained/sram-prior/array-0.bin').read_bytes())==functional['retained_sram_sha256']
    return meta

def install(root):
    deploy.BUILD=BUILD;deploy.audit=lambda:audit(root);deploy.install(root,'2512')

def verify(root):
    import upgrade_v2_fleet as f
    audit(root);plan=read(root/'upgrade/plan.json');pp=root/'upgrade/install/reset-pending.json';pending=read(pp)
    assert pending['device_sectors_verified'] and pending['physical_reset_pending']
    with f.serial_lease('beta28-2512-reset-verify'),(root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link=m.Link(f.port('2512'),log)
        try:
            print('ARMED: receiving physical RESET startup on 2512 (COM4)',flush=True)
            startup=link.until(b'\r\nB3> ',600);assert b'STR8-N 2.0b28' in startup,startup
            (root/'upgrade/boot.txt').write_bytes(startup);assert link.dump(0x7D30,0x7D30)==b'\xA0'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==plan['expected_hashes'][bank],bank
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data);print('PASS beta28 full readback B'+str(bank),flush=True)
            link.command('B3')
            for name,cmd in [('version','VERSION'),('time','TIME'),('table','T'),('map','M1'),('wear','W'),('apps','APPS')]:
                text=link.command(cmd);(root/f'upgrade/{name}.txt').write_bytes(text)
                if name=='version':assert b'STR8-N 2.0b28' in text and b'MONITOR A gen 00000028 VALID default' in text and b'MONITOR B gen 00000025 VALID' in text,text
                if name=='table':assert b'CLOCK' in text and b'MAINT' not in text and b'B2:' not in text,text
                if name=='apps':assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
            for name,title,prompt,query in [('MAINT',b'BANK MAINT 2.3',b'BM> ','?'),('SRAM',b'SRAM 1.3',b'SRAM> ','T'),('WORK',b'WORK 1.3',b'WORK> ','?'),('EDU',b'EDU 1.3',b'EDU> ','?')]:
                text=link.command('R '+name,prompt);assert title in text,text
                text+=link.command(query,prompt);text+=link.command('Q')
                (root/f'upgrade/live-{name}.txt').write_bytes(text);print('PASS live native utility '+name,flush=True)
            text=link.command('R CLOCK',b'CLOCK> ');text+=link.command('STATUS',b'CLOCK> ')
            assert b'Running: yes' in text and b'Backup enabled: yes' in text,text
            text+=link.command('Q');(root/'upgrade/live-CLOCK.txt').write_bytes(text)
            pending.update(physical_reset_pending=False,physical_reset_verified=True);pp.write_text(json.dumps(pending,indent=2)+'\n')
            result=dict(passed=True,board='2512',version='2.0b28',generation=40,active_slot='A',fallback_slot='B',fallback_version='2.0b25',physical_reset_verified=True,complete_flash_readback=True,expected_hashes=plan['expected_hashes'],native_utilities_verified=True,clock_flash_preserved=True,fixed_recovery_preserved=True)
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(result,indent=2)+'\n')
            print('PASS physical startup, exact full flash readback and all four native utilities',flush=True)
        finally:link.serial.close()

def finalize(root):
    import upgrade_v2_fleet as f
    from datetime import datetime,timezone
    audit(root);assert read(root/'upgrade/post-reset-report.json')['passed']
    retained=root/'retained';campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    with f.serial_lease('beta28-2512-retained-final'):
        f.call(f.array,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','final'])
        f.call(f.devices,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','after','--baseline-index',campaign['baseline_index']])
    paths=['upgrade/model-check.json','upgrade/beta28-board-test-results.json','upgrade/post-reset-report.json','retained/sram-final/report.json','retained/devices-after/report.json']
    reports={p:read(root/p) for p in paths};assert all(r['passed'] for r in reports.values())
    assert reports['retained/sram-final/report.json']['sha256']==read(retained/'sram-prior/report.json')['sha256']
    assert all(reports['retained/devices-after/report.json'][k] for k in ['history_preserved','identity_preserved','eeprom_preserved'])
    receipt=dict(passed=True,board='2512',version='2.0b28',generation=40,active_slot='A',fallback_slot='B',fallback_version='2.0b25',qualified_at_utc=datetime.now(timezone.utc).isoformat(),build_sha256=sha((BUILD/'build.json').read_bytes()),evidence_root=str(root.resolve()),complete_flash_readback=True,physical_reset_verified=True,serial_sram_preserved=True,rtc_history_identity_eeprom_trim_preserved=True,fixed_recovery_preserved=True,clock_flash_preserved=True,evidence={p:sha((root/p).read_bytes()) for p in paths})
    for p in [root/'hardware-qualification.json',BUILD/'hardware-qualification-2512.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS beta28 2512 hardware qualification; complete SRAM and RTC/history/identity/EEPROM/trim preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','audit','install','verify','finalize'));p.add_argument('--root',required=True,type=Path);a=p.parse_args();globals()[a.stage](a.root)
