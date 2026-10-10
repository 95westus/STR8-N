"""Prepare a six-sector beta13-to-beta14 SPI recipe from repeated backups."""
import argparse,hashlib,json
from pathlib import Path
import beta4_migration as m
from build_v2_spi_resident import OUT,merge_identity_tail
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=('2512','2205','2609'));p.add_argument('--validate-only',action='store_true');a=p.parse_args()
    info=read(a.root/'prior/manifest.json');assert info['repeat_verified'] and info['board']==a.board
    banks=[(a.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    for b,data in enumerate(banks):assert data==(a.root/f'prior/b{b}-repeat.bin').read_bytes() and sha(data)==info['banks'][b]['sha256']
    old=ROOT/'BUILD/v2-rtc-trim';meta=read(OUT/'build.json')
    assert banks[3][:4096]==(old/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert banks[3][4096:7168]==(old/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    assert banks[3][0x7000:]==(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert banks[3][0x6000:0x7000]==(old/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    assert banks[1][:8192]==(OUT/'str8n-maint-1.7-b1-8000-9fff.bin').read_bytes()
    clock=(ROOT/'BUILD/v2-clock-1.5/clock.bin').read_bytes()
    assert banks[2][:8]==b'SR\x01\x3f\0\x20'+len(clock).to_bytes(2,'little') and banks[2][8:24]==b'CLOCK'.ljust(16,b'\0') and banks[2][24:24+len(clock)]==clock
    for page,label in ((0xA0,'a0'),(0xB0,'b0')):assert banks[3][(page<<8)-0x8000:(page<<8)-0x7000]==(old/f'str8n-v2-recovery-slot-{label}.bin').read_bytes()
    name,config,counts,seq=m.source_settings(banks[3],'str8n');config=bytearray(config);record=m.journal(banks[3]);generation=meta['generation']
    if record and record[15:16]==b'P':
        page=record[16];offset=(page<<8)-0x8000
        assert page in (0xA0,0xB0) and m.slot_valid(banks[3][offset:offset+4096],page)
        assert banks[3][offset+8:offset+12]==record[17:21]
        config[7:13]=b'P'+record[16:17]+generation.to_bytes(4,'little')
    config[14:]=m.config_sum(config);assert seq<0xffffffff and banks[3][0x5000:0x6000]==bytes([255])*4096
    if a.validate_only:print('VALID',a.board,'complete beta13 source, saved CLOCK/MAINT and settings; no preparation or board access');return
    order=[(3,p) for p in (0xC0,0x80,0x90,0xE0,0xB0,0xA0)];after=list(counts)
    for b,page in order:
        index=b*8+(page>>4)-8;assert after[index]<0xffffff;after[index]+=1
    desired={0xC0:m.metadata(bytes(config),after,seq+1)+bytes([255])*(4096-128),
             0x80:(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes(),
             0x90:merge_identity_tail(banks[3][4096:8192],(OUT/'str8n-journal-9000-9fff.bin').read_bytes()),
             0xE0:(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes(),
             0xA0:(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes(),0xB0:(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()}
    template=read(OUT/'migrator/manifest.json');image=OUT/'migrator/rtc-migrator-2000.s19';assert sha(image.read_bytes())==template['sha256']
    cells,entry=m.read_s19(image);cells[template['count']]=len(order);cells[template['commit_after']]=0
    expected=[bytearray(b) for b in banks];payload=[]
    for i,(b,page) in enumerate(order):
        data=desired[page];row=bytes((page,))+m.fnv(expected[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells[template['banks']+i]=b;cells[template['commits']+i]=0
        for addr,value in enumerate(row,template['table']+9*i):cells[addr]=value
        expected[b][(page<<8)-0x8000:(page<<8)-0x7000]=data;payload.append(data)
    assert all(expected[b]==banks[b] for b in (0,1,2)) and expected[3][7168:8192]==banks[3][7168:8192] and expected[3][0x7000:]==banks[3][0x7000:]
    out=a.root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=a.board,version=meta['version'],generation=generation,source_firmware=name,banner_update=True,journal_update=True,binding_update=True,trim_update=True,spi_update=True,clock_update=False,
              steps=[dict(bank=b,sector=p>>4) for b,p in order],prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in expected],installer_sha256=sha(installer),
              config=bytes(config).hex(),counts_before=counts,counts_after=after,fixed_f_changed=False,identity_tail_preserved=True,record_commit_banks=[],record_commit_bank=None,
              clock_build=str(ROOT/'BUILD/v2-clock-1.5'),clock_sha256=sha((ROOT/'BUILD/v2-clock-1.5/clock.bin').read_bytes()),no_sram_format=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payload):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b,data in enumerate(expected):(out/f'expected-b{b}.bin').write_bytes(data)
    print('PREPARED',a.board,'six B3 sectors; B0/B1/B2/F and EUI tail retained; no record commit or SRAM formatting')

if __name__=='__main__':main()
