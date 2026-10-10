"""Rehearse future SPI update recipes on archived images, never on boards."""
import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_v2_spi_resident import OUT
ROOT=Path(__file__).resolve().parents[1]

def main():
    results=[]
    parent=OUT/'rehearsal';parent.mkdir(exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='run-',dir=parent))
    for board in ('2512','2205','2609'):
        root=run/board;prior=root/'prior';prior.mkdir(parents=True,exist_ok=False)
        source=ROOT/f'output/qualification/spi-phase2-2026-10-08/{board}/prior'
        for name in ['manifest.json']+[f'b{b}{suffix}.bin' for b in range(4) for suffix in ('','-repeat')]:shutil.copyfile(source/name,prior/name)
        subprocess.run([sys.executable,str(ROOT/'tools/prepare_v2_spi_upgrade.py'),'--root',str(root),'--board',board],check=True)
        env=dict(os.environ,STR8_RTC_BUILD='BUILD/v2-spi-resident')
        subprocess.run([sys.executable,str(ROOT/'tools/test_v2_rtc_upgrade.py'),'--root',str(root)],check=True,env=env)
        result=json.loads((root/'upgrade/model-check.json').read_text());assert result['passed'] and result['record_commits']==[]
        results.append(dict(board=board,root=str(root),installer_sha256=result['installer_sha256'],expected_hashes=result['expected_hashes'],stale_preimage_refused=result['stale_preimage_refused'],corrupt_payload_refused=result['corrupt_payload_refused']))
    (OUT/'spi-upgrade-test-results.json').write_text(json.dumps(dict(passed=True,boards=results,board_access=False,physical_hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
