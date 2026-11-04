"""Fresh full b14 backup before the owner's 2512 MON removal test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import fast_backup as frozen
source=Path(frozen.__file__).read_text()
for before,after in [('import preflight as pf','import capture_mon_absent_preflight as pf'),
    ('reset-ff-ram-fast-backup','capture-mon-absent-source'),
    ('fast-backup-host-tests.json','capture-mon-absent-backup-tests.json'),
    ('test_fast_backup.py','test_capture_mon_absent_backup.py'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),('2.0proto b07','2.0proto b14')]:
    assert before in source;source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
