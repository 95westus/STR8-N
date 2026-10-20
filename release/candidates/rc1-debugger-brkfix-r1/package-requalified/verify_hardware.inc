
HARDWARE_REPORT_SHA='5d3c2832355725bf9558d3c5415efd0eeb6679d8230f81a9a8762e629ae19730'
HARDWARE_SOURCE_INDEX_SHA='REPLACE_HARDWARE_INDEX_SHA'

def verify_hardware(root,summary):
    index_path=root/'qualification/hardware/source-evidence.json';index=READ(index_path)
    require(SHA(index_path)==HARDWARE_SOURCE_INDEX_SHA and index['source_report_sha256']==HARDWARE_REPORT_SHA,'Changed hardware evidence binding')
    for name,info in index['files'].items():
        p=(root/name).resolve();require(p.is_relative_to(root) and not Path(name).is_absolute(),'Unsafe hardware path')
        require(p.stat().st_size==info['bytes'] and SHA(p)==info['sha256'],'Changed hardware receipt: '+name)
    hw=READ(root/'qualification/hardware/summary.json')
    require(hw['passed'] and hw['firmware_sha256']==IMAGE_SHA and hw['package_manifest_sha256']==KIT_SHA and hw['source_report_sha256']==HARDWARE_REPORT_SHA,'Wrong hardware identity')
    require(hw['promotion_held'] and not hw['native_debugging'] and not hw['native_applications_tested'] and not hw['hardware_test_failures'],'Wrong hardware scope')
    require((hw['registration_scenario_executions'],hw['BRK82_84_hardware_edge_checks'],hw['breakpoint_hits'],hw['verified_transfers'])==(144,168,128,88),'Wrong hardware totals')
    images={SHA(p) for p in (root/'diagnostics/registrations').glob('*.s19')}|{SHA(p) for p in (root/'diagnostics/brk82-84').glob('*.s19')}
    for board,cpu in (('2604','65C02'),('2609','65C816 E=1')):
        b=hw['boards'][board]
        require(b['passed'] and b['CPU']==cpu and b['original_RAM_bytes']==25344,'Wrong board/RAM scope')
        require((b['registration_cases'],b['BRK82_84_edge_cases'],b['breakpoint_hits'],b['verified_transfers'])==(72,84,64,44),'Wrong per-board totals')
        for phase in ('initial','final'):
            r=READ(root/f'qualification/hardware/{board}/{phase}.json')
            require(r['passed'] and r['board']==board and r['RAM_restored_host_verified'] and set(r['slots'])=={'A','B'},'Incomplete both-slot hardware pass')
            require(not r['native_debugging'] and not r['native_applications_tested'] and r['promotion_held'],'Wrong board runtime')
            require(r['final_flash']['all_firmware_and_other_flash_unchanged'] and r['final_flash']['original_config_and_preference_restored'] and r['final_flash']['erase_counts_unchanged'],'Failed final flash/settings guard')
            require(r['final_RTC']['controls_trim_oscillator_backup_preserved'],'RTC controls/trim changed')
            if board=='2609':require(r['final_mode']['E_before_probe'] and not r['final_mode']['probe_enters_native'],'Wrong final 816 mode')
            for slot,unit in r['slots'].items():
                reg=unit['registrations'];edge=unit['edge_checks'];smoke=unit['debugger_smoke'];apps=unit['apps']
                require(unit['passed'] and reg['passed'] and reg['cases']==18 and len(reg['completed'])==18 and all(x['passed'] and x['image_sha256'] in images for x in reg['completed']),'Incomplete hardware registrations')
                require(edge['passed'] and edge['cases']==21 and edge['actual_application_RAM_limit']==0x64FF and edge['application_RAM_ownership_unchanged'] and len(edge['results'])==21 and all(x['passed'] and x['image_sha256'] in images for x in edge['results']),'Incomplete hardware BRK82/84 coverage')
                require(smoke['passed'] and smoke['breakpoint_hits_verified']==16 and smoke['BRK_C_S_N_eight_persistent_breakpoints'],'Incomplete debugger/breakpoint coverage')
                require(apps['passed'] and apps['MAINT_SRAM_WORK_EDU_BATCH'] and apps['ASM_05_assembly_S19_RAM_execution'] and apps['UCHESS_launch_copyright_HOLD'] and apps['CLOCK_111']['controls_trim_oscillator_backup_preserved'],'Incomplete app regression')
                if board=='2609':
                    for when in ('mode_before','mode_after'):
                        mode=unit[when];require(mode['E_before_probe'] and not mode['probe_enters_native'] and mode['DBR']==mode['PBR']==mode['direct_page']==0,'Wrong E=1 hardware context')
        for phase in ('v1f-rollback','v1g-install','v1g-rollback','v1g-reinstall'):
            folder=root/f'qualification/hardware/{board}/transactions'
            tx=READ(folder/(phase+'-execute.json'));flash=READ(folder/(phase+'-flash.json'));ram=READ(folder/(phase+'-RAM.json'));boot=READ(folder/(phase+'-boot.json'))
            pin='87f5b610ed309f0be7ab8bd63e7f630bbc9c2e9885ecd048022227502934bb7d' if phase=='v1f-rollback' else KIT_SHA
            require(tx['passed'] and tx['board']==board and tx['transaction_device_verified'] and tx['transfers_sent']==tx['transfers_completed']==11 and tx['package_manifest_sha256']==pin,'Wrong transaction receipt')
            require(flash['passed'] and flash['all_four_flash_banks_verified'] and ram['passed'] and ram['RAM_restoration_host_verified'],'Failed transaction flash/RAM check')
            require(boot['passed'] and boot['board']==board and boot['operation']==phase and boot['fresh_boot_observed'] and not boot['watcher_issued_reset'],'Missing actual boot observation')
            generation='00000031' if phase.endswith('rollback') else '00000032'
            require(all(f'MONITOR {slot} gen {generation} VALID' in boot['version'] for slot in ('A','B')),'Wrong boot generation')
    pending=READ(root/'qualification/soak/pending.json')
    require(pending['status']=='running-not-qualified' and pending['authorized_hours']==3 and pending['firmware_sha256']==IMAGE_SHA and pending['package_manifest_sha256']==KIT_SHA,'Wrong live soak snapshot')
    require(pending['snapshot_only'] and not pending['soak_qualified'] and pending['final_drift_snapshot_passed'] is None and not pending['parent_results_reused'],'Premature soak/drift claim')
    require(summary['hardware_requalification_passed'] is True and summary['three_hour_soak_passed'] is None and summary['six_hour_soak_passed'] is None and summary['final_drift_snapshot_passed'] is None,'Wrong qualification state')
    require((summary['hardware_registration_scenarios'],summary['hardware_BRK82_84_edge_checks'],summary['hardware_breakpoint_hits'],summary['device_verified_hardware_transfers'])==(144,168,128,88),'Wrong qualification totals')
    require(not (root/'qualification/hardware/pending.json').exists(),'Stale pending hardware state')
    return hw
