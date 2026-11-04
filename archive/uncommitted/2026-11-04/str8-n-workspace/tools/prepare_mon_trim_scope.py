"""Prepare the exact gD MON-only upgrade, including required native D rotation."""
import binascii,json,sys
from pathlib import Path
import install_2512_native_utilities as d

t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import inspect,valid_snapshot
OUT=t.ROOT/'output/qualification/MON-trim-scope-20261031-r1'
BUILD=t.ROOT/'BUILD/mon-gD-trim-r1'


def bind_b(bank3):
    rows=[(int.from_bytes(bank3[i+8:i+12],'little'),i,bank3[i:i+256])
          for i in range(0x4000,0x6000,256) if valid_snapshot(bank3[i:i+256])]
    seq,off,raw=max(rows);where=off+256
    assert where&0xF00!=0xF00 and bank3[where:where+256]==b'\xff'*256
    row=bytearray(raw);row[8:12]=(seq+1).to_bytes(4,'little');row[18:22]=(13).to_bytes(4,'little')
    row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little')
    row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little')
    assert valid_snapshot(row)
    result=bytearray(bank3);result[where:where+256]=row
    return bytes(result),dict(page=f'{where+0x8000:04X}',sequence=seq+1,kind='same-default-B-generation-D-binding')


def run():
    manifest=json.loads((BUILD/'manifest.json').read_text());assert manifest['generation']=='0000000D'
    frozen=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    slots={}
    for name,a in manifest['artifacts'].items():
        if a['variant'] in ('A','B'):
            body=(BUILD/name).read_bytes();assert t.sha(body)==a['sha256']
            slots[a['variant']]=(name,body)
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    result=dict(status='REVIEW_READY_NOT_APPROVED',F_writes=0,C_erases=0,
                total_erases=5,power_cuts=0,excluded_boards=['2205','2604'],boards={})
    for board,suffix in [('2512','r2'),('2609','r1')]:
        trial=t.ROOT/f'output/qualification/{board}-MON-trim-RAM-20261031-{suffix}'
        proof=json.loads((trial/'report.json').read_text());assert proof['passed']
        old3=(trial/'B3-before.bin').read_bytes()
        marker=json.loads((t.ROOT/f'output/qualification/device-operations/{board}.json').read_text())
        assert t.sha(old3)==marker['current_physical_bank_sha256']['B3'] and old3[-4096:]==frozen
        prior=t.classify_journal(old3);assert prior['default']=='B'
        state=old3;operations=[];targets=[];out=OUT/board;out.mkdir()
        for slot,index,page in [('A',26,0xA0),('B',27,0xB0)]:
            state,operation=reserve(state,index)
            name,body=slots[slot];(out/name).write_bytes(body)
            off=(page-0x80)*256
            target=dict(bank=3,page=page,address=f'{page:02X}00',file=name,sha256=t.sha(body),
                        before_sha256=t.sha(old3[off:off+4096]))
            targets.append(target);operations.append(operation)
            updated=bytearray(state);updated[off:off+4096]=body;state=bytes(updated)
        state,binding=bind_b(state);latest=t.classify_journal(state)
        erased=[s for op in operations for s in op['journal_sector_erases']]
        assert erased==([] if board=='2512' else ['B3:D'])
        old_D=sum(valid_snapshot(old3[i:i+256]) for i in range(0x5000,0x6000,256)) if erased else 0
        assert old_D==(0 if board=='2512' else 16)
        for off in range(0x4000,0x5000,256):
            if valid_snapshot(old3[off:off+256]):assert state[off:off+256]==old3[off:off+256]
        for key in ('default','enabled_mask','entries','unknown_mask'):assert latest[key]==prior[key]
        assert state[:0x2000]==old3[:0x2000] and state[0x6000:]==old3[0x6000:]
        for name,body in [('B3-before.bin',old3),('CD-history-before.bin',old3[0x4000:0x6000]),('B3-target.bin',state)]:
            (out/name).write_bytes(body)
        info=dict(board=board,status='REVIEW_READY_NOT_APPROVED',targets=targets,
            before_B3_sha256=t.sha(old3),target_B3_sha256=t.sha(state),
            image_erases=2,D_erases=len(erased),C_erases=0,F_writes=0,total_erases=2+len(erased),
            counts_before=prior['counts'],counts_after=latest['counts'],
            sequence_before=prior['sequence'],sequence_after=latest['sequence'],
            records_before=prior['valid_records'],records_after=latest['valid_records'],
            old_D_records_archived_and_replaced=old_D,old_rows_remaining_exact_on_chip=prior['valid_records']-old_D,
            journal_room_before=inspect(old3),operations=operations,binding=binding,
            generation_before='0000000C',generation_after='0000000D',default='B',
            mask=prior['enabled_mask'],entries=prior['entries'],RAM_evidence=str(trial/'report.json'),
            trim_RAM_observed=proof['CLOCK_trim_steps'],control_RAM_observed=proof['readings'][-1]['control_register'],
            preserved=['F','B0/B1/B2','B3:8/9/E','RTC time/trim/control/PF/history','SRAM/WORKSPACE','fresh owner RAM/ZP'],
            qualification=['live TIME control/trim on A and B','UI/1 R MAINT/Q and existing utilities',
                           'same B default rebound to D, software startup','native NTP/TIME trim reader registration'])
        t.save(out/'plan.json',info);result['boards'][board]=info
    t.save(OUT/'review.json',result)
    print(json.dumps({b:{k:p[k] for k in ('total_erases','sequence_after','records_after',
           'old_D_records_archived_and_replaced','counts_after','binding')} for b,p in result['boards'].items()},indent=2))


if __name__=='__main__':run()
