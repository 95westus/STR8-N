"""Build the RAM-only NFX1 fixture-preparation engine for reviewed lab use.

This is separate from the release migrator. It commits one host-sealed SNBT
reservation before exactly F/D/C fixture writes. It never runs automatically
and its unrendered template refuses. Frozen F is not assembled or modified.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def build(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    upgrade=module('nfx_upgrade_source',ROOT/'migrator/upgrade/build.py')
    source=upgrade.source()
    changes={
        'MODULE NF_UPGRADE':'MODULE NF_FIXTURE',
        'MIG_NEXT:\n        JSR U_APPEND\n        BCC FAIL_FLASH\n':
            'MIG_NEXT:\n        LDA INDEX\n        BNE FX_RESERVED\n        JSR U_APPEND\n        BCC FAIL_FLASH\nFX_RESERVED:\n',
        'MAGIC: DB "NFU1"':'MAGIC: DB "NFX1"',
        'STR8N-F JOURNAL F UPGRADE / NFU1 / USB':'TEMPORARY WDC FIXTURE / NFX1 / USB',
        'Append one C/D page, then F only. Preserve boot policy.':
            'Reserve fixture erases, then B3:F/D/C only. Private lab target.',
        'U_CHECK:\n        LDA PLAN+5\n        CMP #1\n':
            'U_CHECK:\n        LDA PLAN+5\n        CMP #3\n',
        'JOURNAL: append F erase reservation; no C/D erase':
            'JOURNAL: append fixture F/D/C erase reservation',
        'JOURNAL: F reservation committed and full B3 verified':
            'JOURNAL: fixture reservation committed and full B3 verified',
    }
    for before,after in changes.items():
        if source.count(before)!=1:raise ValueError('Changed fixture anchor: '+before)
        source=source.replace(before,after)
    out.mkdir(parents=True);inputs=out/'input';inputs.mkdir()
    (inputs/'nf-migrate.asm').write_text(source,encoding='ascii',newline='\n')
    builder=module('nfx_base_build',ROOT/'migrator/build.py');builder.ROOT=inputs
    report=builder.build(out/'assembled')
    report.update(protocol='NFX1',release_artifact=False,F_rebuilt=False,CPU_simulations=0,
        order=['append-one-SNBT-reservation','F','D','C'],
        purpose='Explicit lab fixture preparation before real WDC-to-BASE1 migration',
        reservation_frame_address=0x3100,reservation_metadata_address=0x3300)
    (out/'assembled/manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('NFX1 fixture engine only; frozen F and public NFM1/NFU1 artifacts unchanged')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    build(parser.parse_args().out)
