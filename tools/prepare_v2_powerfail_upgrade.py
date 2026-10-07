"""Prepare exact beta6->beta7 plus atomic CLOCK 1.1 record replacement."""
import argparse,json,hashlib
from pathlib import Path
import beta4_migration as m
from build_v2_rtc_powerfail import OUT,VERSION,GENERATION
from build_v2_clock_powerfail import OUT as CLOCK

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);a=p.parse_args()
    manifest=json.loads((a.root/'prior/manifest.json').read_text());assert manifest['repeat_verified'] and manifest['board']==a.board
    banks=[(a.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    for b,data in enumerate(banks):assert sha(data)==manifest['banks'][b]['sha256'] and data==(a.root/f'prior/b{b}-repeat.bin').read_bytes()
    assert banks[3][:4096]==(ROOT/'BUILD/v2-rtc-banner/str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert banks[3][0x7000:]==(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    oldclock=(ROOT/'BUILD/v2-clock/clock.bin').read_bytes()
    oldrecord=b'SR\x01\x3f'+b'\0\x20'+len(oldclock).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+oldclock
    assert banks[2][:4096]==oldrecord+bytes([255])*(4096-len(oldrecord)), 'Unknown B2 record; no overwrite'
    name,config,counts,sequence=m.source_settings(banks[3],'str8n');config=bytearray(config);record=m.journal(banks[3])
    if record and record[15:16]==b'P':
        page=record[16];offset=(page<<8)-0x8000
        if page in (0xA0,0xB0) and m.slot_valid(banks[3][offset:offset+4096],page) and int.from_bytes(banks[3][offset+8:offset+12],'little')==int.from_bytes(record[17:21],'little'):
            config[7:13]=b'P'+bytes((page,))+GENERATION.to_bytes(4,'little')
    config[14:]=m.config_sum(config)
    order=([(3,0xD0)] if banks[3][0x5000:0x6000]!=bytes([255])*4096 else [])+[(3,0xC0),(3,0x80),(3,0xE0),(3,0xB0),(3,0xA0),(2,0x80)]
    after=list(counts)
    for bank,page in order:
        index=bank*8+(page>>4)-8;assert after[index]<0xFFFFFF;after[index]+=1
    assert sequence<0xFFFFFFFF
    body=(CLOCK/'clock.bin').read_bytes();assert len(body)+24<4096
    pending=b'SR\x01\xff'+b'\0\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    desired={(3,0xD0):bytes([255])*4096,(3,0xC0):m.metadata(bytes(config),after,sequence+1)+bytes([255])*(4096-128),
        (3,0x80):(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes(),(3,0xE0):(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes(),
        (3,0xA0):(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes(),(3,0xB0):(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes(),
        (2,0x80):pending+bytes([255])*(4096-len(pending))}
    template=json.loads((OUT/'migrator/manifest.json').read_text());image=OUT/'migrator/rtc-migrator-2000.s19';assert sha(image.read_bytes())==template['sha256']
    cells,entry=m.read_s19(image);cells[template['count']]=len(order);cells[template['commit_after']]=len(order)
    expected=[bytearray(b) for b in banks];transfers=[]
    for index,(bank,page) in enumerate(order):
        data=desired[bank,page];row=bytes((page,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little');cells[template['banks']+index]=bank
        for address,value in enumerate(row,template['table']+9*index):cells[address]=value
        expected[bank][(page<<8)-0x8000:(page<<8)-0x7000]=data;transfers.append(data)
    expected[2][3]=0x3F
    installer=m.s19(cells,entry);out=a.root/'upgrade';out.mkdir(exist_ok=False);(out/'installer.s19').write_bytes(installer)
    info=dict(board=a.board,version=VERSION,generation=GENERATION,banner_update=True,clock_update=True,
        source_firmware=name,steps=[dict(bank=b,sector=p>>4) for b,p in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in expected],
        installer_sha256=sha(installer),config=bytes(config).hex(),counts_before=counts,counts_after=after,fixed_f_changed=False,
        maintenance_commit_after=len(order),record_commit_bank=2,clock_sha256=sha(body),journals_preaccount_planned_attempts=True)
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    for i,data in enumerate(transfers):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for bank,data in enumerate(expected):(out/f'expected-b{bank}.bin').write_bytes(data)
    print(a.board,VERSION,'CLOCK 1.1 atomic commit; sectors',info['steps'])


if __name__=='__main__':main()
