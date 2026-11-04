"""Exact b14 REC/MON normalization before the scoped MON-removal backup."""
from pathlib import Path
import normalize_b12_source as frozen
source=Path(frozen.__file__).read_text().replace('capture_b12_preflight','capture_mon_absent_preflight').replace('capture_b12_backup','capture_mon_absent_backup')
source=source.replace('2.0proto b11','2.0proto b14').replace('normalize-b11-source','normalize-b14-mon-removal')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
