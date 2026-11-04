"""2512-only b09 adapter; qualified b07 protocol with explicit new bindings."""
from pathlib import Path
import board_b07_2512 as frozen

source = Path(frozen.__file__).read_text()
for before, after in (
    ('b06 -> b07', 'b07 -> b09'),
    ('import deployment_b07 as deployment_plan', 'import deployment_b09 as deployment_plan'),
    ('from b07_admission import bindings', 'from b09_admission import bindings'),
    ('deploy-native-b07-bench-core', 'deploy-native-b09-bench-core'),
    ('Boot : 3 2 1 0', 'Boot : 6 5 4 3 2 1 0'),
    ('RAM recovery L/R/D/V A/B', 'Recovery L/R/D/V A/B 0-3'),
    ("source='2.0proto b06'", "source='2.0proto b07'"),
    ("'source-b06'", "'source-b07'"),
    ('native b06 repeated capture', 'native b07 repeated capture'),
    ('pr04-b07-bench-core', 'pr04-b09-bench-core'),
    ('b07 startup', 'b09 startup'),
    ('ordered b07 physical', 'ordered b09 physical'),
):
    assert before in source, before
    source = source.replace(before, after)
before = '        state.update(application_RAM_restore_pending=False, RAM_restored=True,'
after = '''        owner_zp = (Path(plan) / 'capture/owner-zp.bin').read_bytes()
        r.require(len(owner_zp) == 0xe0, 'Fresh owner ZP escrow missing')
        for _ in range(2):
            r.require(link.dump(0, 0xdf) == owner_zp, 'Original owner ZP00-DF differs')
        state.update(owner_ZP_preserved=True, final_owner_ZP_rereads=2)
''' + before
assert source.count(before) == 1
source = source.replace(before, after)
exec(compile(source, str(Path(frozen.__file__)), 'exec'), globals())
