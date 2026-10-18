"""Exercise new outer review-verifier refusal paths on disposable copies."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('kit',type=Path);ap.add_argument('--report',required=True,type=Path);a=ap.parse_args();checks=[]
    def run(name,mutate,expected=None):
        with tempfile.TemporaryDirectory(prefix='q35outer-',dir=ROOT/'tmp') as temp:
            path=Path(temp);assert path.resolve().is_relative_to((ROOT/'tmp').resolve());kit=path/'kit';shutil.copytree(a.kit,kit,ignore=shutil.ignore_patterns('__pycache__'))
            mutate(kit);result=subprocess.run([sys.executable,'-B',str(kit/'verify_review.py'),str(kit)],capture_output=True,text=True)
            if expected:assert result.returncode!=0 and expected in result.stderr,(name,result.stdout,result.stderr)
            else:assert result.returncode==0,(name,result.stdout,result.stderr)
            checks.append(dict(name=name,passed=True,refused=expected is not None));print('PASS',name,flush=True)
    def write_manifest(k,m):(k/'review-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    def permission(k):
        m=json.loads((k/'review-manifest.json').read_text());m['installation_permitted']=True;write_manifest(k,m)
    def append(k,name):
        p=k/name;p.write_bytes(p.read_bytes()+b'\nmodified\n')
    def unexpected(k):(k/'b0.bin').write_bytes(bytes(32768))
    def missing(k):(k/'examples/asm-print-a.s19').unlink()
    def scope_change(k,field,value):
        file=k/'release/beta35-prerelease/beta35-route-scope.json';m=json.loads(file.read_text());m[field]=value;file.write_text(json.dumps(m))
    def unsafe(k):
        m=json.loads((k/'review-manifest.json').read_text());allow=json.loads((k/'review-allowlist.json').read_text());allow.append('../outside.bin')
        (k/'review-allowlist.json').write_text(json.dumps(allow));d=(k/'review-allowlist.json').read_bytes();m['files']['review-allowlist.json']=dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest());m['files']['../outside.bin']=dict(bytes=0,sha256='0'*64);write_manifest(k,m)
    def bad_link(k):
        file=k/'docs/beta35/README.md';file.write_bytes(file.read_bytes()+b'\n[missing](NO_SUCH_FILE.md)\n');m=json.loads((k/'review-manifest.json').read_text());d=file.read_bytes();m['files']['docs/beta35/README.md']=dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest());write_manifest(k,m)
    try:
        run('exact expanded extraction',lambda k:None)
        run('altered manual refused',lambda k:append(k,'docs/beta35/ASM_GUIDE.md'),'Size/hash mismatch')
        run('altered offline tool refused',lambda k:append(k,'tools/plan_beta35_offline.py'),'Size/hash mismatch')
        run('altered source catalog refused',lambda k:append(k,'release/beta35-prerelease/source-catalog.json'),'Size/hash mismatch')
        run('unexpected full bank refused',unexpected,'unexpected review files')
        run('missing example refused',missing,'FileNotFoundError')
        run('installation flag refused',permission,'permission flags')
        run('A-target policy refused',lambda k:scope_change(k,'target_monitor_page',0xa0),'B-target scope required')
        run('unapproved scope refused',lambda k:scope_change(k,'owner_scope_approved',False),'B-target scope required')
        run('scope cannot grant installation',lambda k:scope_change(k,'installation_permitted',True),'Scope permission flags')
        run('unsafe path refused before reading outside extraction',unsafe,'Unsafe path')
        run('broken manual link refused even with updated file digest',bad_link,'Broken/escaping document link')
    except Exception:
        a.report.with_suffix('.failure.json').write_text(json.dumps(dict(passed=False,checks=checks),indent=2)+'\n');raise
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,kit=str(a.kit.resolve()),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),finished_utc=datetime.now(timezone.utc).isoformat(),board_access=False),indent=2)+'\n')
if __name__=='__main__':main()
