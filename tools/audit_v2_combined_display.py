"""Validate combined beta20 and optionally pin three modeled board installers."""
import argparse,hashlib,json
from pathlib import Path
from beta4_migration import crc

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-combined-display'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path)
    a=p.parse_args();meta=read(OUT/'build.json')
    assert meta['version']=='2.0b20' and meta['generation']==29
    assert meta['quiet_monitor_return'] and meta['weekday_display'] and meta['trim_display']
    assert max(meta['monitor_bytes'].values())<=3968
    for name,digest in meta['artifacts'].items():assert sha(OUT/name)==digest,name
    asset=(OUT/'boot-status/asset.bin').read_bytes()
    assert len(asset)==2560 and crc(asset)==0 and sha(OUT/'boot-status/asset.bin')==meta['status_asset_sha256']
    assert meta['status_code_bytes']<=2558 and meta['weekday_entry']==0x6E07
    prior=ROOT/'BUILD/v2-trim-display'
    for name in ('str8n-v2-recovery-f000-ffff.bin','store/sram.bin','workspace/workspace.bin','edu/edu.bin','clock/clock.bin',meta['maintenance_storage_file']):
        assert (OUT/name).read_bytes()==(prior/name).read_bytes(),name
    name='str8n-rtc-component-8000-8fff.bin'
    assert (OUT/name).read_bytes()[:0x900]==(prior/name).read_bytes()[:0x900]
    journal=(OUT/'str8n-journal-9000-9fff.bin').read_bytes();assert crc(journal[:3072])==0 and journal[3072:]==b'\xff'*1024
    reports=('quiet-return-test-results.json','weekday-test-results.json','trim-display-test-results.json','kernel-test-results.json','banner-test-results.json','journal-test-results.json','spi-resident-test-results.json')
    for name in reports:
        result=read(OUT/name);assert result['passed'] and result['artifacts']==meta['artifacts'],name
    candidate=dict(passed=True,version=meta['version'],artifacts=meta['artifacts'],status_asset_sha256=meta['status_asset_sha256'],
        quiet_monitor_return=True,weekday_display=True,trim_display=True,tests=list(reports),board_access=False)
    (OUT/'storage-candidate-check.json').write_text(json.dumps(candidate,indent=2)+'\n')
    if a.root:
        rows=[]
        for board in ('2512','2205','2609'):
            root=a.root/board;plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json')
            assert plan['version']==meta['version'] and plan['weekday_display'] and plan['quiet_monitor_return']
            assert model['passed'] and model['stale_preimage_refused'] and model['corrupt_payload_refused']
            assert model['installer_sha256']==plan['installer_sha256']==sha(root/'upgrade/installer.s19')
            assert model['expected_hashes']==plan['expected_hashes'] and model['record_commits']==[]
            assert [(s['bank'],s['sector']) for s in plan['steps']]==[(3,12),(2,13),(2,12),(3,8),(3,9),(3,14),(3,11),(3,10)]
            for bank in range(4):
                assert sha(root/f'prior/b{bank}.bin')==sha(root/f'prior/b{bank}-repeat.bin')==plan['prior_hashes'][bank]
                assert sha(root/f'upgrade/expected-b{bank}.bin')==plan['expected_hashes'][bank]
            before=[(root/f'prior/b{bank}.bin').read_bytes() for bank in range(4)]
            after=[(root/f'upgrade/expected-b{bank}.bin').read_bytes() for bank in range(4)]
            assert before[:2]==after[:2]
            assert before[2][:0x4800]==after[2][:0x4800] and before[2][0x5200:]==after[2][0x5200:]
            assert before[3][:0x900]==after[3][:0x900] and before[3][0x1C00:0x2000]==after[3][0x1C00:0x2000]
            assert before[3][0x5000:0x6000]==after[3][0x5000:0x6000] and before[3][0x7000:]==after[3][0x7000:]
            rows.append(dict(board=board,root=str(root.resolve()),plan_sha256=sha(root/'upgrade/plan.json'),
                model_sha256=sha(root/'upgrade/model-check.json'),installer_sha256=plan['installer_sha256'],
                prior_hashes=plan['prior_hashes'],expected_hashes=plan['expected_hashes']))
        scripts={name:sha(ROOT/'tools'/name) for name in ('audit_v2_combined_display.py','install_v2_rtc_upgrade.py','qualify_v2_trim_display_board.py')}
        manifest=dict(passed=True,scheduled_local='2026-10-09 01:00:00 America/Chicago',build=str(OUT),
            build_metadata_sha256=sha(OUT/'build.json'),candidate_check_sha256=sha(OUT/'storage-candidate-check.json'),
            scripts=scripts,boards=rows)
        (a.root/'flash-schedule.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('PASS beta20 combined display: sealed assets, paired weekdays, quiet returns, trim, services and preserved utilities'+('; three guarded installers pinned' if a.root else ''))

if __name__=='__main__':main()
