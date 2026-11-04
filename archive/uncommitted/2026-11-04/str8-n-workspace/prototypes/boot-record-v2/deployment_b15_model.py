"""Frozen native reservation and flash transaction model, b15 planner binding."""
from pathlib import Path
import deployment_b07_model as frozen
source=Path(frozen.__file__).read_text().replace('import deployment_b07 as planning','import deployment_b15 as planning')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
