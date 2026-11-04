"""Run the full frozen regression/selection suite with the b11 identity."""
from pathlib import Path
import test_b08 as frozen

if __name__ == '__main__':
    source = Path(frozen.__file__).read_text()
    source = source.replace('2.0proto b08','2.0proto b11').replace('0x80000008','0x8000000B')
    source = source.replace("'b08-selection-tests.json'","'b11-selection-tests.json'")
    exec(compile(source,str(Path(frozen.__file__)),'exec'),dict(__file__=__file__,__name__='__main__'))
