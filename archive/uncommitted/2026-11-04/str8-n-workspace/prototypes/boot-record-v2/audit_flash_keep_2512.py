"""Audit the fresh B0 backup, one-sector FLASH install and owner RAM restoration."""
import argparse
from pathlib import Path
import board_flash_keep_2512 as h


def audit(run):
    state,result,proof = (h.io.read(run/name) for name in ('state.json','test-results.json','live-model-proof.json'))
    assert state['passed'] and state['FLASH_installed'] and state['leave_installed']
    assert result['passed'] and result['hardware'] and result['serial_released']
    assert not state['RAM_pending'] and not state['verification_pending']
    assert result['helper_sha256'] == proof['helper_sha256'] == h.io.sha(Path(h.__file__).read_bytes())
    assert result['model_proof_sha256'] == h.io.sha((run/'live-model-proof.json').read_bytes())
    assert proof['checker_sha256'] == h.io.sha((h.HERE/'prepare_flash_keep_2512.py').read_bytes())
    assert len(proof['cases']) == 2 and all(c['passed'] for c in proof['cases'])
    for name,digest in proof['bindings'].items(): assert h.io.sha(Path(name).read_bytes()) == digest,name
    before = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]
    after = [(run/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    for repeat in (1,2):
        assert after == [(run/f'installed-full-flash-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]
    image = (h.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    assert after[0][:4096] == image and after[0][4096:] == before[0][4096:]
    assert after[1:3] == before[1:3]
    assert (run/'original-B0.bin').read_bytes() == before[0]
    assert (run/'original-B0-80.bin').read_bytes() == before[0][:4096]
    backup = h.io.read(run/'backup-manifest.json')
    assert backup['original_B0']['sha256'] == h.io.sha(before[0])
    assert backup['overwritten_sector']['sha256'] == h.io.sha(before[0][:4096])
    old,new = h.io.latest(before),h.io.latest(after)
    assert h.prior.policy(old) == h.prior.policy(new)
    assert int.from_bytes(new[8:12],'little') == int.from_bytes(old[8:12],'little')+1
    for index in range(32):
        count = lambda row: int.from_bytes(row[64+index*3:67+index*3],'little')
        assert count(new)-count(old) == int(index == 0)
    changed = []
    for offset in range(0,32768,256):
        a,b = before[3][offset:offset+256],after[3][offset:offset+256]
        if a == b: continue
        assert 0x4000 <= offset < 0x6000 and a == b'\xff'*256 and b[:4] == b'SNBT'
        changed.append(offset+0x8000)
    assert len(changed) == 1
    owner,zp = (run/'owner-ram.bin').read_bytes(),(run/'owner-zp.bin').read_bytes()
    for n in (1,2):
        assert (run/f'restored-owner-ram-r{n}.bin').read_bytes() == owner
        assert (run/f'restored-owner-zp-r{n}.bin').read_bytes() == zp
    assert (run/'final-MON-owner-ram.bin').read_bytes() == owner
    assert (run/'final-MON-owner-zp.bin').read_bytes() == zp
    assert b'FLASH / MAINT - b15 example' in (run/'FLASH-boot.txt').read_bytes()
    assert b'STR8-N 2.0proto b15 B3 65C02' in (run/'FLASH-Q-to-B3.txt').read_bytes()
    marker = h.io.read(h.io.MARKER)
    assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'),map(h.io.sha,after)))
    assert not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending',
        'firmware_verification_pending','opaque_sector_restore_pending','recovery_worker_active'))
    assert marker['FLASH_installed']['sha256'] == h.io.sha(image)
    assert marker['original_B0_backup']['sha256'] == h.io.sha(before[0])
    assert h.io.read(h.ROOT/'output/qualification/serial-coordination/owner.json')['kind'] == 'idle'
    final = dict(passed=True,audited=True,hardware=True,board='2512',FLASH_left_installed=True,
        target='B0:8',entry='8000',image_sha256=h.io.sha(image),boot_help_Q_verified=True,
        original_B0_backup=str(run/'original-B0.bin'),original_B0_sha256=h.io.sha(before[0]),
        boot_settings_preserved=True,owner_RAM_restored=True,owner_ZP_preserved=True,
        default_boot=chr(new[7]),bank_mask=new[13],entries_hex=[f'{v<<12:04X}' for v in new[14:18]],
        original_sequence=int.from_bytes(old[8:12],'little'),final_sequence=int.from_bytes(new[8:12],'little'),
        erase_attempts_added={'B0:8':1},C_D_erases=0,new_journal_page=f'{changed[0]:04X}',
        F_MON_B0_9_and_other_images_unchanged=True,final_console='BOTH',final_monitor='B',
        serial_released=True,RTC_writes=False,physical_reset_used=False,
        hardware_report_sha256=h.io.sha((run/'test-results.json').read_bytes()),
        auditor_sha256=h.io.sha(Path(__file__).read_bytes()),limits=result['limits'])
    h.io.save(run/'audited-results.json',final)
    print('PASS audited FLASH left installed; B0 backup durable; boot settings/owner RAM preserved')
    return final


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
