"""Run the complete b08 regression/selection suite against the b09 identity."""
from pathlib import Path
import test_b08 as previous


if __name__ == '__main__':
    source = Path(previous.__file__).read_text()
    source = source.replace('2.0proto b08', '2.0proto b09').replace('0x80000008', '0x80000009')
    source = source.replace("'b08-selection-tests.json'", "'b09-selection-tests.json'")
    namespace = dict(__file__=__file__, __name__='__main__')
    exec(compile(source, str(Path(previous.__file__)), 'exec'), namespace)
