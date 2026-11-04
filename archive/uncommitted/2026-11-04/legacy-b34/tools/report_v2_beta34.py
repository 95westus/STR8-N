"""Seal measured beta34 model/rebuild evidence. Never accesses a board."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-beta34-candidate'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    meta=read(OUT/'build.json');digest=sha(OUT/'build.json')
    assert meta['version']=='2.0b34' and meta['generation']==46 and not meta['v21_included']
    for n,h in meta['artifacts'].items():assert sha(OUT/n)==h,n
    names=('beta34-integration.json','beta34-batch.json','beta34-reproducibility.json')
    for n in names:
        result=read(OUT/n);assert result['passed'] and result['build_sha256']==digest,n
    micro=read(OUT/'beta34-microchess.json')
    assert micro['passed'] and micro['candidate_build_sha256']==digest
    assert micro['printed_save_command_verified'] and micro['assembler_version']=='0.5'
    asm=read(OUT/'assembler/test-results.json');ar=read(OUT/'assembler/build.json')
    assert len(asm['passed'])==12 and 'test_save_summary' in asm['passed'] and asm['all_212_encodings_compared_with_wdc']
    assert asm['sha256']==ar['sha256']==sha(OUT/'assembler/asm-e000.bin')
    assert ar['version']=='0.5' and ar['bytes']==meta['assembler']['bytes']
    x=read(OUT/'xip/build.json');before=read(ROOT/'BUILD/v2-beta33-candidate/assembler/build.json')
    usage=dict(assembler_flash_bytes=ar['bytes'],assembler_flash_increase=ar['bytes']-before['bytes'],
        assembler_flash_allocated_bytes=8192,assembler_flash_bytes_outside_image=8192-ar['bytes'],
        vector_tail_included_in_allocation=True,native_bundle_bytes=x['flash_linked_bytes']+2,
        native_bundle_spare_bytes=x['flash_spare_bytes'],permanent_ram_increase_bytes=0,
        assembler_active_workspace_bytes=25344,assembler_zero_page_bytes=64,
        assembler_source_bytes=7168,assembler_output_bytes=12544,assembler_symbols=256)
    assert usage['native_bundle_bytes']==22062 and usage['native_bundle_spare_bytes']==466
    paths=[ROOT/'Makefile',ROOT/'src/v2-config/str8n-v2-public.inc']+sorted((ROOT/'src/asm').glob('*'))
    paths += [ROOT/'tools'/n for n in ('build_asm.py','build_v2_beta33.py','build_v2_beta34.py',
        'test_asm.py','test_v2_beta34.py','test_v2_beta34_batch.py','check_v2_beta34_rebuild.py','report_v2_beta34.py',
        'build_microchess_asm04.py','test_microchess_asm05.py')]
    paths+=sorted((ROOT/'examples/beta33').glob('*.asm'))
    source={p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()}
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    assert branch=='codex/v2-beta34-asm-summary' and not (ROOT/'src/v2.1-alpha').exists()
    report=dict(passed=True,version='2.0b34',generation=46,assembler_version='0.5',
        build_sha256=digest,branch=branch,source_sha256=source,usage=usage,
        receipts={n:sha(OUT/n) for n in (*names,'beta34-microchess.json')},assembler_tests=asm['passed'],
        candidate_only=True,board_access=False,boards_flashed=False,hardware_tested=False,
        v21_included=False,stable_release=False,freeze_complete=False,soak_started=False,
        ready_for_hardware_qualification=True)
    (OUT/'usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    (OUT/'beta34-qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS beta34 candidate qualification',digest,flush=True)
    print(json.dumps(usage,indent=2),flush=True)


if __name__=='__main__':main()
