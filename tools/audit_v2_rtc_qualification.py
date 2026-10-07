"""Bind completed three-board qualification to built images and exact plans."""
import argparse
import hashlib
import json
from pathlib import Path

from beta4_migration import journal, read_s19

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    build = ROOT / 'BUILD/v2-rtc-kernel'
    manifest = read(build / 'build.json')
    tests = read(build / 'kernel-test-results.json')
    assert tests['passed'] and tests['artifacts'] == manifest['artifacts']
    for name, digest in manifest['artifacts'].items():
        assert sha((build / name).read_bytes()) == digest
    split = ROOT / 'BUILD/v2-rtc-phase2-split'
    split_meta = read(split / 'build.json')
    for name in ('test-results.json', 'i2c-test-results.json'):
        result = read(split / name)
        assert result['passed']
        assert result['provider_sha256'] == split_meta['provider_sha256'] == sha((split / 'provider.bin').read_bytes())
        assert result['gateway_sha256'] == split_meta['gateway_sha256'] == sha((split / 'gateway.bin').read_bytes())
    component = (build / 'str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert component[:1760] == (split / 'provider.bin').read_bytes()
    assert component[1760:2272] == (split / 'gateway.bin').read_bytes()
    client, entry = read_s19(build / 'client/kernel-client.s19')
    assert entry == 0x2000
    client_sha = sha(bytes(client[a] for a in range(min(client), max(client)+1)))
    report = dict(passed=True, version=manifest['version'], generation=manifest['generation'],
                  kernel_checks=tests['checks'], artifacts=manifest['artifacts'], boards=[])
    for board in ('2512', '2205', '2609'):
        root = args.root / board
        plan = read(root / 'upgrade/plan.json')
        model = read(root / 'upgrade/model-check.json')
        services = read(root / 'service-check/report.json')
        slots = read(root / 'slot-check/report.json')
        final = read(root / 'post-qualification/manifest.json')
        prior = read(root / 'prior/manifest.json')
        assert model['passed'] and model['installer_sha256'] == plan['installer_sha256']
        assert model['expected_hashes'] == plan['expected_hashes']
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused']
        assert sha((root / 'upgrade/installer.s19').read_bytes()) == plan['installer_sha256']
        assert b'MIGRATION VERIFIED; PRESS PHYSICAL RESET' in (root / 'upgrade/install/result.txt').read_bytes()
        assert services['passed'] and services['client_sha256'] == client_sha
        assert services['cold_state_uninitialized'] and services['descriptor'] == '535601030065ff64'
        assert services['final_flash_hashes'] == plan['expected_hashes']
        assert slots['passed'] and [c['slot'] for c in slots['checks']] == ['A', 'B', 'A']
        assert prior['repeat_verified'] and final['repeat_verified']
        for bank in range(4):
            before = (root / f'prior/b{bank}.bin').read_bytes()
            after = (root / f'post-qualification/b{bank}.bin').read_bytes()
            assert before == (root / f'prior/b{bank}-repeat.bin').read_bytes()
            assert after == (root / f'post-qualification/b{bank}-repeat.bin').read_bytes()
            assert after == (root / f'upgrade/expected-b{bank}.bin').read_bytes()
            assert sha(before) == plan['prior_hashes'][bank] == prior['banks'][bank]['sha256']
            assert sha(after) == plan['expected_hashes'][bank] == final['banks'][bank]['sha256']
            if bank in (0, 2):
                assert before == after
        b3 = (root / 'post-qualification/b3.bin').read_bytes()
        assert b3[:4096] == (build / 'str8n-rtc-component-8000-8fff.bin').read_bytes()
        assert b3[0x6000:] == ((build / 'str8n-v2-recovery-e000-efff.bin').read_bytes()
                               + (build / 'str8n-v2-recovery-f000-ffff.bin').read_bytes())
        assert (root / 'post-qualification/b1.bin').read_bytes()[:8192] == (build / 'str8n-maint-1.6-b1-8000-9fff.bin').read_bytes()
        metadata = journal(b3)
        assert metadata[8:24].hex() == plan['config']
        assert [int.from_bytes(metadata[24+i*3:27+i*3], 'little') for i in range(32)] == plan['counts_after']
        reset = read(root / 'upgrade/install/reset-pending.json')
        reset.update(physical_reset_pending=False, physical_reset_confirmed_by_user=True,
                     post_reset_qualification='service-check/report.json', final_readback='post-qualification/manifest.json')
        (root / 'upgrade/install/reset-pending.json').write_text(json.dumps(reset, indent=2)+'\n')
        report['boards'].append(dict(board=board, passed=True, full_flash_bytes=131072,
            final_hashes=plan['expected_hashes'], bank_statuses=services['bank_statuses'],
            i2c_result=services['i2c_result'], slots=['A','B','A'],
            fixed_f_changed=plan['fixed_f_changed'], planned_erases=len(plan['steps'])))
        print('PASS', board, 'model/install/reset/services/slots/repeated full flash/journals all agree')
    (args.root / 'acceptance.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
