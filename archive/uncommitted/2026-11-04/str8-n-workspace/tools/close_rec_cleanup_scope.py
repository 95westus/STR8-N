"""Bind successful RAM admission to the pending review; no hardware access."""
import json
from pathlib import Path
import devtools_2512_session as ds
t=ds.t;Q=ds.Q;out=Q/'2604-2609-REC-cleanup-scope-20261102-r3'
p=json.loads((out/'plan.json').read_text())
proof=Q/'2609-REC-cleanup-tools-20261102-r1/report.json';r=json.loads(proof.read_text());assert r['passed']
assert all(r[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'))
for board in ('2604','2609'):
 m=json.loads((Q/f'device-operations/{board}.json').read_text())
 assert not m['block_snapshot'] and m['application_ram_restored'] and not m['application_RAM_restore_pending']
 assert m['current_physical_bank_sha256']==p['boards'][board]['before_bank_sha256']
 (out/board/'device-marker-before.json').write_text(json.dumps(m,indent=2)+'\n')
for b in range(4):
 f=proof.parent/f'B{b}-before.bin';assert t.sha(f.read_bytes())==p['boards']['2609']['before_bank_sha256'][f'B{b}']
 (out/'2609'/f'B{b}-fresh-readonly-capture.bin').write_bytes(f.read_bytes())
p['REC_tools_admission']=dict(qualified_65C02_receipt=str(Q/'2512-loadable-full-MAINT-20261102-r2/report.json'),qualified_816_receipt=str(proof),qualified_816_receipt_sha256=t.sha(proof.read_bytes()),MAINT_sha256=r['MAINT_sha256'],FLASH_sha256=r['FLASH_sha256'],builds_for_this_scope=0)
(out/'REC-tools-admission.json').write_text(json.dumps(p['REC_tools_admission'],indent=2)+'\n')
(out/'plan.json').write_text(json.dumps(p,indent=2)+'\n')
doc=out/'review-document.txt';doc.write_text(doc.read_text()+'\nREC TOOL ADMISSION COMPLETE: Existing full MAINT.bin and FLASH.bin passed\nRAM-only qualification on 2609 in 65C816 emulation. MAINT also passed on\n2512 in 65C02 mode. The four fresh 2609 flash captures match this plan.\nBoth boards are recorded idle with owner RAM restored. No write was made\nto flash, PROGRAM/WORKSPACE, RTC settings or the boot/wear journal.\nSee REC-tools-admission.json. Fresh admission is still required at execution.\n')
review=json.loads((out/'review.json').read_text());review.update(plan_sha256=t.sha((out/'plan.json').read_bytes()),review_document_sha256=t.sha(doc.read_bytes()),RAM_admission_complete=True)
(out/'review.json').write_text(json.dumps(review,indent=2)+'\n')
print('Review ready: 21 erases; REC tools admitted on both CPU paths; no flash writes performed.')
