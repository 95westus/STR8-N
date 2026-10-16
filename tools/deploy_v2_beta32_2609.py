"""Backup-bound beta27 -> beta32 A on 2609, preserving B27/F and retained data."""
import argparse
import json
from pathlib import Path
import re

import migrate_v2 as u
import update_v2_beta24 as deploy
from serial_test_coordination import serial_lease

ROOT=u.ROOT;BUILD=ROOT/'BUILD/v2-beta32-2609-candidate';SOURCE=ROOT/'BUILD/v2-beta27'
read=u.read;sha=u.sha;m=u.m


def audit_build():
    meta=read(BUILD/'build.json');proof=read(BUILD/'profile-proof.json')
    assert proof['passed'] and proof['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert meta['batch_target_active_page']==0xA0 and meta['boot']['BOOT_SLOT_CHECK']==0xF31B
    for name,h in meta['artifacts'].items():assert sha((BUILD/name).read_bytes())==h,name
    for name,key in [('boot-status','status'),('battery','battery'),('local-display','local'),('version','version')]:
        assert sha((BUILD/name/'asset.bin').read_bytes())==meta[key+'_asset_sha256'],name
    assert sha((BUILD/'xip/utilities.bin').read_bytes())==read(BUILD/'xip/build.json')['sha256']
    assert (BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(SOURCE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    return meta


def prepare(root):
    audit_build();manifest=read(root/'prior-verified/manifest.json');state=read(root/'initial-state.json')
    assert manifest['repeat_verified'] and manifest['board']=='2609' and state['active_page']==0xB0
    before=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    reference=ROOT/'output/qualification/beta27-2026-10-15/2609/upgrade'
    for i,b in enumerate(before):
        assert len(b)==32768 and b==(root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert sha(b)==manifest['banks'][i]['sha256']
        assert b==(reference/f'post-reset-b{i}.bin').read_bytes(),'Unknown current data; preserve and review before planning'
    final=[bytearray(b) for b in before]
    final[2][:]=(BUILD/'candidate/b2.bin').read_bytes()
    final[3][0x6000:0x7000]=(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    final[3][0x2000:0x3000]=(BUILD/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    assert before[3][:4096]==(BUILD/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert before[3][0x1000:0x1C00]==(BUILD/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    assert final[0]==before[0] and final[1]==before[1]
    assert final[3][:0x2000]==before[3][:0x2000] and final[3][0x3000:0x4000]==before[3][0x3000:0x4000]
    assert final[3][0x7000:]==before[3][0x7000:]
    order=[(3,12)]+[(2,s) for s in range(15,7,-1) if final[2][(s-8)*4096:(s-7)*4096]!=before[2][(s-8)*4096:(s-7)*4096]]
    if final[3][0x6000:0x7000]!=before[3][0x6000:0x7000]:order.append((3,14))
    order.append((3,10))
    j=m.journal(before[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xA0'+(44).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    prior_counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];counts=prior_counts[:]
    for b,s in order:
        index=b*8+s-8;assert counts[index]<0xFFFFFF;counts[index]+=1
    sequence=int.from_bytes(j[4:8],'little');assert sequence<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,sequence+1)+b'\xff'*(4096-128)
    mf=read(BUILD/'migrator/manifest.json');assert mf['mixed_commit_values'] and len(order)<=mf['max_sectors']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    sy=mf['symbols'];call=sy['MIG_HALT']-3;printer=sy['MIG_PRINT']
    assert bytes(cells[call+i] for i in range(3))==b'\x20'+printer.to_bytes(2,'little')
    trampoline=max(cells)+1;assert trampoline+6<0x6200
    cells.update(dict(enumerate(b'\x20'+printer.to_bytes(2,'little')+b'\x4C\x04\xF0',trampoline)))
    cells.update(dict(enumerate(b'\x20'+trampoline.to_bytes(2,'little'),call)))
    message=b'MIGRATION VERIFIED; READY FOR J3\r\n\0';assert len(message)<=sy['MIG_BAD']-sy['MIG_DONE']
    cells.update(dict(enumerate(message,sy['MIG_DONE'])))
    pending=[bytearray(b) for b in before];payloads=[]
    for i,(b,s) in enumerate(order):
        off=(s-8)*4096;data=bytearray(final[b][off:off+4096]);addresses=[0xA01F] if (b,s)==(3,10) else []
        for address in addresses:data[address-0x8000-off]=0xFF
        row=bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=b;cells[mf['commits']+i]=b+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),mf['commit_addresses']+4*i)))
        pending[b][off:off+4096]=data
        for address in addresses:pending[b][address-0x8000]=0
        payloads.append(data)
    assert pending==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    peak=max(counts);index=counts.index(peak)
    plan=dict(board='2609',version='2.0b32',generation=44,source=dict(active_page=0xB0,inactive_page=0xA0,version='2.0b27',generation=39),
              target_build=str(BUILD.relative_to(ROOT)),target_page=0xA0,fallback_page=0xB0,prior_directory='prior-verified',
              steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in before],expected_hashes=[sha(b) for b in final],
              installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
              config=cfg.hex(),counts_before=prior_counts,counts_after=counts,storage_update=True,commit_records=[],
              fallback_sha256=sha(before[3][0x3000:0x4000]),monitor_commit=dict(bank=3,address=0xA01F,value=0),no_sram_format=True,
              physical_reset_required=False,returns_to_monitor=True,success_checkpoint=trampoline+3,completion_token='MIGRATION VERIFIED; READY FOR J3',
              immutable_recovery_unchanged=True,saved_clk_version='1.8',saved_clk_preserved=True,
              expected_wear_status='HIGH' if peak>=80000 else 'WARNING' if peak>=50000 else 'OK',
              wear_peak_count=peak,wear_peak_bank=index//8,wear_peak_sector=8+index%8,
              expected_wear_peak=f'Sector B{index//8}:{8+index%8:X}, max {peak} tracked erases.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    print('PREPARED beta32 A; beta27 B/F and all B0/B1/SRAM preserved; sectors',order,flush=True)


def audit(root):
    audit_build();plan=read(root/'upgrade/plan.json')
    assert plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert plan['template_manifest_sha256']==sha((BUILD/'migrator/manifest.json').read_bytes())
    for name in ['upgrade/model-check.json','upgrade/beta32-board-test-results.json','retained/sram-prior/report.json','retained/devices-before/report.json']:
        assert read(root/name)['passed'],name
    model=read(root/'upgrade/model-check.json');functional=read(root/'upgrade/beta32-board-test-results.json')
    assert model['fallback_unchanged'] and model['monitor_commit_verified_last'] and model['expected_hashes']==plan['expected_hashes']
    assert functional['expected_hashes']==plan['expected_hashes'] and functional['build_sha256']==plan['build_sha256']
    rebuild=read(BUILD/'rebuild-proof.json')
    assert rebuild['passed'] and rebuild['build_sha256']==plan['build_sha256']
    for name,h in rebuild['artifacts'].items():assert sha((BUILD/name).read_bytes())==h,name
    for i,h in enumerate(plan['expected_hashes']):assert sha((root/f'upgrade/expected-b{i}.bin').read_bytes())==h,i
    return plan


def install(root):
    deploy.BUILD=BUILD;deploy.audit=lambda:audit(root)
    deploy.serial_lease=lambda kind:serial_lease(kind,priority=True)
    deploy.install(root,'2609')


def verify(root):
    import upgrade_v2_fleet as f
    from rtc_prompt_sync import establish_b3
    from run_v2_beta32_soak import batch
    plan=audit(root)
    with serial_lease('beta32-2609-verify',priority=True),(root/'upgrade/post-reset-serial.jsonl').open('x') as log:
        link=m.Link(f.port('2609'),log)
        try:
            establish_b3(link);text=link.command('J3')
            assert b'STR8-N 2.0b32' in text and b'MONITOR A gen 0000002C VALID default' in text,text
            assert text.count(b'FLASH: wear check ')==1 and plan['expected_wear_peak'].encode() in text,text
            (root/'upgrade/boot.txt').write_bytes(text)
            assert link.dump(0x7D30,0x7D30)==b'\xA0'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==plan['expected_hashes'][bank],bank
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS 2609 full beta32 readback B'+str(bank),flush=True)
            link.command('B3')
            for command in ['VERSION','TIME','APPS','T','M1','W','C']:
                text=link.command(command);(root/f'upgrade/{command}.txt').write_bytes(text)
                if command=='VERSION':assert b'Board: 2609' in text and b'65C816' in text and b'2.0b32' in text and b'MONITOR B gen 00000027 VALID' in text,text
                if command=='TIME':assert b'(-05:00)' in text,text
                if command=='APPS':assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
            for name,title,prompt,query in [('MAINT',b'MAINT 2.4',b'BM> ','?'),('SRAM',b'SRAM 1.4',b'SRAM> ','T'),('WORK',b'WORK 1.4',b'WORK> ','?'),('EDU',b'EDU 1.4',b'EDU> ','?')]:
                text=link.command(name,prompt);assert title in text,text
                text+=link.command(query,prompt)+link.command('Q');(root/f'upgrade/live-{name}.txt').write_bytes(text)
            (root/'upgrade/batch.txt').write_bytes(batch(link,'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')+batch(link,'VERSION;TIME'))
            text=link.command('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed')+link.until(b'SRAM> ')
            text+=link.command('Q');(root/'upgrade/batch-error.txt').write_bytes(text)
            text=link.command('BATCH MAINT;NAME TEST;Q',b'Type YES: ')
            link.send(b'\x1b');text+=link.until(b'BATCH canceled')+link.until(b'BM> ')+link.command('Q')
            (root/'upgrade/batch-escape.txt').write_bytes(text)
            text=link.command('BATCH SRAM;G CLK;Q',b'BATCH stopped: command failed')+link.until(b'SRAM> ')
            assert b'SRAM: 4A' in text,text
            text+=link.command('Q');(root/'upgrade/legacy-clk-batch-refused.txt').write_bytes(text)
            link.command('SRAM',b'SRAM> ');text=link.command('G CLK',b'CLOCK> ')
            assert b'CLOCK 1.8' in text,text
            text+=link.command('STATUS',b'CLOCK> ')+link.command('Q');(root/'upgrade/live-CLOCK.txt').write_bytes(text)
            assert b'Running: yes' in text and b'Backup enabled: yes' in text,text
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(dict(passed=True,board='2609',version='2.0b32',generation=44,
                active_slot='A',fallback_slot='B',fallback_version='2.0b27',j3_reset_verified=True,complete_flash_readback=True,
                expected_hashes=plan['expected_hashes'],native_utilities_verified=True,batch_completion_error_escape_verified=True,
                saved_clk_preserved=True,saved_clk_version='1.8',legacy_clk_batch_refusal_verified=True,wear_peak_verified=True),indent=2)+'\n')
        finally:link.serial.close()


def finalize(root):
    import upgrade_v2_fleet as f
    from datetime import datetime,timezone
    plan=audit(root);assert read(root/'upgrade/post-reset-report.json')['passed']
    retained=root/'retained';campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    with serial_lease('beta32-2609-retained-final',priority=True):
        f.call(f.array,['--root',str(retained),'--board','2609','--port',f.port('2609'),'--stage','final'])
        f.call(f.devices,['--root',str(retained),'--board','2609','--port',f.port('2609'),'--stage','after',
                          '--baseline-index',campaign['baseline_index'],'--clock-source','sram','--clock-name','CLK','--clock19-display-transition'])
    names=['upgrade/model-check.json','upgrade/beta32-board-test-results.json','upgrade/post-reset-report.json',
           'retained/sram-final/report.json','retained/devices-after/report.json']
    assert all(read(root/n)['passed'] for n in names)
    receipt=dict(passed=True,board='2609',version='2.0b32',generation=44,active_slot='A',fallback_slot='B',fallback_version='2.0b27',
                 qualified_at_utc=datetime.now(timezone.utc).isoformat(),build_sha256=sha((BUILD/'build.json').read_bytes()),
                 complete_flash_readback=True,j3_reset_verified=True,fixed_recovery_preserved=True,serial_sram_preserved=True,
                 rtc_history_identity_eeprom_trim_preserved=True,saved_clk_version='1.8',wear_peak_count=plan['wear_peak_count'],
                 evidence={n:sha((root/n).read_bytes()) for n in names})
    for p in [root/'hardware-qualification.json',BUILD/'hardware-qualification-2609.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS 2609 beta32 hardware qualification; full flash/SRAM/EEPROM/history/identity/trim preserved',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','audit','install','verify','finalize']);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();globals()[args.stage](args.root)
