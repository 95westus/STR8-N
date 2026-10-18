"""Second restoration admission from pinned saved restoration interruptions.

Original upgrade and restoration traces are replayed as one history against
the original verified backup. Durable counts include every prior attempted
erase and previously committed conservative reservation. No hardware access.
"""
from pathlib import Path
import plan_beta35_attested_restoration as first
c=first.c;p=c.p

def context(name,banks,backup):
    cp=p.read(c.EVIDENCE/'variants-restoration-checkpoint.json');path=Path(cp['restore_instruction_report'])
    p.require(p.sha(path.read_bytes())==cp['restore_instruction_report_sha256'],'Pinned restoration receipt changed')
    receipt=p.read(path);p.require(receipt['passed'],'Prior restoration did not pass')
    cases=[v for v in receipt['checks'] if v['name']==name]
    p.require(len(cases)==1 and name.startswith(('restoration-cut-','restoration-corrupt-','restoration-partial-')),
              'Not a registered interrupted restoration')
    case=cases[0];p.require(p.bank_hashes(banks)==case['bank_sha256'],'Interrupted restoration preimage changed')
    oldcp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json');oldpath=Path(oldcp['report'])
    p.require(p.sha(oldpath.read_bytes())==oldcp['report_sha256'],'Pinned original upgrade receipt changed')
    parent=next(v for v in p.read(oldpath)['checks'] if v['name']=='2512-complete')
    upgraded=[(oldpath.parent/'2512-complete'/f'b{i}.bin').read_bytes() for i in range(4)]
    p.require(p.bank_hashes(upgraded)==parent['bank_sha256'],'Upgrade parent changed')
    upgrade_events=p.read(oldpath.parent/'2512-complete/events.json')
    original_plan=p.read(Path(oldcp['build_report']).parent/'2512/plan.json')
    tx,data,expected=first.restoration(upgraded,backup,certificate=parent,events=upgrade_events,upgrade_plan=original_plan)
    plan=p.read(path.parent/name/'plan.json')
    p.require(plan['transaction']==tx and plan['source_sha256']==p.bank_hashes(upgraded)
              and plan['expected_sha256']==p.bank_hashes(expected),'Parent restoration plan changed')
    steps=[[v['bank'],v['address']>>12] for v in tx['operations'][1:]]
    p.require(plan['steps']==steps,'Parent restoration step order changed')
    events=p.read(path.parent/name/'events.json')
    # Admission accepts only the retained known transaction lineage. The
    # lower-level planner independently replays all bytes and verifies counts.
    lineage=dict(source_sha256=original_plan['source_sha256'],steps=original_plan['steps']+steps,
                 transaction=original_plan['transaction'])
    recovery,records,wanted=c.restoration(banks,backup,certificate=case,
        events=upgrade_events+events,upgrade_plan=lineage)
    recovery['recovery_lineage']=dict(upgrade_receipt_sha256=oldcp['report_sha256'],
        restoration_receipt_sha256=cp['restore_instruction_report_sha256'],interrupted_case=name,
        upgrade_events=len(upgrade_events),restoration_events=len(events),
        original_backup_sha256=p.bank_hashes(backup),complete_history_replayed=True)
    return recovery,records,wanted
