"""Use the unchanged native transaction model with the b09 planner."""
from pathlib import Path
import deployment_b07_model as frozen

source = Path(frozen.__file__).read_text()
assert source.count('import deployment_b07 as planning') == 1
source = source.replace('import deployment_b07 as planning', 'import deployment_b09 as planning')
exec(compile(source, str(Path(frozen.__file__)), 'exec'), globals())
