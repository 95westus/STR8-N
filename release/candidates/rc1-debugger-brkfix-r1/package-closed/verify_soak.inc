# Exact immutable closeout evidence bindings survive a resealed inventory.
SOAK_BINDINGS = __SOAK_BINDINGS__
BASELINE_SHA = '5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e'
RECOVERY_SHA = 'bf2d178b28bb2a0a0cf7831215f5d70c8a063d0db6dc78fd8d73978008dd1607'
RECOVERY_SEGMENT = '2609-post-RTC-recovery-2026-10-18-r1'


def verify_soak(root, summary):
    manifest = READ(root / 'package-manifest.json')
    require(manifest['soak_scope'] == 'owner-stopped-R6-ten-pattern-continuation' and manifest['final_drift_passed'] is True,
            'Wrong manifest closed-soak scope')
    for name, digest in SOAK_BINDINGS.items():
        require(SHA(root / name) == digest, 'Changed closed-soak evidence: ' + name)
    require(not (root / 'qualification/soak/pending.json').exists(), 'Stale pending soak state')
    require(summary['hardware_requalification_passed'] is True and summary['owner_stopped_continuation_passed'] is True,
            'Wrong closed qualification state')
    require(summary['three_hour_soak_passed'] is None and summary['six_hour_soak_passed'] is None,
            'Owner STOP cannot become a fixed-duration pass')
    require(summary['soak_state'] == 'owner-stopped-passed' and summary['final_drift_snapshot_passed'] is True
            and summary['pending'] == ['explicit-promotion-decision'], 'Wrong end-of-soak state')
    require((summary['hardware_registration_scenarios'], summary['hardware_BRK82_84_edge_checks'],
             summary['hardware_breakpoint_hits'], summary['device_verified_hardware_transfers']) == (144, 168, 128, 88),
            'Wrong original hardware qualification totals')
    require(not (root / 'qualification/hardware/pending.json').exists(), 'Stale pending hardware state')
    closed = READ(root / 'qualification/soak/summary.json')
    require(closed['passed'] and closed['owner_stopped_continuation_passed'] and closed['actual_worker_exit_verified']
            and closed['owner_requested_stop'] and not closed['completed_fixed_duration_claimed'], 'Missing clean owner STOP')
    require(closed['firmware_sha256'] == IMAGE_SHA and closed['package_manifest_sha256'] == KIT_SHA
            and closed['candidate_build'] == BUILD, 'Wrong closed-soak firmware')
    require(closed['promotion_held'] and not closed['release_qualification_passed'] and not closed['native_debugging']
            and not closed['native_applications'] and not closed['inherited_results_substitute_for_current_run'],
            'Wrong closed-soak scope')
    require(closed['workload_failures'] == closed['restoration_failures'] == 0, 'Unresolved soak failure')
    require(closed['LED_frames_per_unit'] == 630 and closed['LED_pattern_count'] == 10
            and len(set(closed['LED_pattern_names'])) == 10, 'Incomplete ten-pattern scope')
    require(closed['frozen_pins_verified'] == {'source': 72, 'external': 41, 'workload': 95}, 'Incomplete frozen-input audit')
    duration = closed['duration']
    require(duration['monitored_seconds'] > 0 and duration['active_workload_seconds'] > 0
            and duration['periodic_checkpoint_seconds'] >= 0
            and abs(duration['active_workload_seconds'] + duration['periodic_checkpoint_seconds'] - duration['monitored_seconds']) < .1,
            'Invalid actual duration')
    timing = closed['worker_timing']
    require(timing['monitored_duration_excludes_final_checkpoint'] and timing['final_checkpoint_seconds'] > 0
            and timing['total_wall_seconds'] > duration['monitored_seconds']
            and abs(timing['total_wall_seconds'] - duration['monitored_seconds'] - timing['final_checkpoint_seconds']) < 1,
            'Final restoration time was conflated with workload time')
    require(closed['periodic_checkpoint_count'] == 0 and closed['final_snapshot_is_periodic_checkpoint'] is False,
            'Final snapshot is not a periodic checkpoint')
    evidence = READ(root / 'qualification/soak/source-evidence.json')
    require(not evidence['private_backups_or_serial_logs_exported'] and not evidence['board_access_during_packaging'], 'Private board capture exported')
    for board, cycles in (('2604', 61), ('2609', 60)):
        value = closed['boards'][board]
        require(value['runtime'] == ('65C02' if board == '2604' else '65C816 E=1')
                and not value['native_debugging'] and not value['native_applications'], 'Wrong per-board soak runtime')
        require(value['passed_cycles'] == cycles and value['LED_frames'] == 630 * cycles
                and value['LED_patterns_completed'] == 10 * cycles and value['breakpoint_hits'] == 16 * cycles,
                'Incorrect successful unit counts')
        require(all(value[key] for key in ('all_40_ASM_sources_covered', 'full_original_RAM_restored',
                'RAM_verified_after_snapshot', 'all_four_bank_flash_unchanged', 'settings_unchanged'))
                and len(value['flash_sha256']) == 4, 'Incomplete original board restoration')
        require(len(evidence['current_successful_cycle_receipts'][board]) == cycles, 'Missing successful unit source bindings')
    drift = closed['final_drift']
    require(drift['passed'] and drift['baseline_preserved'] and drift['baseline_sha256'] == BASELINE_SHA
            and drift['recovery_anchor_sha256'] == RECOVERY_SHA and drift['clocks_trim_flash_unchanged']
            and drift['both_RAMs_preserved'] and drift['rates_compare_recorded_anchors_not_checkpoint_interval'],
            'Incomplete preserving final drift')
    require({b['board'] for b in drift['boards']} == {'2604', '2609'}, 'Both final drift results required')
    for value in drift['boards']:
        require(value['elapsed_seconds'] > duration['monitored_seconds'] and len(value['drift_ppm_interval']) == 2
                and value['drift_ppm_interval'][0] <= value['drift_ppm_interval'][1]
                and len(value['drift_seconds_per_day_interval']) == 2, 'Wrong long-baseline drift interval')
        if value['board'] == '2609':
            require(value['measurement_segment'] == RECOVERY_SEGMENT and value['original_baseline_replaced'] is False,
                    '2609 post-recovery segment replaced')
    checkpoints = READ(root / 'qualification/soak/drift-checkpoints.json')
    current = [c for c in checkpoints if c['source_run'] == closed['source_run']]
    require(len(current) == 1 and current[0]['label'] == 'final' and current[0]['passed']
            and current[0]['both_full_original_RAMs_restored'] and current[0]['both_full_original_RAMs_reread_after_snapshot']
            and current[0]['drift'] == drift, 'Missing final restoration/snapshot evidence')
    history = READ(root / 'qualification/soak/history.json')
    require(len(history) >= 7 and history[0]['source_run'] == closed['source_run'] and history[0]['passed']
            and sum(bool(h['qualifies_current_ten_pattern_scope']) for h in history) == 1,
            'Prior scopes substituted for the final candidate')
    fixed = [h for h in history if h['authorized_hours'] == 3]
    require(len(fixed) == 1 and fixed[0]['completed_fixed_duration'] is not True
            and fixed[0]['qualification_limit'] == 'owner-stopped before fixed duration; never a three-hour pass',
            'Partial fixed run was relabeled')
    offline = READ(root / 'qualification/soak/offline.json')
    require(offline['passed'] and offline['newly_executed_offline_tests'] == 93
            and offline['new_LED_CPU_assemblies'] == 16 and offline['new_LED_CPU_executions'] == 4
            and offline['inherited_full_utility_CPU_model_units'] == 4
            and offline['inherited_isolated_ASM_CPU_executions'] == 160
            and offline['review_only_join_checks_not_added_to_qualification_counts'], 'Wrong new/inherited offline scope')
    require(sum(v['onboard_assemblies'] for v in offline['CPU_models'].values()) == 16
            and sum(v['full_LED_executions'] for v in offline['CPU_models'].values()) == 4
            and all(v['passed'] and v['frames_per_execution'] == 630 and v['patterns_per_execution'] == 10
                    for v in offline['CPU_models'].values()), 'Incomplete actual CPU matrix')

