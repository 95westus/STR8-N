"""2512 b12 fresh RAM-escrowed source backup for b14 deployment."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reset-ff-ram'))
import fast_backup as frozen
source=Path(frozen.__file__).read_text()
for before,after in [('import preflight as pf','import capture_b14_preflight as pf'),
    ('reset-ff-ram-fast-backup','capture-b14-source'),
    ('fast-backup-host-tests.json','capture-b14-backup-tests.json'),
    ('test_fast_backup.py','test_capture_b14_backup.py'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),('2.0proto b07','2.0proto b12')]:
    assert before in source;source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
