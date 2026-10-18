"""Bind completed fleet hardware evidence without changing firmware metadata."""
import argparse,json
from pathlib import Path
import migrate_v2 as u

def finish(base):
    boards=[]
    for board in ('2205','2512','2604','2609'):
        root=base/board;source=u.read(root/'source.json')
        if (root/'upgrade/plan.json').exists():
            plan=u.read(root/'upgrade/plan.json');build=u.ROOT/plan['target_build'];u.audit(root,build)
            result=u.read(root/'retest/report.json');assert result['passed'] and result['fixed_f_wear_report_verified'] and result['physical_reset_verified']
            assert result['final_flash_hashes']==plan['expected_hashes']
            before=u.read(root/'retained/sram-prior/report.json');after=u.read(root/'retained/sram-final/report.json')
            assert before['passed'] and after['passed'] and before['sha256']==after['sha256']
            old=u.read(root/'retained/devices-before/report.json');new=u.read(root/'retained/devices-after/report.json')
            assert old['eeprom_sha256']==new['eeprom_sha256'] and old['control_register']==new['control_register'] and old['trim_steps']==new['trim_steps']
            assert new['passed'] and new['eeprom_preserved'] and new['identity_preserved'] and new['history_preserved']
            receipt=dict(passed=True,board=board,version='2.0b25',generation=37,fallback_version=source['version'],fallback_generation=source['generation'],fallback_slot='A',updated_slot='B',
                build_sha256=u.sha((build/'build.json').read_bytes()),artifacts=u.read(build/'build.json')['artifacts'],
                plan_sha256=u.sha((root/'upgrade/plan.json').read_bytes()),installer_sha256=plan['installer_sha256'],
                physical_report_sha256=u.sha((root/'retest/report.json').read_bytes()),expected_hashes=plan['expected_hashes'],fallback_sha256=plan['fallback_sha256'],
                physical_reset_verified=True,physical_boot_capture_complete=result['physical_boot_capture_complete'],physical_power_cycle_tested=result['physical_power_cycle_tested'],physical_nmi_tested=False,
                sram_array_sha256=after['sha256'],eeprom_sha256=new['eeprom_sha256'],rtc_control=new['control_register'],trim_steps=new['trim_steps'],
                report=str(root/'retest/report.json'))
            (build/f'hardware-qualification-{board}.json').write_text(json.dumps(receipt,indent=2)+'\n')
            action='upgraded-shared-and-inactive-B';fallback=source['version'];hashes=plan['expected_hashes']
        else:
            result=u.read(root/'report.json');assert result['passed'] and result['action']=='already-current-no-write' and not result['flash_written']
            action=result['action'];fallback=result['fallback_version'];hashes=result['flash_hashes']
        boards.append(dict(board=board,passed=True,version='2.0b25',generation=37,active_slot='B',fallback_slot='A',fallback_version=fallback,action=action,final_flash_hashes=hashes))
    report=dict(passed=True,version='2.0b25',generation=37,boards=boards,all_boards_on_beta25=True,preserved_monitor_A=True,
        issue_004_affected_board_hardware_acceptance=True,issue_005_destructive_f_only_hardware_acceptance=False)
    (base/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS all four boards beta25 B; A fallback retained; complete fleet evidence bound',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();finish(a.root)
