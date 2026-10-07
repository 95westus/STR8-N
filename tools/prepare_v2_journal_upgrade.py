"""Pinned beta7->beta8, MAINT 1.7 and CLOCK 1.2 multi-record update."""
import argparse,json,hashlib
from pathlib import Path
import beta4_migration as m
from build_v2_rtc_journal import OUT,VERSION,GENERATION,ROOT
from build_v2_clock_journal import OUT as CLOCK
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);a=p.parse_args()
    info=json.loads((a.root/'prior/manifest.json').read_text());assert info['repeat_verified'] and info['board']==a.board
    banks=[(a.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    for b,data in enumerate(banks):assert sha(data)==info['banks'][b]['sha256'] and data==(a.root/f'prior/b{b}-repeat.bin').read_bytes()
    assert banks[3][:4096]==(ROOT/'BUILD/v2-rtc-powerfail/str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert banks[3][4096:8192]==bytes([255])*4096 and banks[2][4096:8192]==bytes([255])*4096
    assert banks[3][0x7000:]==(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert banks[1][:8192]==(ROOT/'BUILD/v2-rtc-kernel/str8n-maint-1.6-b1-8000-9fff.bin').read_bytes()
    old=(ROOT/'BUILD/v2-clock-1.1/clock.bin').read_bytes();rec=b'SR\x01\x3f\0\x20'+len(old).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+old
    assert banks[2][:4096]==rec+bytes([255])*(4096-len(rec))
    name,config,counts,seq=m.source_settings(banks[3],'str8n');config=bytearray(config);jr=m.journal(banks[3])
    if jr and jr[15:16]==b'P':
        page=jr[16];offset=(page<<8)-0x8000
        if page in (0xA0,0xB0) and m.slot_valid(banks[3][offset:offset+4096],page) and int.from_bytes(banks[3][offset+8:offset+12],'little')==int.from_bytes(jr[17:21],'little'):
            config[7:13]=b'P'+bytes((page,))+GENERATION.to_bytes(4,'little')
    config[14:]=m.config_sum(config);assert seq<0xFFFFFFFF
    # All current boards have erased D; reject rather than exceed bounded 10-row table.
    assert banks[3][0x5000:0x6000]==bytes([255])*4096
    order=[(1,0x80),(1,0x90),(3,0xC0),(3,0x80),(3,0x90),(3,0xE0),(3,0xB0),(3,0xA0),(2,0x80),(2,0x90)]
    after=list(counts)
    for b,page in order:
        i=b*8+(page>>4)-8;assert after[i]<0xFFFFFF;after[i]+=1
    maint=bytearray((OUT/'str8n-maint-1.7-b1-8000-9fff.bin').read_bytes());maint[3]=255
    body=(CLOCK/'clock.bin').read_bytes();record=b'SR\x01\xff\0\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    record+=bytes([255])*(8192-len(record))
    desired={(1,0x80):bytes(maint[:4096]),(1,0x90):bytes(maint[4096:]),(2,0x80):record[:4096],(2,0x90):record[4096:],
        (3,0xC0):m.metadata(bytes(config),after,seq+1)+bytes([255])*(4096-128),
        (3,0x80):(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes(),(3,0x90):(OUT/'str8n-journal-9000-9fff.bin').read_bytes(),
        (3,0xE0):(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes(),(3,0xA0):(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes(),(3,0xB0):(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()}
    t=json.loads((OUT/'migrator/manifest.json').read_text());image=OUT/'migrator/rtc-migrator-2000.s19';assert sha(image.read_bytes())==t['sha256'];cells,entry=m.read_s19(image)
    cells[t['count']]=10;cells[t['commit_after']]=0;expected=[bytearray(b) for b in banks];payload=[]
    for i,(b,page) in enumerate(order):
        data=desired[b,page];row=bytes((page,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little');cells[t['banks']+i]=b;cells[t['commits']+i]=(b+1 if i in (1,9) else 0)
        for address,value in enumerate(row,t['table']+9*i):cells[address]=value
        expected[b][(page<<8)-0x8000:(page<<8)-0x7000]=data;payload.append(data)
        if i in (1,9):expected[b][3]=0x3F
    installer=m.s19(cells,entry);out=a.root/'upgrade';out.mkdir(exist_ok=False);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,version=VERSION,generation=GENERATION,banner_update=True,clock_update=True,journal_update=True,source_firmware=name,
        steps=[dict(bank=b,sector=p>>4) for b,p in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in expected],installer_sha256=sha(installer),
        config=bytes(config).hex(),counts_before=counts,counts_after=after,fixed_f_changed=False,record_commit_banks=[1,2],clock_sha256=sha(body),journals_preaccount_planned_attempts=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(expected):(out/f'expected-b{b}.bin').write_bytes(data)
    print(a.board,'ten-sector update, two verified record commits; fixed F and B0 preserved')

if __name__=='__main__':main()
