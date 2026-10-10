"""Backup-bound beta20/21 -> beta22; preserve records and device settings."""
import argparse,hashlib,json
from pathlib import Path
import beta4_migration as m
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-startup'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=('2512','2205','2609'));a=p.parse_args()
    prior=read(a.root/'prior/manifest.json');assert prior['repeat_verified'] and prior['board']==a.board
    banks=[(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for i,b in enumerate(banks):assert len(b)==32768 and b==(a.root/f'prior/b{i}-repeat.bin').read_bytes() and sha(b)==prior['banks'][i]['sha256']
    gens=[]
    for page,offset in ((0xA0,0x2000),(0xB0,0x3000)):
        slot=banks[3][offset:offset+4096];assert m.slot_valid(slot,page)
        gens.append(int.from_bytes(slot[8:12],'little'))
    assert gens[0]==gens[1] and gens[0] in (29,30),'Unqualified source generation'
    old=ROOT/('BUILD/v2-combined-display' if gens[0]==29 else 'BUILD/v2-local-time')
    meta=read(BUILD/'build.json');audit=read(BUILD/'spi-startup-candidate-check.json')
    assert audit['passed'] and audit['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert audit['artifacts']==meta['artifacts'] and meta['version']=='2.0b22' and meta['generation']==31
    for name,digest in meta['artifacts'].items():assert sha((BUILD/name).read_bytes())==digest
    for name,digest in audit['model_report_hashes'].items():assert sha((BUILD/name).read_bytes())==digest and read(BUILD/name)['passed']
    for offset,name,length in ((0,'str8n-rtc-component-8000-8fff.bin',4096),(0x1000,'str8n-journal-9000-9fff.bin',3072),(0x2000,'str8n-v2-recovery-slot-a0.bin',4096),(0x3000,'str8n-v2-recovery-slot-b0.bin',4096),(0x6000,'str8n-v2-recovery-e000-efff.bin',4096),(0x7000,'str8n-v2-recovery-f000-ffff.bin',4096)):
        assert banks[3][offset:offset+length]==(old/name).read_bytes()[:length],name
    assert banks[2][0x4800:0x5200]==(old/'boot-status/asset.bin').read_bytes()
    final=[bytearray(b) for b in banks];relocate=gens[0]==29;commits=[]
    if relocate:
        assert banks[1][0x3000:0x6000]==b'\xff'*12288,'CLOCK destination occupied'
        assert banks[2][0x6000:0x6600]==b'\xff'*1536,'Local asset destination occupied'
        h=banks[2][:24];n=int.from_bytes(h[6:8],'little')
        assert h[:6]==b'SR\x01\x3f\0\x20' and h[8:24].rstrip(b'\0')==b'CLOCK'
        assert banks[2][24:24+n]==(old/'clock/clock.bin').read_bytes()
        final[2][:24+n]=b'\xff'*(24+n)
        body=(BUILD/'clock/clock.bin').read_bytes();record=b'SR\x01\x3f\0\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
        assert len(record)<=12288;final[1][0x3000:0x3000+len(record)]=record
        final[2][0x6000:0x6600]=(BUILD/'local-display/asset.bin').read_bytes()
        commits=[dict(bank=1,address=0xB000)]
        order=[(3,12),(1,13),(1,12),(1,11),(2,9),(2,8),(2,14),(2,13),(2,12),(3,14),(3,11),(3,10)]
    else:
        body=(BUILD/'clock/clock.bin').read_bytes();record=b'SR\x01\x3f\0\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
        assert banks[1][0x3000:0x3000+len(record)]==record,'Current CLOCK changed'
        assert banks[2][0x6000:0x6600]==(BUILD/'local-display/asset.bin').read_bytes()
        order=[(3,12),(2,13),(2,12),(3,11),(3,10)]
        if banks[3][0x6000:0x7000]!=(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes():order.insert(3,(3,14))
    final[2][0x4800:0x5200]=(BUILD/'boot-status/asset.bin').read_bytes()
    for offset,name in ((0x2000,'str8n-v2-recovery-slot-a0.bin'),(0x3000,'str8n-v2-recovery-slot-b0.bin'),(0x6000,'str8n-v2-recovery-e000-efff.bin')):
        final[3][offset:offset+4096]=(BUILD/name).read_bytes()
    journal=m.journal(banks[3]);assert journal;cfg=bytearray(journal[8:24]);assert cfg[14:]==m.config_sum(cfg)
    saved_edu=cfg[13]
    if cfg[7]==ord('P'):cfg[9:13]=meta['generation'].to_bytes(4,'little')
    cfg[14:]=m.config_sum(cfg);counts=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for b,s in order:
        idx=b*8+s-8;assert counts[idx]<0xFFFFFF;counts[idx]+=1
    seq=int.from_bytes(journal[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert cfg[13]==saved_edu and final[0]==banks[0] and final[3][:0x2000]==banks[3][:0x2000] and final[3][0x7000:]==banks[3][0x7000:]
    if not relocate:assert final[1]==banks[1]
    else:
        assert final[1][:0x3000]==banks[1][:0x3000] and final[1][0x6000:]==banks[1][0x6000:]
        assert final[2][24+n:0x4800]==banks[2][24+n:0x4800]
    assert final[2][0x5200:0x6000]==banks[2][0x5200:0x6000] and final[2][0x6600:]==banks[2][0x6600:]
    mf=read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    stage=[bytearray(b) for b in final]
    if relocate:stage[1][0x3003]=255
    expected=[bytearray(b) for b in banks];payload=[]
    for i,(b,s) in enumerate(order):
        offset=(s-8)*4096;data=bytes(stage[b][offset:offset+4096]);row=bytes((s<<4,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos,v in enumerate(row,mf['table']+9*i):cells[pos]=v
        cells[mf['banks']+i]=b;commit=relocate and (b,s)==(1,11);cells[mf['commits']+i]=b+1 if commit else 0
        for slot in range(2):
            value=0xB003 if commit and slot==0 else 0;cells[mf['commit_addresses']+4*i+2*slot]=value&255;cells[mf['commit_addresses']+4*i+2*slot+1]=value>>8
        expected[b][offset:offset+4096]=data
        if commit:expected[1][0x3003]=63
        payload.append(data)
    assert expected==final,'Unmodeled final sector changes'
    out=a.root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,source_generation=gens[0],version=meta['version'],generation=meta['generation'],steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),build_sha256=audit['build_sha256'],config=cfg.hex(),counts_before=before,counts_after=counts,storage_update=True,local_time_update=True,spi_startup_update=True,clock_update=relocate,banner_update=False,journal_update=False,commit_records=commits,clock_sha256=meta['clock_sha256'],clock_bank=1,clock_address=0xB000,no_sram_format=True,quiet_monitor_return=True,weekday_display=True,preserved='B0, MAINT, other saved records, RTC provider/journal/identity/recovery and EDU mode')
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(final):(out/f'expected-b{b}.bin').write_bytes(data)
    print('PREPARED',a.board,len(order),'sectors; source generation',gens[0],'; saved EDU',hex(saved_edu))

if __name__=='__main__':main()
