"""Rerun positive/negative exact admission checks for b10."""
from pathlib import Path
import test_b09_admission as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('import board_b09_2512 as board','import board_b10_2512 as board'),
    ('b09-selection-tests.json','b10-selection-tests.json'),('b09-usb-wait-','b10-usb-wait-'),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
