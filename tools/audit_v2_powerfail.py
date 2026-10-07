"""Bind drift measurement, beta7/CLOCK models, device updates and live ACK."""
import argparse,json,hashlib
from pathlib import Path
from beta4_migration import journal
from build_v2_rtc_powerfail import OUT
from build_v2_clock_powerfail import OUT as CLOCK

sha=lambda data:hashlib.sha256(data).hexdigest()
read=lambda path:json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    meta=read(OUT/'build.json');clock=read(CLOCK/'build.json');checks=read(OUT/'powerfail-test-results.json')
    assert checks['passed'] and checks['kernel_artifacts']==meta['artifacts'] and checks['clock_sha256']==clock['sha256']
    assert read(CLOCK/'test-results.json')['sha256']==clock['sha256']
    for name,digest in meta['artifacts'].items():assert sha((OUT/name).read_bytes())==digest
    report=dict(passed=True,version=meta['version'],clock_version=clock['version'],clock_sha256=clock['sha256'],boards=[])
    for board in ('2512','2205','2609'):
        root=a.root/board;plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json');live=read(root/'powerfail-check/report.json')
        assert live['passed'] and model['passed'] and live['final_hashes']==plan['expected_hashes']==model['expected_hashes']
        assert not live['clock_set'] and live['clock_sha256']==clock['sha256']
        assert model['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())==plan['installer_sha256']
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused'] and model['record_committed']
        assert model['committed_record_bank']==2 and not model['maintenance_committed']
        assert not read(root/'upgrade/install/reset-pending.json')['physical_reset_pending']
        assert read(root/'prior/manifest.json')['repeat_verified']
        for bank in range(4):
            before=(root/f'prior/b{bank}.bin').read_bytes();after=(root/f'powerfail-check/final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes() and sha(before)==plan['prior_hashes'][bank]
            assert after==(root/f'upgrade/expected-b{bank}.bin').read_bytes() and sha(after)==plan['expected_hashes'][bank]
            if bank in (0,1):assert before==after
            if bank==2:assert before[4096:]==after[4096:]
            if bank==3:
                assert before[0x7000:]==after[0x7000:]
                record=journal(after);assert record[8:24].hex()==plan['config']
                assert [int.from_bytes(record[24+i*3:27+i*3],'little') for i in range(32)]==plan['counts_after']
        if board!='2512':assert live['ack_requested'] and not live['powerfail_after'] and live['retained_capture']
        report['boards'].append(dict(board=board,passed=True,clock_set=False,acknowledged=board!='2512',archived_outage=live['archived_outage'],final_hashes=live['final_hashes']))
        print('PASS',board,'beta7/CLOCK update, ACK/absence, archives and exact flash')
    baseline=read(Path('output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json'))
    for b in baseline['boards']:
        assert sha(Path(b['sync_report']).read_bytes())==b['sync_sha256']
        assert sha(Path(b['baseline_report']).read_bytes())==b['baseline_sha256']
    report['drift']=read(Path('output/qualification/rtc-drift-2026-10-07/summary.json'))
    report['original_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
