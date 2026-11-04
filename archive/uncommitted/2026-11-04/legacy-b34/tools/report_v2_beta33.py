"""Seal beta33 model/rebuild receipts and measured usage; no board access."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-beta33-candidate'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    meta=read(OUT/'build.json');digest=sha(OUT/'build.json')
    assert meta['version']=='2.0b33' and meta['generation']==45 and not meta['v21_included']
    for name,value in meta['artifacts'].items():assert sha(OUT/name)==value,name
    receipts={name:read(OUT/name) for name in ('beta33-integration.json','beta33-batch.json','beta33-reproducibility.json')}
    for name,result in receipts.items():assert result['passed'] and result['build_sha256']==digest,name
    asm=read(OUT/'assembler/test-results.json')
    assert len(asm['passed'])==11 and asm['all_212_encodings_compared_with_wdc']
    assert asm['sha256']==sha(OUT/'assembler/asm-e000.bin')
    assert asm['sha256']==read(OUT/'assembler/build.json')['sha256']
    x=read(OUT/'xip/build.json')
    usage=dict(assembler_flash_bytes=6244,assembler_flash_allocated_bytes=8192,
        assembler_flash_bytes_outside_image=1948,application_vector_tail_included_in_allocation=True,
        native_bundle_bytes=x['flash_linked_bytes']+2,native_bundle_reserved_bytes=22528,
        native_bundle_spare_bytes=x['flash_spare_bytes'],native_bundle_increase_bytes=50,
        assembler_active_workspace_bytes=25344,assembler_zero_page_bytes=64,
        assembler_source_bytes=7168,assembler_output_bytes=12544,assembler_symbol_records=256,
        permanent_ram_increase_bytes=0,edu_on_application_ram_end=0x64FF)
    assert usage['native_bundle_bytes']==22062 and usage['native_bundle_spare_bytes']==466
    paths=[ROOT/'Makefile',ROOT/'src/v2-config/str8n-v2-public.inc']
    paths+=sorted((ROOT/'src/asm').glob('*'))+sorted((ROOT/'examples/beta33').glob('*'))
    paths += [ROOT/'tools'/name for name in ('build_asm.py','build_v2_beta33.py','test_asm.py',
        'test_v2_beta33.py','test_v2_beta33_batch.py','report_v2_beta33.py')]
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()}
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    base=subprocess.check_output(['git','rev-parse','e97d785'],cwd=ROOT,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert branch=='codex/v2-beta33-asm'
    assert subprocess.run(['git','merge-base','--is-ancestor',base,head],cwd=ROOT).returncode==0
    assert not (ROOT/'src/v2.1-alpha').exists()
    report=dict(passed=True,version='2.0b33',generation=45,build_sha256=digest,
        branch=branch,base_commit=base,source_head=head,assembler_source_checkpoint='5313633',
        assembler_version='0.4',assembler_encodings=212,assembler_tests=asm['passed'],
        receipts={name:sha(OUT/name) for name in receipts},source_sha256=sources,
        usage=usage,candidate_only=True,intended_freeze_candidate=True,freeze_complete=False,
        stable_release=False,board_access=False,boards_flashed=False,hardware_tested=False,
        v21_included=False,combined_soak_evidence_accepted_by_owner=True,soak_stopped=True,
        soak_acceptance_date='2026-10-16',enhanced_soak_completed_24_hours=False,
        hourly_reminder_disabled=True,ready_for_hardware_qualification=True)
    (OUT/'usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    (OUT/'beta33-qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS beta33 candidate qualification:',digest,flush=True)
    print('ASM 6244 flash bytes / two sectors; active RAM 25344 + 64 ZP; contiguous code 0200-32FF; permanent RAM increase 0',flush=True)


if __name__=='__main__':main()
