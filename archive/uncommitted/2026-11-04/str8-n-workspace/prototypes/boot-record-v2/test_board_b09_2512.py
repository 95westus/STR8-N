"""Execute the frozen exact-runtime shim and reset watcher tests for b09."""
from pathlib import Path
import test_board_b07_2512 as frozen

source = Path(frozen.__file__).read_text()
for before, after in (
    ('import board_b07_2512 as board', 'import board_b09_2512 as board'),
    ('source-b06', 'source-b07'),
    ('target-b07', 'target-b09'),
    ('Boot : 3 2 1 0', 'Boot : 6 5 4 3 2 1 0'),
    ('2.0proto b07', '2.0proto b09'),
    ("raw.replace(b'3 2 1 0', b'3')", "raw.replace(b'6 5 4 3 2 1 0', b'6')"),
):
    assert before in source, before
    source = source.replace(before, after)
exec(compile(source, str(Path(frozen.__file__)), 'exec'), globals())
