"""Bind the unified build, reproduction and CPU results without board access."""
import argparse
import hashlib
import json
from pathlib import Path
import verify

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())


def qualify(build, compare, core_results, system_results, out):
    build, compare, out = map(lambda p: Path(p).resolve(), (build, compare, out))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(passed=False, phase='verification-in-progress'))+'\n',
                   encoding='utf-8', newline='\n')
    verify.verify(build)
    core = read(Path(core_results)/'qualification.json')
    system = read(Path(system_results)/'qualification.json')
    assert core['passed'] and core['checks'] == 26 and not core['hardware']
    assert system['passed'] and system['checks'] == 16 and not system['hardware']
    assert not core['serial_access'] and not system['serial_access']
    first, second = read(build/'system-manifest.json'), read(compare/'system-manifest.json')
    assert first['sources'] == second['sources']
    all_artifacts = dict(read(build/'manifest.json')['artifacts'], **first['artifacts'])
    for name, info in all_artifacts.items():
        assert sha(build/'payload'/name) == sha(compare/'payload'/name) == info['sha256']
    record = dict(passed=True, checks=42, core_groups=26, system_groups=16,
        hardware=False, serial_access=False, reproducible_payloads=len(all_artifacts),
        artifacts={name: info['sha256'] for name, info in all_artifacts.items()},
        profile_sha256=sha(ROOT/'profiles.json'),
        sources={name: sha(ROOT/name) for name in ('tools/build.py', 'tools/build_system.py',
            'tools/qualify_system.py', 'tests/test_boot_and_opaque.py', 'tests/test_system.py',
            'tests/flash_model.py')},
        cases=core['cases']+system['cases'],
        limits=['Both CPU models run both board layouts with synthetic banks and wear',
                'Existing F, MON variants, VX1, ES1, FLASH and readback payloads reproduce their qualified predecessor bytes',
                'MAINT and EDU client use declared generic text changes and corresponding CRC updates',
                'No new physical power-cut, serial timing, ACIA or EDU electrical qualification'])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('PASS 42 CPU/profile groups; 18 reproduced payloads; no device access', flush=True)
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'compare', 'core-results', 'system-results', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    qualify(a.build, a.compare, a.core_results, a.system_results, a.out)
