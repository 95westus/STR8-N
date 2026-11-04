"""Exact b14/native-SNBT -> b15 preserving native transaction planner."""
from pathlib import Path
import deployment_b07 as frozen
source=Path(frozen.__file__).read_text()
for before,after in [('BUILD/pr04-b06-startup-r2','BUILD/pr04-b14-raw-r4'),
    (frozen.BASE_SHA,'fe3da8b96b0e2111533fc61504a7f013f83f5b1e54e3d246c390ee894ce83018'),
    ('0x80000006','0x8000000E'),('b06','b14'),
    ('import deployment_b07_model','import deployment_b15_model'),
    ('deployment_b07_model.qualify','deployment_b15_model.qualify')]:
    assert before in source;source=source.replace(before,after)
source=source.replace("        check = Path(temp) / 'plan'",
    "        assert Path(temp).resolve().parent == folder.parent.resolve() and Path(temp).resolve().is_relative_to(ROOT.resolve())\n"
    "        check = Path(temp) / 'plan'")
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
