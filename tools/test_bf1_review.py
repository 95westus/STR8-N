"""Test bf1 extraction-verifier corruption, scope and path refusals offline."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('kit',type=Path);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args();checks=[]
    a.report.parent.mkdir(parents=True,exist_ok=True)
    def run(name,mutate,expected=None):
        with tempfile.TemporaryDirectory(prefix='bf1-review-',dir=ROOT/'tmp') as tmp:
            path=Path(tmp).resolve();assert path.is_relative_to((ROOT/'tmp').resolve())
            kit=path/'kit';shutil.copytree(a.kit,kit);mutate(kit)
            r=subprocess.run([sys.executable,'-B',str(kit/'verify_review.py'),str(kit)],capture_output=True,text=True)
            (a.report.parent/(name+'.json')).write_text(json.dumps(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr),indent=2)+'\n')
            assert (r.returncode!=0 and expected in r.stderr) if expected else r.returncode==0,(name,r.stdout,r.stderr)
            checks.append(dict(name=name,passed=True,refused=bool(expected)));print('PASS',name,flush=True)
    def alter(k,name,data=None,rebind=False):
        f=k/name;f.write_bytes(f.read_bytes()+b'\nmodified\n' if data is None else data)
        if rebind:
            p=k/'review-manifest.json';m=json.loads(p.read_text());m['files'][name]=dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest());p.write_text(json.dumps(m))
    def scope(k,field,value):
        n='release/bf1-prerelease/acceptance-scope.json';m=json.loads((k/n).read_text());m[field]=value;alter(k,n,json.dumps(m).encode(),True)
    def permission(k):
        p=k/'review-manifest.json';m=json.loads(p.read_text());m['installation_permitted']=True;p.write_text(json.dumps(m))
    def unsafe(k,name):
        p=k/'review-manifest.json';m=json.loads(p.read_text());allow=json.loads((k/'review-allowlist.json').read_text());allow.append(name)
        alter(k,'review-allowlist.json',json.dumps(allow).encode(),True);m=json.loads(p.read_text());m['files'][name]=dict(bytes=0,sha256='0'*64);p.write_text(json.dumps(m))
    try:
        run('exact-extraction',lambda k:None)
        run('altered-manual',lambda k:alter(k,'docs/bf1/ASM_GUIDE.md'),'Size/hash mismatch')
        run('altered-source',lambda k:alter(k,'release/candidates/batchfix-r1/source/core/monitor-b0.asm'),'Size/hash mismatch')
        run('altered-payload',lambda k:alter(k,'release/candidates/batchfix-r1/payload/xip/utilities.bin'),'Size/hash mismatch')
        run('altered-builder',lambda k:alter(k,'build_helper.py'),'Size/hash mismatch')
        run('missing-example',lambda k:(k/'examples/A-example.s19').unlink(),'Missing file')
        run('unexpected-bank',lambda k:(k/'b0.bin').write_bytes(bytes(32768)),'Missing or unexpected review files')
        run('installation-flag',permission,'Review permission flags')
        run('native816-scope',lambda k:scope(k,'processor_execution_scope','65C816 native'),'Processor/profile scope')
        run('removed-deferral',lambda k:scope(k,'deferred',['ACIA','crypto']),'Scope deferrals')
        run('scope-publication',lambda k:scope(k,'publication_permitted',True),'Scope permission flags')
        run('parent-path',lambda k:unsafe(k,'../outside.bin'),'Unsafe path')
        run('windows-drive-path',lambda k:unsafe(k,'C:/outside.bin'),'Unsafe path')
        run('case-collision',lambda k:unsafe(k,'README.MD'),'Case collisions')
        run('rebound-broken-link',lambda k:alter(k,'docs/bf1/README.md',(k/'docs/bf1/README.md').read_bytes()+b'\n[missing](MISSING.md)\n',True),'Broken/escaping document link')
        run('rebound-bad-S19',lambda k:alter(k,'examples/A-example.s19',b'S10D020078D8A941206D7E4C677E00\nS9030200FA\n',True),'Invalid S-record checksum')
        run('rebound-helper-source',lambda k:alter(k,'release/candidates/batchfix-route-r1/source/reservation.asm',rebind=True),'Helper source binding')
        run('broadened-route',lambda k:scope(k,'migration_scope','Any stock or legacy board; generic conversion permitted'),'Migration scope')
        run('clock-write-policy',lambda k:scope(k,'campaign',dict(soak_board='2604',rtc_snapshot_boards=['2512','2604'],powered_off_boards=['2205','2609'],clock_trim_changes_permitted=True,baseline_replacement_permitted=False)),'Campaign preservation scope')
    except Exception:
        a.report.with_suffix('.failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    a.report.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,kit=str(a.kit.resolve()),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),finished_utc=datetime.now(timezone.utc).isoformat(),board_access=False),indent=2)+'\n')
if __name__=='__main__':main()
