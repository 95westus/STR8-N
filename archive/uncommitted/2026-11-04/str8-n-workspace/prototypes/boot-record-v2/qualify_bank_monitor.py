"""Bind FLASH example model results to exact sources and reproducible BINs."""
import argparse
import json
from pathlib import Path
from build_bank_monitor import HERE, ROOT
from str8build.formats import save, sha


def qualify(build, repro):
    report = json.loads((build / 'bank-monitor-build.json').read_text())
    second = json.loads((repro / 'bank-monitor-build.json').read_text())
    tests = json.loads((build / 'bank-monitor-tests.json').read_text())
    assert tests['passed'] and not tests['hardware'] and not tests['serial_access']
    assert tests['build_sha256'] == sha((build / 'bank-monitor-build.json').read_bytes())
    assert tests['test_source_sha256'] == sha((HERE / 'test_bank_monitor.py').read_bytes())
    assert report['source_hashes'] == second['source_hashes']
    for name, digest in report['source_hashes'].items():
        assert sha((HERE / name).read_bytes()) == digest, name
    assert report['variants'] == second['variants']
    reproduced = {}
    for path in (build / 'payload').iterdir():
        if path.is_file():
            assert path.read_bytes() == (repro / 'payload' / path.name).read_bytes(), path
            reproduced[path.name] = sha(path.read_bytes())
    source = Path(report['source_build'])
    unchanged = {}
    for path in (source / 'payload').iterdir():
        if path.is_file():
            assert path.read_bytes() == (build / 'payload' / path.name).read_bytes(), path
            unchanged[path.name] = sha(path.read_bytes())
    engine = (source / 's/core/prototype-engine.inc').read_bytes()
    assert engine == (build / 's/core/prototype-engine.inc').read_bytes()
    for variant in report['variants']:
        image = build / 'payload' / (variant['name'] + '.bin')
        assert sha(image.read_bytes()) == variant['sha256']
        assert image.stat().st_size == variant['image_bytes']
    result = dict(passed=True, hardware=False, installed=False, serial_access=False,
                  build=str(build), reproduced_build=str(repro), model_groups=tests['groups'],
                  build_report_sha256=tests['build_sha256'],
                  model_report_sha256=sha((build / 'bank-monitor-tests.json').read_bytes()),
                  qualifier_sha256=sha(Path(__file__).read_bytes()),
                  reproduced_payloads=reproduced, unchanged_b15_payloads=unchanged,
                  frozen_engine_byte_identical=True,
                  limitations=['CPU/NOR simulation only; no 2512 install',
                               'Named application launcher remains planned',
                               'Owner RAM prefix borrowed until externally restored',
                               'Flash interruption may tear the edited target sector'])
    save(build / 'bank-monitor-qualification.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--repro', type=Path, required=True)
    x = p.parse_args()
    result = qualify(x.build.resolve(), x.repro.resolve())
    print('PASS:', result['model_groups'], 'CPU/NOR groups; all BINs reproducible')
