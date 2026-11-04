"""Unchanged native transaction model, bound to the b11 planner."""
from pathlib import Path
import deployment_b07_model as frozen
source=Path(frozen.__file__).read_text().replace('import deployment_b07 as planning','import deployment_b11 as planning')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
