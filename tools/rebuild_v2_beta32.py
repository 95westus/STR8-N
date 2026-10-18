"""Independently rebuild beta32 and compare every published candidate byte."""
import json
import build_v2_beta32 as b

def main():
    original=b.OUT;other=b.ROOT/'BUILD/v2-beta32-rebuild-check';b.OUT=other;b.main()
    meta=b.read(original/'build.json')
    names=list(meta['artifacts'])+['build.json','xip/build.json','clock/build.json','candidate/manifest.json']+[f'candidate/b{i}.bin' for i in range(4)]
    for n in names:assert (original/n).read_bytes()==(other/n).read_bytes(),n
    report=dict(passed=True,version='2.0b30',build_sha256=b.sha((original/'build.json').read_bytes()),independent_output=str(other.resolve()),files_compared=len(names),byte_exact=True,board_access=False,boards_flashed=False)
    (original/'beta32-reproducibility-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS independent beta32 rebuild:',len(names),'files identical; no board access')

if __name__=='__main__':main()
