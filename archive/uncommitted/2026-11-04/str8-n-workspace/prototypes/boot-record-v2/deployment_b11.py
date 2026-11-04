"""Exact b10 native-SNBT to b11 preservation planner."""
from pathlib import Path
import deployment_b07 as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('BUILD/pr04-b06-startup-r2','BUILD/pr04-b10-wait'),
    (frozen.BASE_SHA,'4be0a7e45a3582f82095a79c6dfb3997647fc7dc9aca25e540e2735856661cae'),
    ('0x80000006','0x8000000A'),('b06','b10'),
    ('import deployment_b07_model','import deployment_b11_model'),
    ('deployment_b07_model.qualify','deployment_b11_model.qualify'),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
