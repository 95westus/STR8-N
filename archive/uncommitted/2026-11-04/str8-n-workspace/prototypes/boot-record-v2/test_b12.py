"""Full b12 regression and selection suite; explicit D/V test adaptation."""
from pathlib import Path
import test_b08 as frozen
from build_b12 import RECOVERY

if __name__=='__main__':
    source=Path(frozen.__file__).read_text()
    source=source.replace('import test_b07 as previous','import test_b12_core as previous')
    source=source.replace('2.0proto b08','2.0proto b12').replace('0x80000008','0x8000000C')
    source=source.replace('Recovery L/R/D/V A/B 0-3 C1/2/3',RECOVERY)
    source=source.replace('b08-selection-tests.json','b12-selection-tests.json')
    exec(compile(source,str(Path(frozen.__file__)),'exec'),dict(__file__=__file__,__name__='__main__'))
