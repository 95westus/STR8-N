"""Review the exact transfer installation; no port, build or flash operation."""
import json,sys
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot

OUT=t.ROOT/'output/qualification/TRANSFER-scope-20261101-r2'


def run():
    build=t.ROOT/'BUILD/transfer-final-g1-r2';m=json.loads((build/'manifest.json').read_text())
    def artifact(name):
        data=(build/name).read_bytes();assert t.sha(data)==m['artifacts'][name]['sha256'];return data
    storage=artifact('STORAGE-g2-transfer-r1.bin');bundle=artifact('TRANSFER-B2-8000.bin');service=artifact('TRANSFER-SERVICES-E.bin')
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    result=dict(status='REVIEW_READY_NOT_APPROVED',F_writes=0,power_cuts=0,excluded_boards=['2205','2604'],boards={},
        temporary_SPI_trial=dict(board='2512',directory='00140-0017F (slot4)',payload='09800-0B7FF',
            total_bytes=8256,source_CPU='4700-66FF',action='Store via new frontend; TABLE; load-only RESTORE; exact SPI/owner-RAM restoration',
            admission='Fresh primary header/directory and target bytes must match escrow; slot4 free and payload unallocated; otherwise stop',
            WORKSPACE_writes=0,format=False,automatic_erase=False))
    for board in ('2512','2609'):
        marker=json.loads((t.ROOT/f'output/qualification/device-operations/{board}.json').read_text())
        installed=t.ROOT/f'output/qualification/{board}-native-storage-installed-20261101-r1'
        old={1:(installed/'B1-after.bin').read_bytes(),2:(t.ROOT/f'output/qualification/{board}-STATUS-literals-repair-20261101-r1/B2-target.bin').read_bytes(),3:(installed/'B3-after.bin').read_bytes()}
        assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
        assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
        images={b:bytearray(v) for b,v in old.items()}
        images[1][0x3000:0x6000]=storage
        # Only PROGRAM's exact footprint changes; preserve all four STATUS
        # extents and the bootstrap/WB/native tools without collateral padding.
        assert bundle[:0x1F00]==old[2][:0x1F00]
        images[2][0x1F00:0x2C00]=bundle[0x1F00:0x2C00]
        images[3][0x6000:0x7000]=service
        state=old[3];prior=t.classify_journal(state);targets=[];operations=[]
        folder=OUT/board;folder.mkdir()
        for b,page in ((1,0xD0),(2,0x90),(2,0xA0),(3,0xE0)):
            off=(page-0x80)*256;before=old[b][off:off+4096];target=bytes(images[b][off:off+4096]);assert before!=target
            filename=f'B{b}-{page:02X}-target.bin';(folder/filename).write_bytes(target)
            (folder/f'B{b}-{page:02X}-original.bin').write_bytes(before)
            state,operation=reserve(state,b*8+(page-0x80)//16);operations.append(operation)
            assert not operation['journal_sector_erases']
            if b==3:
                revised=bytearray(state);revised[off:off+4096]=target;state=bytes(revised)
            targets.append(dict(bank=b,page=page,address=f'B{b}:{page:02X}00',file=filename,
                before_sha256=t.sha(before),sha256=t.sha(target)))
        images[3]=bytearray(state);after=t.classify_journal(state)
        for off in range(0x4000,0x6000,256):
            if valid_snapshot(old[3][off:off+256]):assert state[off:off+256]==old[3][off:off+256]
        for key in ('default','enabled_mask','entries','unknown_mask'):assert prior[key]==after[key]
        assert images[1][:0x5000]==old[1][:0x5000] and images[1][0x6000:]==old[1][0x6000:]
        assert images[2][:0x1F00]==old[2][:0x1F00] and images[2][0x2C00:]==old[2][0x2C00:]
        assert images[3][:0x4000]==old[3][:0x4000] and images[3][0x7000:]==old[3][0x7000:]
        for b,v in old.items():
            (folder/f'B{b}-original.bin').write_bytes(v);(folder/f'B{b}-target.bin').write_bytes(images[b])
        p=dict(board=board,image_erases=4,journal_erases=0,F_writes=0,targets=targets,operations=operations,
            counts_before=prior['counts'],counts_after=after['counts'],sequence_before=prior['sequence'],sequence_after=after['sequence'],
            old_rows_retained=prior['valid_records'],records_after=after['valid_records'],
            before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},target_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},
            preserved=['all old boot/wear rows','boot choice/binding/entries','F/MON A/B','B0','CLOCK/FLASH/MAINT/RTC','STATUS all four extents','owner RAM/ZP','SPI except separately restored 2512 trial'],
            open_gates=['Installed positive STORE and S19 front-door return','Legacy I flash-stream S19 still not implemented','Factory execution replaces F and is excluded'])
        t.save(folder/'plan.json',p);result['boards'][board]=p
    result['total_erases']=8;t.save(OUT/'review.json',result)
    print(json.dumps({b:{k:v[k] for k in ('image_erases','journal_erases','sequence_after','old_rows_retained','records_after')} for b,v in result['boards'].items()},indent=2))


if __name__=='__main__':run()
