"""Compare a fresh independent beta34 build with the candidate artifacts."""
import hashlib
import json
from pathlib import Path
import tempfile
import build_v2_beta34 as b


def main():
    candidate=b.ROOT/'BUILD/v2-beta34-candidate'
    directory=Path(tempfile.mkdtemp(prefix='beta34-rebuild-',dir=b.ROOT/'BUILD'))
    b.OUT=directory/'candidate';b.main()
    names=list(json.loads((candidate/'build.json').read_text())['artifacts'])+['build.json']+[f'candidate/b{i}.bin' for i in range(4)]
    for n in names:assert (candidate/n).read_bytes()==(b.OUT/n).read_bytes(),n
    result=dict(passed=True,build_sha256=hashlib.sha256((candidate/'build.json').read_bytes()).hexdigest(),
        files=names,identical_files=len(names),independent_directory=str(b.OUT),board_access=False)
    (candidate/'beta34-reproducibility.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS independent rebuild:',len(names),'identical files',flush=True)


if __name__=='__main__':main()
