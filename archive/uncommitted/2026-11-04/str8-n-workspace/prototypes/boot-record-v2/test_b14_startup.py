"""b13 startup matrix adapted only for b14's removed RAM-valid/R state."""
from pathlib import Path
import test_b13_startup as frozen
source=Path(frozen.__file__).read_text().replace('from build_b13 import ROOT','from build_b14 import ROOT')
source=source.replace("assert item.m.ram[item.b['RL_VALID']]==0 and item.m.ram[0xec]==0","assert item.m.ram[0xec]==0")
source=source.replace("assert item.m.ram[item.b['RL_VALID']]==0;item.preserved()","item.preserved()")
source=source.replace('b13-startup-','b14-startup-')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
