"""Build one RAM-only NFC1 lab for reviewed programmer-F qualification.

Mode 2 appends a sealed reservation, then prepares D/C fixture sectors.
Mode 1 appends the sealed original policy at C100 without sector erase.
Production NFM1/CONFIG and frozen F are unchanged. No CPU model or port access.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
sha = lambda body: hashlib.sha256(body).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Fresh build directory required')
    lock = json.loads((ROOT / 'F_FREEZE.json').read_text())
    for name, digest in lock['sources'].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    assert sha((ROOT / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == lock['sha256']
    symbols = dict(re.findall(r'^(\w+)\s+EQU\s+\$([0-9A-Fa-f]+)',
                             (ROOT / 'src/core/boot-symbols.inc').read_text(), re.M))
    recovery = int(symbols['BOOT_RECOVERY'], 16)
    assert recovery == 0xf2af
    source = module('nfc_upgrade', ROOT / 'migrator/upgrade/build.py').source()
    changes = {
        'MODULE NF_UPGRADE': 'MODULE NF_CD_PROVISION_LAB',
        'MAGIC: DB "NFU1"': 'MAGIC: DB "NFC1"',
        'STR8N-F JOURNAL F UPGRADE / NFU1 / USB': 'C/D PROVISIONING LAB / NFC1 / USB',
        'Append one C/D page, then F only. Preserve boot policy.':
            'Lab modes: reserve then D/C fixture; or C100 policy append only. F GOLDEN.',
        'U_CHECK:\n        LDA PLAN+5\n        CMP #1\n        BNE U_BAD\n': '''U_CHECK:
        LDA PLAN+5
        CMP #2
        BEQ NFC_FIXTURE_CHECK
        CMP #1
        BNE U_BAD
        LDA U_INFO+4
        CMP #$C1
        BNE U_BAD
        BRA NFC_MODE_OK
NFC_FIXTURE_CHECK:
        LDA U_INFO+4
        CMP #$C4
        BNE U_BAD
NFC_MODE_OK:
''',
        'MIG_NEXT:\n        JSR U_APPEND\n        BCC FAIL_FLASH\n': '''MIG_NEXT:
        LDA INDEX
        BNE NFC_RESERVED
        JSR U_APPEND
        BCC FAIL_FLASH
        LDA PLAN+5
        CMP #1
        BEQ NFC_APPEND_DONE
NFC_RESERVED:
''',
        # Mode 1 never reaches the sector writer; its sole row describes C.
        # Mode 2 retains the native D-then-C address/commit validation.
        'PLAN_FIRST:\n        LDA PLAN+5\n        CMP #2\n        BEQ PLAN_D\n': '''PLAN_FIRST:
        LDA PLAN+5
        CMP #2
        BEQ PLAN_D
        CMP #1
        BEQ PLAN_C
''',
        'JOURNAL: append F erase reservation; no C/D erase':
            'JOURNAL: append reviewed NFC1 record before any sector operation',
        'JOURNAL: F reservation committed and full B3 verified':
            'JOURNAL: NFC1 record committed and full B3 verified',
        'MIG_END:\n': f'''NFC_APPEND_DONE:
        JSR GUARD_FINAL_ALL
        BCC FAIL_POSTIMAGE
        LDA #1
        STA LED
        LDX #<NFC_POLICY_DONE
        LDY #>NFC_POLICY_DONE
        JSR PRINT
        JMP ${recovery:04X}
NFC_POLICY_DONE: DB "NFC1 POLICY RESTORED; COUNTERS RETAINED; NO ERASE; MON NOT EXECUTED",13,10,0
MIG_END:
''',
    }
    for before, after in changes.items():
        if source.count(before) != 1:
            raise ValueError('Changed NFC1 source anchor: ' + before)
        source = source.replace(before, after)
    out.mkdir(parents=True)
    inputs = out / 'input'
    inputs.mkdir()
    (inputs / 'nf-migrate.asm').write_text(source, encoding='ascii', newline='\n')
    builder = module('nfc_base_builder', ROOT / 'migrator/build.py')
    builder.ROOT = inputs
    manifest = builder.build(out / 'assembled')
    manifest.update(protocol='NFC1', release_artifact=False, F_rebuilt=False,
        production_NFM1_changed=False, CPU_simulations=0, hardware_access=False,
        allowed_orders=[['C400 reservation', 'D', 'C'], ['C100 policy append only']],
        modes={'2': 'fixture: exactly one D erase and one C erase',
               '1': 'policy: zero erases, C100 page programming only'},
        operations_always_erase=False, F_write_path=False,
        journal_commit_address='sealed append page + 00FF; sector fixture commits at D0FF/C0FF',
        recovery_return=f'{recovery:04X}; mode 1 only, matching golden BASE1 required',
        inputs_sha256={name: sha((ROOT / name).read_bytes()) for name in (
            'tools/build_cd_provisioning_lab.py', 'migrator/upgrade/build.py',
            'migrator/upgrade/reserve.inc', 'migrator/nf-migrate.asm', 'migrator/build.py',
            'src/core/boot-symbols.inc')})
    (out / 'assembled/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('NFC1 RAM lab built once; public NFM1/CONFIG, F and kit unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(parser.parse_args().out)
