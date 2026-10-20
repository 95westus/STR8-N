"""Prepare a separate v1g kit offline; never executes a board operation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;PARENT=HERE.parent/'rc1-debugger'

def main():
    spec=importlib.util.spec_from_file_location('parent_prepare',PARENT/'prepare_board_test.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.HERE=HERE;module.main()
    out=Path(sys.argv[sys.argv.index('--out')+1]).resolve();path=out/'board-test-manifest.json'
    manifest=json.loads(path.read_text());manifest.update(candidate_build='v1g-BRK82-84-edge-fix',promotion_held=True,
        hardware_qualified=False,soak_qualified=False,native_applications_tested=False)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Offline-prepared only; not installed or soaked; promotion held')

if __name__=='__main__':main()
