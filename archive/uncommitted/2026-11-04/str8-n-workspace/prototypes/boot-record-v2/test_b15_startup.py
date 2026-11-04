"""Unchanged full startup/drain/J3 instruction tests against the b15 build."""
from pathlib import Path
source=(Path(__file__).parent/'test_b14_startup.py').read_text()
source=source.replace('from build_b14 import ROOT','from build_b15 import ROOT')
source=source.replace("'b14-startup-'","'b15-startup-'")
exec(compile(source,str(Path(__file__).parent/'test_b14_startup.py'),'exec'),dict(__file__=__file__,__name__='__main__'))
