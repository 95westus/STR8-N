# Current owner-approved scope. Older held receipts retain their historical flags.
REGISTER_BINDINGS = __REGISTER_BINDINGS__
APPROVAL_SHA = '__APPROVAL_SHA__'
EXPECTED_FILES = frozenset(__EXPECTED_FILES__)


def verify_release_scope(root, manifest, summary):
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual == EXPECTED_FILES, 'Unexpected package member, including private/transient data')
    approval = READ(root / 'qualification/release-authorization.json')
    require(SHA(root / 'qualification/release-authorization.json') == APPROVAL_SHA, 'Changed owner decision')
    require(approval['owner_authorized'] and approval['promotion_authorized'], 'Promotion not authorized')
    require(approval['firmware_sha256'] == IMAGE_SHA and approval['distribution_revision'] == 8, 'Wrong authorized image')
    require(approval['release_qualification_scope'] == ['65C02', '65C816 E=1'], 'Wrong approved runtime')
    require(not approval['native_applications'] and not approval['native_debugging'], 'Native mode excluded')
    require(not approval['RTC_drift_in_release_qualification'] and not approval['RTC_drift_is_promotion_gate'], 'RTC drift is outside release qualification')
    for value in (manifest, summary):
        require(value['release_qualification_passed'] and not value['promotion_held'] and value['register_edits_qualified'], 'Incomplete current qualification')
        require(value['RTC_drift_in_release_qualification'] is False and value['RTC_drift_is_promotion_gate'] is False and value['native_debugging'] is False, 'Wrong current scope')
    require(summary['pending'] == [], 'Unresolved current gate')
    verify_register_edits(root)


def verify_register_edits(root):
    import importlib.util
    for name, digest in REGISTER_BINDINGS.items():
        require(SHA(root / name) == digest, 'Changed register evidence: ' + name)
    proof = READ(root / 'qualification/register-edits/report.json')
    require(proof['passed'] and proof['firmware_sha256'] == IMAGE_SHA and proof['actual_hardware_failures'] == 0, 'Wrong register qualification')
    require(not proof['native_debugging'] and not proof['native_applications'], 'Wrong register runtime')
    require(proof['hardware_totals'] == dict(parser=5752, actual_resume=220, unsafe_PC_C_S_N_refusals=132, S_N_then_C=48), 'Incomplete register totals')
    path = root / 'diagnostics/register-edits/cases.py'
    spec = importlib.util.spec_from_file_location('qualified_register_cases', path)
    cases = importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
    rows = cases.parser_cases(True)
    resumes = [dict(v, operation='C') for v in cases.resume_cases(False, hardware=True)] + cases.step_resume_cases()
    for board in ('2604', '2609'):
        b = READ(root / f'qualification/register-edits/{board}/report.json')
        require(b['passed'] and b['checks_passed'] and b['RAM_restored_host_verified'] and b['full_RAM_rereads'] == 2, 'Register RAM restoration failed')
        require(b['all_four_flash_banks_unchanged'] and not any('failure' in k for k in b), 'Register preservation failed')
        require(b['monitor_return']['entry'] == (0xb087 if board == '2604' else 0xa087), 'Original monitor not restored')
        exit_proof = READ(root / f'qualification/register-edits/{board}/process-exit.json')
        require(exit_proof['actual_exit_verified'] and exit_proof['exit_code'] == 0, 'Worker exit unverified')
        for slot in ('A', 'B'):
            unit = b['slots'][slot]
            require(unit['passed'] and (unit['parser_checks'], unit['resume_checks'], unit['unsafe_PC_refusals']) == (1438, 55, 33), 'Wrong per-slot counts')
            parsed = READ(root / f'qualification/register-edits/{board}/{slot}/parser-receipts.json')
            require(len(parsed) == len(rows) == 1438, 'Incomplete parser receipts')
            context = dict(cases.BASELINE)
            for case, receipt in zip(rows, parsed):
                context = cases.expected_after(context, case)
                require(all(receipt[k] == case[k] for k in ('name', 'command', 'accepted', 'category')) and receipt['passed'], 'Wrong parser case')
                require(receipt['actual_context'] == receipt['expected_context'] == context, 'Register isolation failed')
            executed = READ(root / f'qualification/register-edits/{board}/{slot}/resume-receipts.json')
            require(len(executed) == len(resumes) == 55, 'Incomplete resume receipts')
            for case, receipt in zip(resumes, executed):
                require(receipt['passed'] and receipt['name'] == case['name'] and receipt['action'] == case['operation'], 'Wrong resume action')
                require(receipt['actual_trace'] == receipt['expected_trace'] == cases.resume_expected(cases.BASELINE, case).hex(), 'Edited CPU trace differs')
                require(receipt['program_bytes_unchanged'] and receipt['stop_context']['PC'] == cases.CAPTURE + 25, 'Wrong resume stop/code')
                if case['operation'] in ('S', 'N'):
                    expected = cases.expected_after(cases.BASELINE, case);expected['PC'] = cases.CAPTURE
                    if case['field'] == 'PC':expected['SP'] = (expected['SP'] + 2) & 255
                    require(receipt['step_context'] == expected, 'Wrong edited step state')
            if board == '2609':
                for when in ('mode_before_switch', 'mode_before', 'mode_after'):
                    mode = unit[when]
                    require(mode['E_before_probe'] and not mode['probe_enters_native'] and mode['DBR'] == mode['PBR'] == mode['direct_page'] == 0, 'Wrong register E=1 context')
    unsafe = READ(root / 'qualification/register-edits/unsafe-PC-execution-refusals.json')
    require(unsafe['passed'] and unsafe['total_refusals'] == len(unsafe['refusals']) == 132, 'Incomplete unsafe-PC evidence')
    seen = set()
    for item in unsafe['refusals']:
        require(item['passed'] and item['actual_context'] == item['expected_context'], 'Unsafe-PC changed context')
        seen.add((item['board'], item['slot'], item['PC'], item['operation']))
    require(seen == {(b,s,pc,op) for b in ('2604','2609') for s in ('A','B') for pc in cases.UNSAFE_PC_TARGETS for op in ('C','S','N')}, 'Missing unsafe-PC operation')
    for cpu in ('02', '816'):
        model = READ(root / f'qualification/register-edits/register-edits-CPU-{cpu}.json')
        require(model['passed'] and model['exhaustive'] and not model['board_access'] and not model['native_debugging'], 'Wrong register model')
        require((model['parser_cases'], model['actual_resume_cases'], model['unsafe_PC_resume_refusals'], model['edited_register_step_then_resume_cases']) == (2876,2578,66,24), 'Incomplete register CPU matrix')
    audit = READ(root / 'qualification/register-edits/independent-physical-audit.json')
    require(audit['passed'] and audit['both_original_full_RAM_images_verified_twice'] and audit['actual_worker_exit_verified_by_root'], 'Independent preservation audit failed')


def verify_soak(root, summary):
    # These exact historical records remain integrity checked. RTC drift values,
    # durations, offsets and thresholds are not consulted for release acceptance.
    for name, digest in SOAK_BINDINGS.items():
        require(SHA(root / name) == digest, 'Changed historical soak evidence: ' + name)
    closed = READ(root / 'qualification/soak/summary.json')
    require(closed['actual_worker_exit_verified'] and closed['owner_requested_stop'], 'Unclosed workload')
    require(closed['firmware_sha256'] == IMAGE_SHA and closed['package_manifest_sha256'] == KIT_SHA, 'Wrong workload image')
    require(closed['workload_failures'] == closed['restoration_failures'] == 0, 'Unresolved workload failure')
    require(not closed['completed_fixed_duration_claimed'] and closed['periodic_checkpoint_count'] == 0, 'Relabeled owner stop')
    require(not closed['native_debugging'] and not closed['native_applications'], 'Wrong workload runtime')
    for board, cycles in (('2604',61),('2609',60)):
        value = closed['boards'][board]
        require(value['passed_cycles'] == cycles and value['LED_frames'] == 630 * cycles and value['LED_patterns_completed'] == 10 * cycles and value['breakpoint_hits'] == 16 * cycles, 'Wrong workload counts')
        require(value['full_original_RAM_restored'] and value['RAM_verified_after_snapshot'] and value['all_four_bank_flash_unchanged'] and value['settings_unchanged'], 'Workload restoration failed')
    offline = READ(root / 'qualification/soak/offline.json')
    require(offline['passed'] and (offline['newly_executed_offline_tests'], offline['new_LED_CPU_assemblies'], offline['new_LED_CPU_executions']) == (93,16,4), 'Wrong LED qualification')
    require((offline['inherited_full_utility_CPU_model_units'],offline['inherited_isolated_ASM_CPU_executions']) == (4,160), 'Conflated inherited scope')


def verify_documentation(root):
    import sys
    spec_path = root / 'verification/audit_docs.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location('release_documentation_audit', spec_path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result = module.audit(root, list(root.rglob('*.md')))
    require(result['passed'], str(result['errors']))
    return result
