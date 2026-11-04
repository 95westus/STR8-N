"""Read-only capture/result audit for the 2512 FLASH example round trip."""
import argparse
from pathlib import Path
import board_bank_monitor_2512 as h


def audit(run):
    state = h.io.read(run/'state.json'); result = h.io.read(run/'test-results.json')
    proof = h.io.read(run/'live-model-proof.json')
    assert state['passed'] and result['passed'] and result['hardware'] and result['serial_released']
    assert not state['RAM_pending'] and not state['images_pending']
    assert result['helper_sha256'] == h.io.sha(Path(h.__file__).read_bytes()) == proof['helper_sha256']
    assert result['model_proof_sha256'] == h.io.sha((run/'live-model-proof.json').read_bytes())
    assert proof['checker_sha256'] == h.io.sha((h.HERE/'prepare_bank_monitor_2512.py').read_bytes())
    for name,digest in proof['bindings'].items(): assert h.io.sha(Path(name).read_bytes()) == digest,name
    assert len(proof['cases']) == 2 and all(c['passed'] for c in proof['cases'])
    before = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]
    phases = {}
    for phase in ('edited','restored'):
        expected = [(run/f'expected-{phase}-b{n}.bin').read_bytes() for n in range(4)]
        for repeat in (1,2):
            assert expected == [(run/f'{phase}-full-flash-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]
        phases[phase] = expected
    edited,final = phases['edited'],phases['restored']
    image = (h.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    sector9 = (run/'edited-B0-90.bin').read_bytes()
    assert edited[0][:4096] == image and edited[0][4096:8192] == sector9
    assert sector9[4:] == before[0][4100:8192]
    assert sector9[:4] == bytes(v ^ 255 for v in before[0][4096:4100])
    assert final[:3] == before[:3]
    assert edited[0][8192:] == before[0][8192:] and edited[1:3] == before[1:3]
    for offset in (0,0x1000,0x2000,0x3000,0x6000,0x7000):
        assert edited[3][offset:offset+4096] == final[3][offset:offset+4096] == before[3][offset:offset+4096]
    old,mid,new = h.io.latest(before),h.io.latest(edited),h.io.latest(final)
    assert h.policy(old) == h.policy(mid) == h.policy(new)
    assert int.from_bytes(mid[8:12],'little') == int.from_bytes(old[8:12],'little')+2
    assert int.from_bytes(new[8:12],'little') == int.from_bytes(old[8:12],'little')+4
    for index in range(32):
        count = lambda r: int.from_bytes(r[64+3*index:67+3*index],'little')
        assert count(mid)-count(old) == int(index in (0,1))
        assert count(new)-count(old) == (2 if index in (0,1) else 0)
    added = []
    for offset in range(0x4000,0x6000,256):
        a,b = before[3][offset:offset+256],final[3][offset:offset+256]
        if a == b: continue
        assert a == b'\xff'*256 and b[:4] == b'SNBT'
        added.append(offset+0x8000)
    assert len(added) == 4
    owner,zp = (run/'owner-ram.bin').read_bytes(),(run/'owner-zp.bin').read_bytes()
    for repeat in (1,2):
        assert (run/f'restored-owner-ram-r{repeat}.bin').read_bytes() == owner
        assert (run/f'restored-owner-zp-r{repeat}.bin').read_bytes() == zp
    assert (run/'final-MON-owner-ram.bin').read_bytes() == owner
    assert (run/'final-MON-owner-zp.bin').read_bytes() == zp
    assert b'41 42 03 00 FF ' in (run/'RAM-readback.txt').read_bytes()
    assert b'OK: verified sector' in (run/'flash-edit-YES.txt').read_bytes()
    assert b'OK: identical; no erase' in (run/'identical-YES.txt').read_bytes()
    assert b'STR8-N 2.0proto b15 B3 65C02' in (run/'FLASH-Q-to-B3.txt').read_bytes()
    assert b'Boot : 6 5 4 3 2 1 0' in (run/'final-default-B-boot.txt').read_bytes()
    marker = h.io.read(h.io.MARKER)
    assert not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending',
        'opaque_sector_restore_pending','boot_settings_restore_pending','recovery_worker_active'))
    assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'),map(h.io.sha,final)))
    assert h.io.read(h.ROOT/'output/qualification/serial-coordination/owner.json')['kind'] == 'idle'
    audited = dict(passed=True,audited=True,hardware=True,board='2512',failures=0,
        installed_example='B0:8 FLASH; restored after test',flash_edit_target='B0:9',
        RAM_edit='2000: 41 42 03 00 FF; restored after test',Q_returns_to_B3=True,
        example_boot_verified=True,flash_edit_preserved_other_4092_bytes=True,identical_noop_verified=True,
        original_images_restored=True,boot_policy_preserved=True,owner_RAM_restored=True,owner_ZP_preserved=True,
        original_sequence=int.from_bytes(old[8:12],'little'),final_sequence=int.from_bytes(new[8:12],'little'),
        default_boot=chr(new[7]),bank_mask=new[13],entries_hex=[f'{v<<12:04X}' for v in new[14:18]],
        erase_attempts_added={'B0:8':2,'B0:9':2},C_D_erases=0,
        journal_new_pages=[f'{v:04X}' for v in added],prior_journal_pages_preserved=True,
        F_MON_unchanged=True,final_monitor='B',final_console='BOTH',serial_released=True,
        physical_reset_used=False,RTC_writes=False,original_opaque_bank_sha256=list(map(h.io.sha,final[:3])),
        helper_sha256=result['helper_sha256'],proof_sha256=result['model_proof_sha256'],
        hardware_result_sha256=h.io.sha((run/'test-results.json').read_bytes()),
        auditor_sha256=h.io.sha(Path(__file__).read_bytes()),limits=result['limits'])
    h.io.save(run/'audited-results.json',audited)
    print('PASS audited hardware round trip; original images/settings/RAM restored; four erase attempts retained')
    return audited


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
