"""Bind beta6 banner build/model/installation/readback and drift evidence."""
import argparse
import hashlib
import json
from pathlib import Path

from beta4_migration import journal
from build_v2_rtc_banner import OUT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--baseline-root',required=True,type=Path)
    args = parser.parse_args()
    build = read(OUT/'build.json')
    for name,digest in build['artifacts'].items():
        assert sha((OUT/name).read_bytes())==digest
    kernel,banner = read(OUT/'kernel-test-results.json'),read(OUT/'banner-test-results.json')
    assert kernel['passed'] and banner['passed']
    assert kernel['artifacts']==banner['artifacts']==build['artifacts']
    report = dict(passed=True,version=build['version'],generation=build['generation'],
        artifacts=build['artifacts'],banner_checks=banner['checks'],kernel_checks=kernel['checks'],boards=[])
    report['restart_events'] = read(args.root/'restart-events.json')
    for board in ('2512','2205','2609'):
        root = args.root/board
        plan,model,live = read(root/'upgrade/plan.json'),read(root/'upgrade/model-check.json'),read(root/'banner-check/report.json')
        assert model['passed'] and live['passed'] and live['drift_baseline_preserved']
        assert model['installer_sha256']==plan['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())
        assert model['expected_hashes']==live['final_hashes']==plan['expected_hashes']
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused']
        assert b'MIGRATION VERIFIED; PRESS PHYSICAL RESET' in (root/'upgrade/install/result.txt').read_bytes()
        assert not read(root/'upgrade/install/reset-pending.json')['physical_reset_pending']
        assert [entry['slot'] for entry in live['slots']]==['A','B','A']
        assert read(root/'prior/manifest.json')['repeat_verified']
        for bank in range(4):
            before = (root/f'prior/b{bank}.bin').read_bytes()
            after = (root/f'banner-check/final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes()
            assert sha(before)==plan['prior_hashes'][bank]
            assert after==(root/f'upgrade/expected-b{bank}.bin').read_bytes()
            assert sha(after)==plan['expected_hashes'][bank]
            if bank!=3:
                assert before==after
            else:
                assert before[0x1000:0x2000]==after[0x1000:0x2000]
                assert before[0x7000:]==after[0x7000:]
                metadata = journal(after)
                assert metadata[8:24].hex()==plan['config']
                assert [int.from_bytes(metadata[24+i*3:27+i*3],'little') for i in range(32)]==plan['counts_after']
        row = dict(board=board,port=live['port'],passed=True,
            clock_written=False,drift_baseline_preserved=True,final_hashes=live['final_hashes'],
            new_powerfail_observed=live.get('new_powerfail_observed',False),
            observed_outage=live.get('observed_outage'))
        if board!='2512':
            sample = read(root/'sample-check/report.json')
            assert sample['passed'] and sample['snapshot_survives_banner'] and sample['powerfail_preserved']
            assert sample['sha256']==read(Path('BUILD/v2-rtc-kernel/utc-client/sample-build.json'))['sha256']
            row['private_drift_sample_qualified'] = True
        report['boards'].append(row)
        print('PASS',board,'banner/slots/CLOCK/MAINT/reset/full flash/journals agree')
    baseline = read(args.baseline_root/'baseline-index.json')
    assert baseline['passed']
    for row in baseline['boards']:
        assert sha(Path(row['sync_report']).read_bytes())==row['sync_sha256']
        assert sha(Path(row['baseline_report']).read_bytes())==row['baseline_sha256']
    report['drift_baseline_records'] = baseline['boards']
    (args.root/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
