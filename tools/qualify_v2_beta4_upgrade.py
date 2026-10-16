"""Backup-bound 2604-only published-b4 fixture and original-state restoration."""
import argparse,json,shutil,sys,time
from pathlib import Path
import migrate_v2 as u
import beta4_migration as m
BASE=u.ROOT/'output/qualification/beta25-b4-unified-2026-10-14'
BUILD=u.ROOT/'BUILD/v2-beta25-b4-unified'

def save_prior(root,banks,projected=False):
    p=root/'prior-verified';p.mkdir(parents=True,exist_ok=False)
    for i,b in enumerate(banks):
        (p/f'b{i}.bin').write_bytes(b);(p/f'b{i}-repeat.bin').write_bytes(b)
    (p/'manifest.json').write_text(json.dumps(dict(board='2604',repeat_verified=not projected,projected_preimage=projected,banks=[dict(sha256=u.sha(b)) for b in banks]),indent=2)+'\n')

def make_plan(root,banks,target,label,projected=False):
    root.mkdir(parents=True,exist_ok=False);save_prior(root,banks,projected)
    # Source snapshots here have already been read twice. Restore changes only
    # registered system ranges; preserve B0, user records and current devices.
    assert target[0]==banks[0] and target[2]==banks[2]
    order=[(b,s) for b in (1,3) for s in range(15,7,-1) if target[b][(s-8)*4096:(s-7)*4096]!=banks[b][(s-8)*4096:(s-7)*4096]]
    if (3,12) in order:order.remove((3,12));order.insert(0,(3,12))
    # Keep at least a complete retained current slot until its replacement core
    # and matching source monitor are staged. These are supervised test fixtures.
    for s in (10,11):
        if (3,s) in order:order.remove((3,s));order.append((3,s))
    template=u.read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    assert len(order)<=template['max_sectors'];cells[template['count']]=len(order);cells[template['commit_after']]=0
    staged=[bytearray(b) for b in banks];payloads=[];records=[]
    for n,(b,s) in enumerate(order):
        i=(s-8)*4096;data=bytearray(target[b][i:i+4096]);addresses=[]
        if b==1 and s==8:
            assert data[:4]==b'SR\1\x3f';data[3]=255;addresses=[0x8003];records.append(dict(bank=1,address=0x8000))
        if b==3 and s in (10,11) and m.slot_valid(data,s<<4):data[31]=255;addresses=[(s<<12)+31]
        row=bytes((s<<4,))+m.fnv(staged[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,template['table']+9*n)));cells[template['banks']+n]=b;cells[template['commits']+n]=b+1 if addresses else 0
        cells.update(dict(enumerate(b''.join(a.to_bytes(2,'little') for a in addresses).ljust(4,b'\0'),template['commit_addresses']+4*n)))
        staged[b][i:i+4096]=data
        for a in addresses:staged[b][a-0x8000]=0 if b==3 else 63
        payloads.append(data)
    assert staged==target
    out=root/'upgrade';out.mkdir();installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board='2604',version='2.0b25',generation=37,test_fixture=label,target_build=str(BUILD.relative_to(u.ROOT)),prior_directory='prior-verified',
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[u.sha(b) for b in banks],expected_hashes=[u.sha(b) for b in target],
        installer_sha256=u.sha(installer),build_sha256=u.sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=u.sha((BUILD/'migrator/manifest.json').read_bytes()),storage_update=True,commit_records=records,no_sram_format=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(target):(out/f'expected-b{i}.bin').write_bytes(b)
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    return plan

def restoration():
    # Prepare recovery before creating the b4 fixture on hardware. The projected
    # preimage is explicitly labelled; installation freshly compares all banks.
    original=BASE/'original/2604';source=BASE/'projected/2604'
    banks=[(source/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
    target=[bytearray((original/f'prior-verified/b{i}.bin').read_bytes()) for i in range(4)]
    attempts=[]
    for p in (BASE/'fixture/2604/upgrade/plan.json',source/'upgrade/plan.json'):
        attempts.extend((r['bank'],r['sector']) for r in u.read(p)['steps'])
    restore=[(b,s) for b in (1,3) for s in range(8,16) if target[b][(s-8)*4096:(s-7)*4096]!=banks[b][(s-8)*4096:(s-7)*4096]]
    if (3,12) not in restore:restore.append((3,12))
    attempts+=restore
    journal=m.journal(target[3]);counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)]
    for b,s in attempts:assert counts[b*8+s-8]<0xFFFFFF;counts[b*8+s-8]+=1
    sequence=max(int.from_bytes(m.journal(banks[3])[4:8],'little'),int.from_bytes(journal[4:8],'little'))+1
    i=next(i for i in range(0x4000,0x5000,128) if target[3][i:i+128]==b'\xff'*128)
    target[3][i:i+128]=m.metadata(journal[8:24],counts,sequence)
    plan=make_plan(BASE/'restoration/2604',banks,target,'original-beta24-A-beta25-B',True)
    assert {(r['bank'],r['sector']) for r in plan['steps']}==set(restore)
    ledger=dict(attempts=[dict(bank=b,sector=s) for b,s in attempts],counts_after=counts,sequence=sequence,original_journal_preserved=True)
    (BASE/'restoration/erase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print('PREPARED original-state restoration; all',len(attempts),'fixture/upgrade/restore erases accounted',flush=True)

def fixture():
    original=BASE/'original/2604';manifest=u.read(original/'prior-verified/manifest.json');assert manifest['repeat_verified']
    banks=[(original/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert b==(original/f'prior-verified/b{i}-repeat.bin').read_bytes() and u.sha(b)==manifest['banks'][i]['sha256']
    expected=u.ROOT/'output/qualification/beta25-recovery-2026-10-14/2604/post-005/report.json';assert [u.sha(b) for b in banks]==u.read(expected)['full_flash_hashes']
    kit=u.ROOT/'BUILD/v2-beta4/kit';m.validate_kit(kit);target=[bytearray(b) for b in banks]
    target[3][:8192]=m.maintenance_storage(kit)
    for offset,name in ((0x2000,'slot-a'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')):target[3][offset:offset+4096]=(kit/f'str8n-v2-b4-{name}.bin').read_bytes()
    journal=m.journal(banks[3]);cfg=bytearray(journal[8:24]);cfg[7:13]=b'P\xA0'+(13).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    steps=[(3,s) for s in range(8,16) if target[3][(s-8)*4096:(s-7)*4096]!=banks[3][(s-8)*4096:(s-7)*4096]]
    if (3,12) not in steps:steps.append((3,12))
    counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)]
    for b,s in steps:counts[b*8+s-8]+=1
    seq=int.from_bytes(journal[4:8],'little')+1
    i=next(i for i in range(0x4000,0x5000,128) if target[3][i:i+128]==b'\xff'*128)
    target[3][i:i+128]=m.metadata(cfg,counts,seq)
    plan=make_plan(BASE/'fixture/2604',banks,target,'published-b4-source')
    assert len(plan['steps'])==len(steps)
    print('PREPARED 2604 published b4 A fixture; original B0/B1/B2 and devices retained;',len(steps),'accounted erases',flush=True)

def rehearse(root):
    import test_v2_rtc_upgrade as t
    plan=u.read(root/'upgrade/plan.json');t.MANIFEST=u.read(BUILD/'migrator/manifest.json');t.S=t.MANIFEST['symbols'];t.kernel.fw.OUT=BUILD
    expected=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
    prior=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)];Base=t.Memory
    class Memory(Base):
        def mutated(self,kind,address,value):
            assert self.bank in (1,3),'User bank mutated'
            if self.bank==3 and kind=='program' and address in (0xA01F,0xB01F) and value==0:
                i=(address&0xF000)-0x8000;assert bytes(self.banks[3][i:i+4096])==expected[3][i:i+4096]
            super().mutated(kind,address,value)
    t.Memory=Memory;sys.argv=['rehearse','--root',str(root)];t.main()
    r=u.read(root/'upgrade/model-check.json');r['fixture_user_banks_preserved']=True;(root/'upgrade/model-check.json').write_text(json.dumps(r,indent=2)+'\n')

def install(root):
    plan=u.read(root/'upgrade/plan.json');check=u.read(root/'upgrade/model-check.json');assert check['passed'] and check['fixture_user_banks_preserved']
    assert plan['board']=='2604' and check['expected_hashes']==plan['expected_hashes']
    def audit():
        assert u.sha((BUILD/'migrator/manifest.json').read_bytes())==plan['template_manifest_sha256']
        meta=u.read(BUILD/'build.json')
        for name,h in meta['artifacts'].items():assert u.sha((BUILD/name).read_bytes())==h
        return meta
    u.deploy.BUILD=BUILD;u.deploy.audit=audit;u.deploy.install(root,'2604')

def capture(root):
    from serial.tools.list_ports import comports
    from rtc_boards import SERIALS
    from serial_test_coordination import serial_lease
    out=root/'physical-reset';out.mkdir(exist_ok=False)
    with serial_lease('2604-b4-test-reset'),(out/'serial.jsonl').open('x') as log:
        port=next(p.device for p in comports() if p.serial_number==SERIALS['2604']);l=m.Link(port,log)
        try:
            print('ARMED: 2604-only receive-only boot capture for 15 minutes',flush=True)
            text=l.until(b'\r\nB3> ',900);(out/'boot.txt').write_bytes(text)
            label=u.read(root/'upgrade/plan.json')['test_fixture'];version=b'2.0b4' if label=='published-b4-source' else b'2.0b25'
            assert b'STR8-N '+version in text,text
            active=l.dump(0x7D30,0x7D30);assert active==(b'\xA0' if version==b'2.0b4' else b'\xB0')
            state=u.read(root/'upgrade/install/reset-pending.json');state.update(physical_reset_pending=False,physical_reset_verified=True)
            (root/'upgrade/install/reset-pending.json').write_text(json.dumps(state,indent=2)+'\n')
            (out/'report.json').write_text(json.dumps(dict(passed=True,version=version.decode(),active_page=active[0]),indent=2)+'\n')
            print('PASS physical RESET:',version.decode(),'on 2604',flush=True)
        finally:l.serial.close()

def verify_restoration():
    import re
    import upgrade_v2_fleet as fleet
    import archive_v2_edu_sram as array
    import capture_v2_display_devices as devices
    from serial_test_coordination import serial_lease
    from rtc_prompt_sync import establish_b3
    root=BASE/'restoration/2604';original=BASE/'original/2604'
    assert u.read(root/'physical-reset/report.json')['passed']
    upgrade=u.read(BASE/'hardware/2604/retest/report.json');assert upgrade['passed'] and upgrade['fixed_f_wear_report_verified']
    ledger=u.read(BASE/'restoration/erase-ledger.json');out=BASE/'final';out.mkdir(exist_ok=False)
    plan=u.read(root/'upgrade/plan.json');port=fleet.port('2604')
    with serial_lease('2604-b4-restoration-verify'),(out/'serial.jsonl').open('x') as log:
        l=m.Link(port,log)
        try:
            establish_b3(l);assert l.dump(0x7D30,0x7D30)==b'\xB0'
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                data=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert data==(root/f'upgrade/expected-b{bank}.bin').read_bytes()
                before=(original/f'prior-verified/b{bank}.bin').read_bytes()
                if bank!=3:assert data==before
                else:
                    differences=[i for i in range(0,len(data),128) if data[i:i+128]!=before[i:i+128]]
                    assert len(differences)==1 and 0x4000<=differences[0]<0x5000
                    assert before[differences[0]:differences[0]+128]==b'\xff'*128
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(u.sha(data))
            l.command('B3');text=l.command('W');(out/'wear.txt').write_bytes(text)
            rows=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',text);assert len(rows)==32
            counts=[None]*32
            for b,s,n in rows:counts[int(b)*8+int(s,16)-8]=int(n,16)
            assert counts==ledger['counts_after']
            text=l.command('TIME');assert b'(+00:00)' in text and b'UTC ' not in text;(out/'time.txt').write_bytes(text)
            l.command('R MAINT',b'BM> ');assert b'Board: 2604' in l.command('NAME',b'BM> ');l.command('Q')
            l.command('R CLOCK',b'CLOCK> ');history=l.command('HISTORY',b'CLOCK> ');status=l.command('STATUS',b'CLOCK> ');l.command('Q')
            assert b'History unavailable' not in history and b'Power-fail latched: no' in status
            (out/'clock-history.txt').write_bytes(history+status)
        finally:l.serial.close()
    retained=out/'retained';shutil.copytree(original/'retained',retained)
    with serial_lease('2604-b4-final-retention'):
        fleet.call(array,['--root',str(retained),'--board','2604','--port',port,'--stage','final'])
        campaign=u.read(u.ROOT/'output/qualification/active-rtc-campaign.json')
        fleet.call(devices,['--root',str(out),'--board','2604','--port',port,'--stage','before','--baseline-index',campaign['baseline_index']])
    before=original/'retained/devices-before';after=out/'devices-before'
    assert (before/'eeprom-0.bin').read_bytes()[:137]==(after/'eeprom-0.bin').read_bytes()[:137]
    prior=u.read(before/'report.json');now=u.read(after/'report.json')
    assert (prior['control_register'],prior['trim_steps'])==(now['control_register'],now['trim_steps'])
    assert (before/'eui.txt').read_bytes()==(after/'eui.txt').read_bytes()
    result=dict(passed=True,board='2604',source='published 2.0b4 generation 13',target='2.0b25 generation 37',
        physical_b4_boot_verified=True,unified_upgrade_passed=True,b4_A_preserved_during_upgrade=True,beta25_B_verified=True,
        final_original_beta24_A_beta25_B_restored=True,original_journal_records_preserved=True,
        accounted_fixture_upgrade_restore_erases=len(ledger['attempts']),flash_hashes=hashes,
        full_sram_preserved=True,repaired_eeprom_history_preserved=True,rtc_control_trim_eui_preserved=True,other_boards_accessed=False,
        physical_source_layout='published b4 core/A/MAINT; existing system programs retained in B1/B2',
        pure_b4_full_layout_A_and_B='17-sector conversion qualified in exact linked installer/monitor models')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    receipt=BUILD/'hardware-qualification-b4-2604.json';assert not receipt.exists()
    (receipt).write_text(json.dumps(dict(result,artifacts=u.read(BUILD/'build.json')['artifacts'],evidence=str(out.relative_to(u.ROOT))),indent=2)+'\n')
    print('PASS b4->b25 hardware upgrade and original-state restoration; all',len(ledger['attempts']),'erases accounted; full SRAM/EEPROM/settings preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('fixture','restoration','rehearse','install','capture','verify-restoration'));p.add_argument('--root',type=Path);a=p.parse_args()
    if a.stage=='fixture':fixture()
    elif a.stage=='restoration':restoration()
    elif a.stage=='verify-restoration':verify_restoration()
    else:dict(rehearse=rehearse,install=install,capture=capture)[a.stage](a.root.resolve())
