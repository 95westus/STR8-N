"""Build extended RAM CONFIG against frozen b14 services; no firmware rebuild."""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from build import long_branches
from str8build.assemble import Assembly
from str8build.formats import save, sha


def build(out, source):
    assert not out.exists(), 'Fresh output required'
    report = json.loads((source / 'prototype-report.json').read_text())
    assert report['banner'] == '2.0proto b14'
    assert report['raw_loader']['load_start'] == 0x200
    assert report['journal_duplicate_guard']
    out.mkdir(parents=True)
    for name in ('s', 'payload'):
        shutil.copytree(source / name, out / name)
    a = object.__new__(Assembly)
    a.out, a.assembler, a.linker = out, shutil.which('wdc02as'), shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled = []
    a.symbols = json.loads((source / 'symbols.json').read_text())
    core = out / 's/core'
    # Extend only this RAM app's writer dispatch. Retain the frozen full-CRC,
    # duplicate-history, rollover, durable wear reservation and commit logic.
    engine = (source / 's/core/prototype-engine.inc').read_text()
    assert 'JSR JE_CHECK_DUPLICATES' in engine
    old = "        CMP #3\n        BEQ JE_PROMOTE\n        LDA JE_REQUEST\n"
    assert engine.count(old) == 1, 'Unexpected frozen journal dispatch'
    engine = engine.replace(old, "        CMP #3\n        BEQ JE_PROMOTE\n"
                            "        CMP #6\n        BNE CONFIG_NOT_BANK\n"
                            "        JMP CONFIG_BANK_APPLY\nCONFIG_NOT_BANK:\n"
                            "        LDA JE_REQUEST\n", 1)
    # Expand relative branches after inserting the RAM-only dispatch.
    (core / 'config-engine.inc').write_text(long_branches(engine).replace('P_LONG_', 'CE_LONG_'))
    app_source = HERE / 'ram-config-b14.asm'
    (core / 'ram-config.asm').write_text(long_branches(app_source.read_text()).replace('P_LONG_', 'CF_LONG_'))
    data, sy = a.link('core', 'ram-config', 0x200, 'CONFIG_END')
    assert sy['CONFIG_START'] == 0x200 and sy['CONFIG_END'] <= 0x6500
    a.emit('ram-config-offline.bin', data)
    save(out / 'symbols.json', a.symbols)
    unchanged = {}
    for path in (source / 'payload').iterdir():
        if path.name == 'ram-config-offline.bin' or not path.is_file():
            continue
        assert (out / 'payload' / path.name).read_bytes() == path.read_bytes()
        unchanged[path.name] = sha(path.read_bytes())
    report['config'] = dict(start=0x200, end=sy['CONFIG_END'], bytes=len(data),
                            writer_start=sy['JE_ENTER'], writer_bytes=sy['JE_END']-sy['JE_ENTER'])
    save(out / 'prototype-report.json', report)
    result = dict(passed=True, hardware=False, serial_access=False, source_build=str(source),
                  load_address='0200', end_exclusive=f'{sy["CONFIG_END"]:04X}',
                  app_bytes=len(data), app_sha256=sha(data),
                  remaining_application_bytes=0x6500-sy['CONFIG_END'],
                  commands=['?', 'B', 'B bank entry', 'C', 'C target', 'I (blank only)', 'W', 'Q'],
                  entries='8000-E000 in steps of 1000; B3 excludes C000/D000',
                  journal_format_unchanged=True, unchanged_payloads=unchanged,
                  frozen_engine_sha256=sha((source / 's/core/prototype-engine.inc').read_bytes()),
                  sources={p.name:sha(p.read_bytes()) for p in (Path(__file__), app_source)},
                  compiled=a.compiled,
                  limitations=['Matching b14 F services required', 'Raw L is unverified',
                               'Opaque images installed separately', 'No physical hardware qualification'])
    save(out / 'ram-config-build.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source', type=Path, default=ROOT / 'BUILD/pr04-b14-raw-r4')
    x = p.parse_args()
    print(json.dumps(build(x.out.resolve(), x.source.resolve()), indent=2))
