"""Compare extracted portable runtime to CPU-qualified plans and exact RAM installers."""
import argparse,importlib,sys,json,hashlib,tempfile,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
def main():
    p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();kit=a.kit.resolve();sys.path.insert(0,str(kit));r=importlib.import_module('runtime');m=importlib.import_module('migrate');m.verify_kit(kit);checks=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='bf1-portable-proof-') as temp:
        for folder in sorted((Q/'bf1-2512-legacy-offline-2026-10-17-r6').iterdir()):
            if folder.name not in ('wdcmonv2-stage-source','wdcmonv2-convert','wdcmonv2-restore-historical-source','wdcmonv2-restore-original','v2-0b4-stage-source','v2-0b4-convert','v2-0b4-restore-historical-source','v2-0b4-restore-original'):continue
            old=json.loads((folder/'plan.json').read_text());tx=old['transaction'];source=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)];expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            actual,data,after=r.transaction(source,expected,bytes.fromhex(tx['target_config']),tx['label']);assert actual==tx and after==expected;checks.append(dict(name=folder.name+' portable transaction identical',passed=True,fresh_CPU_execution=False,reference_plan_sha256=hashlib.sha256((folder/'plan.json').read_bytes()).hexdigest()))
            out=Path(temp)/folder.name;r.compose(kit/'template',out,source,actual,data,after);assert (out/'installer-model-only.s19').read_bytes()==(folder/'installer-model-only.s19').read_bytes();assert all((out/f'transfer-{n:02d}.bin').read_bytes()==(folder/f'transfer-{n:02d}.bin').read_bytes() for n in range(len(data)-1));checks.append(dict(name=folder.name+' exact qualified RAM image/transfers',passed=True,fresh_CPU_execution=False))
        invalid=[b'\xff'*32768]*4
        try:r.latest(invalid)
        except ValueError:checks.append(dict(name='no-journal-refused',passed=True))
        else:raise AssertionError('No-journal source admitted')
        cmd=[sys.executable,'-I','-O','-c',"import sys;sys.path.insert(0,sys.argv[1]);import runtime;r=runtime.latest([bytes([255])*32768]*4)",str(kit)]
        result=subprocess.run(cmd,cwd=temp,capture_output=True,text=True);assert result.returncode!=0 and 'No valid journal' in result.stderr;checks.append(dict(name='guards-survive-python-optimization-and-clean-directory',passed=True))
        result=subprocess.run([sys.executable,str(kit/'migrate.py'),'verify-kit','--kit',str(kit)],cwd=temp,capture_output=True,text=True);assert result.returncode==0,(result.stdout,result.stderr);checks.append(dict(name='clean-directory-kit-verification-no-repository-paths',passed=True))
    report=dict(passed=True,cases=len(checks),checks=checks,kit=str(kit),kit_manifest_sha256=hashlib.sha256((kit/'kit-manifest.json').read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),board_access=False,distribution_qualified=False,limits='Exact byte equivalence reuses historical CPU execution evidence; live portable capture/launcher, WDC bridge, portable recovery cases, manuals and extracted final package still require qualification')
    assert not a.out.exists();a.out.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'portable runtime checks; distributable-kit gate remains pending')
if __name__=='__main__':main()
