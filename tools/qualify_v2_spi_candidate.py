"""Run independent candidate models, then offline recipes and artifact audits."""
import concurrent.futures,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TESTS=('test_v2_spi_resident','test_v2_rtc_kernel','test_v2_journal',
       'test_v2_rtc_banner','test_v2_rtc_time','test_v2_clock',
       'test_v2_clock_journal','test_v2_binding','test_v2_binding_clock','test_v2_trim')

def main():
    env=os.environ.copy();env['STR8_RTC_BUILD']='BUILD/v2-spi-resident';env['STR8_CLOCK_BUILD']='BUILD/v2-clock-1.5'
    def run(name):
        p=subprocess.run([sys.executable,str(ROOT/'tools'/f'{name}.py')],cwd=ROOT,env=env,capture_output=True,text=True)
        log=ROOT/'BUILD/v2-spi-resident'/f'{name}.log';log.write_text(p.stdout+p.stderr)
        print(('PASS ' if p.returncode==0 else 'FAIL ')+name,flush=True)
        if p.returncode:print((p.stdout+p.stderr)[-2500:],flush=True)
        return p.returncode
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        result=list(pool.map(run,TESTS))
    if any(result):raise SystemExit('Candidate regression failed; see individual BUILD logs')
    for name in ('rehearse_v2_spi_upgrade','audit_v2_spi_resident'):
        if run(name):raise SystemExit('Offline qualification failed')
    print('PASS all resident/RTC/CLOCK models and offline update recipes; no board access',flush=True)

if __name__=='__main__':main()
