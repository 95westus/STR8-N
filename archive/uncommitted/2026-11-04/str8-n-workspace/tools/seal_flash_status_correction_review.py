"""Pin the corrective review and verify every STATUS allocation; no hardware."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from status_extents import assert_preserved
sha=lambda b:hashlib.sha256(b).hexdigest()


def run():
    q=ROOT/'output/qualification';p=q/'FLASH-status-correction-scope-20261101-r1'
    plan=json.loads((p/'plan.json').read_text());r=json.loads(Path(plan['RAM_receipt']).read_text())
    assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    assert sha(Path(plan['RAM_receipt']).read_bytes())==plan['RAM_receipt_sha256']
    assert_preserved((q/'FLASH-transfer-scope-20261101-r1/B2-original.bin').read_bytes(),(p/'B2-target.bin').read_bytes())
    freeze=json.loads((REPO/'F_FREEZE.json').read_text())
    assert all(sha((REPO/n).read_bytes())==v for n,v in freeze['sources'].items())
    f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f)==freeze['sha256'] and (p/'B3-target.bin').read_bytes()[-4096:]==f
    assert plan['total_erases']==3 and plan['journal_sector_erases']==plan['F_writes']==0
    assert plan['old_records_retained']==21 and plan['records_after']==24
    doc=(REPO/'docs/FLASH_STATUS_CORRECTION_2512_SCOPE.md').read_bytes()
    (p/'review-document.md').write_bytes(doc)
    review=dict(status='REVIEW_READY_NOT_APPROVED',plan_sha256=sha((p/'plan.json').read_bytes()),review_document_sha256=sha(doc),
        candidate_manifest_sha256=plan['candidate_manifest_sha256'],RAM_report_sha256=plan['RAM_receipt_sha256'],
        F_sha256=sha(f),frozen_sources_unchanged=True,all_four_STATUS_allocations_exact=True,
        additional_erases=3,all21_current_records_retained=True,final_sequence=1133,C_D_E_F=plan['counts_after'][28:32])
    (p/'review.json').write_text(json.dumps(review,indent=2)+'\n')
    print(json.dumps(review,indent=2))


if __name__=='__main__':run()
