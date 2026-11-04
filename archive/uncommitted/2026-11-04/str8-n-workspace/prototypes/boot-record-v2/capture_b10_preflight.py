"""Use the qualified read-only preflight policy for the installed b09 source."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import preflight as frozen

source = Path(frozen.__file__).read_text()
for before,after in (
    ('import board_b07_2512 as board','import board_b09_2512 as board'),
    ('BUILD/pr04-b07-startup','BUILD/pr04-b09-usb2'),
    ('tmp/pr04-b07-2512-native-plan','tmp/pr04-b09-2512-native-plan'),
    ('output/qualification/pr04-b07-2512-install-r2','output/qualification/pr04-b09-2512-install'),
    ('0x80000007','0x80000009'),('2.0proto b07','2.0proto b09'),
):
    assert before in source,before
    source = source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
