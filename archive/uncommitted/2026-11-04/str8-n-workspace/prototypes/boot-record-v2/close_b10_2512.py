"""Audit completed b10 hardware evidence and close the 2512 preservation record."""
import json
from datetime import datetime
from pathlib import Path
import board_b10_2512 as board

ROOT=board.ROOT
BUILD=ROOT/'BUILD/pr04-b10-wait'
PLAN=ROOT/'tmp/pr04-b10-2512-native-plan'
RUN=ROOT/'output/qualification/pr04-b10-2512-install'
AUTH=ROOT/'output/qualification/pr04-b10-2512-authorization'
MARKER=ROOT/'output/qualification/device-operations/2512.json'
r=board.r


def main():
    board.admission(BUILD,PLAN,RUN,r.read(AUTH/'deploy-authorization.json'))
    state=r.read(RUN/'state.json')
    required=('passed','transaction_device_verified','prearmed_physical_reset_boot_verified',
        'all_four_banks_verified','J3_S_verified','RLP1_load_readback_verified',
        'OIP1_read_only_sector_verified','read_only_probe_flash_unchanged','boot_verified',
        'initial_L_wait_Ctrl_C_verified','delayed_binary_load_verified','RAM_restored',
        'owner_ZP_preserved','final_software_boot_verified','full_timeout_default_B_verified',
        'final_software_boot_RAM_reread')
    r.require(all(state.get(key) is True for key in required),'Incomplete required hardware check')
    r.require(state['phase']=='completed' and state['final_console_mode']=='BOTH'
              and not state['application_RAM_restore_pending'] and not state['physical_reset_pending'],
              'Preservation cleanup incomplete')
    r.require(r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle',
              'Shared serial lease has not been released')
    physical=(RUN/'prearmed-reset-boot.txt').read_bytes()
    recovery=(RUN/'software-boot-recovery.txt').read_bytes()
    r.require(b'STR8-N 2.0proto b10 B3 65C02' in physical
              and b'Boot : 6 5 4 3 2 1 0\r\n' in physical
              and b'\r\nRecovery L/R/D/V A/B 0-3 C1/2/3\r\nREC> ' in recovery,
              'Exact physical boot/software recovery capture missing')
    idle=r.read(RUN/'b10-idle-cancel.json');binary=r.read(RUN/'b10-delayed-binary.json')
    r.require(idle['passed'] and idle['hardware'] and idle['initial_idle_seconds']>=12
              and idle['returned_to_REC_without_REFUSED'] and idle['unexpected_RX_bytes']==0,
              'Live indefinite-wait/Ctrl-C case incomplete')
    r.require(binary['passed'] and binary['hardware'] and binary['initial_idle_seconds']>=3
              and binary['payload_contains_03'] and binary['RLP1_header_payload_and_V_readback_CRC_verified'],
              'Live delayed binary/readback case incomplete')
    info=r.read(PLAN/'plan.json')
    source=[(PLAN/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(PLAN/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.require(source[:3]==expected[:3] and source[3][:0x2000]==expected[3][:0x2000]
              and source[3][0x6000:0x7000]==expected[3][0x6000:0x7000], 'Owner/RTC sectors changed')
    for _,offset,row in board.deployment_plan.snbt_records(source):
        r.require(expected[3][offset:offset+256]==row,'An original native snapshot changed')
    r.require(info['transaction']['native_C_D_erases']==0,'Unexpected C/D erase')
    others=[]
    for row in r.read(AUTH/'other-board-markers-before.json'):
        r.require(r.sha((ROOT/row['path']).read_bytes())==row['sha256'],'Other-board marker changed')
        others.append(dict(board=row['board'],marker_unchanged=True,port_opened=False,flashed=False))
    confirmation=r.read(RUN/'owner-reset-confirmation.json')
    r.require(confirmation['owner_confirmed'],'Owner physical reset confirmation missing')
    logs=list(RUN.glob('serial-*.jsonl'))
    watcher=list(RUN.glob('serial-watch-reset-*.jsonl'))
    r.require(len(watcher)==1,'One exact reset/verification stream required')
    before_TX=bytearray()
    for line in watcher[0].read_text().splitlines():
        row=json.loads(line)
        if row['direction']=='TX':break
        if row['direction']=='RX':before_TX.extend(bytes.fromhex(row['hex']))
    r.require(bytes(before_TX)==physical,'Physical boot not fully received before first TX')
    startup=r.read(RUN/'software-startup-recovery.json')
    wait_seconds=(datetime.fromisoformat(startup['WAIT_received_utc'])-datetime.fromisoformat(startup['J3_sent_utc'])).total_seconds()
    marker=r.read(MARKER)
    r.require(marker['firmware']=='2.0proto b10' and marker['monitor_generation']==0x8000000a
              and marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),r.hashes(expected)))
              and not marker['block_snapshot'] and not marker['installer_worker_active'], 'Final device marker differs')
    names=('state.json','admission.json','offline-admission-tests.json','owner-authorization.json',
        'owner-reset-confirmation.json','prearmed-reset-boot.txt','prearmed-reset-receipt.json',
        'software-boot-recovery.txt','software-startup-recovery.json','b10-idle-cancel.txt',
        'b10-idle-cancel.json','b10-delayed-binary.json','final-BOTH-software-boot.txt')
    report=dict(passed=True,failures=0,hardware=True,board='2512',usb_serial=board.USB,
        firmware='2.0proto b10',generation_hex='8000000A',firmware_sha256=info['firmware_sha256'],
        physical_reset_boot_captured=True,no_TX_before_exact_physical_boot=True,
        software_J3_to_S_without_another_physical_reset=True,recovery_heading_on_new_line=True,
        initial_L_idle_and_Ctrl_C=idle,delayed_framed_binary_and_readback=binary,
        host_observed_J3_to_WAIT_seconds=wait_seconds,
        full_flash_readback_matches_exact_expected=True,recovery_probes_did_not_change_flash=True,
        application_RAM_restored_bytes=0x6300,owner_ZP_preserved_bytes=0xe0,
        RAM_reread_after_final_default_boot=True,final_monitor='B',final_console='BOTH',serial_released=True,
        B0_B1_B2_RTC_history_and_E_preserved=True,original_native_journal_records_preserved=True,C_D_erases=0,
        planned_erases=info['transaction']['planned_erase_order'],RTC_set_trim_ACK_commands=False,
        F_body_bytes=4063,F_reserved_bytes=32,F_free_bytes=1,MON_body_bytes=3830,MON_header_bytes=128,MON_free_bytes=138,
        offline_checks=dict(regression_selection=426,receive_wait_cancel_binary=32,USB_timing=2,bench=4,
            native_transaction_models=10,source_target_host_and_reset_watcher=6,live_probe_buffered=3,
            admission_positive_negative=11,source_backup_buffered=11,failures=0),other_boards=others,
        earlier_nonfinal_attempts=[
            dict(kind='test-harness',evidence='output/qualification/b10-wait.log',reason='Corrected DC state-address expectation'),
            dict(kind='test-harness',evidence='output/qualification/b10-wait-r2.log',reason='Corrected stack expectation at a called prompt helper'),
            dict(kind='backup',evidence='output/qualification/pr04-b10-2512-backup',reason='COM4 occupied; no RAM/flash writes'),
            dict(kind='backup',evidence='output/qualification/pr04-b10-2512-backup-r2',reason='Board at REC; stopped before RAM borrowing; selected validated MON B without reset')],
        limitations=['Live serial path was FT245; ACIA electrical operation was not measured',
            'Destructive interruption/refusal cases ran offline; no extra hardware erases',
            'Only the pre-frame wait is indefinite; partial frames still time out',
            'Recovery L requires RLP1 header plus payload; no bare-bin autodetection'],
        evidence={name:r.sha((RUN/name).read_bytes()) for name in names},
        raw_serial_logs={path.name:r.sha(path.read_bytes()) for path in logs},
        audit_script_sha256=r.sha(Path(__file__).read_bytes()))
    board.save(RUN/'test-results.json',report)
    marker.update(last_preservation_report=str(RUN/'test-results.json'),
        last_recovery_scope='b10 captured physical boot; software J3 -> S; idle12/Ctrl-C; delayed binary/readback; full RAM/ZP; BOTH',
        last_owner_reset_confirmation=str(RUN/'owner-reset-confirmation.json'),
        last_software_timeout_boot_report=str(RUN/'state.json'),physical_reset_boot_banner_captured=True,
        software_full_countdown_boot_verified=True,
        completion_receipt=dict(path=str(RUN/'state.json'),sha256=r.sha((RUN/'state.json').read_bytes())))
    board.save(MARKER,marker)
    print('PASS 2512 b10 hardware/boot/J3-S/wait/cancel/binary/preservation; other boards unchanged',flush=True)


if __name__=='__main__':main()
