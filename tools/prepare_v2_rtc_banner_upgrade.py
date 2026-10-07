"""Prepare beta5-to-beta6 banner update; preserve MAINT, CLOCK and fixed F."""
import argparse
import hashlib
import json
from pathlib import Path

import beta4_migration as migration
from build_v2_rtc_banner import ROOT,OUT,VERSION,GENERATION


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--board',required=True)
    args = parser.parse_args()
    backup = args.root/'prior'
    manifest = json.loads((backup/'manifest.json').read_text())
    assert manifest['board']==args.board and manifest['repeat_verified']
    banks = [(backup/f'b{b}.bin').read_bytes() for b in range(4)]
    for b,data in enumerate(banks):
        assert sha(data)==manifest['banks'][b]['sha256']
        assert data==(backup/f'b{b}-repeat.bin').read_bytes()
    old = ROOT/'BUILD/v2-rtc-kernel'
    assert banks[3][:4096]==(old/'str8n-rtc-component-8000-8fff.bin').read_bytes(), 'Unexpected RTC component'
    assert banks[1][:8192]==(old/'str8n-maint-1.6-b1-8000-9fff.bin').read_bytes(), 'Unexpected MAINT record'
    assert banks[3][0x7000:]==(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes(), 'Fixed F must remain unchanged'
    name,config,counts,sequence = migration.source_settings(banks[3],'str8n')
    config = bytearray(config)
    record = migration.journal(banks[3])
    if record and record[15:16]==b'P':
        page = record[16]
        generation = int.from_bytes(record[17:21],'little')
        offset = (page<<8)-0x8000
        if page in (0xA0,0xB0) and migration.slot_valid(banks[3][offset:offset+4096],page):
            if int.from_bytes(banks[3][offset+8:offset+12],'little')==generation:
                config[7:13]=b'P'+bytes((page,))+GENERATION.to_bytes(4,'little')
    config[14:]=migration.config_sum(config)
    assert sequence<0xFFFFFFFF
    # Install the optional component/E before new slots. Existing beta5 slots
    # retain working RTC/RST interfaces throughout this ordering.
    order = ([0xD0] if banks[3][0x5000:0x6000]!=bytes([255])*4096 else [])+[0xC0,0x80,0xE0,0xB0,0xA0]
    after = list(counts)
    for page in order:
        index = 24+(page>>4)-8
        assert after[index]<0xFFFFFF
        after[index]+=1
    desired = {0xC0:migration.metadata(bytes(config),after,sequence+1)+bytes([255])*(4096-128),
        0xD0:bytes([255])*4096,
        0x80:(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes(),
        0xE0:(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes(),
        0xA0:(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes(),
        0xB0:(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()}
    template = json.loads((OUT/'migrator/manifest.json').read_text())
    image = OUT/'migrator/rtc-migrator-2000.s19'
    assert sha(image.read_bytes())==template['sha256']
    cells,entry = migration.read_s19(image)
    cells[template['count']]=len(order)
    cells[template['commit_after']]=0  # Existing B1 MAINT stays untouched.
    expected = [bytearray(b) for b in banks]
    transfers = []
    for index,page in enumerate(order):
        data = desired[page]
        row = bytes((page,))+migration.fnv(expected[3]).to_bytes(4,'little')+migration.fnv(data).to_bytes(4,'little')
        cells[template['banks']+index]=3
        for address,value in enumerate(row,template['table']+9*index):
            cells[address]=value
        expected[3][(page<<8)-0x8000:(page<<8)-0x7000]=data
        transfers.append(data)
    installer = migration.s19(cells,entry)
    out = args.root/'upgrade'
    out.mkdir(exist_ok=False)
    (out/'installer.s19').write_bytes(installer)
    info = dict(board=args.board,version=VERSION,generation=GENERATION,banner_update=True,
        source_firmware=name,steps=[dict(bank=3,sector=p>>4) for p in order],
        prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in expected],
        installer_sha256=sha(installer),config=bytes(config).hex(),counts_before=counts,counts_after=after,
        fixed_f_changed=False,maintenance_commit_after=0,journals_preaccount_planned_attempts=True)
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    for index,data in enumerate(transfers):
        (out/f'transfer-{index:02d}.bin').write_bytes(data)
    for bank,data in enumerate(expected):
        (out/f'expected-b{bank}.bin').write_bytes(data)
    print(args.board,'banner plan:',[f'B3:{p>>4:X}' for p in order],'; F/B0/B1/B2 preserved')


if __name__=='__main__':
    main()
