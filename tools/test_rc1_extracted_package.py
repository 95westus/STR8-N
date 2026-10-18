"""Clean-extracted Windows/Linux launchers, complete workflows and recovery; no ports."""
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/rc1-2026-10-18-r1';WORK=OUT/'clean extraction'
def linux(p):return '/mnt/c/'+Path(p).resolve().as_posix()[3:]
def main():
    assert not WORK.exists();WORK.mkdir();archive=OUT/'str8n-v2.0rc1-release.zip';checks=[]
    with zipfile.ZipFile(archive) as z:z.extractall(WORK)
    root=WORK/'str8n-2.0rc1';env=dict(os.environ,STR8N_PYTHON=sys.executable,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='')
    for platform in ('windows','linux'):
        def run(args):
            if platform=='windows':cmd='"'+os.environ['COMSPEC']+'" /d /s /c ""'+str(root/'rc1.cmd')+'" '+' '.join('"'+str(x)+'"' for x in args)+'"'
            else:cmd=['wsl.exe','-d','Ubuntu-24.04','--exec','/usr/bin/env','STR8N_PYTHON=/usr/bin/python3','PYTHONDONTWRITEBYTECODE=1','/bin/sh',linux(root/'rc1.sh'),*[linux(x) if isinstance(x,Path) else str(x) for x in args]]
            result=subprocess.run(cmd,cwd=WORK,env=env,capture_output=True,text=True,encoding='utf-8',timeout=90)
            return result
        for op in ('verify','status'):
            r=run([op]);assert r.returncode==0,(platform,r.stdout,r.stderr)
            assert ('PASS rc1 kit hashes' in r.stdout if op=='verify' else json.loads(r.stdout)['generation']==49 and json.loads(r.stdout)['live_installation_enabled'])
            checks.append(dict(platform=platform,operation=op,passed=True))
        for route,name in [('wdcmonv2','2609-source'),('beta4','2604-source')]:
            plan=WORK/(platform+' '+route+' private plan');args=[route,'--capture',Q/'rc1-empty-models'/name,'--out',plan]+(['--accept-unknown-wear-history'] if route=='wdcmonv2' else [])
            r=run(args);assert r.returncode==0,(platform,r.stdout,r.stderr)
            r=run(['verify-plan','--plan',plan]);assert r.returncode==0,(platform,r.stdout,r.stderr)
            expected=Q/'rc1-empty-models'/('2609-WDC-to-full-bf1' if route=='wdcmonv2' else '2604-beta4-to-full-bf1')
            assert (plan/'installer-model-only.s19').read_bytes()==(expected/'installer-model-only.s19').read_bytes()
            checks.append(dict(platform=platform,operation=route+' exact CPU-qualified installer and plan guard',passed=True))
        r=run(['beta4','--port','MUST-NOT-OPEN','--board','fixture','--out',WORK/(platform+' refusal'),'--empty-banks']);assert r.returncode!=0 and 'USB serial required' in r.stderr
        checks.append(dict(platform=platform,operation='missing USB identity refuses before port opening',passed=True))
        test=ROOT/'tools/test_rc1_candidate_workflow.py';receipt=WORK/(platform+' workflow.json');fixtures=Q/'bf1-empty-bank-tests-2026-10-18-r1'
        args=[str(test),'--kit',str(root/'migration'),'--fixtures',str(fixtures),'--out',str(receipt)]
        if platform=='windows':cmd=[sys.executable,*args]
        else:cmd=['wsl.exe','-d','Ubuntu-24.04','--exec','/usr/bin/env','PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3',linux(test),'--kit',linux(root/'migration'),'--fixtures',linux(fixtures),'--out',linux(receipt)]
        r=subprocess.run(cmd,cwd=WORK,env=env,capture_output=True,text=True,encoding='utf-8',timeout=90);assert r.returncode==0,(platform,r.stdout,r.stderr);assert json.loads(receipt.read_text())['passed']
        checks.append(dict(platform=platform,operation='actual complete WDC/beta4/restore workflow with simulated endpoints',passed=True))
        print('PASS clean extracted',platform,'launchers, plans, identity refusal, full migrations and recovery',flush=True)
    (OUT/'platform-tests.json').write_text(json.dumps(dict(passed=True,checks=checks,cases=len(checks),zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),board_access=False,simulated_endpoints=True,native_Windows_cmd=True,native_Linux_Ubuntu_WSL=True),indent=2)+'\n')
if __name__=='__main__':main()
