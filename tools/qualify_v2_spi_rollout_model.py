"""Model the three fresh-source board installation recipes; no ports."""
import argparse,concurrent.futures,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    env=dict(os.environ,STR8_RTC_BUILD='BUILD/v2-spi-resident')
    def run(board):
        root=a.root/board
        result=subprocess.run([sys.executable,str(ROOT/'tools/test_v2_rtc_upgrade.py'),'--root',str(root)],env=env,cwd=ROOT,capture_output=True,text=True)
        (root/'upgrade/model.log').write_text(result.stdout+result.stderr)
        print(('PASS ' if result.returncode==0 else 'FAIL ')+board+' fresh-source installer model',flush=True)
        if result.returncode:print((result.stdout+result.stderr)[-2000:],flush=True)
        return result.returncode
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(run,('2512','2205','2609')))
    if any(r):raise SystemExit(1)
if __name__=='__main__':main()
