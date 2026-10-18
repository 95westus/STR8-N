"""Independently replay planned rows and check whole-record publication order."""
import argparse,json
from pathlib import Path
import plan_bf1_2512_legacy as p

def audit(folder):
    info=p.read(folder/'plan.json');tx=info['transaction'];cells=p.migration.read_s19(folder/'installer-model-only.s19')[0]
    expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    source=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)]
    assert p.hashes(source)==info['source_sha256']
    # All source bytes are bound by the installer's initial all-bank guard.
    # Unchanged body sectors may already match; changed ones must arrive first.
    seen=[bytearray(b'\1'*32768) for _ in range(4)];state=list(map(bytearray,source));issues=[];published=[]
    for n,op in enumerate(tx['operations'][1:]):
        body=(folder/f'transfer-{n:02d}.bin').read_bytes();assert len(body)==4096
        bank=op['bank'];off=op['address']-0x8000;state[bank][off:off+4096]=body;seen[bank][off:off+4096]=b'\1'*4096
        address=op['commit_address']
        if address is None:continue
        value=expected[bank][address-0x8000];state[bank][address-0x8000]=value
        if value==0x3f and address==op['address']+3:
            header=expected[bank][off:off+24];assert header[:4]==b'SR\1\x3f'
            length=24+int.from_bytes(header[6:8],'little');assert off+length<=32768
            complete=all(seen[bank][off:off+length]) and state[bank][off:off+length]==expected[bank][off:off+length]
            item=dict(bank=bank,address=op['address'],record=header[8:24].rstrip(b'\0').decode('ascii'),bytes=length,row=n,body_complete_before_publication=bool(complete))
            published.append(item)
            if not complete:issues.append(item)
    return dict(plan=str(folder.resolve()),plan_sha256=p.sha((folder/'plan.json').read_bytes()),passed=not issues,records=published,issues=issues)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plans',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
    checks=[audit(path.parent) for path in sorted(a.plans.glob('*/plan.json'))]
    assert checks
    report=dict(passed=all(x['passed'] for x in checks),checks=checks,auditor_source_sha256=p.sha(Path(__file__).read_bytes()),scope='Conservative row publication proof: all new record body bytes must have been transferred before its commit',board_access=False)
    a.out.write_text(json.dumps(report,indent=2)+'\n');print('PASS' if report['passed'] else 'FAIL',len(checks),'plan publication-order checks')
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
