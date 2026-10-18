"""Backup-bound beta27 B2 consolidation on 2609; preserve beta26 A and F."""
import argparse,json
from pathlib import Path
import beta4_migration as m
import update_v2_beta24 as deploy

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'BUILD/v2-beta27';BASE=ROOT/'BUILD/v2-beta26'
read,sha=deploy.read,deploy.sha

def capture(root):
    import upgrade_v2_fleet as fleet
    from rtc_prompt_sync import establish_b3
    from serial_test_coordination import serial_lease
    root.mkdir(parents=True,exist_ok=True)
    assert not (root/'prior-verified').exists(),'Keep existing backup; use its completed receipts or a new evidence directory'
    with serial_lease('beta27-capture'),(root/'inventory-serial.jsonl').open('a') as log:
        link=m.Link(fleet.port('2609'),log)
        try:
            establish_b3(link);active=link.dump(0x7D30,0x7D30)[0]
            state=dict(board='2609',port=fleet.port('2609'),active_page=active,inactive_page=active^0x10,
                version=link.command('VERSION').decode(),table=link.command('T').decode(),config=link.command('C').decode())
            assert active==0xA0 and 'STR8-N 2.0b26' in state['version'],state
            (root/'initial-state.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
        finally:link.serial.close()
        fleet.call(fleet.backup,['--board','2609','--port',fleet.port('2609'),'--out',str(root/'prior-verified')])
    retained=root/'retained';retained.mkdir()
    campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    with serial_lease('beta27-retained-reference'):
        fleet.call(fleet.array,['--root',str(retained),'--board','2609','--port',fleet.port('2609'),'--stage','prior'])
        fleet.call(fleet.devices,['--root',str(retained),'--board','2609','--port',fleet.port('2609'),'--stage','before','--baseline-index',campaign['baseline_index'],'--clock-source','sram'])
    print('PASS beta27 fresh repeated flash/SRAM backups and retained device references',flush=True)

def build_audit():
    meta=read(BUILD/'build.json')
    assert (meta['version'],meta['generation'])==('2.0b27',39)
    assert meta['parent_build_sha256']==sha((BASE/'build.json').read_bytes())
    for n,h in meta['artifacts'].items():assert sha((BUILD/n).read_bytes())==h,n
    for n,key in [('boot-status/asset.bin','status_asset_sha256'),('battery/asset.bin','battery_asset_sha256'),('local-display/asset.bin','local_asset_sha256'),('version/asset.bin','version_asset_sha256')]:
        assert sha((BUILD/n).read_bytes())==meta[key],(n,key)
    assert (BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    return meta

def layout(banks):
    """Refuse unknown source allocations; construct final banks entirely offline."""
    meta=build_audit();old=read(BASE/'build.json')
    assert len(banks)==4 and all(len(b)==32768 for b in banks)
    original=(ROOT/'output/qualification/beta26-2026-10-15-retry/2609/upgrade/post-reset-b2.bin').read_bytes()
    assert banks[2]==original,'B2 differs from qualified beta26; preserve and review new allocations'
    assert banks[2][:0x2000]==b'\xff'*8192 and banks[2][0x7000:]==b'\xff'*4096
    assert banks[1][:0x3000]==(BASE/old['maintenance_storage_file']).read_bytes()
    assert banks[1][0x3000:]==b'\xff'*(32768-12288),'B1 still contains saved contents; cannot free without preserving them'
    assert banks[3][0x6000:0x7000]==(BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    assert banks[3][0x7000:]==(BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert banks[3][0x2000:0x3000]==(BASE/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    final=[bytearray(b) for b in banks]
    final[1][:]=b'\xff'*32768
    final[2][0x3000:0x8000]=banks[2][0x2000:0x7000]
    final[2][:0x3000]=(BUILD/meta['maintenance_storage_file']).read_bytes()
    final[2][0x5800:0x6200]=(BUILD/'boot-status/asset.bin').read_bytes()
    final[3][0x6000:0x7000]=(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    final[3][0x3000:0x4000]=(BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    # Descending copies publish WORK and SRAM before their old extents change.
    # MAINT continuations precede its header; source B1 is erased only afterward.
    # The new monitor is committed last. RAM installer never returns mid-layout.
    order=[(3,12)]+[(2,s) for s in (15,14,13,12,11,10,9,8)]+[(3,14),(1,10),(1,9),(1,8),(3,11)]
    j=m.journal(banks[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xB0'+(39).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    before=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];counts=before[:]
    for bank,sector in order:
        i=bank*8+sector-8;assert counts[i]<0xFFFFFF;counts[i]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[3][:0x3000]==banks[3][:0x3000] and final[3][0x7000:]==banks[3][0x7000:]
    return final,order,cfg,before,counts

def prepare(root):
    meta=build_audit();manifest=read(root/'prior-verified/manifest.json');state=read(root/'initial-state.json')
    assert manifest['repeat_verified'] and manifest['board']=='2609' and state['active_page']==0xA0
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==manifest['banks'][i]['sha256']
    final,order,cfg,before,counts=layout(banks)
    mf=read(BUILD/'migrator/manifest.json');assert mf['mixed_commit_values'] and len(order)<=mf['max_sectors']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']],cells[mf['commit_after']]=len(order),0
    commits={(2,13):[0xD583],(2,12):[0xC003],(2,11):[0xB003],(2,8):[0x8003],(3,11):[0xB01F]}
    pending=[bytearray(b) for b in banks];payloads=[]
    for i,(bank,sector) in enumerate(order):
        offset=(sector-8)*4096;data=bytearray(final[bank][offset:offset+4096]);addresses=commits.get((bank,sector),[])
        for address in addresses:data[address-0x8000-offset]=0xFF
        row=bytes((sector<<4,))+m.fnv(pending[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)))
        cells[mf['banks']+i]=bank;cells[mf['commits']+i]=bank+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),mf['commit_addresses']+4*i)))
        pending[bank][offset:offset+4096]=data
        for address in addresses:pending[bank][address-0x8000]=0 if bank==3 else 0x3F
        payloads.append(data)
    assert pending==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board='2609',version='2.0b27',generation=39,target_build=str(BUILD.relative_to(ROOT)),prior_directory='prior-verified',
        source=dict(active_page=0xA0,inactive_page=0xB0,version='2.0b26',generation=38),
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
        config=cfg.hex(),counts_before=before,counts_after=counts,storage_update=True,
        commit_records=[dict(bank=b,address=a) for b,a in [(2,0xD580),(2,0xC000),(2,0xB000),(2,0x8000)]],
        monitor_commit=dict(bank=3,address=0xB01F,value=0),fallback_page=0xA0,fallback_version='2.0b26',fallback_sha256=sha(banks[3][0x2000:0x3000]),
        immutable_recovery_unchanged=True,physical_reset_required=True,b1_freed=True,b2_relocation=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    print('PREPARED beta27 B / preserved beta26 A; 14 sectors; SRAM/WORK/MAINT and final monitor commit withheld until verification')

def audit(root):
    meta=build_audit();plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json');functional=read(root/'upgrade/beta27-test-results.json')
    assert plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert plan['template_manifest_sha256']==sha((BUILD/'migrator/manifest.json').read_bytes())
    assert model['passed'] and model['fallback_unchanged'] and model['monitor_commit_verified_last'] and model['maint_committed_before_source_erase']
    assert functional['passed'] and functional['expected_hashes']==plan['expected_hashes'] and functional['artifacts']==meta['artifacts']
    retained=read(root/'retained/sram-prior/report.json')
    array=(root/'retained/sram-prior/array-0.bin').read_bytes()
    assert retained['passed'] and retained['repeat_verified'] and array==(root/'retained/sram-prior/array-1.bin').read_bytes()
    assert retained['sha256']==functional['retained_sram_sha256']==sha(array)
    assert functional['standalone_receipt_sha256']==sha((BUILD/'beta27-test-results.json').read_bytes())
    assert read(root/'retained/devices-before/report.json')['passed']
    return meta

def install(root):
    deploy.BUILD=BUILD;deploy.audit=lambda:audit(root);deploy.install(root,'2609')

def verify(root):
    from serial.tools.list_ports import comports
    from serial_test_coordination import serial_lease
    audit(root);plan=read(root/'upgrade/plan.json');pp=root/'upgrade/install/reset-pending.json';pending=read(pp);assert pending['device_sectors_verified']
    port=next(p.device for p in comports() if p.serial_number=='A10MPQXCA')
    with serial_lease('beta27-reset-verify'),(root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link=m.Link(port,log)
        try:
            print('ARMED: physical RESET on 2609; receiving beta27 startup',flush=True)
            startup=link.until(b'\r\nB3> ',180);assert b'STR8-N 2.0b27' in startup,startup
            (root/'upgrade/boot.txt').write_bytes(startup);assert link.dump(0x7D30,0x7D30)==b'\xB0'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                actual=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(actual)==plan['expected_hashes'][bank],bank
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(actual);print('PASS beta27 full readback B'+str(bank),flush=True)
            link.command('B3')
            for name,command in [('version','VERSION'),('time','TIME'),('table','T'),('map','M1'),('wear','W')]:
                text=link.command(command);(root/f'upgrade/{name}.txt').write_bytes(text)
                if name=='version':assert b'STR8-N 2.0b27' in text and b'MONITOR A gen 00000026 VALID' in text and b'MONITOR B gen 00000027 VALID default' in text,text
                if name=='table':assert b'B2:8000' in text and b'B2:B000' in text and b'B2:C000' in text and b'B2:D580' in text and b'B1:' not in text,text
                if name=='map':assert b'B1 .  .  .  .  .  .  .  .' in text and b'B2 S  +  +  S  S  +  F  F' in text,text
            text=link.command('R SRAM',b'SRAM> ');text+=link.command('T',b'SRAM> ');assert b'CLK 2000 2FD7' in text,text
            text+=link.command('G CLK',b'CLOCK> ');assert b'CLOCK 1.8' in text,text
            text+=link.command('STATUS',b'CLOCK> ');assert b'Running: yes' in text and b'Backup enabled: yes' in text and b'80 0E ' in text,text
            text+=link.command('Q');(root/'upgrade/sram-clock.txt').write_bytes(text)
            text=link.command('R MAINT',b'BM> ');assert b'BANK MAINT 2.2' in text,text
            text+=link.command('Q');(root/'upgrade/maint.txt').write_bytes(text)
            pending.update(physical_reset_pending=False,physical_reset_verified=True);pp.write_text(json.dumps(pending,indent=2)+'\n')
            report=dict(passed=True,board='2609',version='2.0b27',generation=39,active_slot='B',fallback_slot='A',fallback_version='2.0b26',complete_flash_readback=True,physical_reset_verified=True,b1_erased=True,relocated_utilities_passed=True,expected_hashes=plan['expected_hashes'])
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS beta27 B; B1 free; shifted B2 utilities, SRAM CLK, map, TIME/VERSION/W verified',flush=True)
        finally:link.serial.close()

def finalize(root):
    """Read-only retained-data checks and separate hardware qualification seal."""
    from datetime import datetime,timezone
    import upgrade_v2_fleet as fleet
    from serial_test_coordination import serial_lease
    meta=audit(root);reset=read(root/'upgrade/post-reset-report.json')
    assert reset['passed'] and reset['physical_reset_verified'] and reset['complete_flash_readback']
    retained=root/'retained';campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    with serial_lease('beta27-retained-final'):
        fleet.call(fleet.array,['--root',str(retained),'--board','2609','--port',fleet.port('2609'),'--stage','final'])
        fleet.call(fleet.devices,['--root',str(retained),'--board','2609','--port',fleet.port('2609'),'--stage','after','--baseline-index',campaign['baseline_index'],'--clock-source','sram'])
    paths=['upgrade/post-reset-report.json','upgrade/model-check.json','upgrade/beta27-test-results.json','retained/sram-final/report.json','retained/devices-after/report.json']
    reports={p:read(root/p) for p in paths};assert all(r['passed'] for r in reports.values())
    assert reports['retained/sram-final/report.json']['sha256']==read(retained/'sram-prior/report.json')['sha256']
    device=reports['retained/devices-after/report.json'];assert all(device[k] for k in ('history_preserved','identity_preserved','eeprom_preserved'))
    receipt=dict(passed=True,board='2609',version='2.0b27',generation=39,active_slot='B',fallback_slot='A',fallback_version='2.0b26',
        qualified_at_utc=datetime.now(timezone.utc).isoformat(),evidence_root=str(root.resolve()),build_sha256=sha((BUILD/'build.json').read_bytes()),
        complete_flash_readback=True,b1_free_bytes=32768,serial_sram_preserved=True,rtc_history_identity_eeprom_trim_preserved=True,
        evidence={p:dict(sha256=sha((root/p).read_bytes()),report=r) for p,r in reports.items()})
    (BUILD/'hardware-qualification-2609.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (root/'hardware-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS beta27 hardware qualification: B1 free, beta26 A and F preserved, entire SRAM/RTC history/identity/EEPROM/trim retained',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('capture','prepare','audit','install','verify','finalize'));p.add_argument('--root',type=Path,required=True);a=p.parse_args();globals()[a.stage](a.root)
