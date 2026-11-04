"""Bind both CPU receipts to the extended CONFIG sources and reproducible BIN."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def qualify(build, repro):
    info = read(build/'ram-config-build.json')
    data = (build/'payload/ram-config-offline.bin').read_bytes()
    assert info['passed'] and not info['hardware'] and not info['serial_access']
    assert len(data) == info['app_bytes'] and sha(data) == info['app_sha256']
    assert data == (repro/'payload/ram-config-offline.bin').read_bytes()
    sy = read(build/'symbols.json')['core/ram-config']
    assert sy['CONFIG_START'] == 0x200 and sy['CONFIG_END'] == 0x200+len(data) <= 0x6500
    source = Path(info['source_build'])
    for name, digest in info['sources'].items():
        assert sha((HERE/name).read_bytes()) == digest
    assert sha((source/'s/core/prototype-engine.inc').read_bytes()) == info['frozen_engine_sha256']
    for name, digest in info['unchanged_payloads'].items():
        assert sha((build/'payload'/name).read_bytes()) == digest
        assert (build/'payload'/name).read_bytes() == (source/'payload'/name).read_bytes()
        assert (build/'payload'/name).read_bytes() == (repro/'payload'/name).read_bytes()
    cases, receipts = [], {}
    for cpu in ('65c02', '65c816-e'):
        path = build/f'ram-config-tests-{cpu}.json'
        receipt = read(path)
        assert receipt['passed'] and receipt['failures'] == 0
        assert not receipt['hardware'] and not receipt['serial_access']
        assert receipt['checks'] == len(receipt['cases']) == 10
        assert receipt['app_sha256'] == sha(data)
        assert receipt['checker_sha256'] == sha((HERE/'test_ram_config_b14.py').read_bytes())
        assert receipt['build_report_sha256'] == sha((build/'ram-config-build.json').read_bytes())
        assert all(case['passed'] and case['cpu'] == cpu for case in receipt['cases'])
        cases.extend(receipt['cases'])
        receipts[path.name] = sha(path.read_bytes())
    help_offset = sy['CONFIG_HELP_TEXT']-0x200
    (build/'ram-config-help.txt').write_bytes(data[help_offset:].split(b'\0', 1)[0])
    result = dict(passed=True, checks=len(cases), failures=0, hardware=False, serial_access=False,
                  app_bytes=len(data), app_sha256=sha(data), byte_reproducible=True,
                  all_admitted_bank_entries=26, CPUs=['65c02', '65c816-e'], ports=['FT245', 'ACIA'],
                  interrupted_mutation_prefixes=sum(c.get('prefixes', 0) for c in cases),
                  selected_interruption_retries=sum(c.get('retries', 0) for c in cases),
                  unchanged_payloads=info['unchanged_payloads'], receipts=receipts,
                  cases=cases, limitations=['CPU/NOR model qualification; no physical board access',
                                           'Raw L remains an unverified transfer',
                                           'Opaque image installation is separate'])
    (build/'ram-config-qualification.json').write_text(json.dumps(result, indent=2)+'\n')
    return {key:value for key,value in result.items() if key not in ('cases', 'unchanged_payloads', 'receipts')}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--repro', type=Path, required=True)
    x = p.parse_args()
    print(json.dumps(qualify(x.build.resolve(), x.repro.resolve()), indent=2))
