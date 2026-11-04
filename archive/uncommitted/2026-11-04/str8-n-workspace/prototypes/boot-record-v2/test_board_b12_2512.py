"""Exact source b11/target b12 runtime shim and zero-TX reset watcher checks."""
from pathlib import Path
import test_board_b07_2512 as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('import board_b07_2512 as board','import board_b12_2512 as board'),
    ('source-b06','source-b11'),('target-b07','target-b12'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),('2.0proto b07','2.0proto b12'),
    ("raw.replace(b'3 2 1 0', b'3')","raw.replace(b'6 5 4 3 2 1 0', b'6')"),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
