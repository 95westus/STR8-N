"""Run the beta25 package suites with hash-bound results and live log files."""
import argparse,concurrent.futures,os,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',required=True);p.add_argument('--logs',required=True,type=Path);a=p.parse_args()
    os.environ['STR8_RTC_BUILD']=a.build;a.logs.mkdir(parents=True,exist_ok=False)
    commands=[['test_v2_fix005.py'],['test_v2_fix005_faults.py'],['test_v2_fix004.py'],['test_v2_time_local.py'],['test_v2_startup_fifo.py'],['test_v2_storage.py','--maint']]
    def run(args):
        path=a.logs/(args[0]+'.log')
        with path.open('wb') as log:r=subprocess.run([sys.executable,'tools/'+args[0],*args[1:]],stdout=log,stderr=subprocess.STDOUT)
        print(args,r.returncode,path.read_bytes()[-500:].decode(errors='replace'),flush=True);return r.returncode
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:codes=list(pool.map(run,commands))
    assert not any(codes),codes

if __name__=='__main__':main()
