"""Read-only final audit of the preserving b15 hardware installation and probes."""
import argparse
import json
from pathlib import Path
import board_b15_2512 as h
from installer.engine import legacy_transport as wire


def audit(run):
    state=h.io.read(run/'state.json');result=h.io.read(run/'test-results.json');proof=h.io.read(run/'live-model-proof.json')
    assert state['passed'] and result['passed'] and result['hardware'] and result['serial_released']
    assert not state['RAM_pending'] and not state['firmware_pending']
    assert result['live_model_proof_sha256']==h.io.sha((run/'live-model-proof.json').read_bytes())
    assert proof['helper_sha256']==h.io.sha(Path(h.__file__).read_bytes())
    assert proof['checker_sha256']==h.io.sha((h.HERE/'prepare_b15_2512.py').read_bytes())
    for name,digest in proof['bindings'].items():assert h.io.sha(Path(name).read_bytes())==digest,name
    assert len(proof['cases'])==10 and len(proof['post_install_checks'])==2
    assert all(c['passed'] for c in proof['cases']+proof['post_install_checks'])
    plan=run/'plan';info=h.io.read(plan/'plan.json');tx=info['transaction']
    before=[(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before==[(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]
    assert list(map(h.io.sha,before))==info['source_sha256']
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    for repeat in (1,2):assert expected==[(run/f'b15-device-final-flash-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]
    assert expected[:3]==before[:3]
    for offset in (0,0x1000,0x6000):assert expected[3][offset:offset+4096]==before[3][offset:offset+4096]
    for address,name in ((0xa000,'monitor-a0-offline-component.bin'),(0xb000,'monitor-b0-offline-component.bin'),(0xf000,'f-offline-component.bin')):
        offset=address-0x8000;data=expected[3][offset:offset+4096]
        assert data==(h.BUILD/'payload'/name).read_bytes()
        if address!=0xf000:assert wire.slot_valid(data,address>>8) and int.from_bytes(data[8:12],'little')==0x8000000f
    old,new=h.io.latest(before),h.io.latest(expected)
    assert h.policy(old)==h.policy(new)
    assert new[18:22]==bytes.fromhex('0f000080') and new[32+9:32+13]==bytes.fromhex('0f000080')
    assert old[32:41]==new[32:41] and old[45:46]==new[45:46]
    assert old[48:64]+old[160:252]==new[48:64]+new[160:252]
    assert int.from_bytes(new[8:12],'little')==int.from_bytes(old[8:12],'little')+1
    reserved={26,27,31}
    for index in range(32):
        assert int.from_bytes(new[64+index*3:67+index*3],'little')==int.from_bytes(old[64+index*3:67+index*3],'little')+int(index in reserved)
    offset=tx['reservation_offset']
    assert before[3][offset:offset+256]==b'\xff'*256
    assert expected[3][0x4000:offset]==before[3][0x4000:offset]
    assert expected[3][offset+256:0x6000]==before[3][offset+256:0x6000]
    assert tx['planned_erase_order']==[[3,10],[3,15],[3,11]] and tx['native_C_D_erases']==0
    owner=(run/'owner-ram.bin').read_bytes();zp=(run/'owner-zp.bin').read_bytes()
    for n in (1,2):
        assert (run/f'restored-owner-ram-r{n}.bin').read_bytes()==owner
        assert (run/f'restored-owner-zp-r{n}.bin').read_bytes()==zp
    assert (run/'final-MON-owner-ram.bin').read_bytes()==owner and (run/'final-MON-owner-zp.bin').read_bytes()==zp
    for label in ('Ctrl-C-USB-after-wait','Ctrl-C-BOTH-CRLF'):
        c=h.io.read(run/(label+'.json'));assert c['passed'] and c['first_byte_Ctrl_C'] and c['cancel_reply_seconds']<2
    assert h.io.read(run/'Ctrl-C-USB-after-wait.json')['initial_wait_seconds']>=3.5
    app=h.ROOT/'BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin';body=bytearray(app.read_bytes())
    sy=h.io.read(h.ROOT/'BUILD/pr04-b14-ram-config-r1/symbols.json')['core/ram-config'];body[sy['CONFIG_ROW']-0x200]=4
    assert (run/'normal-BIN-independent-RAM-readback.bin').read_bytes()==body
    marker=h.io.read(h.MARKER)
    assert marker['firmware']=='2.0proto b15' and marker['monitor_generation']==0x8000000f
    assert not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending','physical_reset_pending',
        'installer_worker_active','firmware_verification_pending'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),map(h.io.sha,expected)))
    assert h.io.read(h.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    final=dict(passed=True,audited=True,hardware=True,failures=0,board='2512',firmware='2.0proto b15',generation_hex='8000000F',
        original_default=chr(old[7]),final_default=chr(new[7]),bank_mask=new[13],entries_hex=[f'{b<<12:04X}' for b in new[14:18]],
        original_sequence=int.from_bytes(old[8:12],'little'),final_sequence=int.from_bytes(new[8:12],'little'),
        erase_targets=['B3:A','B3:F','B3:B'],erase_attempts_added=3,C_D_erases=0,old_journal_pages_preserved=True,
        Ctrl_C_cases=2,normal_BIN_bytes=len(body),normal_BIN_execution_and_independent_readback=True,
        owner_RAM_restored=True,owner_ZP_preserved=True,opaque_images_preserved=True,RTC_writes=False,
        final_console='BOTH',final_monitor='B',serial_released=True,physical_reset_used=False,
        original_native_models=10,software_restart_models=10,post_install_CPU_profiles=2,
        hardware_result_sha256=h.io.sha((run/'test-results.json').read_bytes()),
        proof_sha256=h.io.sha((run/'live-model-proof.json').read_bytes()),auditor_sha256=h.io.sha(Path(__file__).read_bytes()),
        limits=result['limits'])
    h.io.save(run/'audited-results.json',final);print(json.dumps(final,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
