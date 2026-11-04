"""Exact b12/native-SNBT to b14 preserving transaction planner."""
from pathlib import Path
import deployment_b07 as frozen
source=Path(frozen.__file__).read_text()
for before,after in [('BUILD/pr04-b06-startup-r2','BUILD/pr04-b12-no-readback-r4'),
    (frozen.BASE_SHA,'1c9e17964949da871fceca047254431fb1c539d6dd51cadaf25aa6ec42beabb6'),
    ('0x80000006','0x8000000C'),('b06','b12'),
    ('import deployment_b07_model','import deployment_b14_model'),
    ('deployment_b07_model.qualify','deployment_b14_model.qualify')]:
    assert before in source;source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
