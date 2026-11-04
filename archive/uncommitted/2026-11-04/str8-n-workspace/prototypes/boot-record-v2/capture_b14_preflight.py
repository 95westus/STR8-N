"""Qualified read-only preflight bound to 2512's installed b12 source."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import preflight as frozen
source=Path(frozen.__file__).read_text()
for before,after in [
    ('import board_b07_2512 as board','import board_b12_2512 as board'),
    ('BUILD/pr04-b07-startup','BUILD/pr04-b12-no-readback-r4'),
    ('tmp/pr04-b07-2512-native-plan','tmp/pr04-b12-2512-native-plan'),
    ('output/qualification/pr04-b07-2512-install-r2','output/qualification/pr04-b12-2512-install'),
    ('0x80000007','0x8000000C'),('2.0proto b07','2.0proto b12')]:
    assert before in source;source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
