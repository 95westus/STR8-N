"""Close the approved BANK MAINT trial from existing device receipts; no ports."""
import json
from pathlib import Path
import install_2512_native_utilities as d

t=d.t
SCOPE=t.ROOT/'output/qualification/BANK-MAINT-scope-20261031-r1'
OUT=t.ROOT/'output/qualification/BANK-MAINT-closeout-20261031-r1'


def run():
    result=dict(passed=True,total_erases=0,F_writes=0,C_D_erases=0,power_cuts=0,
                boards={},excluded_boards=['2205','2604'],published_download_changes=0,
                firmware_rebuilds_after_first_native_WB_services_builds=0,
                scope=str(t.REPO/'docs/BANK_MAINT_2512_2609_SCOPE.md'))
    for board in ('2512','2609'):
        case=t.ROOT/f'output/qualification/{board}-BANK-MAINT-installed-20261031-r1'
        report=json.loads((case/'report.json').read_text())
        plan=json.loads((SCOPE/board/'plan.json').read_text())
        assert report['passed'] and report['port_released']
        assert report['owner_RAM_restored'] and report['owner_ZP_restored']
        assert report['fixture_verified_exact'] and report['image_erases_requested']==7
        assert report['final_journal']['counts']==plan['counts_after']
        assert report['final_journal']['valid_records']==plan['records_after']
        assert all(report[k]==0 for k in ('F_writes','C_D_erases','RTC_writes','SRAM_data_writes','power_cuts'))
        marker=json.loads((t.ROOT/f'output/qualification/device-operations/{board}.json').read_text())
        assert not marker['application_RAM_restore_pending'] and not marker['bank_maint_installation_pending']
        assert not marker['bank_maint_fixture_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        assert marker['final_prompt']=='B3>' and marker['current_journal_sequence']==plan['sequence_after']
        for bank in (1,2,3):
            assert t.sha((case/f'B{bank}-after.bin').read_bytes())==report['final_bank_sha256'][f'B{bank}']
            assert marker['current_physical_bank_sha256'][f'B{bank}']==report['final_bank_sha256'][f'B{bank}']
        before=report['owner_RAM_sha256'];after=report['RAM_sha256']
        assert before==after and report['owner_ZP_sha256']==report['ZP_sha256']
        result['total_erases']+=plan['total_erases']
        result['boards'][board]=dict(passed=True,report=str(case/'report.json'),
            image_erases=7,fixture_erases=plan['fixture_erases'],
            journal_appends=plan['total_erases'],naming_appends=2,
            original_journal_rows_retained=plan['records_before'],
            sequence=plan['sequence_after'],valid_journal_rows=plan['records_after'],
            owner_RAM_sha256=after,owner_ZP_sha256=report['ZP_sha256'],
            bank_sha256=marker['current_physical_bank_sha256'],final_prompt='B3>')
    assert result['total_erases']==17
    assert result['boards']['2512']['bank_sha256']['B1']==result['boards']['2609']['bank_sha256']['B1']
    assert result['boards']['2512']['bank_sha256']['B2']==result['boards']['2609']['bank_sha256']['B2']
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    t.save(OUT/'final-receipt.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
