"""Retain beta23 source, build and model hashes plus backup-bound rehearsals."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'BUILD/v2-compact-boot'
OUT = ROOT/'output/qualification/beta23-phase1-2026-10-09'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def main():
    audit = read(BUILD/'compact-boot-candidate-check.json')
    assert audit['passed'] and audit['build_sha256'] == sha(BUILD/'build.json')
    for name, digest in audit['artifacts'].items(): assert sha(BUILD/name) == digest
    for name, digest in audit['model_report_hashes'].items(): assert sha(BUILD/name) == digest
    boards = []
    for board in ('2512', '2205', '2609'):
        root = OUT/board/'fresh'; prior = read(root/'prior/manifest.json')
        plan = read(root/'upgrade/plan.json'); model = read(root/'upgrade/model-check.json')
        assert prior['repeat_verified'] and prior['board'] == board
        assert plan['source_generation'] == 31 and plan['generation'] == 32
        assert plan['build_sha256'] == audit['build_sha256']
        assert plan['candidate_audit_sha256'] == sha(BUILD/'compact-boot-candidate-check.json')
        assert model['passed'] and model['stale_preimage_refused'] and model['corrupt_payload_refused']
        assert model['expected_hashes'] == plan['expected_hashes']
        assert model['installer_sha256'] == plan['installer_sha256'] == sha(root/'upgrade/installer.s19')
        for b in range(4):
            path = root/f'prior/b{b}.bin'
            assert sha(path) == plan['prior_hashes'][b] == prior['banks'][b]['sha256']
            assert path.read_bytes() == (root/f'prior/b{b}-repeat.bin').read_bytes()
            assert sha(root/f'upgrade/expected-b{b}.bin') == plan['expected_hashes'][b]
        boards.append(dict(board=board, root=str(root.relative_to(ROOT)),
                           prior_manifest_sha256=sha(root/'prior/manifest.json'),
                           plan_sha256=sha(root/'upgrade/plan.json'), model_sha256=sha(root/'upgrade/model-check.json'),
                           installer_sha256=plan['installer_sha256'], prior_hashes=plan['prior_hashes'],
                           expected_hashes=plan['expected_hashes'], sectors=plan['steps'], saved_edu=plan['saved_edu']))
    frozen = OUT/'frozen'; frozen.mkdir(exist_ok=False)
    shutil.copytree(BUILD, frozen/'build', ignore=shutil.ignore_patterns('__pycache__'))
    sources = {}
    for parent in ('src', 'tools'):
        for p in sorted((ROOT/parent).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts: continue
            relative = p.relative_to(ROOT)
            target = frozen/'source'/relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target); sources[relative.as_posix()] = sha(target)
    files = {p.relative_to(frozen/'build').as_posix(): sha(p)
             for p in sorted((frozen/'build').rglob('*')) if p.is_file()}
    receipt = dict(passed=True, version='2.0b23', generation=32, date='2026-10-09',
                   git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   source_basis='Exact working-tree snapshot, including uncommitted/untracked source; clean reproduction remains a later gate',
                   build_sha256=audit['build_sha256'], candidate_audit_sha256=sha(BUILD/'compact-boot-candidate-check.json'),
                   source_hashes=sources, build_file_hashes=files, boards=boards,
                   fresh_repeated_flash_backups=True, rehearsal_passed=True, boards_flashed=False,
                   hardware_qualification_pending=True, excluded_boards=['2604'],
                   limitation='STR8N-001 ACIA receive on 2512/2205 remains deferred; qualified USB console only')
    (OUT/'freeze-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS frozen beta23 source/build/models and three fresh-backup exact-image rehearsals')
    print('Freeze receipt SHA256:', sha(OUT/'freeze-receipt.json'))


if __name__ == '__main__': main()
