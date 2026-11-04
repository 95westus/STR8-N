"""Save exact installed project artifacts locally; no rebuild, port or publication."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sha=lambda b:hashlib.sha256(b).hexdigest()
def run():
    final=json.loads((ROOT/'output/qualification/STATUS-install-20261031-r1/final-receipt.json').read_text())
    assert final['passed'] and final['total_erases']==11 and final['F_writes']==0
    freeze=json.loads((REPO/'F_FREEZE.json').read_text())
    for name,digest in freeze['sources'].items():assert sha((REPO/name).read_bytes())==digest
    assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==final['F_sha256']==freeze['sha256']
    acceptance=dict(status='INSTALLED_STATUS_ACCEPTED_2512_2609',scope='MON gC / STATUS g1 only; retained utilities differ',
        F_sha256=freeze['sha256'],F_rebuilt=False,published_downloads_changed=False,
        document='docs/MON_STARTUP_STATUS_ROM_ACCEPTANCE.md',private_board_captures_included=False,
        boards={b:dict(CPU='65C02' if b=='2512' else '65C816 emulation',default=x['default'],
            sequence=x['sequence'],valid_records=x['valid_records'],owner_RAM_ZP_restored=True,
            RTC_native_TIME_admitted=True,startup_stream_captured=False,
            reset_evidence='Owner-reported RESET; post-reset default observed before selector; RAM/ZP/B3 verified') for b,x in final['boards'].items()})
    for source,name in [('mon-gC-status-r3','g0000000c-status'),('status-g1-r4','status-g00000001')]:
        origin=ROOT/'BUILD'/source;target=REPO/'monitors/candidates'/name;target.mkdir(exist_ok=False)
        m=json.loads((origin/'manifest.json').read_text())
        for filename,a in m['artifacts'].items():
            image=(origin/filename).read_bytes();assert sha(image)==a['sha256'] and len(image)==a['bytes']
            (target/filename).write_bytes(image)
            if a.get('variant') in ('A','B'):
                address=0x2000 if a['variant']=='A' else 0x3000
                for board in ('2512','2609'):
                    live=(ROOT/f'output/qualification/STATUS-install-20261031-r1/{board}/B3-after.bin').read_bytes()
                    assert live[address:address+4096]==image
                a['status']='LIVE_STATUS_ACCEPTED_2512_2609'
        for file in ('build-log.json','linked-sizes.json'):
            if (origin/file).exists():shutil.copyfile(origin/file,target/file)
        m['runtime_qualification']=acceptance
        m['packaging']='LOCAL_CANDIDATE_ONLY; not a published download or replacement ZIP'
        (target/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
        print('Saved exact installed artifacts',target)
    (REPO/'monitors/review/g0000000c-status-acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
if __name__=='__main__':run()
