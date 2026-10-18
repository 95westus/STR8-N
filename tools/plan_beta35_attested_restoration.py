"""Admit restoration only from the pinned successful upgrade-model receipt.

An arbitrary caller-provided certificate or backup hash cannot authorize a
new source. This module has no serial or hardware launcher.
"""
from pathlib import Path
import beta35_model_transactions as c
p=c.p

def restoration(banks,backup,*,certificate,events,upgrade_plan):
    cp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json');receipt=Path(cp['report'])
    p.require(p.sha(receipt.read_bytes())==cp['report_sha256'],'Pinned source receipt changed')
    trusted=p.read(receipt);p.require(trusted['passed'] and certificate in trusted['checks'],'Certificate is not in pinned source receipt')
    label=certificate['name'];p.require(not label.startswith('stale-bank-'),'Stale source is not an interrupted known transaction')
    board=label.split('-')[0] if label.endswith('-complete') else '2512'
    build=Path(cp['build_report']);p.require(p.sha(build.read_bytes())==cp['build_report_sha256'],'Pinned source build changed')
    expected=p.read(build.parent/board/'plan.json')
    row=next(b for b in p.read(build)['boards'] if b['board']==board)
    p.require(p.sha((build.parent/board/'plan.json').read_bytes())==row['plan_sha256'],'Pinned upgrade plan changed')
    p.require(upgrade_plan==expected,'Unregistered upgrade plan')
    # Bind replay input to the retained event evidence in addition to replaying
    # it against the verified backup and checking durable count lower bounds.
    retained_events=p.read(receipt.parent/label/'events.json')
    p.require(events==retained_events,'Interrupted-event trace differs from retained evidence')
    return c.restoration(banks,backup,certificate=certificate,events=events,upgrade_plan=upgrade_plan)
