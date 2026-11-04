"""Build NFU1 RAM-only variant once, using the existing NFM1 source/build rules."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def source():
    text=(BASE/'nf-migrate.asm').read_text(encoding='utf-8')
    replacements={
        'MODULE NF_MIGRATE':'MODULE NF_UPGRADE',
        'CHECK_PLAN:\n':'CHECK_PLAN:\n        JSR U_CHECK\n        BCC CHECK_BAD\n',
        'MIG_NEXT:\n':'MIG_NEXT:\n        JSR U_APPEND\n        BCC FAIL_FLASH\n',
        'MAGIC: DB "NFM1"':'MAGIC: DB "NFU1"',
        'STR8N-F RAM MIGRATOR / NFM1 / USB':'STR8N-F JOURNAL F UPGRADE / NFU1 / USB',
        'Only B3:F and declared C/D may change. No B0 copy.':'Append one C/D page, then F only. Preserve boot policy.',
        'MIG_END:\n':(HERE/'reserve.inc').read_text(encoding='utf-8')+'\nMIG_END:\n',
    }
    for before,after in replacements.items():
        if text.count(before)!=1:raise ValueError('Changed NFM1 anchor: '+before)
        text=text.replace(before,after)
    return text


def build(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Use a fresh build directory')
    out.mkdir(parents=True);inputs=out/'input';inputs.mkdir()
    text=source();(inputs/'nf-migrate.asm').write_text(text,encoding='ascii',newline='\n')
    spec=importlib.util.spec_from_file_location('nfu_base_builder',BASE/'build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=inputs
    manifest=module.build(out/'assembled')
    manifest.update(protocol='NFU1',status='unrendered-upgrade-template-refuses',
        allowed_orders=[['append-one-SNBT-page','F']],C_D_erases=False,
        operations_always_erase=False,F_operation_always_erase=True,
        journal_commit_address='selected erased append page + 00FF; no C/D erase',
        reservation_frame_address=0x3100,reservation_metadata_address=0x3300,
        durable_reservation_before_F_erase=True,
        inputs_sha256={p.relative_to(BASE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (BASE/'nf-migrate.asm',BASE/'build.py',HERE/'reserve.inc',Path(__file__))})
    (out/'assembled/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('NFU1: RAM-only build; F and factory NFM1 artifacts unchanged')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(p.parse_args().out)
