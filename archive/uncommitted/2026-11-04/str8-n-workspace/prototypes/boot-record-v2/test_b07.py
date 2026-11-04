"""Run the frozen b06 core regression with only b07 display expectations.

The original checker stays byte-for-byte unchanged. Its executable model and
all352 checks are compiled from an explicitly bounded in-memory adaptation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
BASE = HERE / 'test.py'
FROZEN_BASE_SHA256 = 'e534a0374b59506f7a7e32e8f1829621bacde8c3434f8f61c06b34c6b101e410'
NEW_CHOICES = b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_core():
    raw = BASE.read_bytes()
    assert sha(raw) == FROZEN_BASE_SHA256, 'Frozen b06 core checker changed'
    source = raw.decode()
    old_full = "b'OFFLINE PROTOTYPE S A B 0 1 2 3\\r\\n'"
    new_full = repr(NEW_CHOICES)
    assert source.count(old_full) == 2
    source = source.replace(old_full, new_full)
    old_partial, new_partial = "b'OFFLINE PROTOTYPE'", "b'S=Recovery  A/B=Monitor  0-3=Bank'"
    assert source.count(old_partial) == 1
    source = source.replace(old_partial, new_partial)
    module = types.ModuleType('b07_display_adapted_core')
    module.__file__ = str(BASE)
    exec(compile(source, str(BASE), 'exec'), module.__dict__)
    return module, dict(base_checker_sha256=sha(raw),
                        adapted_source_sha256=sha(source.encode()),
                        full_chooser_marker_substitutions=2,
                        partial_chooser_marker_substitutions=1,
                        model_or_test_logic_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    report = json.loads((build / 'prototype-report.json').read_text())
    assert report['banner'] == '2.0proto b07'
    assert report['experimental_generation'] == 0x80000007 and report['bootstrap_contract'] == 'PR04'
    core, adaptation = load_core()
    core.main()
    output = build / 'cpu-tests.json'
    proof = json.loads(output.read_text())
    assert proof['passed'] and proof['checks'] == 352 and proof['failures'] == 0
    assert {row['cpu'] for row in proof['cases']} == {'65c02', '65c816-e'}
    proof.update(checker_sha256=sha(Path(__file__).read_bytes()),
                 frozen_b06_checker_adaptation=adaptation,
                 symbols_sha256=sha((build / 'symbols.json').read_bytes()),
                 prototype_report_sha256=sha((build / 'prototype-report.json').read_bytes()),
                 b06_checker_source_unchanged=sha(BASE.read_bytes()) == FROZEN_BASE_SHA256)
    assert proof['b06_checker_source_unchanged']
    core.save(output, proof)
    print('PASS b07 text-only checker adaptation:352 groups; frozen b06 checker unchanged', flush=True)


if __name__ == '__main__':
    main()
