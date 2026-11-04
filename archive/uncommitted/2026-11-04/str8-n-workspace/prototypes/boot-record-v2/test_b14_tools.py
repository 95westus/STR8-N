"""Rebased OIP1 protection/readback/interruption suite via b14 raw autorun."""
from pathlib import Path
import test_opaque_installer as frozen

source=Path(frozen.__file__).read_text()
a=source.index("spec = importlib.util.spec_from_file_location('boot_record_v2_tests'")
b=source.index('ROOT = base.ROOT',a)
source=source[:a]+'from test_b14_core import load_core,fast_idle\nbase,_=load_core()\n'+source[b:]
a=source.index('            self.command(b\'L\\r\', b\'SEND HEADER+BIN')
b=source.index('        else:',a)
source=source[:a]+'''            self.command(b'L\\r', b'SEND BIN\\r\\n')
            self.command(binary, PROMPT)
'''+source[b:]
source=source.replace('self.m.ram[0x2000:0x2000 + len(binary)]','self.m.ram[0x0200:0x0200 + len(binary)]')
source=source.replace('self.c.pc = 0x2000','self.c.pc = 0x0200')
source=source.replace('h.m.ram[0x200:0x2000]','h.m.ram[0x200:0x200]')
source=source.replace('            self.steps += 1','            self.steps += 1\n            fast_idle(self)')
source=source.replace('opaque-installer-cpu-','b14-opaque-installer-cpu-')
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
