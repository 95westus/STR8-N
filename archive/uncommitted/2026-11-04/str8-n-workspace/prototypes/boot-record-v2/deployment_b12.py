"""Exact b11 native-SNBT to b12 preservation planner."""
from pathlib import Path
import deployment_b07 as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('BUILD/pr04-b06-startup-r2','BUILD/pr04-b11-help-r7'),
    (frozen.BASE_SHA,'9d44c608758f17363928aa020cf2a06174856830c02eb75a0c2d75c84d1e774d'),
    ('0x80000006','0x8000000B'),('b06','b11'),
    ('import deployment_b07_model','import deployment_b12_model'),
    ('deployment_b07_model.qualify','deployment_b12_model.qualify'),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
