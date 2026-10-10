"""Build beta23 from an isolated frozen source snapshot with explicit prerequisites."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',required=True,type=Path)
    p.add_argument('--expected',required=True,type=Path)
    a=p.parse_args(); root=a.source_root.resolve(); expected=a.expected.resolve()
    docs=root/'docs';docs.mkdir(exist_ok=True)
    doc_hashes={}
    for name in ('STR8N_V2_BETA4.md','STR8N_V2_BETA4_RST.md','STR8N_BANK_MAINT_RECOVERY.md'):
        source_doc=ROOT/'docs'/name
        if source_doc.resolve()!=(docs/name).resolve():shutil.copyfile(source_doc,docs/name)
        doc_hashes[name]=sha(docs/name)
    steps=[]
    def run(script,code=False):
        command=[sys.executable,'-c',script] if code else [sys.executable,str(root/'tools'/script)]
        result=subprocess.run(command,cwd=root,capture_output=True,text=True)
        n=len(steps);(root/'BUILD'/f'reproduction-{n:02d}.log').write_text(result.stdout+result.stderr)
        steps.append(dict(command=command,exit_code=result.returncode))
        print('REPRO',n,result.returncode,script,flush=True)
        if result.returncode: raise RuntimeError(result.stderr[-1500:])
    report=dict(passed=False,source_root=str(root),source_basis='Isolated frozen working-tree source, not a committed clean checkout',
                prebuilt_firmware_inputs=False,beta4_document_inputs=doc_hashes,steps=steps)
    try:
        for name in ('build_v2_beta4.py','build_v2_rtc_kernel.py','build_bank_maint_rtc.py','build_v2_rtc_trim.py','build_v2_storage.py','build_v2_clock_trim.py'):
            run(name)
        shutil.copytree(root/'BUILD/v2-clock-1.5',root/'BUILD/v2-storage/clock',dirs_exist_ok=True)
        run("import sys; from pathlib import Path; sys.path.insert(0,'tools'); import build_v2_spi_resident_example as b; b.OUT=Path('BUILD/v2-storage/example').resolve(); b.main()",True)
        run('build_v2_compact_boot.py')
        built=root/'BUILD/v2-compact-boot'; meta=json.loads((expected/'build.json').read_text())
        names=list(meta['artifacts'])+['boot-status/asset.bin','local-display/asset.bin','clock/clock.bin','workspace/workspace.bin','store/sram.bin','edu/edu.bin']
        comparisons={name:dict(expected=sha(expected/name),rebuilt=sha(built/name)) for name in names}
        report['comparisons']=comparisons
        assert all(v['expected']==v['rebuilt'] for v in comparisons.values()), 'Rebuilt firmware differs from frozen candidate'
        report['passed']=True
    except Exception as e:
        report['error']=repr(e)
    (root/'BUILD/reproduction-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print('REPRO RESULT',report['passed'],report.get('error','all compared firmware bytes match'),flush=True)
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
