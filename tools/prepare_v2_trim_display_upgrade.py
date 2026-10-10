"""Prepare six-sector beta17 -> beta18 display updates from repeated backups."""
import argparse
import hashlib
import json
from pathlib import Path
import beta4_migration as m
from build_v2_spi_resident import merge_identity_tail

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'BUILD/v2-trim-display'
sha=lambda data:hashlib.sha256(data).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True)
    p.add_argument('--build',type=Path,default=BUILD)
    a=p.parse_args();build=a.build.resolve();prior=read(a.root/'prior/manifest.json')
    assert prior['repeat_verified'] and prior['board']==a.board
    banks=[(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):
        assert b==(a.root/f'prior/b{i}-repeat.bin').read_bytes() and sha(b)==prior['banks'][i]['sha256']
    meta=read(build/'build.json');check=read(build/'trim-display-test-results.json')
    assert check['passed'] and check['artifacts']==meta['artifacts'] and meta['trim_display']
    assert check['status_asset_sha256']==meta['status_asset_sha256']
    for name,digest in meta['artifacts'].items():assert sha((build/name).read_bytes())==digest,name
    assert banks[3][0x7000:]==(build/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    component=(build/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    if meta.get('weekday_display'):assert banks[3][:0x900]==component[:0x900]
    else:assert banks[3][:0x1000]==component
    journal_source=ROOT/'BUILD/v2-trim-display' if meta.get('weekday_display') else build
    assert banks[3][0x1000:0x1C00]==(journal_source/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    for offset in (0x2000,0x3000):
        slot=banks[3][offset:offset+4096]
        assert slot[:3]==b'MI\x01' and int.from_bytes(slot[8:12],'little')==26
        assert m.slot_valid(slot,0x80+(offset>>8)) and b'STR8-N 2.0b17' in slot
    assert banks[2][0x4800:0x4804]==b'BS\x01\x02'
    assert m.crc(banks[2][0x4800:0x5000])==0
    assert banks[2][0x5000:0x5200]==b'\xff'*512,'Expanded formatter allocation occupied; no plan'
    final=[bytearray(b) for b in banks]
    for offset,name in ((0x2000,'str8n-v2-recovery-slot-a0.bin'),(0x3000,'str8n-v2-recovery-slot-b0.bin'),(0x6000,'str8n-v2-recovery-e000-efff.bin')):
        final[3][offset:offset+4096]=(build/name).read_bytes()
    final[2][0x4800:0x5200]=(build/'boot-status/asset.bin').read_bytes()
    order=[(3,12),(2,13),(2,12),(3,14),(3,11),(3,10)]
    if meta.get('weekday_display'):
        final[3][:0x1000]=component
        order.insert(3,(3,8))
        final[3][0x1000:0x2000]=merge_identity_tail(banks[3][0x1000:0x2000],(build/'str8n-journal-9000-9fff.bin').read_bytes())
        order.insert(4,(3,9))
    journal=m.journal(banks[3]);assert journal
    cfg=bytearray(journal[8:24]);assert cfg[14:]==m.config_sum(cfg)
    if cfg[7]==ord('P'):cfg[9:13]=meta['generation'].to_bytes(4,'little')
    cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for b,s in order:
        idx=b*8+s-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(journal[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[1]==banks[1]
    assert final[2][:0x4800]==banks[2][:0x4800] and final[2][0x5200:]==banks[2][0x5200:]
    assert final[3][0x1C00:0x2000]==banks[3][0x1C00:0x2000] and final[3][0x7000:]==banks[3][0x7000:]
    assert final[3][:0x900]==banks[3][:0x900]
    mf=read(build/'migrator/manifest.json');cells,entry=m.read_s19(build/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    expected=[bytearray(b) for b in banks];payload=[]
    for i,(b,s) in enumerate(order):
        offset=(s-8)*4096;data=bytes(final[b][offset:offset+4096])
        row=bytes((s<<4,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos,v in enumerate(row,mf['table']+9*i):cells[pos]=v
        cells[mf['banks']+i]=b;cells[mf['commits']+i]=0
        expected[b][offset:offset+4096]=data;payload.append(data)
    assert expected==final
    out=a.root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry)
    (out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,version=meta['version'],generation=meta['generation'],
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],
        expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),
        config=cfg.hex(),counts_before=before,counts_after=counts,
        storage_update=True,trim_display_update=True,banner_update=bool(meta.get('weekday_display')),journal_update=False,
        quiet_monitor_return=bool(meta.get('quiet_monitor_return')),weekday_display=bool(meta.get('weekday_display')),
        journal_helper_relocation=bool(meta.get('weekday_display')),
        clock_update=False,commit_records=[],no_sram_format=True,
        preserved='B0/B1, all saved records, B3 F/RTC provider/EUI tail; journal helpers relinked; RTC/SRAM/EEPROM not accessed by installer')
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(final):(out/f'expected-b{b}.bin').write_bytes(data)
    print('PREPARED',a.board,len(order),'backup-bound sectors; saved programs, RTC/identity and recovery retained')

if __name__=='__main__':main()
