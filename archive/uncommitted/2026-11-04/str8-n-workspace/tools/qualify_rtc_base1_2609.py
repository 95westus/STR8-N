"""Offline admission/adapter checks; no CPU rebuild or board/network access."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import rtc_base1_2609 as target


def main():
    out = target.Q/'rtc-drift-3hour-20261028/setup-verification/base1-2609-20261029'
    out.mkdir(parents=True, exist_ok=False)
    original_read = target.driver.read
    with patch.object(target.driver.transport, 'RecoveryLink', side_effect=AssertionError('USB forbidden in offline proof')), patch.object(target.driver, 'ntp_sample', side_effect=AssertionError('Network forbidden in offline proof')):
        initial = target.inputs()
        tests = [dict(case='valid exact 2609 receipt/escrow/F/CPU/USB routing', passed=True)]
        for label, update in (
            ('changed F', {'current_F_sha256':'0'*64}),
            ('wrong board', {'board':'2512'}),
            ('changed firmware profile', {'current_firmware_profile':'legacy'}),
            ('owner application running', {'owner_application_running':True}),
            ('RAM restore pending', {'application_RAM_restore_pending':True}),
            ('worker active', {'some_other_worker_active':True}),
            ('one shot in progress', {'one_shot_collection_active':True}),
            ('physical reset pending', {'physical_reset_pending':True}),
            ('changed flash bank', {'current_physical_bank_sha256':dict(initial[0]['current_physical_bank_sha256'],B0='0'*64)}),
            ('changed wear', {'current_tracked_erase_counts':{'C':78,'D':47,'F':32}}),
        ):
            changed = copy.deepcopy(initial[0]);changed.update(update)
            def guarded_read(path):
                return changed if Path(path).resolve()==target.driver.MARK.resolve() else original_read(path)
            with patch.object(target.driver, 'read', side_effect=guarded_read):
                try:
                    target.inputs()
                except AssertionError:
                    tests.append(dict(case=label, passed=True, rejected_before_hardware=True))
                else:
                    raise AssertionError('Admission accepted '+label)
    assert target.driver.collect.__globals__['inputs'] is target.inputs
    assert target.driver.MARK == target.Q/'device-operations/2609.json'
    assert "RecoveryLink('COM8',log,usb_serial='A10MPQXCA')" in target.DRIVER_SOURCE
    assert "r=dict(board='2609',usb_serial='A10MPQXCA',port='COM8'" in target.DRIVER_SOURCE
    assert "base=state['baselines']['2609']" in target.AUDIT_SOURCE
    assert "r['driver_sha256']==sha(Path(__file__))" in target.AUDIT_SOURCE
    proof = dict(passed=True, offline=True, hardware_ports_opened=False, network_ports_opened=False,
        tests=tests, unchanged_RAM_binary_sha256=initial[4]['sha256'],
        inherited_CPU_model='65C02 only; 65C816 emulation requires the separate live qualification receipt',
        inherited_I2C_fault_cases=initial[4]['checks'],
        original_driver_sha256=target.DRIVER_SHA, original_auditor_sha256=target.AUDIT_SHA,
        adapter_sha256=target.sha(target.__file__), test_sha256=target.sha(__file__),
        campaign_sha256=target.sha(target.campaign.__file__), source_receipt_sha256=target.RECEIPT_SHA,
        original_capture_sha256=target.CAPTURE_SHA)
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n', encoding='utf-8')
    for name, text in (('adapted-driver.py',target.DRIVER_SOURCE), ('adapted-audit.py',target.AUDIT_SOURCE)):
        (out/name).write_text(text,encoding='utf-8')
    for path in (Path(target.__file__),Path(target.campaign.__file__),Path(__file__)):
        (out/path.name).write_bytes(path.read_bytes())
    print(json.dumps(dict(passed=True,cases=len(tests),proof=str(out/'proof.json'),no_hardware=True),indent=2))


if __name__=='__main__':
    main()
