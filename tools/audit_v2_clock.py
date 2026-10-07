"""Bind CLOCK build/model/hardware/save evidence and retained drift records."""
import argparse
import hashlib
import json
from pathlib import Path

from build_v2_clock import OUT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--baseline-root',required=True,type=Path)
    args = parser.parse_args()
    meta,tests = read(OUT/'build.json'),read(OUT/'test-results.json')
    body = (OUT/'clock.bin').read_bytes()
    assert tests['passed'] and tests['sha256']==meta['sha256']==sha(body)
    assert tests['s19_sha256']==meta['s19_sha256']==sha((OUT/'clock.s19').read_bytes())
    record = b'SR\x01\x3f'+bytes((0,0x20))+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    report = dict(passed=True,version=meta['version'],sha256=meta['sha256'],checks=tests['checks'],boards=[])
    for board in ('2512','2205','2609'):
        root = args.root/board
        plan,live = read(root/'plan/model-check.json'),read(root/'board-check/report.json')
        prior = read(root/'prior/manifest.json')
        assert prior['repeat_verified'] and plan['passed'] and live['passed'] and live['flash_saved']
        assert plan['sha256']==live['sha256']==meta['sha256']
        assert live['drift_baseline_preserved'] and not live['clock_set_confirmed']
        assert live['final_hashes']==plan['expected_hashes']
        assert plan['changed_regions']==['B2 sector 8 CLOCK record']
        for bank in range(4):
            before = (root/f'prior/b{bank}.bin').read_bytes()
            after = (root/f'board-check/final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes()
            assert sha(before)==plan['prior_hashes'][bank]
            assert after==(root/f'plan/expected-b{bank}.bin').read_bytes()
            assert sha(after)==plan['expected_hashes'][bank]
            if bank==2:
                assert after[:len(record)]==record and after[len(record):]==before[len(record):]
            else:
                assert before==after
        report['boards'].append(dict(board=board,port=live['port'],passed=True,
            stored_label='CLOCK',bank=2,sector=8,final_hashes=live['final_hashes'],
            clock_written=False,drift_baseline_preserved=True))
        print('PASS',board,'CLOCK artifact/model/backup/restore/launch/final flash agree; RTC not set')
    baseline = read(args.baseline_root/'baseline-index.json')
    assert baseline['passed']
    for board in baseline['boards']:
        # The index stores repository-relative paths for owner-local records.
        for path,digest in (('sync_report','sync_sha256'),('baseline_report','baseline_sha256')):
            assert sha(Path(board[path]).read_bytes())==board[digest], 'Drift evidence changed'
    report['drift_baseline_records'] = baseline['boards']
    (args.root/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
