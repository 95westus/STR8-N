"""Close the owner-authorized 2609 pilot from actual receipts; no serial access."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from atomic_json import publish

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'output/qualification'
H = Q / 'bf1-2609-hardware-2026-10-17'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    destination = H / 'shared-cpu-acceptance.json'
    assert not destination.exists(), 'Preserve completed acceptance receipts'
    pre = read(H / 'shared-firmware-preflight.json')
    assert pre['passed'] and pre['one_firmware_set']
    auth = read(H / 'owner-authorization.json')
    assert auth['unchanged_startup_detection_exception_accepted']
    assert auth['shared_firmware_preflight_sha256'] == sha(H / 'shared-firmware-preflight.json')
    phase_receipts = {}
    observations = 0
    backup = Q / '2609-return-backup-2026-10-17-1931Z'
    assert read(backup / 'report.json')['passed'] and not read(backup / 'restore-needed.json')['needed']
    for phase in ('B', 'A'):
        checks = H / (phase + '-checks')
        install = H / (phase + '-install')
        result = read(checks / 'report.json')
        confirmation = H / (phase + '-reset-confirmation.json')
        assert result['passed'] and result['full_flash_verified'] and result['initial_checks_passed']
        assert result['application_ram_restored'] and result['ports_released']
        assert len(result['checks']) == 12 and all(c['passed'] for c in result['checks'])
        assert not result['clock_set'] and not result['trim_changed'] and not result['persistent_device_writes']
        assert result['reset_confirmation_sha256'] == sha(confirmation)
        assert read(confirmation)['user_confirmed_physical_reset']
        assert result['install_report_sha256'] == sha(install / 'report.json')
        assert result['shared_firmware_preflight_sha256'] == sha(H / 'shared-firmware-preflight.json')
        for folder in (checks, install):
            restoration = read(folder / 'restore-needed.json')
            assert not restoration['needed'] and restoration['verified']
        activation = read(install / 'activation-completed.json')
        assert activation['user_physical_reset_confirmed'] and not activation['physical_reset_pending']
        assert activation['hardware_report_sha256'] == sha(checks / 'report.json')
        modes = [result[k] for k in ('cpu_mode_before', 'cpu_after_clock', 'cpu_after_batch', 'cpu_mode_after')]
        modes += list(result['cpu_exit_checks'].values())
        assert len(modes) == 7
        for mode in modes:
            assert mode['detected_cpu'] == '65C816' and mode['emulation_mode_before_probe']
            assert mode['dbr'] == mode['pbr'] == mode['direct_page'] == 0
            assert mode['entry_irq_disabled'] and mode['entry_decimal_clear']
            assert not mode['probe_enters_native_mode'] and not mode['native_monitor_calls_advertised']
        observations += len(modes)
        for bank, digest in enumerate(result['expected_hashes']):
            assert sha(checks / f'after-checks-b{bank}.bin') == digest
        assert (checks / 'sram-after.bin').read_bytes() == (backup / 'sram.bin').read_bytes()
        for name in ('eeprom-after-0.bin', 'eeprom-after-1.bin'):
            assert (checks / name).read_bytes() == (backup / 'eeprom.bin').read_bytes()
        phase_receipts[phase] = dict(report=str((checks / 'report.json').resolve()),
                                    report_sha256=sha(checks / 'report.json'), check_groups=12,
                                    emulation_runtime_observations=len(modes))

    prior = Q / 'bf1-2604-hardware-2026-10-17/A-checks'
    assert read(prior / 'report.json')['passed']
    assert sha(prior / 'report.json') == pre['prior_2604_hardware_report_sha256']
    assert b'65C02' in (prior / 'version.txt').read_bytes()
    build = ROOT / 'tmp/bfx5/payload'
    pin = read(Q / 'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    assert len(pin['artifacts']) == 19
    for name, info in pin['artifacts'].items():
        assert sha(build / name) == info['sha256']
    for name, digest in pin['source_files'].items():
        assert sha(ROOT / 'release/candidates/batchfix-r1' / name) == digest
    old = [(prior / f'after-checks-b{i}.bin').read_bytes() for i in range(4)]
    new = [(H / 'A-checks' / f'after-checks-b{i}.bin').read_bytes() for i in range(4)]
    ranges = []
    for segment in read(ROOT / 'release/beta35/layout.json')['segments']:
        bank, start, size = segment['bank'], segment['address'] - 0x8000, segment['bytes']
        target = (build / segment['file']).read_bytes()[segment['offset']:segment['offset'] + size]
        assert old[bank][start:start + size] == new[bank][start:start + size] == target
        ranges.append(dict(bank=bank, address=segment['address'], bytes=size,
                           sha256=hashlib.sha256(target).hexdigest()))
    assert old[3][0x2000:0x3000] == new[3][0x2000:0x3000] == (build / 'str8n-v2-recovery-slot-a0.bin').read_bytes()
    protected = {
        'str8n-2.0bf1-local-review-2026-10-17-r2.zip': '042500224adf7fa68aac1057192512eca539cac06b238457b9eea5b77402993b',
        'str8n-2.0b35-review.zip': 'dc7c854f71852a853eac48dbf0070560feb64c8c47df0441d496a5062d7afa1f',
        'str8n-2.0b35-B-target-review-2026-10-17-r2.zip': '2333a9deade33c6b00064625454e62d43c0057b9e0c9b1985526aed3dcee031a',
    }
    for name, digest in protected.items():
        assert sha(ROOT / 'output/releases' / name) == digest
    active = read(Q / 'active-rtc-campaign.json')
    assert active['powered_off_boards'] == ['2205']
    assert sha(Path(active['baseline_index'])) == active['baseline_index_sha256']
    state_path = Path(active['campaign_state'])
    state = read(state_path)
    assert str(state['soak_board']) == '2604' and set(state['snapshot_boards']) == {'2512', '2604', '2609'}
    guard = read(Q / 'device-operations/2609.json')
    assert guard['state'] == 'idle' and not guard['block_snapshot']
    result = dict(passed=True, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  candidate_id='batchfix-r1', version='2.0bf1', generation=48,
                  owner_authorized_pilot_boards=['2604', '2609'], one_firmware_set=True,
                  artifact_count=19, shared_firmware_ranges=ranges, additional_A_monitor_identical=True,
                  phase_receipts=phase_receipts, emulation_runtime_observations=observations,
                  prior_65C02_report=str((prior / 'report.json').resolve()),
                  prior_65C02_report_sha256=sha(prior / 'report.json'),
                  shared_preflight_sha256=sha(H / 'shared-firmware-preflight.json'),
                  baseline_sha256=active['baseline_index_sha256'], protected_review_zip_sha256=protected,
                  runtime_contract='65C02 or 65C816 emulation E=1; DBR/PBR/direct page zero, I=1, D=0',
                  startup_exception='Owner accepts unchanged F30D CPU detection entering native mode briefly before restoring emulation',
                  deferred=['native 816 applications/tests', 'ACIA', 'crypto'],
                  remaining_gates=['Long-term soak and RTC measurement accumulation',
                                   'Physical electrical interruption and original-payload restoration acceptance on exact supported routes',
                                   'Explicit scoped-candidate acceptance and separate release/publication decision'],
                  clocks_trims_settings_changed=False, board_access=False,
                  release_qualified=False, installation_permitted=False, publication_permitted=False,
                  scope_note='Separate owner-authorized 2609 pilot; sealed review ZIP policy remains historical and unchanged')
    publish(destination, result)
    publish(Q / 'bf1-2609-hardware-current.json', dict(checkpoint=str(destination.resolve()), checkpoint_sha256=sha(destination)))
    state.update({'2609_bf1_hardware_state': 'B/A initial hardware checks passed; emulation runtime verified; original application RAM restored',
                  '2609_role': 'Powered on, bf1 A active with verified bf1 B recovery monitor; RTC snapshots only; no workload soak requested',
                  '2609_bf1_hardware_checkpoint': str(destination.resolve())})
    publish(state_path, state)
    pointer = read(Q / 'batchfix-r1-current.json')
    pointer['previous_local_review_checkpoint'] = pointer['report']
    pointer['previous_local_review_checkpoint_sha256'] = pointer['report_sha256']
    pointer.update(report=str(destination.resolve()), report_sha256=sha(destination),
                   status='shared_firmware_65C02_and_65C816_emulation_initial_hardware_checks_passed')
    assert not pointer['release_qualified'] and not pointer['installation_permitted'] and not pointer['publication_permitted']
    publish(Q / 'batchfix-r1-current.json', pointer)
    print('PASS shared bf1 firmware: 2604 65C02, 2609 B/A with 24 groups and 14 emulation runtime observations; sealed ZIPs preserved')


if __name__ == '__main__':
    main()
