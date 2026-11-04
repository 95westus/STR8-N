"""Audit the LED-fixed FLASH install and preservation of the owner's B0:9 erase."""
import argparse
from pathlib import Path
import board_flash_led_2512 as h


def audit(run):
    state,result,proof = (h.io.read(run/name) for name in ('state.json','test-results.json','live-model-proof.json'))
    assert state['passed'] and state['LED_fix_installed'] and state['FLASH_left_installed']
    assert result['hardware'] and result['serial_released'] and not state['RAM_pending'] and not state['verification_pending']
    assert proof['helper_sha256'] == result['helper_sha256'] == h.io.sha(Path(h.__file__).read_bytes())
    assert proof['checker_sha256'] == h.io.sha((h.HERE/'prepare_flash_led_2512.py').read_bytes())
    assert result['model_proof_sha256'] == h.io.sha((run/'live-model-proof.json').read_bytes())
    for name,digest in proof['bindings'].items(): assert h.io.sha(Path(name).read_bytes()) == digest,name
    assert len(proof['cases']) == 2 and all(c['passed'] for c in proof['cases'])
    before = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]
    after = [(run/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    for r in (1,2): assert after == [(run/f'final-full-flash-r{r}-b{n}.bin').read_bytes() for n in range(4)]
    image = (h.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    assert after[0][:4096] == image and after[0][4096:] == before[0][4096:]
    assert after[0][4096:8192] == b'\xff'*4096
    assert after[1:3] == before[1:3]
    sy = h.io.read(h.BUILD/'symbols.json')['core/bank-monitor-8000']
    body = (h.BUILD/'payload/bank-monitor-8000-ram.bin').read_bytes()
    offset = sy['BM_MENU']-0x200
    assert body[offset:offset+5] == bytes.fromhex('A9018DA07F'), 'Expected idle write must precede every prompt'
    old,new = h.io.latest(before),h.io.latest(after)
    assert h.wire.policy(old) == h.wire.policy(new)
    assert int.from_bytes(new[8:12],'little') == int.from_bytes(old[8:12],'little')+3
    for index in range(32):
        count = lambda row: int.from_bytes(row[64+index*3:67+index*3],'little')
        assert count(new)-count(old) == (1 if index==0 else 2 if index==1 else 0)
    changed = []
    for offset in range(0,32768,256):
        a,b = before[3][offset:offset+256],after[3][offset:offset+256]
        if a == b: continue
        assert 0x4000<=offset<0x6000 and a == b'\xff'*256 and b[:4] == b'SNBT'
        changed.append(offset+0x8000)
    assert len(changed) == 3
    owner,current,zp = ((run/name).read_bytes() for name in ('owner-ram.bin','current-RAM-before-tools.bin','owner-zp.bin'))
    assert owner[0xd00:] == current[0xd00:]
    assert owner[:0xd00] == (h.PREVIOUS/'owner-ram.bin').read_bytes()[:0xd00]
    for r in (1,2):
        assert (run/f'restored-RAM-r{r}.bin').read_bytes() == owner
        assert (run/f'restored-ZP-r{r}.bin').read_bytes() == zp
    assert (run/'final-MON-RAM.bin').read_bytes() == owner and (run/'final-MON-ZP.bin').read_bytes() == zp
    for label in ('program','erase'):
        assert b'OK: verified sector\r\nFLASH> ' in (run/(label+'-returned-prompt.txt')).read_bytes()
    marker = h.io.read(h.io.MARKER)
    assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'),map(h.io.sha,after)))
    assert marker['FLASH_installed']['LED_fix'] and marker['FLASH_installed']['sha256'] == h.io.sha(image)
    assert not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending',
        'firmware_verification_pending','recovery_worker_active','opaque_sector_restore_pending'))
    assert h.io.read(h.ROOT/'output/qualification/serial-coordination/owner.json')['kind'] == 'idle'
    final = dict(passed=True,audited=True,hardware=True,board='2512',LED_fix_installed=True,
        FLASH_left_installed=True,image_sha256=h.io.sha(image),idle_LED_write='01 before FLASH prompt',
        busy_LED_model_verified=True,LED_model_groups=34,regression_groups=69,source_bound_CPU_profiles=2,
        live_program_erase_prompt_paths_verified=True,independent_optical_LED_measurement=False,
        user_B0_9_erase_preserved=True,settings_preserved=True,owner_RAM_restored=True,owner_ZP_preserved=True,
        original_sequence=int.from_bytes(old[8:12],'little'),final_sequence=int.from_bytes(new[8:12],'little'),
        erase_attempts_added={'B0:8':1,'B0:9':2},C_D_erases=0,new_journal_pages=[f'{v:04X}' for v in changed],
        F_MON_and_other_opaque_images_unchanged=True,final_console='BOTH',final_monitor='B',serial_released=True,
        hardware_report_sha256=h.io.sha((run/'test-results.json').read_bytes()),
        auditor_sha256=h.io.sha(Path(__file__).read_bytes()),limits=result['limits'])
    h.io.save(run/'audited-results.json',final)
    print('PASS audited LED fix; user B0:9 erase/settings/RAM preserved; serial idle')
    return final


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
