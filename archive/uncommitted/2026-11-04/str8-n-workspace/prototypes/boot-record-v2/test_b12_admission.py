"""Positive and negative offline tests of the exact b12 deployment admission."""
import argparse
import builtins
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

real_import = builtins.__import__


def deny_serial(name, *args, **kwargs):
    if name == 'serial' or name.startswith('serial.'):
        raise AssertionError('Offline admission imported serial')
    return real_import(name, *args, **kwargs)


with patch.object(builtins, '__import__', deny_serial):
    import board_b12_2512 as board


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build','plan','run','authorization'):
        p.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    build,plan,run = (getattr(args,name).resolve() for name in ('build','plan','run'))
    auth = board.r.read(args.authorization)
    proof = board.prepare(build,plan,run)
    assert board.admission(build,plan,run,auth) == proof
    rows = [dict(case='exact-owner-scope-and-qualified-preimage',passed=True)]
    actual_read = board.r.read
    mutations = (
        ('no-V-host-probe',build/'b12-probe-host-tests.json',lambda x:x['cases'][0].__setitem__('passed',False)),
        ('independent-MON-CPU-proof',build/'b12-deployment-cpu-tests.json',lambda x:x['cases'][0].__setitem__('MON_independent_RAM_readback_verified',False)),
        ('selection-missing-CPU',build/'b12-selection-tests.json',lambda x:x.__setitem__('cases',x['cases'][:1])),
        ('core-component-hash',build/'cpu-tests.json',lambda x:x['component_hashes'].__setitem__('f-offline-component.bin','0'*64)),
        ('USB-wait-length',build/'b12-usb-wait-65c02.json',lambda x:x.__setitem__('cycles',24_000_000)),
        ('host-stale-preimage-protection',build/'native-host-cpu-tests.json',lambda x:x['cases'][0].__setitem__('stale_MON_preimage_refused_before_write',False)),
        ('native-commit-order',plan/'model-proof.json',lambda x:x['models'][0].__setitem__('native_commit255_last',False)),
    )
    for label,path,mutate in mutations:
        def altered(candidate):
            value = actual_read(candidate)
            if Path(candidate).resolve() == path.resolve():
                value = deepcopy(value); mutate(value)
            return value
        with patch.object(board.r,'read',side_effect=altered):
            try:
                board.bindings(build,plan)
            except (ValueError,AssertionError):
                pass
            else:
                raise AssertionError('Altered proof admitted: '+label)
        rows.append(dict(case='refuse-'+label,passed=True,files_unchanged=True))
    for label,key,value in (
        ('different-firmware','firmware_sha256','0'*64),
        ('different-plan','plan_sha256','0'*64),
        ('other-boards','other_boards_authorized',True),
        ('RTC-resume','RTC_campaign_resume_authorized',True),
        ('inactive-feature-scope','bench_features_inactive_accepted',False),
    ):
        changed = deepcopy(auth); changed[key] = value
        try:
            board.admission(build,plan,run,changed)
        except ValueError:
            pass
        else:
            raise AssertionError('Altered authorization admitted: '+label)
        rows.append(dict(case='refuse-owner-'+label,passed=True,files_unchanged=True))
    board.save(run/'offline-admission-tests.json',dict(passed=True,hardware=False,serial_access=False,
        checks=len(rows),cases=rows,adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
        admission_sha256=board.r.sha((run/'admission.json').read_bytes()),
        checker_sha256=board.r.sha(Path(__file__).read_bytes())))
    print('PASS b12 offline admission',len(rows),flush=True)


if __name__ == '__main__':
    main()
