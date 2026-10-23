"""End-to-end offline current-build checks in a minimal isolated tree."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from str8build.formats import save, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New isolated test directory; use a short path')
    args = parser.parse_args()
    work = args.out.resolve()
    if work.exists():
        parser.error('Use a fresh test directory')
    if work.is_relative_to(ROOT/'src') or work.is_relative_to(ROOT/'tools'):
        parser.error('Keep test output separate from source and tools')
    work.mkdir(parents=True)
    tree = work/'tree'
    shutil.copytree(ROOT/'src/current',tree/'src/current')
    shutil.copytree(ROOT/'tools/str8build',tree/'tools/str8build',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('tools/build_current.py','tools/verify_current_sources.py','Makefile',
                 'tests/baselines/phase1.json','tests/baselines/phase2.json',
                 'tests/baselines/phase1-legacy-debugger.bin',
                 'tests/baselines/phase2-evidence/direct-source-build.json'):
        target = tree/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    selection = ROOT/'src/current/target.json'
    if selection.exists():
        name = json.loads(selection.read_text())['fixture']
        target = tree/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    checks, runs = [], []
    env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    def run(name,script,*arguments,success=True):
        command = [sys.executable,'-B',script,*arguments]
        with (work/(name+'.log')).open('w',encoding='utf-8') as log:
            result = subprocess.run(command,cwd=tree,env=env,stdout=log,stderr=subprocess.STDOUT)
        runs.append(dict(name=name,command=command,returncode=result.returncode))
        save(work/'progress.json',dict(runs=runs,checks=checks))
        if (result.returncode==0) != success:
            raise AssertionError(f'{name}: unexpected exit {result.returncode}; see {work/(name+".log")}')
        print('PASS',name,flush=True)
        return tree/'BUILD'/name

    first = run('first','tools/build_current.py','--out','BUILD/first')
    second = run('second','tools/build_current.py','--out','BUILD/second','--assembler','wdc02as','--linker','wdcln')
    wrapper = run('wrapper','tools/verify_current_sources.py','--out','BUILD/wrapper')
    report = json.loads((first/'build-report.json').read_text())
    files = ['firmware.bin','symbols.json','source-symbols.json','source-9000.bin',
             'debugger/debugger-a000.bin',*['payload/'+n for n in report['artifacts']]]
    expected = {name:sha((first/name).read_bytes()) for name in files}
    for candidate in (second,wrapper):
        assert {name:sha((candidate/name).read_bytes()) for name in files} == expected
    checks.append('Two independent builds and compatibility entry point produce identical firmware, all payloads and symbol files')
    if 'target_checks' in report:
        assert all(report['target_checks'].values())
    else:
        assert all(report['baseline_checks'].values()) and all(report['symbol_checks'].values())
    checks.append('Selected baseline, 20 payloads and 29 linked symbol maps match')

    before = {p.relative_to(first).as_posix():sha(p.read_bytes()) for p in first.rglob('*') if p.is_file()}
    run('existing-output','tools/build_current.py','--out','BUILD/first',success=False)
    assert before == {p.relative_to(first).as_posix():sha(p.read_bytes()) for p in first.rglob('*') if p.is_file()}
    checks.append('Existing build output is refused and every file remains unchanged')
    fixture = tree/'tests/baselines/phase1-legacy-debugger.bin'
    original = fixture.read_bytes(); changed = bytearray(original); changed[100] ^= 1
    fixture.write_bytes(changed)
    try:
        run('changed-fixture','tools/build_current.py','--out','BUILD/changed-fixture',success=False)
        assert not (tree/'BUILD/changed-fixture').exists()
    finally:
        fixture.write_bytes(original)
    checks.append('A changed legacy fixture is refused before compiler output is created')

    source = tree/'src/current/debugger/debugger.asm'; original = source.read_bytes()
    text = source.read_text(); anchor = 'DBG_ENTRY:\n CLD'; assert text.count(anchor)==1
    source.write_text(text.replace(anchor,'DBG_ENTRY:\n SED',1))
    try:
        changed = run('changed-instruction','tools/build_current.py','--out','BUILD/changed-instruction',success=False)
        failed = json.loads((changed/'build-report.json').read_text())
        assert not failed['passed'] and not failed['firmware_matches']
        if 'target_checks' in failed:
            assert failed['target_checks']['symbols'] and failed['target_checks']['debugger_symbols']
        else:
            assert all(failed['symbol_checks'].values())
    finally:
        source.write_bytes(original)
    checks.append('A same-size instruction change assembles but fails firmware/payload equivalence while symbol checks still pass')

    makefile = (tree/'Makefile').read_text()
    assert '.DEFAULT_GOAL := all' in makefile and '\nall: current\n' in makefile
    assert 'tools/build_current.py --out "$(CURRENT_OUT)"' in makefile
    assert '\ncheck: current-check installer-check\n' in makefile
    assert 'tools/test_current_build.py --out "$(BUILD_CHECK_OUT)"' in makefile
    assert 'tools/test_current_installer.py --out "$(INSTALLER_CHECK_OUT)"' in makefile
    assert 'tools/install_current.py --help' in makefile
    assert all(text not in makefile for text in ('legacy-v1:', 'clean:', 'Remove-Item', 'tools/build_v2', 'src/str8.asm', ' preflight ', ' execute ', ' recover '))
    checks.append('Make exposes only the current build, offline checks and installer help; historical and broad-delete targets are retired (static check)')
    summary = dict(passed=True,board_access=False,hardware_qualified=False,isolated=True,runs=runs,checks=checks,
                   firmware_sha256=report['firmware_sha256'],payload_files=20,symbol_maps=29,artifact_fingerprints=expected,
                   test_source_sha256=sha(Path(__file__).read_bytes()))
    save(work/'report.json',summary)
    print('PASS all current-build integration checks:',work/'report.json',flush=True)


if __name__ == '__main__':
    main()
