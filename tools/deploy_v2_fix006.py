"""Exact-backup two-sector STR8N-006 helper update; fixed beta24 generation 33."""
import json,sys
from pathlib import Path
import beta4_migration as m
import update_v2_beta24 as deploy
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease
from rtc_prompt_sync import establish_b3
from qualify_v2_beta24 import valid_names
from qualify_v2_beta24_power import append
import backup_str8n_board as backup

ROOT=deploy.ROOT
BUILD=ROOT/'BUILD/v2-board-name-fix006'
OLD=ROOT/'BUILD/v2-board-name'
BASE=ROOT/'output/qualification/fix006-2026-10-14'
deploy.BUILD=BUILD


def backups():
    with serial_lease('fix006-backup'):
        ports={p.serial_number:p.device for p in comports()}
        for b in ('2604','2609'):
            root=BASE/b;root.mkdir(parents=True,exist_ok=False)
            with (root/'name-preparation.jsonl').open('x') as log:
                l=m.Link(ports[SERIALS[b]],log)
                try:
                    establish_b3(l);names=valid_names(l.dump(0x9C00,0x9FFF))
                    original=max(names)[1] if names else ''
                    tail=append(l,'LAB-'+b)
                    (root/'name-state.json').write_text(json.dumps(dict(original=original,named_tail=tail.hex()),indent=2)+'\n')
                finally:l.serial.close()
            sys.argv=['backup','--port',ports[SERIALS[b]],'--board',b,'--out',str(root/'prior-verified')];backup.main()


def prepare(board):
    meta=deploy.audit();root=BASE/board;prior=deploy.read(root/'prior-verified/manifest.json')
    assert prior['repeat_verified'] and prior['board']==board
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i,data in enumerate(banks):
        assert len(data)==32768 and data==(root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert deploy.sha(data)==prior['banks'][i]['sha256']
    assert banks[2][0x6000:0x6700]==(OLD/'local-display/asset.bin').read_bytes()
    final=[bytearray(b) for b in banks]
    final[2][0x6000:0x6700]=(BUILD/'local-display/asset.bin').read_bytes()
    order=[(3,12),(2,14)]
    j=m.journal(banks[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for bank,sector in order:
        i=bank*8+sector-8;assert counts[i]<0xFFFFFF;counts[i]+=1
    seq=int.from_bytes(j[4:8],'little');assert seq<0xFFFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,seq+1)+b'\xff'*(4096-128)
    assert final[0]==banks[0] and final[1]==banks[1]
    assert final[2][:0x6000]==banks[2][:0x6000] and final[2][0x6700:]==banks[2][0x6700:]
    assert final[3][:0x4000]==banks[3][:0x4000] and final[3][0x5000:]==banks[3][0x5000:]
    mf=deploy.read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=2;cells[mf['commit_after']]=0;expected=[bytearray(b) for b in banks];payloads=[]
    for i,(bank,sector) in enumerate(order):
        offset=(sector-8)*4096;data=bytes(final[bank][offset:offset+4096])
        row=bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos,v in enumerate(row,mf['table']+9*i):cells[pos]=v
        cells[mf['banks']+i]=bank;cells[mf['commits']+i]=0
        for pos in range(mf['commit_addresses']+4*i,mf['commit_addresses']+4*i+4):cells[pos]=0
        expected[bank][offset:offset+4096]=data;payloads.append(data)
    assert expected==final
    out=root/'upgrade';out.mkdir(exist_ok=False);installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    plan=dict(board=board,version=meta['version'],generation=33,fix='STR8N-006',prior_directory='prior-verified',
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[deploy.sha(b) for b in banks],
        expected_hashes=[deploy.sha(b) for b in final],installer_sha256=deploy.sha(installer),
        build_sha256=deploy.sha((BUILD/'build.json').read_bytes()),counts_before=before,counts_after=counts,
        storage_update=True,commit_records=[],config=cfg.hex())
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    for i,data in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED',board,'only B3:C wear journal and B2:E sealed helper',flush=True)


if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='backups':backups()
    elif stage=='prepare':
        for b in ('2604','2609'):prepare(b)
    elif stage=='install':
        for b in ('2604','2609'):deploy.install(BASE/b,b)
    else:raise ValueError(stage)
