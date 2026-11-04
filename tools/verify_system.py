"""Verify the unified source/build/profile closure; never opens serial ports."""
import argparse
import hashlib
import json
from pathlib import Path
import verify
from build import cells

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())


def check(build=None, compare=None):
    build = Path(build or ROOT/'firmware').resolve()
    verify.verify(build, compare)
    manifest = read(build/'system-manifest.json')
    baseline = read(ROOT/'system-baseline.json')['artifacts']
    profiles = read(ROOT/'profiles.json')
    assert manifest['passed'] and not manifest['hardware'] and not manifest['serial_access']
    assert manifest['core_manifest_sha256'] == sha(build/'manifest.json')
    assert manifest['profiles'] == profiles
    assert manifest['sources'] == read(build/'manifest.json')['source']
    assert set(manifest['artifacts']) == set(baseline)
    all_artifacts = dict(read(build/'manifest.json')['artifacts'], **manifest['artifacts'])
    for name, info in manifest['artifacts'].items():
        path = build/'payload'/name
        assert sha(path) == info['sha256'] == baseline[name]['sha256']
        assert path.stat().st_size == info['bytes'] == baseline[name]['bytes']
        decoded = cells(path.with_suffix('.s19'))
        start = int(info['address'], 16)
        assert set(decoded) == set(range(start, start+info['bytes']))
        assert bytes(decoded[n] for n in sorted(decoded)) == path.read_bytes()
        if compare:
            assert path.read_bytes() == (Path(compare)/'payload'/name).read_bytes()
    for board, profile in profiles['boards'].items():
        assert board in ('2512', '2609')
        for target, name in profile['installed_components'].items():
            bank, sector = int(target[1]), int(target[3], 16)
            info = all_artifacts[name]
            assert 0 <= bank <= 3 and 8 <= sector <= 15
            assert int(info['address'], 16) == sector*4096 and info['bytes'] == 4096
        assert not any('C' == t[3] or 'D' == t[3] for t in profile['installed_components'])
    q = read(ROOT/'validation/system-qualification.json')
    assert q['passed'] and q['checks'] == 42 and q['reproducible_payloads'] == 18
    assert not q['hardware'] and not q['serial_access']
    assert q['artifacts'] == {name: info['sha256'] for name, info in all_artifacts.items()}
    assert q['profile_sha256'] == sha(ROOT/'profiles.json')
    for name, digest in q['sources'].items():
        assert sha(ROOT/name) == digest, name
    print('PASS unified system: 18 payloads, source closure, two profiles, 42-group qualification', flush=True)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path)
    p.add_argument('--compare', type=Path)
    a = p.parse_args()
    check(a.build, a.compare)
