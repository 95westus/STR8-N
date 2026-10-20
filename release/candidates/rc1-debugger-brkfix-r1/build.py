"""Build the separate v1g BRK edge-fix candidate offline. No board access."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'rc1-debugger'
PARENT_BUILDER_SHA='af1ebc22f0ff8c343d50e2cbb36ab30e6eb7f16f3e06bf2ab64beb0dda023e06'
PARENT_FIRMWARE_SHA='923c8fee01310b873e89cc5e8982778e25fd425ccb9050735fb07604ef6228ba'
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert SHA(PARENT/'build.py')==PARENT_BUILDER_SHA,'Parent builder changed; review before rebuilding'
    spec=importlib.util.spec_from_file_location('maint_corrected_builder',PARENT/'build.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    builder.HERE=HERE
    builder.main()
    out=Path(sys.argv[sys.argv.index('--out')+1]).resolve()
    provenance=dict(candidate_build='v1g-BRK82-84-edge-fix',parent_candidate_build='v1f-MAINT-corrected',
        parent_firmware_sha256=PARENT_FIRMWARE_SHA,parent_builder_sha256=PARENT_BUILDER_SHA,
        fixes=['DBG1-REVIEW-82-ZERO','DBG1-REVIEW-84-END'],promotion_held=True,
        hardware_qualified=False,soak_qualified=False,board_access=False,native_debugging=False,native_applications_tested=False,
        candidate_source_sha256={p.name:SHA(p) for p in sorted((HERE/'source').iterdir()) if p.is_file()})
    path=out/'debugger-build.json';report=json.loads(path.read_text());report.update(provenance)
    path.write_text(json.dumps(report,indent=2)+'\n')
    provenance['firmware_sha256']=report['firmware_sha256']
    (out/'candidate-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

if __name__=='__main__':main()
