# Current uniform upgrade acceptance. Development and failed receipts stay dated.
UNIFORM_BINDINGS = __UNIFORM_BINDINGS__


def verify_uniform_scope(root, manifest, summary):
    for name,digest in UNIFORM_BINDINGS.items():
        require(SHA(root/name)==digest, 'Changed uniform-upgrade proof or runtime: '+name)
    for value in (manifest,summary):
        require(value['uniform_upgrade_qualified'] is True, 'Uniform upgrade not qualified')
        require(value['RTC_drift_in_release_qualification'] is False and value['RTC_drift_is_promotion_gate'] is False, 'Drift excluded')
        require(value['native_debugging'] is False, 'Native debugging excluded')
    report=READ(root/'qualification/uniform-upgrade/report.json')
    require(report['passed'] and report['target_firmware_sha256']==IMAGE_SHA, 'Wrong uniform target')
    require(report['direct_physical_routes_passed']==4 and report['actual_firmware_failures']==0, 'Incomplete physical routes')
    require(report['new_host_checks']==12 and report['inherited_CPU_model_installer_executions']==32, 'Conflated host/model qualification')
    require(report['private_fixture_CPU_executions']==8, 'Missing exact private fixture rehearsals')
    require(report['host_protocol_qualification_failures']==1 and report['host_protocol_failure_resolved'], 'Hidden or unresolved host failure')
    require(report['both_full_original_RAM_restored'] and report['both_full_EEPROM_SRAM_preserved'] and report['all_workers_actual_exit_verified'], 'Unclosed preservation')
    require(not report['native_debugging'] and not report['native_applications'] and not report['RTC_drift_in_release_qualification'], 'Wrong runtime/scope')
    require(report['intermediate_generation49'] is False and report['current_v1g_no_write_boards']==['2604','2609'], 'Missing direct/current route')
    require(report['RTC_issue_deferred'] is True, 'RTC issue was not qualified here')
    components=READ(root/'firmware/components.json')
    require(components['passed'] and components['firmware_sha256']==IMAGE_SHA and components['model_checks']==12,'Wrong component identity/scope')
    for key in ('B0_included','private_board_bytes_included','firmware_rebuilt','F_only_has_normal_monitor_or_Jn',
                'B3_only_with_opaque_B1_B2_qualified','erase_only_DBG1_uninstall_supported','generic_component_uninstaller_qualified',
                'component_models_hardware_removal_tested','native_debugging','RTC_drift_in_release_qualification'):
        require(components[key] is False,'Unsupported component claim: '+key)
    image=(root/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin').read_bytes()
    require(len(components['files'])==7,'Wrong component inventory')
    for name,info in components['files'].items():
        require('/' not in name and '\\' not in name,'Unsafe component path')
        require((root/'firmware'/name).read_bytes()==image[info['source_offset']:info['source_offset']+info['bytes']], 'Changed exact component slice')
        require(info['full_device_offset']==info['source_offset']+0x8000 and not info['standalone_bank_launcher'] and not info['preserving_update'],'Wrong component map')
    removal=READ(root/'qualification/uniform-upgrade/component-layout-models.json')
    require(removal['passed'] and removal['checks']==12 and removal['monitor_slots_exercised']==['A'] and removal['model_only'],'Conflated component model scope')
    require(not removal['hardware_component_removal_tested'] and not removal['board_access'] and not removal['uninstaller_implemented'],'Invented physical uninstall proof')
    kit=root/'upgrade';uniform=READ(kit/'uniform-manifest.json')
    require(uniform['hardware_qualified'] is True and uniform['host_protocol_revision']==2 and uniform['default_target']=='v1g', 'Wrong released entry')
    require(not uniform['native_debugging'] and not uniform['RTC_drift_in_release_qualification'] and not uniform['intermediate_generation49'], 'Wrong upgrade policy')
    require(uniform['required_source_routes']==['wdcmonv2-65C02','wdcmonv2-65C816','beta4','rc1-gen49','v1e','v1f','v1g'], 'Changed source whitelist')
    for name,info in uniform['files'].items():
        path=(kit/name).resolve()
        require(not Path(name).is_absolute() and path.is_relative_to(kit.resolve()), 'Escaping upgrade member')
        require(path.stat().st_size==info['bytes'] and SHA(path)==info['sha256'], 'Changed upgrade member: '+name)
    acceptance=READ(kit/'current-acceptance.json')
    require(acceptance['passed'] and acceptance['qualified_development_manifest_sha256']==report['qualified_uniform_manifest_sha256'], 'Wrong tested-kit lineage')
    require(acceptance['runtime_bytes_unchanged'] and acceptance['firmware_sha256']==IMAGE_SHA, 'Untested runtime/image changes')
    require(acceptance['report_sha256']==SHA(root/'qualification/uniform-upgrade/report.json'), 'Unbound current acceptance')
    for board,wdc in [('2604','wdcmonv2-65C02'),('2609','wdcmonv2-65C816')]:
        value=READ(root/f'qualification/uniform-upgrade/{board}/board-final-audit.json')
        require(value['passed'] and value['board']==board, 'Missing board upgrade audit')
        require(set(value['routes'])=={wdc,'beta4'} and value['persistent_breakpoint_hits']==64, 'Wrong per-board routes/hits')
        for source,transfers in [(wdc,23),('beta4',22)]:
            route=value['routes'][source]
            require(route['passed'] and route['monitor_slots']==['A','B'] and route['smoke_cases']==8 and route['breakpoint_hits']==32, 'Incomplete monitor smoke')
            require(route['transfers']==transfers and route['original_RAM_rereads']==2 and route['actual_worker_exit_verified'], 'Unverified migration/restore/exit')
        require(value['original_RAM_restored'] and value['full_original_RAM_bytes']==25344 and value['final_RAM_rereads']==2, 'Wrong original RAM restoration')
        require(value['EEPROM_137_bytes_unchanged'] and value['SRAM_131072_bytes_unchanged'] and value['original_settings_unchanged'] and value['original_MON_restored'], 'Changed retained data/settings')
        require(value['original_flash_unchanged_except_exact_planned_wear_journals'] and value['exact_planned_final_wear_counts'] and value['reserved_erase_attempts']==90, 'Unaccounted flash changes/wear')
        require(value['already_current_no_write_verified'] and value['actual_workers_exited'] and value['actual_firmware_failures']==0, 'Current route/exit not qualified')
        require(value['host_protocol_qualification_failures']==(1 if board=='2604' else 0), 'Hidden host history')
        require(not value['native_debugging'] and not value['native_applications'] and not value['RTC_drift_in_release_qualification'], 'Wrong per-board scope')
