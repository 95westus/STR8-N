"""Reproduce frozen beta23 from a clean private snapshot checkout; no publication."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'output/qualification/beta23-phase1-2026-10-09'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root',type=Path,default=ROOT/'tmp/b23repro')
    a=p.parse_args();parent=a.work_root.resolve()
    assert parent.is_relative_to(ROOT/'tmp'),'Private reproduction must stay under the workspace tmp directory'
    seed=parent/'source';checkout=parent/'checkout'
    # The legacy WDC assembler crashes in deeply nested build directories.
    assert len(str(checkout))<=65,'Choose a short workspace tmp path for the WDC assembler'
    parent.mkdir(exist_ok=False)
    shutil.copytree(FROZEN/'frozen/source',seed)
    receipt=json.loads((FROZEN/'freeze-receipt.json').read_text())
    for name,digest in receipt['source_hashes'].items():assert sha(seed/name)==digest,name
    docs=seed/'docs';docs.mkdir(exist_ok=True)
    for name in ('STR8N_V2_BETA4.md','STR8N_V2_BETA4_RST.md','STR8N_BANK_MAINT_RECOVERY.md'):
        shutil.copyfile(ROOT/'docs'/name,docs/name)
    shutil.copyfile(ROOT/'tools/reproduce_v2_beta23.py',seed/'tools/reproduce_v2_beta23.py')
    (seed/'.gitignore').write_text('BUILD/\noutput/\n__pycache__/\n**/__pycache__/\n')
    (seed/'.gitattributes').write_text('* -text\n')
    (seed/'snapshot-provenance.json').write_text(json.dumps(dict(frozen_git_base=receipt['git_head'],
        frozen_receipt_sha256=sha(FROZEN/'freeze-receipt.json'),source_hashes=receipt['source_hashes'],
        purpose='Private reproducibility snapshot; shared repository, release status and remotes untouched'),indent=2)+'\n')
    def git(*args,cwd=seed):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
    git('init','-b','codex/beta23-reproduction-snapshot')
    git('config','core.autocrlf','false');git('config','commit.gpgsign','false')
    hooks=parent/'empty-hooks';hooks.mkdir(exist_ok=True);git('config','core.hooksPath',str(hooks))
    git('config','user.name','Local reproducibility test');git('config','user.email','reproducibility@invalid.local')
    git('add','--renormalize','.');git('add','.');git('commit','-m','Retain byte-exact frozen beta23 source for isolated reproduction')
    commit=git('rev-parse','HEAD')
    git('-c','core.autocrlf=false','clone','--no-hardlinks',str(seed),str(checkout),cwd=parent)
    assert git('status','--porcelain',cwd=checkout)==''
    for name,digest in receipt['source_hashes'].items():assert sha(checkout/name)==digest,name
    (checkout/'BUILD').mkdir()
    result=subprocess.run([sys.executable,str(checkout/'tools/reproduce_v2_beta23.py'),
        '--source-root',str(checkout),'--expected',str(FROZEN/'frozen/build')],cwd=checkout,capture_output=True,text=True)
    (parent/'rebuild.log').write_text(result.stdout+result.stderr)
    generated=git('status','--porcelain',cwd=checkout).splitlines()
    clean=not generated
    report=dict(passed=False,snapshot_commit=commit,clean_before=True,clean_after=clean,source_files_verified=len(receipt['source_hashes']),
        shared_repository_changed=False,published=False,private_local_snapshot=True,checkout=str(checkout))
    if result.returncode==0:
        built=json.loads((checkout/'BUILD/reproduction-receipt.json').read_text())
        assert built['passed']
        assert clean,'Build changed tracked or unignored source files: '+repr(generated)
        report.update(passed=True,artifact_comparisons=built['comparisons'],build_generated_profile_changes=generated,
                      rebuild_receipt_sha256=sha(checkout/'BUILD/reproduction-receipt.json'))
    else:report['error']=result.stderr[-1500:]+result.stdout[-1500:]
    (parent/'clean-checkout-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='artifact_comparisons'},indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
