"""Bind the prepared temporary SRAM scope to its final host driver; no port."""
import ast
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
case=t.ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'
source=t.ROOT/'tools/trial_2512_program_positive.py'
ast.parse(source.read_text())
p=json.loads((case/'plan.json').read_text())
assert p['temporary_byte_scope']==1280 and p['flash_writes']==p['journal_writes']==0
p['driver_sha256']=t.sha(source.read_bytes())
t.save(case/'plan.json',p)
(case/source.name).write_bytes(source.read_bytes())
print('2512 plan SHA256',t.sha((case/'plan.json').read_bytes()))
print('Driver SHA256',p['driver_sha256'])
