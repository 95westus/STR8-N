"""Audit captured live CONFIG postimages, original settings and RAM restoration."""
import argparse
import json
from pathlib import Path
import board_ram_config_2512 as h


def audit(run):
    state=h.read(run/'state.json');receipt=h.read(run/'test-results.json');proof=h.read(run/'model-proof.json')
    assert state['passed'] and receipt['passed'] and receipt['hardware'] and receipt['serial_released']
    assert not state['RAM_pending'] and not state['settings_pending']
    assert receipt['model_proof_sha256']==h.sha((run/'model-proof.json').read_bytes())
    assert proof['helper_sha256']==h.sha((h.HERE/'board_ram_config_2512.py').read_bytes())
    assert proof['checker_sha256']==h.sha((h.HERE/'test_ram_config_2512_live.py').read_bytes())
    assert all(c['passed'] for c in proof['cases']) and {c['cpu'] for c in proof['cases']}=={'65c02','65c816-e'}
    for name,digest in proof['artifact_sha256'].items():assert h.sha(Path(name).read_bytes())==digest
    before=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before==[(run/f'before-r2-b{n}.bin').read_bytes() for n in range(4)]
    old=h.latest(before)
    for phase,label in (('saved','saved-settings'),('restored','restored-settings')):
        expected=[(run/f'expected-{phase}-b{n}.bin').read_bytes() for n in range(4)]
        for repeat in (1,2):assert expected==[(run/f'{label}-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]
        for n in range(4):
            for offset in range(0,32768,4096):
                if n==3 and offset in (0x4000,0x5000):continue
                assert expected[n][offset:offset+4096]==before[n][offset:offset+4096]
        r=h.latest(expected)
        assert r[32:64]+r[160:252]==old[32:64]+old[160:252]
        for index in range(32):
            a=int.from_bytes(old[64+index*3:67+index*3],'little')
            b=int.from_bytes(r[64+index*3:67+index*3],'little')
            assert b==a+int(index==28)
        if phase=='saved':assert r[7]==ord('0') and r[13]==15 and r[14:18]==bytes([10,8,8,8])
        else:
            assert h.settings(r)==h.settings(old)
            final=expected
    assert (run/'owner-ram.bin').read_bytes()==(run/'final-owner-ram.bin').read_bytes()
    assert (run/'owner-zp.bin').read_bytes()==(run/'final-owner-zp.bin').read_bytes()
    assert h.sha((run/'owner-ram.bin').read_bytes())==state['owner_ram_sha256']
    assert h.sha((run/'owner-zp.bin').read_bytes())==state['owner_zp_sha256']
    show=(run/'CONFIG-restored.txt').read_bytes()
    assert b'DEFAULT=B\r\n' in show and all(f'B{n} ON  ENTRY=8000\r\n'.encode() in show for n in range(4))
    marker=h.read(h.MARKER)
    assert not marker['block_snapshot'] and not marker['application_RAM_restore_pending']
    assert not marker['recovery_worker_active'] and not marker['boot_settings_restore_pending']
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),map(h.sha,final)))
    assert h.read(h.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    result=dict(passed=True,hardware=True,failures=0,audited=True,board='2512',
        tested=dict(enable='B0 OFF -> ON',entry='A000',default='0',software_reset_retained=True),
        restored=dict(default='B',bank_mask='F',entries=['8000']*4,owner_RAM=True,owner_ZP=True,console='BOTH',monitor='B'),
        original_sequence=int.from_bytes(old[8:12],'little'),final_sequence=int.from_bytes(h.latest(final)[8:12],'little'),
        journal_erases=['B3:C'],additional_erase_attempts=1,new_history_retained=True,
        F_MON_and_opaque_images_unchanged=True,RTC_writes=False,opaque_image_executed=False,
        full_flash_postimage_comparisons=4,serial_released=True,
        host_checks=h.read(h.HERE/'ram-config-host-tests.json')['checks'],
        actual_source_CPU_profiles=2,model_proof_sha256=h.sha((run/'model-proof.json').read_bytes()),
        hardware_report_sha256=h.sha((run/'test-results.json').read_bytes()),
        auditor_sha256=h.sha(Path(__file__).read_bytes()),
        prior_host_attempts_retained=True,limitations=receipt['limits'])
    h.save(run/'audited-results.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
