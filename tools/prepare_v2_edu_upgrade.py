"""Prepare beta14-to-beta15 from repeated full-board backups; no ports."""
import argparse,hashlib,json
from pathlib import Path
import beta4_migration as m
from build_v2_spi_resident import OUT
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=('2512','2205','2609'));a=p.parse_args()
    prior=json.loads((a.root/'prior/manifest.json').read_text());assert prior['repeat_verified'] and prior['board']==a.board
    banks=[(a.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    old=a.root.parent/'source-beta14';oldmeta=json.loads((old/'build.json').read_text());meta=json.loads((OUT/'build.json').read_text())
    assert oldmeta['version']=='2.0b14' and meta['version']=='2.0b15' and meta['edu_mode']
    for b,data in enumerate(banks):assert data==(a.root/f'prior/b{b}-repeat.bin').read_bytes() and sha(data)==prior['banks'][b]['sha256']
    for offset,name in ((0,'str8n-rtc-component-8000-8fff.bin'),(0x6000,'str8n-v2-recovery-e000-efff.bin'),(0x7000,'str8n-v2-recovery-f000-ffff.bin'),(0x2000,'str8n-v2-recovery-slot-a0.bin'),(0x3000,'str8n-v2-recovery-slot-b0.bin')):
        assert banks[3][offset:offset+4096]==(old/name).read_bytes(),name
    assert banks[3][4096:7168]==(old/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    assert banks[3][:4096]==(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert banks[3][4096:7168]==(OUT/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    assert banks[1][:8192]==(OUT/'str8n-maint-1.7-b1-8000-9fff.bin').read_bytes()
    assert banks[3][0x7000:]==(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    work=(OUT/'workspace/workspace.bin').read_bytes();wm=json.loads((OUT/'workspace/build.json').read_text());assert wm['version']=='1.1' and sha(work)==wm['sha256']
    oldwork=banks[2][0x3000:0x3018];assert oldwork[:8]==b'SR\x01\x3f\0\x40\xFA\x11' and oldwork[8:]==b'WORK'.ljust(16,b'\0')
    b2=bytearray(banks[2]);old_end=0x3000+24+4602;b2[0x3000:old_end]=b'\xff'*(old_end-0x3000)
    moved=[];removed=[]
    if a.board=='2609':
        bad=(ROOT/'output/qualification/storage-demo-2609-2026-10-08/flash-repair/before-b2.bin').read_bytes()[0x4240:0x4272]
        assert banks[2][0x4240:0x4272]==bad and bad[:24]==b'SR\x01\x3f\0\x26\x1a\0'+b'DEMO'.ljust(16,b'\0')
        good=banks[2][0x4280:0x42B2];assert good[:24]==b'SR\x01\x3f\0\x26\x1a\0'+b'DEMO2'.ljust(16,b'\0')
        assert b2[0x4540:0x4572]==b'\xff'*50
        b2[0x4240:0x4272]=b'\xff'*50;b2[0x4280:0x42B2]=b'\xff'*50;b2[0x4540:0x4572]=good
        moved=['DEMO2: C280 -> C540'];removed=['Incomplete agent-created DEMO: C240']
    record=b'SR\x01\x3f\0\x40'+len(work).to_bytes(2,'little')+b'WORK'.ljust(16,b'\0')+work
    assert b2[0x3000:0x3000+len(record)]==b'\xff'*len(record),'New WORK overlaps unrecognized data'
    b2[0x3000:0x3000+len(record)]=record
    edu=(OUT/'edu/edu.bin').read_bytes();em=json.loads((OUT/'edu/build.json').read_text());assert sha(edu)==em['sha256']
    edurecord=b'SR\x01\x3f\0\x20'+len(edu).to_bytes(2,'little')+b'EDU'.ljust(16,b'\0')+edu
    assert b2[0x4600:0x4600+len(edurecord)]==b'\xff'*len(edurecord)
    config_record=m.journal(banks[3]);assert config_record is not None
    config=bytearray(config_record[8:24]);assert config[14:]==m.config_sum(config)
    if config[7]==ord('P'):config[9:13]=meta['generation'].to_bytes(4,'little')
    config[13]=0xA5 if a.board=='2512' else 0;config[14:]=m.config_sum(config)
    before_counts=[int.from_bytes(config_record[24+i*3:27+i*3],'little') for i in range(32)];counts=before_counts[:]
    order=[(3,0xC0),(2,0xB0),(2,0xC0),(3,0xE0),(3,0xB0),(3,0xA0)]
    for b,page in order:
        index=b*8+(page>>4)-8;assert counts[index]<0xFFFFFF;counts[index]+=1
    sequence=int.from_bytes(config_record[4:8],'little');assert sequence<0xFFFFFFFF
    desired={(3,0xC0):m.metadata(config,counts,sequence+1)+b'\xff'*(4096-128),(2,0xB0):bytes(b2[0x3000:0x4000]),(2,0xC0):bytes(b2[0x4000:0x5000]),
        (3,0xE0):(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes(),(3,0xB0):(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes(),(3,0xA0):(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes()}
    stage_b=bytearray(desired[2,0xB0]);stage_b[3]=255;desired[2,0xB0]=bytes(stage_b)
    manifest=json.loads((OUT/'migrator/manifest.json').read_text());assert manifest['commit_address']==0xB003
    cells,entry=m.read_s19(OUT/'migrator/rtc-migrator-2000.s19');cells[manifest['count']]=len(order);cells[manifest['commit_after']]=0
    expected=[bytearray(b) for b in banks];payload=[]
    for i,(b,page) in enumerate(order):
        data=desired[b,page];row=bytes((page,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells[manifest['banks']+i]=b;cells[manifest['commits']+i]=3 if i==2 else 0
        for addr,value in enumerate(row,manifest['table']+9*i):cells[addr]=value
        expected[b][(page<<8)-0x8000:(page<<8)-0x7000]=data
        if i==2:expected[2][0x3003]=0x3F
        payload.append(data)
    assert expected[2]==b2 and expected[0]==banks[0] and expected[1]==banks[1]
    assert expected[3][:8192]==banks[3][:8192] and expected[3][0x7000:]==banks[3][0x7000:]
    out=a.root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,version=meta['version'],generation=meta['generation'],source_firmware='verified beta14',banner_update=True,journal_update=True,binding_update=True,trim_update=True,spi_update=True,clock_update=False,work_update=True,
        steps=[dict(bank=b,sector=p>>4) for b,p in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in expected],installer_sha256=sha(installer),config=bytes(config).hex(),counts_before=before_counts,counts_after=counts,
        record_commit_address=0xB000,record_commit_banks=[2],record_commit_bank=2,clock_build=str(ROOT/'BUILD/v2-clock-1.5'),clock_sha256=sha((ROOT/'BUILD/v2-clock-1.5/clock.bin').read_bytes()),edu_mode='OFF' if a.board=='2512' else 'ON',moved_records=moved,removed_records=removed,no_sram_format=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(expected):(out/f'expected-b{b}.bin').write_bytes(data)
    final_b2=bytearray(b2);final_b2[0x4600:0x4600+len(edurecord)]=edurecord;(out/'expected-provisioned-b2.bin').write_bytes(final_b2)
    print('PREPARED',a.board,plan['edu_mode'],'6 sectors; WORK commit last, fresh EDU record after reset; fixed F/B0/B1/EUI retained',flush=True)
if __name__=='__main__':main()
