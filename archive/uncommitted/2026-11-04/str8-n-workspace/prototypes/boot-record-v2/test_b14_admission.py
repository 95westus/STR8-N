"""Positive and tamper/scope refusal checks before any b14 flash admission."""
import argparse,builtins
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import board_b14_2512 as board

def main():
    p=argparse.ArgumentParser()
    for key in ['build','plan','authorization','run']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();build,plan,run=args.build.resolve(),args.plan.resolve(),args.run.resolve()
    auth=board.r.read(args.authorization);proof=board.prepare(build,plan,run)
    assert board.admission(build,plan,run,auth)==proof
    rows=[dict(case='exact-fresh-source-and-qualified-target-owner-scope',passed=True)]
    actual=board.r.read
    for label,path,mutate in [
        ('firmware-checks',build/'b14-qualification.json',lambda v:v.__setitem__('total_test_groups',617)),
        ('native-commit',plan/'model-proof.json',lambda v:v['models'][0].__setitem__('native_commit255_last',False)),
        ('raw-load-address',build/'prototype-report.json',lambda v:v['raw_loader'].__setitem__('load_start',0x2000)),
        ('host-checks',build/'b14-native-host-cpu-tests.json',lambda v:v['cases'][0].__setitem__('stale_MON_preimage_refused_before_write',False)),
        ('probe-checks',build/'b14-probe-host-tests.json',lambda v:v['cases'][0].__setitem__('passed',False)),
        ('RAM-readback',build/'b14-deployment-cpu-tests.json',lambda v:v['cases'][0].__setitem__('MON_independent_RAM_readback_verified',False)),
        ('escrow-binding',plan/'plan.json',lambda v:v.__setitem__('application_ram_sha256','0'*64))]:
        def altered(candidate):
            v=actual(candidate)
            if Path(candidate).resolve()==path.resolve():v=deepcopy(v);mutate(v)
            return v
        with patch.object(board.r,'read',side_effect=altered):
            try:board.bindings(build,plan)
            except (ValueError,AssertionError):pass
            else:raise AssertionError('Tampered proof accepted: '+label)
        rows.append(dict(case='refuse-'+label,passed=True))
    for key,value in [('board','2604'),('other_boards_authorized',True),('RTC_campaign_resume_authorized',True),
                      ('bench_features_inactive_accepted',False),('firmware_sha256','0'*64),('plan_sha256','0'*64)]:
        wrong=deepcopy(auth);wrong[key]=value
        try:board.admission(build,plan,run,wrong)
        except ValueError:pass
        else:raise AssertionError('Wrong authorization accepted: '+key)
        rows.append(dict(case='refuse-authorization-'+key,passed=True))
    assert 'serial' not in __import__('sys').modules
    board.save(run/'offline-admission-tests.json',dict(passed=True,hardware=False,serial_access=False,checks=len(rows),cases=rows,
        checker_sha256=board.r.sha(Path(__file__).read_bytes()),adapter_sha256=board.r.sha(Path(board.__file__).read_bytes())))
    print('PASS b14 positive/negative admission',len(rows),flush=True)

if __name__=='__main__':main()
