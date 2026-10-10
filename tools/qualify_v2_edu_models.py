"""Run independent beta15 firmware/utility model suites without board ports."""
import argparse,concurrent.futures,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident'
def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',choices=('remaining','workspace','core','status-regression','storage','all'),default='remaining');p.add_argument('--build',type=Path,default=OUT);p.add_argument('--clock',type=Path,default=ROOT/'BUILD/v2-clock-1.5');a=p.parse_args()
    scripts=['test_v2_journal.py','test_v2_rtc_banner.py','test_v2_rtc_time.py','test_v2_binding.py','test_v2_binding_clock.py','test_v2_clock.py'] if a.suite=='remaining' else ['test_v2_workspace.py','test_v2_workspace_guards.py','test_v2_workspace_format.py','test_v2_workspace_integration.py','test_v2_workspace_console.py','test_v2_spi_hardware_client.py']
    if a.suite=='core':scripts=['test_v2_rtc_kernel.py','test_v2_spi_resident.py','test_v2_trim.py']
    if a.suite=='status-regression':scripts=['test_v2_journal.py','test_v2_rtc_banner.py','test_v2_spi_resident.py','test_v2_rtc_kernel.py']
    if a.suite=='storage':scripts=['test_v2_storage.py','test_v2_status.py','test_v2_sram_store.py']
    if a.suite=='all':scripts=['test_v2_storage.py','test_v2_status.py','test_v2_sram_store.py','test_v2_rtc_kernel.py','test_v2_spi_resident.py','test_v2_trim.py','test_v2_workspace.py','test_v2_workspace_guards.py','test_v2_workspace_format.py','test_v2_workspace_integration.py','test_v2_workspace_console.py','test_v2_spi_hardware_client.py','test_v2_journal.py','test_v2_rtc_banner.py','test_v2_rtc_time.py','test_v2_binding.py','test_v2_binding_clock.py','test_v2_clock.py']
    env=dict(os.environ,STR8_RTC_BUILD=str(a.build.resolve()),STR8_CLOCK_BUILD=str(a.clock.resolve()))
    logs=a.build/'edu-model-logs';logs.mkdir(exist_ok=True)
    def run(script):
        result=subprocess.run([sys.executable,str(ROOT/'tools'/script)],cwd=ROOT,env=env,capture_output=True,text=True)
        (logs/(script+'.log')).write_text(result.stdout+result.stderr)
        print(('PASS ' if result.returncode==0 else 'FAIL ')+script,flush=True)
        if result.returncode:print((result.stdout+result.stderr)[-2200:],flush=True)
        return result.returncode
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,scripts))
    if any(results):raise SystemExit(1)
if __name__=='__main__':main()
