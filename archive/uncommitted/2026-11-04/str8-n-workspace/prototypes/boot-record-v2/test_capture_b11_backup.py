"""Rerun buffered escrow/refusal/restore tests for the b10 source backup."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import test_fast_backup as frozen

source = Path(frozen.__file__).read_text()
for before,after in (
    ('import fast_backup as h','import capture_b11_backup as h'),
    ('reset-ff-ram-fast-backup','capture-b11-source'),
    ('fast-backup-host-tests.json','capture-b11-backup-tests.json'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),
    ('2.0proto b07','2.0proto b10'),
):
    assert before in source,before
    source = source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
