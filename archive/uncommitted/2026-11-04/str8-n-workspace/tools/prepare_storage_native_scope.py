"""Prepare exact native storage image/history scope from passed RAM trials."""
import json,sys
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot,inspect
OUT=t.ROOT/'output/qualification/STORAGE-native-scope-20261101-r3'

def run():
    builds={k:t.ROOT/'BUILD'/v for k,v in dict(storage='sram-work-g2-native-r1',loader='native-loader-storage-r2',services='services-gC-storage-r2').items()}
    manifests={k:json.loads((v/'manifest.json').read_text()) for k,v in builds.items()}
    def artifact(kind,name):
        body=(builds[kind]/name).read_bytes();assert t.sha(body)==manifests[kind]['artifacts'][name]['sha256'];return body
    storage=artifact('storage','STR8N-STORAGE-g00000002-flash.bin')
    loader=artifact('loader','NATIVE-LOADER-storage-7000.bin')
    name=next(n for n,v in manifests['services']['artifacts'].items() if v['variant']=='B2 bundle');bundle=artifact('services',name)
    name=next(n for n,v in manifests['services']['artifacts'].items() if v['variant']=='E');service=artifact('services',name)
    assert len(storage)==12288 and len(loader)==1024 and len(bundle)==12288 and len(service)==4096
    frozen=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    result=dict(status='REVIEW_READY_NOT_APPROVED',F_writes=0,power_cuts=0,excluded_boards=['2205','2604'],boards={})
    for board,suffix in (('2512','r3'),('2609','r2')):
        case=t.ROOT/f'output/qualification/{board}-native-storage-g2-RAM-20261101-{suffix}'
        proof=json.loads((case/'report.json').read_text());assert proof['passed']
        marker=json.loads((t.ROOT/f'output/qualification/device-operations/{board}.json').read_text())
        old={b:(case/f'B{b}-before.bin').read_bytes() for b in (1,2,3)}
        assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
        assert old[3][-4096:]==frozen and bundle[7936:11264]==old[2][7936:11264]
        images={b:bytearray(v) for b,v in old.items()}
        images[1][0x3000:0x6000]=storage
        images[2][:8192]=bundle[:8192] # B2:A provider and STATUS stay exact.
        images[3][0xC00:0x1000]=loader;images[3][0x6000:0x7000]=service
        out=OUT/board;out.mkdir();targets=[];operations=[];state=old[3]
        pages=[(1,0xB0),(1,0xC0),(1,0xD0),(3,0x80),(2,0x80),(2,0x90),(3,0xE0)]
        prior=t.classify_journal(state)
        for bank,page in pages:
            off=(page-0x80)*256;body=bytes(images[bank][off:off+4096]);before=old[bank][off:off+4096]
            assert body!=before
            name=f'B{bank}-{page:02X}-target.bin';(out/name).write_bytes(body)
            (out/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
            state,op=reserve(state,bank*8+(page-0x80)//16);operations.append(op)
            if bank==3:
                updated=bytearray(state);updated[off:off+4096]=body;state=bytes(updated)
            targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=name,
                sha256=t.sha(body),before_sha256=t.sha(before)))
        images[3]=bytearray(state);final=t.classify_journal(state)
        erases=[v for op in operations for v in op['journal_sector_erases']]
        assert erases==(['B3:D'] if board=='2512' else [])
        old_rows=[(off,old[3][off:off+256]) for off in range(0x4000,0x6000,256) if valid_snapshot(old[3][off:off+256])]
        removed=[f'{off+0x8000:04X}' for off,row in old_rows if state[off:off+256]!=row]
        assert len(removed)==(16 if board=='2512' else 0)
        for key in ('default','enabled_mask','entries','unknown_mask'):assert prior[key]==final[key]
        # Journal reservation may change sequence/counts only, not boot policy.
        def newest(image):
            return max((image[o:o+256] for o in range(0x4000,0x6000,256) if valid_snapshot(image[o:o+256])),key=lambda row:int.from_bytes(row[8:12],'little'))
        assert newest(old[3])[12:30]==newest(state)[12:30]
        assert bytes(images[1][:0x3000])==old[1][:0x3000] and bytes(images[1][0x6000:])==old[1][0x6000:]
        assert bytes(images[2][8192:])==old[2][8192:]
        assert state[:0xC00]==old[3][:0xC00] and state[0x1000:0x4000]==old[3][0x1000:0x4000] and state[0x7000:]==old[3][0x7000:]
        for b in (1,2,3):
            (out/f'B{b}-original.bin').write_bytes(old[b]);(out/f'B{b}-target.bin').write_bytes(images[b])
        (out/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
        p=dict(board=board,targets=targets,operations=operations,image_erases=7,journal_sector_erases=erases,
            total_erases=7+len(erases),F_writes=0,power_cuts=0,
            before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},target_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},
            counts_before=prior['counts'],counts_after=final['counts'],sequence_before=prior['sequence'],sequence_after=final['sequence'],
            records_before=prior['valid_records'],records_after=final['valid_records'],old_rows_remaining_exact_on_chip=len(old_rows)-len(removed),
            old_record_pages_replaced=removed,journal_room_before=inspect(old[3]),
            boot_policy='unchanged, including B/default generation D; no binding append',
            replaced_image='B1:B-D retained legacy CLOCK; native CLOCK at B2:B-D unchanged; all originals archived',
            RAM_evidence=str(case/'report.json'),preserved=['F','MON A/B','B0','B1:8-A/E/F','B2:A-F incl STATUS/PROGRAM/CLOCK/FLASH',
                'B3 RTC/provider/gateway/history/metadata except loader','boot policy','wear totals','SPI SRAM/WORKSPACE','RTC time/trim/PF','fresh owner RAM/ZP'])
        t.save(out/'plan.json',p);result['boards'][board]=p
    result['total_erases']=sum(v['total_erases'] for v in result['boards'].values())
    t.save(OUT/'review.json',result)
    print(json.dumps({b:{k:p[k] for k in ('total_erases','journal_sector_erases','sequence_after','records_after','old_rows_remaining_exact_on_chip')} for b,p in result['boards'].items()},indent=2))
if __name__=='__main__':run()
