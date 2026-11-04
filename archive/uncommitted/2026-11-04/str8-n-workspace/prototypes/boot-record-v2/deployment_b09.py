"""Exact b07 native-SNBT to b09 planner, retaining the qualified transaction."""
from pathlib import Path
import deployment_b07 as frozen

source = Path(frozen.__file__).read_text()
for before, after in (
    ('BUILD/pr04-b06-startup-r2', 'BUILD/pr04-b07-startup'),
    (frozen.BASE_SHA, '77bf4763c4ce582dc0572c12bafb690e34c01b5ca39f5a1c513589edebc01ede'),
    ('0x80000006', '0x80000007'),
    ('b06', 'b07'),
    ('import deployment_b07_model', 'import deployment_b09_model'),
    ('deployment_b07_model.qualify', 'deployment_b09_model.qualify'),
):
    assert before in source, before
    source = source.replace(before, after)
exec(compile(source, str(Path(frozen.__file__)), 'exec'), globals())
