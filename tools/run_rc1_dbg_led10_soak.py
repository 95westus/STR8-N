"""Owner-stopped rc1/ASM/DBG1 continuation with ten bounded LED ASM patterns.

Frozen beside broader_runner.py, continuing_runner.py and base_runner.py.
Only the LED PIA data register is additionally writable; restore its entry
value before BRK. No firmware, clock, trim, preference or storage writes.
"""
import argparse
import ctypes
import hashlib
import importlib
import math
from pathlib import Path
import time
import traceback
import broader_runner as broader
from broader_runner import *


LED_PATTERN_SPECS = (
    ('wigwag', 8), ('gray-code', 256), ('binary-counter', 256),
    ('walking-one', 16), ('walking-zero', 16), ('bouncing-dot', 14),
    ('checkerboard', 8), ('fill-drain', 16),
    ('expanding-contracting-pairs', 8), ('lfsr-sparkle', 32),
)
LED_PATTERN_NAMES = tuple(name for name, frames in LED_PATTERN_SPECS)
LED_PATTERN_COUNT = 10
LED_FRAME_COUNT = 630
LED_SEEDS = (0x12, 0x25, 0x38, 0x4B)


def validate_led_receipt(proof):
    """Require all ten complete patterns and restoration before counting a unit."""
    assert proof['passed'] and proof['frames'] == LED_FRAME_COUNT
    assert proof['pattern_count'] == LED_PATTERN_COUNT
    assert tuple(proof['pattern_names']) == LED_PATTERN_NAMES
    assert [(row['name'], row['frames']) for row in proof['patterns']] == list(LED_PATTERN_SPECS)
    assert sum(row['frames'] for row in proof['patterns']) == LED_FRAME_COUNT
    assert proof['original_led_restored_before_BRK']
    assert proof['entry_led'] == proof['restored_led_before_BRK'] == 0
    assert proof['CRA_before'] == proof['CRA_after'] == 0x34
    assert proof['actual_pin_readback_matches_every_frame']
    assert proof['exact_model_image_verified_before_execution']
    assert proof['HOLD_cleanup'] == dict(lifecycle_hex='00000000', registry_valid=False)


def first_drift_after(start_unix, epoch_unix, interval=14400):
    """Keep the campaign's original four-hour wall-clock phase after transition."""
    assert math.isfinite(start_unix) and math.isfinite(epoch_unix)
    assert interval == 14400 and start_unix >= epoch_unix
    return epoch_unix + interval * (math.floor((start_unix - epoch_unix) / interval) + 1)


def validate_led_authorization(auth):
    assert auth['owner_authorized'] and auth['LED_patterns']
    assert auth['run_until_owner_stop'] and auth['hours'] is None
    assert auth['drift_interval_seconds'] == 14400
    assert auth['LED_allowed_data_address'] == 0x7FA0
    assert auth['LED_CRA_writes'] is False and auth['LED_DDRA_writes'] is False
    assert auth['LED_restore_entry_value'] is True and auth['LED_frames_per_unit'] == LED_FRAME_COUNT
    assert auth['LED_pattern_count'] == LED_PATTERN_COUNT
    assert auth['LED_pattern_names'] == list(LED_PATTERN_NAMES)
    assert auth['promotion_held'] and not auth['native_applications'] and not auth['native_debugging']
    assert not any(auth[k] for k in ('flash_writes','clock_set','trim_changed','settings_changed'))
    assert math.isfinite(auth['campaign_drift_epoch_unix'])


class Runner(broader.Runner):
    def __init__(self, workspace, run):
        super().__init__(workspace, run)
        validate_led_authorization(self.auth)
        assert base.SHA(self.run/'broader_runner.py') == self.auth['broader_runner_sha256']
        assert base.SHA(self.run/'led_units.py') == self.auth['LED_module_sha256']
        assert base.SHA(self.run/'LED-cases.json') == self.auth['LED_cases_sha256']
        self.led = importlib.import_module('led_units')
        assert self.led.FRAME_COUNT == LED_FRAME_COUNT and tuple(self.led.SEEDS) == LED_SEEDS
        assert [(row['name'], row['frames']) for row in self.led.PATTERNS] == list(LED_PATTERN_SPECS)
        self.led_cases = base.READ(self.run/'LED-cases.json')
        assert len(self.led_cases) == 4
        assert [v['seed'] for v in self.led_cases] == list(self.led.SEEDS)
        for case in self.led_cases:
            self.led.validate_case(case)
            assert case['pattern_count'] == LED_PATTERN_COUNT and tuple(case['pattern_names']) == LED_PATTERN_NAMES
        self.state.update(runner_sha256=base.SHA(__file__),
            broader_runner_sha256=base.SHA(self.run/'broader_runner.py'),
            LED_module_sha256=base.SHA(self.run/'led_units.py'),
            workload='rc1 base/utilities, varied ASM, ten LED patterns, DBG1 and all built-in BRK each unit',
            ASM_sources=44, varied_ASM_sources=40, LED_ASM_sources=4,
            LED_patterns=True, LED_pattern_count=LED_PATTERN_COUNT, LED_pattern_names=list(LED_PATTERN_NAMES),
            LED_frames_per_unit=LED_FRAME_COUNT,
            campaign_drift_epoch_unix=self.auth['campaign_drift_epoch_unix'])
        for value in self.state['boards'].values():
            value.update(LED_pattern_units=0, LED_frames=0, LED_variant_indices=[], LED_patterns_completed=0)

    def cycle(self, board):
        self.transport.plans.package(self.kit)
        continuing.verify_workload(self.run, self.auth)
        n = self.state['boards'][board]['passed_cycles']
        index = continuing.case_index(board, n, len(self.cases))
        case = self.cases[index]
        out = self.run/board/f'{n:06d}'
        out.mkdir(parents=True)
        self.status('running', current_board=board, current_unit='rc1/base/utilities/LED10/ASM/DBG1/built-in BRK')
        self.marker(board, 'rc1-LED10-soak-running', application_RAM_restore_pending=True)
        self.publish(self.run/f'{board}-restore-needed.json', dict(needed=True, archive=str(self.run/f'{board}-before'),
            RAM_sha256=hashlib.sha256(self.original[board]).hexdigest()))
        proof = dict(passed=False, board=board, slot=base.BOARDS[board][2], started_utc=base.NOW(),
            native_debugging=False, utility_mutations_permitted=False)
        self.publish(out/'report.json', proof)
        with self.connection(board, out/'serial.jsonl') as link:
            self.establish(link)
            proof['version'] = self.guard(link, board)
            proof['mode_before'] = self.mode(link, board)
            proof['base_utilities'], text = self.units.base_and_utilities(link, self.transport, n)
            (out/'base-utilities.txt').write_bytes(text)
            reference = proof['base_utilities']['base_status_sha256']
            assert set(reference) == {'C','P','W'}
            prior = self.state['boards'][board]['base_status_reference']
            assert prior is None or prior == reference, 'Configuration/preference/wear changed'
            proof['targeted'] = base.targeted_unit(link, self.transport, self.run, n, *self.case_modules)
            proof['builtins'], text = self.units.builtins_unit(link, self.transport, self.cases, self.run/'builtin-images', n)
            (out/'builtin-BRK.txt').write_bytes(text)
            assert proof['builtins']['passed'] and proof['builtins']['services'] == list(range(0x80,0x85))
            proof['LED_patterns'], text = self.led.led_unit(link, self.transport, self.led_cases[n % 4])
            (out/'LED-patterns.txt').write_bytes(text)
            validate_led_receipt(proof['LED_patterns'])
            proof['ASM'], text = variants.asm_unit(link, self.transport, case)
            (out/'asm.txt').write_bytes(text)
            proof['debugger'] = base.debugger_unit(link, self.transport, self.kit)
            proof['mode_after'] = self.mode(link, board)
            self.guard(link, board)
            proof['RTC'], text = self.clock(link, board)
            (out/'clock.txt').write_bytes(text)
            if time.monotonic()-self.last_flash[board] >= 3600:
                proof['flash'] = self.flash(link, board)
        assert all(proof[name]['passed'] for name in ('base_utilities', 'targeted', 'builtins', 'LED_patterns', 'ASM', 'debugger', 'RTC'))
        assert proof['debugger']['breakpoint_hits'] == 16
        proof.update(passed=True, finished_utc=base.NOW())
        self.publish(out/'report.json', proof)
        entry = self.state['boards'][board]
        entry.update(passed_cycles=n+1, breakpoint_hits=16*(n+1), registration_cases_passed=n+1,
            BRK82_84_cases_passed=n+1, latest_receipt=str(out/'report.json'), latest_pass_unix=time.time(),
            ASM_variants_passed=n+1, ASM_variant_indices=sorted(set(entry['ASM_variant_indices']+[index])),
            fixed_BRK_services_passed=list(range(0x80,0x85)), base_command_units=n+1, utility_units=n+1,
            builtin_suite_units=n+1, base_status_reference=reference, LED_pattern_units=n+1,
            LED_frames=LED_FRAME_COUNT*(n+1), LED_variant_indices=sorted(set(entry['LED_variant_indices']+[n % 4])),
            LED_patterns_completed=LED_PATTERN_COUNT*(n+1))
        self.status('running', current_board=None, current_unit=None)
        print('PASS', board, n+1, 'rc1/base/utilities/LED10x630/ASM/DBG1; all BRK80-84; 16 breakpoint hits', flush=True)

    def execute(self):
        self.status('validating-fresh-backups')
        error = None
        started = None
        pause_seconds = 0
        final = None
        assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            for board in base.BOARDS:
                cap = self.run/f'{board}-before'
                identity, banks = self.transport.plans.capture(cap)
                assert identity['board'] == board and identity['usb_serial'] == base.BOARDS[board][1]
                assert base.READ(cap/'report.json')['passed']
                self.original[board] = (cap/'application-ram.bin').read_bytes()
                self.flash_hashes[board] = [hashlib.sha256(b).hexdigest() for b in banks]
                self.last_flash[board] = time.monotonic()
                for sector in base.READ(self.kit/'board-test-manifest.json')['sectors']:
                    offset = sector['address'] - 0x8000
                    assert banks[sector['bank']][offset:offset+4096] == (self.kit/sector['target']).read_bytes()
            started = time.monotonic()
            started_unix = time.time()
            first_unix = first_drift_after(started_unix, self.auth['campaign_drift_epoch_unix'])
            first_monotonic = started + first_unix - started_unix
            number = 1
            self.status('running', started_utc=base.NOW(), started_unix=started_unix, deadline_unix=None,
                first_drift_unix=first_unix, next_drift_unix=first_unix, monitored_seconds=0)
            self.campaign(True)
            while not (self.run/'STOP').exists():
                due = first_monotonic + 14400*(number-1)
                if time.monotonic() >= due:
                    pause_start = time.monotonic()
                    proof = self.checkpoint(f'periodic-{number:06d}')
                    pause_seconds += time.monotonic()-pause_start
                    if not proof['passed']:
                        raise RuntimeError('Four-hour restoration/drift checkpoint failed; workload stopped')
                    number += 1
                    self.status('running', current_checkpoint=None, next_drift_unix=first_unix+14400*(number-1))
                    self.campaign(True)
                    continue
                for board in base.BOARDS:
                    if (self.run/'STOP').exists() or time.monotonic() >= due:
                        break
                    assert base.SHA(self.auth['baseline_index']) == self.auth['baseline_index_sha256']
                    assert base.SHA(self.kit/'board-test-manifest.json') == base.KIT_SHA
                    self.cycle(board)
                    self.state['monitored_seconds'] = time.monotonic()-started
                for _ in range(5):
                    if (self.run/'STOP').exists() or time.monotonic() >= due:
                        break
                    time.sleep(1)
            self.state['owner_stop_observed'] = True
        except BaseException:
            error = traceback.format_exc()
            self.state['workload_failure'] = error
            print(error, flush=True)
        finally:
            self.state['monitored_seconds'] = 0 if started is None else time.monotonic()-started
            self.state['active_workload_seconds'] = max(0, self.state['monitored_seconds']-pause_seconds)
            self.state['periodic_checkpoint_seconds'] = pause_seconds
            try:
                final = self.checkpoint('final', collect=not bool(error and self.state['checkpoints'] and not self.state['checkpoints'][-1]['passed']))
            except BaseException:
                self.state['final_checkpoint_failure'] = traceback.format_exc()
                self.state['emergency_restoration'] = base.restore_all(self.original, self.restore)
            passed = not error and bool(self.state.get('owner_stop_observed')) and final is not None and final['passed']
            self.status('stopped-cleanly' if passed else 'stopped-needs-review', passed=passed,
                final=final, finished_utc=base.NOW(), next_drift_unix=None)
            self.publish(self.run/'report.json', self.state)
            self.campaign(False)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print('END', self.state['state'], self.run/'report.json', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    worker = Runner(args.workspace, args.run)
    if args.check_only:
        print('PASS exact ten-pattern LED630/rc1 scope, fixture pins, indefinite duration and original four-hour drift phase; no ports')
        return
    assert not (args.run/'status.json').exists(), 'Never restart an existing workload'
    worker.execute()


if __name__ == '__main__':
    main()
