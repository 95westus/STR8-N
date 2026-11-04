"""Exact b09 native-SNBT to b10 preservation planner."""
from pathlib import Path
import deployment_b07 as frozen
source=Path(frozen.__file__).read_text()
for before,after in (
    ('BUILD/pr04-b06-startup-r2','BUILD/pr04-b09-usb2'),
    (frozen.BASE_SHA,'3611e56a64312884b4a2533baa1c3a388573f12302b9156f0a67fb13b1bec4db'),
    ('0x80000006','0x80000009'),('b06','b09'),
    ('import deployment_b07_model','import deployment_b10_model'),
    ('deployment_b07_model.qualify','deployment_b10_model.qualify'),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
