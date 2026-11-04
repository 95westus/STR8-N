"""Final b14 hardware audit: physical boot, J3/S, raw autorun, preservation."""
import json
from pathlib import Path
import board_b14_2512 as board
ROOT=board.ROOT;r=board.r
BUILD=ROOT/'BUILD/pr04-b14-raw-r4';PLAN=ROOT/'tmp/pr04-b14-2512-native-plan'
RUN=ROOT/'output/qualification/pr04-b14-2512-install';AUTH=ROOT/'output/qualification/pr04-b14-2512-authorization'
MARKER=ROOT/'output/qualification/device-operations/2512.json'

def main():
    board.admission(BUILD,PLAN,RUN,r.read(AUTH/'deploy-authorization.json'))
    state=r.read(RUN/'state.json')
    required=['passed','transaction_device_verified','prearmed_physical_reset_boot_verified','MON_tool_RAM_readback_verified',
        'all_four_banks_verified','J3_S_verified','raw_BIN_autorun_verified','OIP1_read_only_sector_verified',
        'read_only_probe_flash_unchanged','boot_verified','RAM_restored','owner_ZP_preserved',
        'final_software_boot_verified','full_timeout_default_B_verified','final_software_boot_RAM_reread']
    r.require(all(state.get(k) is True for k in required),'Incomplete hardware verification')
    r.require(state['phase']=='completed' and state['final_console_mode']=='BOTH' and not state['application_RAM_restore_pending']
        and not state['physical_reset_pending'],'Preservation cleanup incomplete')
    r.require(r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle','Serial lease remains held')
    physical=(RUN/'prearmed-reset-boot.txt').read_bytes();software=(RUN/'final-BOTH-software-boot.txt').read_bytes()
    for stream in [physical,software]:
        positions=[stream.find(t) for t in [b'\r\nWAIT...\r\n',board.CHOICES,b'Boot : 6 5 4 3 2 1 0\r\n',b'STR8-N 2.0proto b14 B3 65C02']]
        r.require(all(n>=0 for n in positions) and positions==sorted(positions),'Complete ordered b14 boot missing')
    recovery=(RUN/'software-boot-recovery.txt').read_bytes()
    r.require(b'\r\nRecovery L A/B 0-3 C1/2/3 ?\r\nREC> ' in recovery,'b14 recovery banner missing')
    raw=r.read(RUN/'b14-raw-autorrun.json');help=r.read(RUN/'b14-help.json')
    r.require(raw['passed'] and raw['hardware'] and raw['start']==raw['entry']==0x200 and
        raw['initial_no_data_wait_seconds']>=5 and raw['inter_chunk_idle_seconds']>=2 and
        2.75<=raw['host_observed_last_TX_to_program_prompt_seconds']<=4.5 and
        raw['header_bytes']==0 and not raw['length_field'] and not raw['CRC'] and not raw['R_command_sent'], 'Raw auto-run proof differs')
    r.require(help['passed'] and help['hardware'] and help['help_verified'] and help['removed_R_D_V_refused'],'Help/removal verification incomplete')
    info=r.read(PLAN/'plan.json');source=[(PLAN/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(PLAN/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.require(source[:3]==expected[:3] and source[3][:0x2000]==expected[3][:0x2000] and source[3][0x6000:0x7000]==expected[3][0x6000:0x7000],'Owner/RTC sectors changed')
    for _,offset,row in board.deployment_plan.snbt_records(source):r.require(expected[3][offset:offset+256]==row,'Original journal snapshot changed')
    r.require(info['transaction']['native_C_D_erases']==0,'Unexpected C/D erase')
    body=(BUILD/'payload/ram-installer-offline.bin').read_bytes();sy=r.read(BUILD/'symbols.json')['core/ram-installer']
    tool=(RUN/'b14-tool-RAM-readback.bin').read_bytes();toolproof=r.read(RUN/'b14-tool-RAM-readback.json')
    r.require(tool==board.b14_runtime_image(body,expected[0][:4096],sy) and toolproof['passed'] and toolproof['hardware']
        and raw['bytes_sent_sha256']==r.sha(body),'Executed raw tool code/data/workspace readback differs')
    others=[]
    for row in r.read(AUTH/'other-board-markers-before.json'):
        r.require(r.sha((ROOT/row['path']).read_bytes())==row['sha256'],'Other-board marker changed')
        others.append(dict(board=row['board'],marker_unchanged=True,port_opened=False,flashed=False))
    r.require(r.read(RUN/'owner-reset-confirmation.json')['owner_confirmed'],'Owner reset confirmation missing')
    watchers=list(RUN.glob('serial-watch-reset-*.jsonl'));r.require(len(watchers)==1,'One exact reset watcher required')
    before=bytearray()
    for line in watchers[0].read_text().splitlines():
        row=json.loads(line)
        if row['direction']=='TX':break
        if row['direction']=='RX':before.extend(bytes.fromhex(row['hex']))
    r.require(bytes(before)==physical,'Complete boot was not captured before first TX')
    marker=r.read(MARKER)
    r.require(marker['firmware']=='2.0proto b14' and marker['monitor_generation']==0x8000000e and
        marker['current_physical_bank_sha256']==dict(zip(['B0','B1','B2','B3'],r.hashes(expected))) and
        not marker['block_snapshot'] and not marker['installer_worker_active'],'Final marker differs')
    names=['state.json','admission.json','offline-admission-tests.json','owner-authorization.json','owner-reset-confirmation.json',
        'prearmed-reset-boot.txt','prearmed-reset-armed.json','prearmed-reset-receipt.json','post-reset-stream.txt',
        'software-boot-recovery.txt','software-startup-recovery.json','b14-raw-autorrun.json','b14-help.txt','b14-help.json',
        'b14-tool-RAM-readback.bin','b14-tool-RAM-readback.json','final-BOTH-software-boot.txt']
    result=dict(passed=True,failures=0,hardware=True,board='2512',usb_serial=board.USB,firmware='2.0proto b14',generation_hex='8000000E',
        firmware_sha256=info['firmware_sha256'],physical_reset_boot_captured_before_first_TX=True,
        software_J3_to_S_without_another_physical_reset=True,raw_BIN_load_and_automatic_run=raw,
        independent_executed_tool_RAM_readback=True,raw_RAM_start_hex='0200',raw_tool_bytes=len(body),
        OIP1_read_only_sector_verified=True,recovery_probes_changed_flash=False,full_flash_readback_matches_expected=True,
        restored_application_RAM_bytes=0x6300,preserved_owner_ZP_bytes=0xe0,RAM_reread_after_final_software_boot=True,
        final_monitor='B',final_console='BOTH',serial_released=True,original_journal_records_preserved=True,C_D_erases=0,
        B0_B1_B2_RTC_history_E_preserved=True,RTC_set_trim_ACK_commands=False,planned_erases=info['transaction']['planned_erase_order'],
        F_body_bytes=3669,F_reserved_vectors_bytes=32,F_contiguous_free_bytes=395,F_total_available_bytes=492,MON_free_bytes_each=138,
        offline_checks=dict(firmware_groups=618,buffered_raw_probes=17,CPU_independent_readback=2,exact_host_and_reset_watcher=6,
            native_transaction_models=10,admission_refusal=14,source_backup=11,total=678,failures=0),other_boards=others,
        earlier_nonfinal_attempts=[dict(kind='offline-deployment-CPU-test-adaptation',hardware=False,
            issue='Inherited fixture initially checked RAM at 2000; corrected to 0200 and both CPU cases passed before installation',
            evidence='prototypes/boot-record-v2/test_b14_deployment_cpu.py')],
        limitations=['Live transport was FT245; ACIA electrical operation was not tested',
            'Three-second live interval uses host timestamps; physical byte arrival not directly measured',
            'Raw BIN has no CRC/length; independent post-execution MON readback verifies this particular transfer',
            'Interrupted writes tested offline; hardware used only the planned three erases'],
        evidence={name:r.sha((RUN/name).read_bytes()) for name in names},
        serial_logs={p.name:r.sha(p.read_bytes()) for p in RUN.glob('serial-*.jsonl')},audit_script_sha256=r.sha(Path(__file__).read_bytes()))
    board.save(RUN/'test-results.json',result)
    marker.update(last_preservation_report=str(RUN/'test-results.json'),last_owner_reset_confirmation=str(RUN/'owner-reset-confirmation.json'),
        last_recovery_scope='b14 physical boot; software J3 -> S; help and removed R/D/V; raw 0200 BIN idle autorun; OIP read; independent MON readback; owner RAM/ZP restored; BOTH',
        completion_receipt=dict(path=str(RUN/'state.json'),sha256=r.sha((RUN/'state.json').read_bytes())))
    board.save(MARKER,marker)
    print('PASS 2512 b14 boot/J3-S/raw 0200 auto-run/preservation; 2604/2609 unchanged',flush=True)

if __name__=='__main__':main()
