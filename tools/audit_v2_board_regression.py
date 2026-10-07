"""Audit physical regression receipts and exact before/after preservation."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    result=dict(passed=True,version='2.0b12',clock_version='1.4',physical_hardware_tested=True,boards=[],rtc_native_calls_tested=False,flash_mutation_tests=False,power_cycle_tests=False)
    for board in ('2512','2205','2609'):
        root=a.root/board;r=read(root/'report.json');nmi=read(root/'nmi-check/report.json');final=read(root/'final-check/report.json')
        assert r['passed'] and nmi['passed'] and final['passed'] and nmi['pointers_restored']
        assert not r['manual_nmi_pending'] and r['final_post_interrupt_check_passed']
        assert not r['flash_changed'] and not r['clock_set'] and not r['trim_changed'] and not r['powerfail_acknowledged']
        for bank in range(4):
            before=(root/f'before-b{bank}.bin').read_bytes();after=(root/f'after-b{bank}.bin').read_bytes();post=(root/f'final-check/b{bank}.bin').read_bytes()
            accepted=(ROOT/f'output/qualification/rtc-binding-2026-10-07/{board}/binding-check/final-b{bank}.bin').read_bytes()
            assert before==after==post==accepted and sha(before)==r['initial_hashes'][bank]==r['final_hashes'][bank]==final['final_hashes'][bank]
        if board!='2512':
            before=(root/'eeprom-before.bin').read_bytes()
            for p in ('eeprom-after.bin','eeprom-repeat.bin','final-check/eeprom-0.bin','final-check/eeprom-1.bin'):
                assert (root/p).read_bytes()[:137]==before[:137]
            assert final['clock_advanced'] and final['control_trim_unchanged'] and final['eeprom_factory_identity_unchanged']
        native=False
        if board=='2609':
            nr=read(root/'native-check/report.json');assert nr['passed'] and nr['pointers_restored'] and final['returned_816_emulation_state'][0]==1
            native=True
        result['boards'].append(dict(board=board,automated_checks=r['checks'],physical_nmi=True,native_brk_nmi=native,final_hashes=final['final_hashes'],all_flash_preserved=True,eeprom_preserved=board!='2512'))
        print('PASS',board,'physical regression, interrupt restoration and complete preservation audit')
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    for b in baseline['boards']:
        for key in ('sync','baseline'):assert sha(Path(b[key+'_report']).read_bytes())==b[key+'_sha256']
    result['original_utc_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
