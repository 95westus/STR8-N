"""Validate the bounded hardware evidence included in the local review kit."""
import hashlib,json

def verify_physical(root,require):
    read=lambda p:json.loads(p.read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    index=read(root/'evidence/physical/index.json')
    require(index['scope']=='2609 verified transfer boundaries only','Physical scope')
    require(index['mid_erase_program_qualified'] is False and index['2604_electrical_qualified'] is False,'Electrical scope broadened')
    for name,ref in index['receipts'].items():
        path=root/ref['file']
        require(sha(path)==ref['sha256'],'Physical receipt binding: '+name)
    for number in (1,2):
        prefix=f'evidence/physical/case-{number}/'
        cp=read(root/(prefix+'checkpoint.json'))
        require(cp['passed'] and cp['board']=='2609' and cp['hardware_power_interruption_and_recovery_passed'] and cp['actual_cut_state_exactly_modeled'],'Physical checkpoint')
        require(all(cp[k] is False for k in ('release_qualified','installation_permitted','publication_permitted')),'Physical permission flags')
        for key,ref in cp['refs'].items():
            require(sha(root/(prefix+key+'.json'))==ref['sha256'],'Physical checkpoint reference')
        hardware=read(root/(prefix+'hardware.json'))
        tx=read(root/(prefix+'recovery.json'))
        capture=read(root/(prefix+'return_capture.json'))
        admission=read(root/(prefix+'admission.json'))
        require(hardware['passed'] and hardware['physical_interruption_recovery_completed'] and hardware['pre_interruption_RAM_restored'] and hardware['application_ram_restored'] and hardware['ports_released'],'Physical hardware completion')
        require(all(c['passed'] for c in hardware['checks']) and len(hardware['checks'])==8,'Physical hardware checks')
        require(sha(root/(prefix+'recovery.json'))==hardware['transaction_report_sha256'] and sha(root/(prefix+'reset.json'))==hardware['reset_confirmation_sha256'],'Physical hardware lineage')
        require(tx['passed'] and tx['transaction_device_verified'] and not tx['clock_set'] and not tx['trim_changed'] and not tx['EEPROM_SRAM_written'],'Physical transaction')
        require(tx['capture_report_sha256']==sha(root/(prefix+'return_capture.json'))==admission['capture_report_sha256'],'Physical capture lineage')
        require(capture['passed'] and capture['application_ram_restored'] and capture['ports_released'] and capture['flash_repeat_verified'] and capture['eeprom_repeat_verified'] and capture['sram_repeat_verified'],'Physical capture completion')
        require(admission['passed'] and admission['actual_interrupted_flash_matches_exact_model'] and admission['full_SRAM_unchanged'] and admission['EEPROM_factory_status_unchanged'],'Physical cut admission')
        require(admission['EEPROM_expected_PF_event']['sequence']==31+number and admission['EEPROM_expected_PF_event']['CRC_valid'] and admission['EEPROM_expected_PF_event']['committed'],'Physical PF evidence')
        for key in ('cpu_mode_before','cpu_mode_after_batch','cpu_mode_after'):
            m=hardware[key]
            require(m['emulation_mode_before_probe'] and m['dbr']==m['pbr']==m['direct_page']==0 and m['entry_decimal_clear'] and m['entry_irq_disabled'] and not m['probe_enters_native_mode'],'Physical emulation contract')
        for key,event in (('off','controlled_power_off_user_confirmed'),('on','controlled_power_on_user_confirmed')):
            require(read(root/(prefix+key+'.json'))['event']==event,'Physical owner power event')
        require(read(root/(prefix+'reset.json'))['user_confirmed_physical_reset'],'Physical owner RESET')
        require(cp['pre_interruption_RAM_restored'] and cp['SRAM_unchanged'],'Physical preservation')
        if number==2:
            require(cp['A_payload_reerased_during_recovery'] is False and tx['transfers_completed']==2,'Wear-aware A recovery')
    original=read(root/'evidence/physical/original-restoration.json')
    require(original['passed'] and original['original_payload_restoration_hardware_passed'] and original['original_payload_bytes_equal_outside_wear_journals'] and original['original_configuration_restored'],'Original restoration checkpoint')
    for phase,refs in original['phases'].items():
        for name,key in (('transaction','transaction_sha256'),('hardware','hardware_report_sha256')):
            p=root/f'evidence/physical/{phase}-{name}.json'
            require(sha(p)==refs[key] and read(p)['passed'],'Original restoration lineage')
    return dict(bounded_hardware_cases=2,physical_board='2609',mid_erase_program_qualified=False,board_access=False)
