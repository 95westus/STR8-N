"""Exact b12 REC/MON B normalization; no RAM/flash writes or physical reset."""
from pathlib import Path
import normalize_b12_source as frozen
source=Path(frozen.__file__).read_text().replace('capture_b12_preflight','capture_b14_preflight').replace('capture_b12_backup','capture_b14_backup')
source=source.replace('2.0proto b11','2.0proto b12').replace('normalize-b11-source','normalize-b12-source')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
