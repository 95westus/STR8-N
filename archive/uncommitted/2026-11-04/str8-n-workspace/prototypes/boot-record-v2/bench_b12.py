"""Compose/check b12 bench image with corrected no-D/V feature descriptions."""
from pathlib import Path
import bench_target as frozen
source=Path(frozen.__file__).read_text()
source=source.replace('F RLP1 RAM load/run, download escrow and verified-range readback','F RLP1 RAM load/run; recovery RAM is disposable; D/V removed')
source=source.replace('loaded separately with range escrow','loaded separately; recovery tool load may overwrite RAM')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
