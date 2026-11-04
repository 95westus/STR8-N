"""Bind the owner's explicit two-erase target approval to the sealed plan/driver."""
import ast
from pathlib import Path
import qualify_services_g4_2512_ram as t
scope=t.ROOT/'output/qualification/2609-AP02-scope-20261030-r1'
source=t.ROOT/'tools/trial_2609_ap02.py'
ast.parse(source.read_text())
assert t.sha((scope/'plan.json').read_bytes())=='01b1753b72c20069f85f89db7226b489d8a97dd603115d2a13b42f8700fb50e8'
auth=dict(board='2609',owner_answer='Approve two-erase B0:9 trial',recorded_utc=t.utc(),
    plan_sha256=t.sha((scope/'plan.json').read_bytes()),driver_sha256=t.sha(source.read_bytes()),
    approved=True,target='B0:9000',sector_erases=2,C_D_erases=0,F_writes=0,
    native_checksum_1_to_0_cells=['901C','901D','901E','901F'],
    exact_original_WDC_restore_required=True,RTC_readmission_same_instrument=True)
t.save(scope/'owner-approval.json',auth);(scope/source.name).write_bytes(source.read_bytes())
print(auth)
