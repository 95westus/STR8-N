"""Exact b14 raw F load/run and MON independent RAM readback, both CPUs."""
from pathlib import Path
import test_b12_deployment_cpu as frozen
source=Path(frozen.__file__).read_text().replace('import board_b12_2512 as board','import board_b14_2512 as board')
source=source.replace('import test_opaque_installer as model','import test_b14_tools as model')
source=source.replace('0x8000000c','0x8000000e').replace('board.b12_mon_readback','board.b14_mon_readback')
source=source.replace('h.m.ram[0x2000:0x2000+len(body)]','h.m.ram[0x0200:0x0200+len(body)]')
source=source.replace('b12-deployment-cpu-tests','b14-deployment-cpu-tests')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
