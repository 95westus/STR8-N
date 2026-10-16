"""Exact-backup generation 34 startup-key deployment to 2604/2609."""
import json,sys,shutil
import beta4_migration as m
import update_v2_beta24 as deploy
import backup_str8n_board as backup
import qualify_v2_beta24_power as power
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease

ROOT=deploy.ROOT
BUILD=ROOT/'BUILD/v2-startup-keys'
OLD=ROOT/'BUILD/v2-board-name-fix006'
BASE=ROOT/'output/qualification/startup-keys-2026-10-14'
ORIGINAL_BASE=BASE
REPAIR_BASE=BASE/'slot-header-repair'
deploy.BUILD=BUILD
BOARDS=tuple(sys.argv[2:]) or ('2604','2609')

def port(board):return next(p.device for p in comports() if p.serial_number==SERIALS[board])

def backups():
    with serial_lease('startup-key-backup'):
        for b in BOARDS:
            assert b in ('2604','2609')
            root=BASE/b;root.mkdir(parents=True,exist_ok=True)
            target=root/'prior-verified'
            if target.exists():
                assert not (target/'manifest.json').exists(), 'Existing backup must not be replaced'
                assert list(target.iterdir())==[target/'capture.jsonl'] and (target/'capture.jsonl').stat().st_size==0
                saved=root/'prior-port-open-failed'
                assert target.resolve().is_relative_to(ROOT.resolve()) and saved.resolve().is_relative_to(ROOT.resolve())
                target.rename(saved)
            power.call(backup,['--port',port(b),'--board',b,'--out',str(root/'prior-verified')])

def reference():
    campaign=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
    with serial_lease('startup-key-reference'):
        for b in BOARDS:
            root=BASE/b/'retained';prior=root/'sram-prior';prior.mkdir(parents=True,exist_ok=False)
            shutil.copyfile(ROOT/f'output/qualification/fix006-2026-10-14/{b}/power/sram-final/array-0.bin',prior/'array-0.bin')
            power.call(power.array,['--root',str(root),'--board',b,'--port',port(b),'--stage','final'])
            shutil.move(root/'sram-final',root/'sram-reference')
            shutil.copyfile(root/'sram-reference/array-0.bin',prior/'array-0.bin')
            power.call(power.devices,['--root',str(root),'--board',b,'--port',port(b),'--stage','before','--baseline-index',campaign['baseline_index']])
            print('PASS',b,'fresh 128 KiB SRAM and RTC/EEPROM reference',flush=True)

def prepare(b,repair=False):
    meta=deploy.audit();root=BASE/b;prior=deploy.read(root/'prior-verified/manifest.json')
    assert prior['repeat_verified'] and prior['board']==b
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,data in enumerate(banks):
        assert len(data)==32768 and data==(root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert deploy.sha(data)==prior['banks'][i]['sha256']
    final=[bytearray(x) for x in banks]
    regions=[(0x2000,'str8n-v2-recovery-slot-a0.bin'),(0x3000,'str8n-v2-recovery-slot-b0.bin')]
    if repair:
        for i,data in enumerate(banks):assert data==(ORIGINAL_BASE/b/f'upgrade/expected-b{i}.bin').read_bytes(), 'Repair preimage differs from installed plan'
        for page,offset in ((0xA0,0x2000),(0xB0,0x3000)):
            new=(BUILD/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes();old=banks[3][offset:offset+4096]
            assert new[:18]==old[:18] and new[20:70]==old[20:70] and new[72:]==old[72:]
    else:regions += [(0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin')]
    for offset,name in regions:
        if not repair:assert banks[3][offset:offset+4096]==(OLD/name).read_bytes(),name
        final[3][offset:offset+4096]=(BUILD/name).read_bytes()
    name=meta['maintenance_storage_file'];oldmaint=(OLD/name).read_bytes();newmaint=(BUILD/name).read_bytes()
    if not repair:assert banks[1][:len(oldmaint)]==oldmaint
    assert newmaint[4096:]==oldmaint[4096:]
    if not repair:final[1][:4096]=newmaint[:4096]
    assert final[3][0x6000:0x7000]==banks[3][0x6000:0x7000], 'launcher must stay unchanged'
    order=[(3,12),(3,11),(3,10)] if repair else [(3,12),(3,15),(1,8),(3,11),(3,10)]
    j=m.journal(banks[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    if cfg[7]==ord('P'):cfg[9:13]=meta['generation'].to_bytes(4,'little')
    cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for bank,sector in order:
        index=bank*8+sector-8;assert counts[index]<0xFFFFFF;counts[index]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[2]==banks[2] and final[1][4096:]==banks[1][4096:]
    for start,end in ((0,0x2000),(0x5000,0x6000)):assert final[3][start:end]==banks[3][start:end]
    mf=deploy.read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    expected=[bytearray(x) for x in banks];payloads=[]
    for i,(bank,sector) in enumerate(order):
        offset=(sector-8)*4096;data=bytearray(final[bank][offset:offset+4096]);commit=(bank,sector)==(1,8)
        if commit:data[3]=255
        data=bytes(data)
        row=bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos,value in enumerate(row,mf['table']+9*i):cells[pos]=value
        cells[mf['banks']+i]=bank;cells[mf['commits']+i]=2 if commit else 0
        for pos in range(mf['commit_addresses']+4*i,mf['commit_addresses']+4*i+4):cells[pos]=0
        if commit:
            cells[mf['commit_addresses']+4*i]=3;cells[mf['commit_addresses']+4*i+1]=0x80
        expected[bank][offset:offset+4096]=data
        if commit:expected[1][3]=63
        payloads.append(data)
    assert expected==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=b,version=meta['version'],generation=meta['generation'],source_generation=meta['generation'] if repair else deploy.read(OLD/'build.json')['generation'],prior_directory='prior-verified',
        steps=[dict(bank=bank,sector=sector) for bank,sector in order],prior_hashes=[deploy.sha(x) for x in banks],
        expected_hashes=[deploy.sha(x) for x in final],installer_sha256=deploy.sha(installer),
        build_sha256=deploy.sha((BUILD/'build.json').read_bytes()),counts_before=before,counts_after=counts,
        storage_update=True,commit_records=[] if repair else [dict(bank=1,address=0x8000)],config=cfg.hex(),no_sram_format=True,
        private_ram_edit_header_repair=repair)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for i,data in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED',b,order,'all retained data preserved',flush=True)

if __name__=='__main__':
    stage=sys.argv[1]
    repair=stage.startswith('repair-')
    if repair:BASE=REPAIR_BASE;stage=stage.removeprefix('repair-')
    if stage=='backups':backups()
    elif stage=='reference':reference()
    elif stage=='prepare':
        for b in BOARDS:prepare(b,repair)
    elif stage=='install':
        for b in BOARDS:deploy.install(BASE/b,b)
    else:raise ValueError(stage)
