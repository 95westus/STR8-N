"""Rehearse the complete offline battery installer on synthetic bank backups."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-battery')
import json
import sys
import tempfile

import test_v2_battery as battery
import prepare_v2_battery as planner
import test_v2_rtc_upgrade as model


def main():
    planner.audit()
    cpu, memory = battery.fresh()
    banks = [bytearray(b) for b in memory.banks]
    base = planner.BASE
    banks[3][0x6000:0x7000] = (base/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    banks[2][0x4800:0x5200] = (base/'boot-status/asset.bin').read_bytes()
    banks[2][0x5200:0x5C00] = b'\xff'*2560
    banks[1][0x3000:0x6000] = (base/'clock/storage.bin').read_bytes()
    # Real board-specific records must survive this synthetic installation.
    banks[3][0x1C20:0x1C40] = battery.record(battery.date(2025, 10, 1))
    banks[3][0x1C40:0x1C60] = battery.tz_record(-300)
    banks[3][0x1C60:0x1C80] = battery.name_record(b'2609')
    from pathlib import Path
    with tempfile.TemporaryDirectory(prefix='battery-update-', dir=battery.OUT) as name:
        root = Path(name)
        assert root.resolve().is_relative_to(battery.OUT.resolve())
        backup = root/'prior-verified'
        backup.mkdir()
        manifest = dict(board='MODEL', repeat_verified=True, banks=[])
        for i, data in enumerate(banks):
            (backup/f'b{i}.bin').write_bytes(data)
            (backup/f'b{i}-repeat.bin').write_bytes(data)
            manifest['banks'].append(dict(sha256=planner.sha(data)))
        (backup/'manifest.json').write_text(json.dumps(manifest)+'\n')
        planner.prepare(backup, root/'upgrade')
        plan_path = root/'upgrade/plan.json'
        plan = json.loads(plan_path.read_text())
        plan['model_only'] = True
        plan_path.write_text(json.dumps(plan, indent=2)+'\n')
        argv = sys.argv
        try:
            sys.argv = ['battery-model', '--root', str(root)]
            model.main()
        finally:
            sys.argv = argv
        report = json.loads((root/'upgrade/model-check.json').read_text())
        report.update(model_only=True, board_access=False, boards_flashed=False,
            artifacts=battery.META['artifacts'],
            battery_asset_sha256=battery.META['battery_asset_sha256'])
        (battery.OUT/'battery-update-test-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
