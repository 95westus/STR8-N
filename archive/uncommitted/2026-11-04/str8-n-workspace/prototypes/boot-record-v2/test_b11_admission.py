"""Rerun positive/negative exact admission checks for b11."""
from pathlib import Path
import test_b10_admission as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('import board_b10_2512 as board','import board_b11_2512 as board'),
    ('b10-selection-tests.json','b11-selection-tests.json'),('b10-usb-wait-','b11-usb-wait-'),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
