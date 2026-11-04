"""Retain b14's core/selection/bench checks for b15 identity and receipts."""
from pathlib import Path
source=(Path(__file__).parent/'test_b14.py').read_text()
source=source.replace('import build_b14','import build_b15 as build_b14')
source=source.replace('2.0proto b14','2.0proto b15').replace('0x8000000E','0x8000000F')
source=source.replace('b14-selection-tests.json','b15-selection-tests.json')
exec(compile(source,str(Path(__file__).parent/'test_b14.py'),'exec'),dict(__file__=__file__,__name__='__main__'))
