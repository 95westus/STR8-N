"""Read-only source binding to 2512's completed b14 installation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import preflight as frozen
source=Path(frozen.__file__).read_text()
for before,after in [
    ('import board_b07_2512 as board','import board_b14_2512 as board'),
    ('BUILD/pr04-b07-startup','BUILD/pr04-b14-raw-r4'),
    ('tmp/pr04-b07-2512-native-plan','tmp/pr04-b14-2512-native-plan'),
    ('output/qualification/pr04-b07-2512-install-r2','output/qualification/pr04-b14-2512-install'),
    ('0x80000007','0x8000000E'),('2.0proto b07','2.0proto b14')]:
    assert before in source;source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
