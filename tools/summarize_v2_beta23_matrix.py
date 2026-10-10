"""Bind four-board qualification receipts to frozen firmware and final data."""
import argparse,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--require-endurance',action='store_true');p.add_argument('--require-fixed-recovery',action='store_true');a=p.parse_args();a.root=a.root.resolve()
    assert not a.require_fixed_recovery or a.require_endurance
    frozen=ROOT/'output/qualification/beta23-phase1-2026-10-09';build=frozen/'frozen/build'
    candidate=json.loads((build/'build.json').read_text());model_root=ROOT/'BUILD/beta23-storage-models';models={}
    for name in ('local-time-test-results.json','trim-test-results.json','storage-fault-cold-model.json','flash-roundtrip-model.json','fixed-recovery-test-results.json'):
        path=model_root/name;result=json.loads(path.read_text());assert result['passed'] and result['artifacts']==candidate['artifacts'],name
        models[name]=sha(path)
    phases=['storage-workflow','standalone-register-probe','storage-faults','power-check','offset-check','storage-faults-cold']
    if a.require_endurance:phases.append('endurance')
    if a.require_fixed_recovery:phases.append('fixed-recovery-check')
    rows=[]
    regions=[(3,0,'str8n-rtc-component-8000-8fff.bin',4096),(3,0x1000,'str8n-journal-9000-9fff.bin',3072),
             (3,0x2000,'str8n-v2-recovery-slot-a0.bin',4096),(3,0x3000,'str8n-v2-recovery-slot-b0.bin',4096),
             (3,0x6000,'str8n-v2-recovery-e000-efff.bin',4096),(3,0x7000,'str8n-v2-recovery-f000-ffff.bin',4096),
             (2,0x4800,'boot-status/asset.bin',2560),(2,0x6000,'local-display/asset.bin',1536)]
    for board in ('2512','2205','2604','2609'):
        root=a.root/board;reports={}
        for phase in phases:
            path=root/phase/'report.json';data=json.loads(path.read_text());assert data['passed'],(board,phase)
            assert not data.get('clock_set',False) and not data.get('trim_changed',False),(board,phase,'clock changed')
            reports[phase]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        current=root/('fixed-recovery-check' if a.require_fixed_recovery else ('endurance' if a.require_endurance else 'offset-check'));banks=[(current/f'b{i}.bin').read_bytes() for i in range(4)]
        for bank,pos,name,length in regions:assert banks[bank][pos:pos+length]==(build/name).read_bytes()[:length],(board,name)
        original=root/'sram-prior/array-0.bin';assert original.read_bytes()==(root/'sram-prior/array-1.bin').read_bytes()
        final=current/'sram-final/array-0.bin';assert final.read_bytes()==original.read_bytes()
        offset=json.loads((root/'offset-check/report.json').read_text());power=json.loads((root/'power-check/report.json').read_text())
        rows.append(dict(board=board,edu='ON',normal_trim=0,display_offset=offset['original_offset'],
            firmware_regions_exact=True,full_sram_bytes=131072,sram_sha256=sha(final),
            reports=reports,final_flash_sha256=[hashlib.sha256(x).hexdigest() for x in banks],
            new_tz_records=offset['appends'],power_journal_behavior=power['journal_behavior']))
    clean=ROOT/'tmp/b23repro/clean-checkout-receipt.json';assert json.loads(clean.read_text())['passed']
    report=dict(passed=True,scope='Four-board beta23 qualification checkpoint; not RC acceptance',version='2.0b23',generation=32,
        freeze_receipt_sha256=sha(frozen/'freeze-receipt.json'),clean_checkout_receipt_sha256=sha(clean),
        additional_frozen_model_report_hashes=models,
        endurance_complete=a.require_endurance,fixed_recovery_complete=a.require_fixed_recovery,boards=rows,soak_started=False,soak_complete=False,release_packaging_complete=False,
        limitation='STR8N-001 ACIA receive remains deferred; 2604 foreign EEPROM history preserved with error 90',
        published=False)
    destination=a.root/('qualification-summary.json' if a.require_endurance else 'pre-endurance-summary.json')
    destination.write_text(json.dumps(report,indent=2)+'\n');print('PASS',destination,'four boards, frozen firmware and complete retained data')

if __name__=='__main__':main()
