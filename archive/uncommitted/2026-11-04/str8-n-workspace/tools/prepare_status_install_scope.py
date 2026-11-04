"""Pin the concrete STATUS install review from the completed RAM-trial captures.

No port access, firmware build, flash writer, simulator, or published ZIP change.
"""
import json,sys,binascii,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path[:0]=[str(REPO/'tools'),str(REPO/'migration-host')]
from build_mona import sha
from nf_migrate import classify_journal,valid_snapshot
from native_journal_room import inspect

OUT=ROOT/'output/qualification/STATUS-install-scope-20261031-r1'
MON=ROOT/'BUILD/mon-gC-status-r3'
SOURCES={'2512':'2512-STATUS-g1-RAM-20261031-r1','2609':'2609-STATUS-g1-RAM-20261031-r2'}

def run():
    closeout=ROOT/'output/qualification/STATUS-RAM-closeout-20261031-r1/report.json'
    assert json.loads(closeout.read_text())['passed']
    freeze=json.loads((REPO/'F_FREEZE.json').read_text())
    mon=json.loads((MON/'manifest.json').read_text());assert mon['generation']=='0000000C' and not mon['F_rebuilt']
    for name,digest in freeze['sources'].items():assert sha((REPO/name).read_bytes())==digest
    OUT.mkdir(parents=True,exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    result=dict(status='REVIEW_READY_NOT_APPROVED_NOT_INSTALLED',F_sha256=freeze['sha256'],
        F_writes=0,power_cuts=0,excluded_boards=['2205','2604'],
        published_download_changes=0,RAM_closeout=str(closeout),boards={})
    for board,source in SOURCES.items():
        folder=OUT/board;folder.mkdir()
        captured=ROOT/'output/qualification'/source
        old2=(captured/'before-B2.bin').read_bytes();old3=(captured/'before-B3.bin').read_bytes()
        assert sha(old3[-4096:])==freeze['sha256']
        prepared=ROOT/f'output/qualification/STATUS-g1-{board}-prepared-20261031-r1'
        composition=json.loads((prepared/'composition.json').read_text())
        assert composition['before_sha256']==sha(old2)
        new2=(prepared/'B2-STATUS.bin').read_bytes();assert sha(new2)==composition['after_sha256']
        journal=classify_journal(old3);room=inspect(old3);assert journal['kind']=='valid-snbt'
        targets=[]
        for item in composition['sectors']:
            address=int(item['sector'].split(':')[1],16)*4096
            body=(prepared/item['file']).read_bytes();assert sha(body)==item['sha256']
            name=item['file'];(folder/name).write_bytes(body)
            targets.append(dict(bank=2,address=f'{address:04X}',file=name,sha256=sha(body),
                                before_sha256=sha(old2[address-0x8000:address-0x7000])))
        for slot,page in [('A',0xA000),('B',0xB000)]:
            name,artifact=next((n,a) for n,a in mon['artifacts'].items() if a['variant']==slot)
            body=(MON/name).read_bytes();assert sha(body)==artifact['sha256'] and len(body)==4096
            assert binascii.crc_hqx(body[:18]+body[32:],65535)==int.from_bytes(body[18:20],'little')
            (folder/name).write_bytes(body)
            targets.append(dict(bank=3,address=f'{page:04X}',file=name,sha256=sha(body),
                                before_sha256=sha(old3[page-0x8000:page-0x7000])))
        assert len(targets)==5
        for name,data in [('B2-before.bin',old2),('B3-before.bin',old3),('CD-history-before.bin',old3[0x4000:0x6000])]:
            (folder/name).write_bytes(data)
        counts=journal['counts'].copy()
        for step in targets:
            row=step['bank']*8+(int(step['address'],16)-0x8000)//4096;counts[row]+=1
        binding=board=='2512';rotation=6>room['zero_erase_native_operations'] if binding else 5>room['zero_erase_native_operations']
        assert rotation==binding
        archived_rows=0
        if rotation:
            assert room['peer_sector']=='C000';counts[28]+=1
            archived_rows=sum(valid_snapshot(old3[i:i+256]) for i in range(0x4000,0x5000,256))
        operations=len(targets)+int(binding)
        info=dict(before_B2_sha256=sha(old2),before_B3_sha256=sha(old3),final_B2_sha256=sha(new2),
            targets=targets,image_erases=5,native_C_rotation_erases=int(rotation),D_erases=0,
            F_erases=0,C_D_direct_image_writes=0,boot_default_before=journal['default'],boot_default_after=journal['default'],
            default_B_generation_binding='0000000C' if binding else None,
            enabled_mask=journal['enabled_mask'],entries=journal['entries'],unknown_mask=journal['unknown_mask'],
            counts_before=journal['counts'],counts_after=counts,sequence_before=journal['sequence'],
            expected_sequence_after=journal['sequence']+operations+int(rotation),
            records_before=journal['valid_records'],old_C_rows_archived_and_reused=archived_rows,
            expected_valid_records_after=journal['valid_records']-archived_rows+operations+int(rotation),
            old_rows_remaining_on_chip=journal['valid_records']-archived_rows,
            raw_old_CD_archive_sha256=sha(old3[0x4000:0x6000]),journal_room=room,
            legacy_LT_replacement=composition['legacy_LT_replacement'],
            owner_RAM='Fresh native escrow before borrowing; readback restore0200-66FF and00-DF after tests',
            no_writes=['B0','B1','B3:8','B3:9','B3:E','B3:F','SRAM data','WORKSPACE','RTC data/settings/history'],
            board_metadata_note='Existing BN/TZ/BA retained' if binding else 'Legacy sector9 code retained; no compatible BN/TZ/BA pocket. Board--*, UTC, Battery--* remain truthful.')
        result['boards'][board]=info
        (folder/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    result['image_erases_total']=10;result['native_C_rotation_erases_total']=1
    result['total_erases']=11
    (OUT/'review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({b:{k:v for k,v in p.items() if k in ('image_erases','native_C_rotation_erases','sequence_before','expected_sequence_after','records_before','old_C_rows_archived_and_reused','expected_valid_records_after','counts_after')} for b,p in result['boards'].items()},indent=2))
if __name__=='__main__':run()
