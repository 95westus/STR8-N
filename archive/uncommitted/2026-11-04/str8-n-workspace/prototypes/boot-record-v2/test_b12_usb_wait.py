"""Measure b12's complete unchanged two-second startup wait."""
from pathlib import Path
import test_b09_usb_wait as frozen
source=Path(frozen.__file__).read_text().replace('2.0proto b09','2.0proto b12').replace('b09-usb-wait-','b12-usb-wait-')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
