"""Restore backed-up firmware with original history plus accounted test erases."""
import json
from pathlib import Path
import migrate_v2 as u
from prepare_v2_recovery_fixture import prepare
from beta4_migration import journal,metadata

def main():
    base=u.ROOT/'output/qualification/beta25-recovery-2026-10-14/2604';original=[(base/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    attempts=[]
    for name in ('f-only-A','f-only-B'):
        root=base/name;p=u.read(root/'upgrade/plan.json');assert u.read(root/'upgrade/install/reset-pending.json')['device_sectors_verified']
        test=u.read(root/'slot-test/report.json');assert test['passed']
        attempts.extend((r['bank'],r['sector']) for r in p['steps']);attempts.append((3,test['normal_accounted_erase_sector']))
    attempts.extend((3,s) for s in (12,8,9,14,10,11,13))
    record=journal(original[3]);assert record;counts=[int.from_bytes(record[24+3*i:27+3*i],'little') for i in range(32)];before=counts[:]
    for bank,sector in attempts:
        index=bank*8+sector-8;assert counts[index]<0xFFFFFF;counts[index]+=1
    seq=int.from_bytes(record[4:8],'little');assert seq<0xFFFFFFFF
    target=[bytearray(b) for b in original];offset=next(i for i in range(0x4000,0x5000,128) if target[3][i:i+128]==b'\xff'*128)
    target[3][offset:offset+128]=metadata(record[8:24],counts,seq+1)
    out=base/'restoration-target';out.mkdir(exist_ok=False)
    for i,b in enumerate(target):(out/f'b{i}.bin').write_bytes(b)
    ledger=dict(board='2604',attempts=[dict(bank=b,sector=s) for b,s in attempts],counts_before=before,counts_after=counts,
        sequence=seq+1,new_record_offset=offset,original_journal_records_preserved=True,restoration_erases_precharged=True)
    (out/'erase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    prepare(base/'restore',base/'f-only-B/post-test',out)
    print('PASS restoration target preserves original firmware/settings/history and adds',len(attempts),'known test/restore erase attempts',flush=True)

if __name__=='__main__':main()
