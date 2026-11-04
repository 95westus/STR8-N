"""Close the approved CLOCK/native profile install from existing evidence.

No board port, firmware build, journal writer or campaign baseline mutation.
"""
import hashlib
import json
import re
from pathlib import Path
import install_clock_2609_reviewed as i

t = i.t


def run():
    folder = i.CASE
    r = json.loads((folder / 'report.json').read_text())
    plan = i.inputs()
    assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['COM8_released']
    assert r['image_erase_requests'] == len(r['completed']) == 11
    old3 = (folder / 'B3-before.bin').read_bytes()
    new3 = (folder / 'B3-after.bin').read_bytes()
    assert old3[-4096:] == new3[-4096:]
    assert t.sha(new3[-4096:]) == plan['F_sha256']
    assert old3[0x2000:0x4000] == new3[0x2000:0x4000]
    assert old3[0x5000:0x5900] == new3[0x5000:0x5900]
    clock = (folder / 'B2-after.bin').read_bytes()[0x3000:0x6000]
    reference = (t.REPO / 'monitors/candidates/native-g00000001-r16/CLOCK-g00000001-flash.bin').read_bytes()
    assert clock == reference
    state_path = t.ROOT / 'output/qualification/rtc-drift-3hour-campaign.json'
    state = json.loads(state_path.read_text())
    status = next(p.read_bytes() for p in folder.glob('*command.txt')
                  if p.read_bytes().startswith(b'STATUS\r') and b'RTC registers (raw):' in p.read_bytes())
    raw = bytes.fromhex(re.search(rb'RTC registers \(raw\):((?: [0-9A-F]{2}){9})',status)[1].decode())
    trim = int(re.search(rb'Trim (-?\d+) steps',status)[1])
    baseline = state['baselines']['2609']
    assert raw[7] == baseline['control'] and trim == baseline['trim']
    # Payload transfers contain command strings as data. Restrict this audit
    # to separate complete textual confirmation records, not substring grep.
    records = [json.loads(line) for line in (folder / 'serial.jsonl').read_text().splitlines()]
    tx = [bytes.fromhex(x['hex']) for x in records if x.get('direction') == 'TX']
    assert b'YES\r' not in tx and b'YES\r\n' not in tx
    # Audit the actual CLOCK command phase. Short payload fragments can be
    # printable help text beginning with ACK/CLEAR; they are not commands.
    start = tx.index(b'R CLOCK\r') + 1
    end = tx.index(b'Q\r', start) + 1
    assert tx[start:end] == [b'HELP\r',b'TIME\r',b'STATUS\r',b'HISTORY\r',b'STATS\r',b'EUI\r',
        b'SET 2026-02-30 12:00:00\r',b'SET 2028-02-29 12:34:56\r',b'NO\r',
        b'OFFSET +01:00\r',b'NO\r',b'TRIM 1\r',b'NO\r',b'VERSION\r',b'Q\r']
    marker_path = t.ROOT / 'output/qualification/device-operations/2609.json'
    marker = json.loads(marker_path.read_text())
    assert marker['current_physical_bank_sha256']['B2'] == r['final_B2_sha256']
    assert marker['current_physical_bank_sha256']['B3'] == r['final_B3_sha256']
    assert marker['final_prompt'] == 'REC>' and not marker['application_RAM_restore_pending']
    assert marker['status_installation_complete'] and marker['clock_native_installation_complete']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    for key,value in state['board_admission']['2609'].items(): assert marker.get(key) == value
    # Keep the existing gC reader admission and immutable baseline/cadence.
    # Updating utility image hashes does not change its MON/F read path.
    marker.update(current_owner_RAM_sha256=r['owner_RAM_sha256'],
        current_owner_ZP_sha256=r['owner_ZP_sha256'],
        MON_A_generation='0000000C',MON_B_generation='0000000C',
        current_sampling_profile='MON-UI1-GC-NATIVE-TIME',
        clock_previous_CD_history_archive=str(folder / 'B3-before.bin'),
        clock_previous_CD_records_archived_on_host=25,
        clock_original_C_records_replaced_on_chip=16,
        last_CLOCK_native_closeout=str(folder / 'final-receipt.json'))
    t.save(marker_path,marker)
    receipt = dict(passed=True,board='2609',native_profile='CLOCK1.10/FLASHg1r16/WB2gB/SP1g2/servicesg9',
        monitor_generation='0000000C',CLOCK_flash_sha256=t.sha(clock),
        image_erases=11,native_C_erases=1,total_erases=12,D_erases=0,F_writes=0,
        F_sha256=plan['F_sha256'],power_cuts=0,firmware_builds=0,
        sequence=1051,valid_records=21,default='S',enabled_mask=0,entries=['8000']*4,
        all_25_old_records_archived=True,old_C_records_archived_and_replaced_on_chip=16,
        old_D_records_retained_exact=9,counts=r['journal']['counts'],
        owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_sha256=r['RAM_sha256'],
        owner_ZP_sha256=r['ZP_sha256'],COM8_released=True,final_prompt='REC>',
        RTC_control=raw[7],RTC_trim=trim,RTC_PF_latched=bool(raw[3]&0x10),
        RTC_SET=0,RTC_trim_writes=0,PF_ACK=0,RTC_history_writes=0,SRAM_data_writes=0,
        RTC_sampler='Existing admitted MON-UI1-GC-NATIVE-TIME unchanged',
        RTC_baseline_sha256=hashlib.sha256(json.dumps(baseline,sort_keys=True).encode()).hexdigest(),
        RTC_cadence_hours=state['interval_hours'],RTC_campaign_state_changed=False,
        owner_banks_B0_B1='Outside every programming target; no repeated whole-board capture',
        excluded_boards_untouched=['2205','2512','2604'],published_download_changes=0,
        metadata='Empty compatible pocket; no copied identity/policy. Unnamed board, UTC, battery age unset.',
        qualification=r['checks'],positive_CLOCK_setting_writes='Not included; setting confirmations cancelled')
    t.save(folder / 'final-receipt.json',receipt)
    print('PASS 2609 native CLOCK/profile closeout; F preserved; RAM restored; COM8 released',flush=True)
    print('CLOCK SHA256 '+receipt['CLOCK_flash_sha256'],flush=True)
    print('RTC control/trim preserved: '+str(raw[7])+'/'+str(trim)+'; PF latch retained',flush=True)


if __name__ == '__main__': run()
