"""Exact-backup beta30 installation on 2512, retaining beta28 A and all user storage."""
import argparse,json
from pathlib import Path
import migrate_v2 as u
import update_v2_beta24 as deploy
m=u.m;ROOT=u.ROOT;BUILD=ROOT/'BUILD/v2-beta30-candidate';read=u.read;sha=u.sha

def audit_build():
    meta=read(BUILD/'build.json');proof=read(BUILD/'beta30-qualification.json')
    assert proof['passed'] and proof['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert proof['artifacts']==meta['artifacts']
    for n,h in meta['artifacts'].items():assert sha((BUILD/n).read_bytes())==h,n
    for n,r in proof['receipts'].items():
        assert read(BUILD/n)['passed'] and sha((BUILD/n).read_bytes())==r['sha256'],n
    return meta

def prepare(root):
    audit_build();manifest=read(root/'prior-verified/manifest.json');state=read(root/'initial-state.json')
    assert manifest['repeat_verified'] and manifest['board']=='2512' and state['active_page']==0xB0
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert len(b)==32768 and b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==manifest['banks'][i]['sha256']
    old=ROOT/'BUILD/v2-beta29-candidate';reference=ROOT/'output/qualification/beta29-2026-10-15/2512/upgrade'
    assert banks[3][0x2000:0x3000]==(ROOT/'BUILD/v2-beta28-b23/str8n-v2-recovery-slot-a0.bin').read_bytes()
    assert banks[3][0x3000:0x4000]==(old/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    assert banks[3][0x6000:]==(reference/'post-reset-b3.bin').read_bytes()[0x6000:]
    assert banks[2]==(reference/'post-reset-b2.bin').read_bytes(),'Unknown B2 content; installation refused'
    final=[bytearray(b) for b in banks]
    final[2][:0x5800]=(BUILD/'xip/utilities.bin').read_bytes();final[2][0x5800:0x6200]=(BUILD/'boot-status/asset.bin').read_bytes()
    final[3][0x3000:0x4000]=(BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    changes=[(2,s) for s in range(15,7,-1) if final[2][(s-8)*4096:(s-7)*4096]!=banks[2][(s-8)*4096:(s-7)*4096]]
    order=[(3,12)]+changes+[(3,11)]
    j=m.journal(banks[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xB0'+(42).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    before=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];counts=before[:]
    for b,s in order:
        idx=b*8+s-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[1]==banks[1]
    assert final[3][:0x3000]==banks[3][:0x3000] and final[3][0x5000:]==banks[3][0x5000:]
    mf=read(BUILD/'migrator/manifest.json');assert mf['mixed_commit_values'] and len(order)<=mf['max_sectors']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    # Only the successful final-print call is redirected. Every refusal still
    # reaches the original RAM halt, with no reset or further writes.
    sy=mf['symbols'];call=sy['MIG_HALT']-3;printer=sy['MIG_PRINT']
    assert bytes(cells[call+i] for i in range(3))==b'\x20'+printer.to_bytes(2,'little')
    trampoline=max(cells)+1;assert trampoline+6<0x6200;assert all(a not in cells for a in range(trampoline,trampoline+6))
    cells.update(dict(enumerate(b'\x20'+printer.to_bytes(2,'little')+b'\x4C\x04\xF0',trampoline)))
    cells.update(dict(enumerate(b'\x20'+trampoline.to_bytes(2,'little'),call)))
    message=b'MIGRATION VERIFIED; READY FOR J3\r\n\0';assert len(message)<=sy['MIG_BAD']-sy['MIG_DONE']
    cells.update(dict(enumerate(message,sy['MIG_DONE'])))
    pending=[bytearray(b) for b in banks];payloads=[]
    for i,(b,s) in enumerate(order):
        off=(s-8)*4096;data=bytearray(final[b][off:off+4096]);addresses=[0xB01F] if (b,s)==(3,11) else []
        for a in addresses:data[a-0x8000-off]=0xFF
        row=bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=b;cells[mf['commits']+i]=b+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),mf['commit_addresses']+4*i)))
        pending[b][off:off+4096]=data
        for a in addresses:pending[b][a-0x8000]=0
        payloads.append(data)
    assert pending==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    source=dict(active_page=0xB0,inactive_page=0xA0,version='2.0b29',generation=41,source_build='BUILD/v2-beta29-candidate')
    plan=dict(board='2512',version='2.0b30',generation=42,source=source,source_generation=41,target_build=str(BUILD.relative_to(ROOT)),target_page=0xB0,fallback_page=0xA0,prior_directory='prior-verified',steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),config=cfg.hex(),counts_before=before,counts_after=counts,storage_update=True,commit_records=[],fallback_sha256=sha(banks[3][0x2000:0x3000]),monitor_commit=dict(bank=3,address=0xB01F,value=0),no_sram_format=True,physical_reset_required=False,returns_to_monitor=True,success_checkpoint=trampoline+3,return_target=0xF004,completion_token='MIGRATION VERIFIED; READY FOR J3',clock_storage_preserved=True,immutable_recovery_unchanged=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    print('PREPARED beta30 B; beta28 A and all B0/B1 preserved; sectors:',order,flush=True)

def audit(root):
    meta=audit_build();plan=read(root/'upgrade/plan.json')
    assert plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert plan['template_manifest_sha256']==sha((BUILD/'migrator/manifest.json').read_bytes())
    model=read(root/'upgrade/model-check.json');functional=read(root/'upgrade/beta30-board-test-results.json')
    assert model['passed'] and model['fallback_unchanged'] and model['monitor_commit_verified_last']
    assert functional['installer_return_verified'] and functional['j3_reset_verified']
    assert functional['passed'] and functional['expected_hashes']==plan['expected_hashes'] and functional['build_sha256']==plan['build_sha256']
    for p in ['retained/sram-prior/report.json','retained/devices-before/report.json']:assert read(root/p)['passed']
    assert sha((root/'retained/sram-prior/array-0.bin').read_bytes())==functional['retained_sram_sha256']
    return meta

def install(root):
    deploy.BUILD=BUILD;deploy.audit=lambda:audit(root);deploy.install(root,'2512')

def verify(root):
    import upgrade_v2_fleet as f
    audit(root);plan=read(root/'upgrade/plan.json');pp=root/'upgrade/install/reset-pending.json';pending=read(pp)
    assert pending['device_sectors_verified'] and pending['software_reset_pending']
    with f.serial_lease('beta30-2512-reset-verify'),(root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link=m.Link(f.port('2512'),log)
        try:
            from rtc_prompt_sync import establish_b3
            establish_b3(link);print('Issuing J3 restart on 2512',flush=True)
            startup=link.command('J3');assert b'STR8-N 2.0b30' in startup,startup
            (root/'upgrade/boot.txt').write_bytes(startup);assert link.dump(0x7D30,0x7D30)==b'\xB0'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==plan['expected_hashes'][bank],bank
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data);print('PASS beta30 full readback B'+str(bank),flush=True)
            link.command('B3')
            for name,cmd in [('version','VERSION'),('time','TIME'),('table','T'),('map','M1'),('wear','W'),('apps','APPS')]:
                text=link.command(cmd);(root/f'upgrade/{name}.txt').write_bytes(text)
                if name=='time':assert b'(-05:00)' in text,text
                if name=='version':assert b'Board: 2512' in text and b'A/B/S,Enter' not in text and b'SSRAM:' not in text and b'STR8-N 2.0b30' in text and b'MONITOR A gen 00000028 VALID' in text and b'MONITOR B gen 0000002A VALID default' in text,text
                if name=='table':assert b'CLOCK' not in text and b'MAINT' not in text and b'B2:' not in text,text
                if name=='apps':assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
            for name,title,prompt,query in [('MAINT',b'BANK MAINT 2.4',b'BM> ','?'),('SRAM',b'SRAM 1.4',b'SRAM> ','T'),('WORK',b'WORK 1.4',b'WORK> ','?'),('EDU',b'EDU 1.4',b'EDU> ','?')]:
                text=link.command(name,prompt);assert title in text,text
                text+=link.command(query,prompt);text+=link.command('Q')
                (root/f'upgrade/live-{name}.txt').write_bytes(text);print('PASS live native utility '+name,flush=True)
            text=link.command('BATCH VERSION;TIME',b'BATCH done');text+=link.until(b'\r\nB3> ');assert b'BATCH done' in text,text
            (root/'upgrade/live-BATCH.txt').write_bytes(text)
            text=link.command('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed');text+=link.until(b'SRAM> ');assert b'BATCH stopped: command failed' in text,text
            text+=link.command('Q');(root/'upgrade/live-BATCH-error.txt').write_bytes(text)
            text=link.command('R MAINT',b'BM> ');text+=link.command('NAME Z30CHECK',b'Type YES: ')
            text+=link.command('NO',b'BM> ');text+=link.command('Q');(root/'upgrade/live-NAME.txt').write_bytes(text)
            text=link.command('BATCH MAINT;NAME Z30CHECK;Q',b'Type YES: ')
            link.send(b'\x1b');text+=link.until(b'BATCH canceled');text+=link.until(b'BM> ')
            text+=link.command('Q');(root/'upgrade/live-BATCH-ESC.txt').write_bytes(text)
            text=link.command('BATCH SRAM;G CLK;STATUS;Q',b'BATCH done');text+=link.until(b'\r\nB3> ');assert b'CLOCK 1.9' in text and b'Running: yes' in text,text
            (root/'upgrade/live-BATCH-CLOCK.txt').write_bytes(text)
            text=link.command('SRAM',b'SRAM> ');text+=link.command('G CLK',b'CLOCK> ');assert b'CLOCK 1.9' in text,text
            text+=link.command('STATUS',b'CLOCK> ');text+=link.command('BATTERY',b'CLOCK> ')
            assert b'Running: yes' in text and b'Backup enabled: yes' in text,text
            text+=link.command('Q');(root/'upgrade/live-CLOCK.txt').write_bytes(text)
            pending.update(physical_reset_pending=False,software_reset_pending=False,software_reset_verified=True);pp.write_text(json.dumps(pending,indent=2)+'\n')
            result=dict(passed=True,board='2512',version='2.0b30',generation=42,active_slot='B',fallback_slot='A',fallback_version='2.0b28',j3_reset_verified=True,complete_flash_readback=True,expected_hashes=plan['expected_hashes'],native_utilities_verified=True,batch_completion_error_escape_verified=True,name_confirmation_regression_verified=True,clock_version='1.9',fixed_recovery_preserved=True)
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(result,indent=2)+'\n')
            print('PASS J3 startup, exact full flash readback and all four native utilities',flush=True)
        finally:link.serial.close()

def finalize(root):
    import upgrade_v2_fleet as f
    from datetime import datetime,timezone
    audit(root);assert read(root/'upgrade/post-reset-report.json')['passed']
    retained=root/'retained';campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    with f.serial_lease('beta30-2512-retained-final'):
        if not (retained/'sram-final/report.json').exists():f.call(f.array,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','final'])
        f.call(f.devices,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','after','--baseline-index',campaign['baseline_index'],'--clock19-display-transition','--clock-source','sram','--clock-name','CLK'])
    paths=['upgrade/model-check.json','upgrade/beta30-board-test-results.json','upgrade/post-reset-report.json','retained/sram-final/report.json','retained/devices-after/report.json']
    reports={p:read(root/p) for p in paths};assert all(r['passed'] for r in reports.values())
    assert reports['retained/sram-final/report.json']['sha256']==read(retained/'sram-prior/report.json')['sha256']
    assert all(reports['retained/devices-after/report.json'][k] for k in ['history_preserved','identity_preserved','eeprom_preserved'])
    receipt=dict(passed=True,board='2512',version='2.0b30',generation=42,active_slot='B',fallback_slot='A',fallback_version='2.0b28',qualified_at_utc=datetime.now(timezone.utc).isoformat(),build_sha256=sha((BUILD/'build.json').read_bytes()),evidence_root=str(root.resolve()),complete_flash_readback=True,j3_reset_verified=True,serial_sram_preserved=True,rtc_history_identity_eeprom_trim_preserved=True,fixed_recovery_preserved=True,clock_version='1.9',evidence={p:sha((root/p).read_bytes()) for p in paths})
    for p in [root/'hardware-qualification.json',BUILD/'hardware-qualification-2512.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS beta30 2512 hardware qualification; complete SRAM and RTC/history/identity/EEPROM/trim preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','audit','install','verify','finalize'));p.add_argument('--root',required=True,type=Path);a=p.parse_args();globals()[a.stage](a.root)
