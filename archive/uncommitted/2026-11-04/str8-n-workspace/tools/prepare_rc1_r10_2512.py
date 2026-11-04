"""Exact BF1 -> RC1 r10 preserving private 2512 plan and CPU rehearsal."""
import argparse,json,shutil,tempfile
from pathlib import Path
from rc1_r10_board import validate_capture
from installer.engine import runtime as r
from installer.common import save
from installer import model

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'output/releases/bf1-github-prerelease-2026-10-17/str8n-2.0bf1-firmware.bin'
SOURCE_SHA='3583598b5252684f6098b499e57264bf5c83f4c156d99b10717adcd5ba3c4369'
TEMPLATE=ROOT/'tools/installer/engine/template'
OWNED=json.loads((ROOT/'tools/installer/profiles.json').read_text())['owned_sectors']

def derive(build,cap):
    banks,ram=validate_capture(cap)
    before=SOURCE.read_bytes();assert len(before)==131072 and r.sha(before)==SOURCE_SHA
    target=(build/'firmware.bin').read_bytes();meta=r.read(build/'r10-build.json')
    assert len(target)==98304 and r.sha(target)==meta['firmware_sha256'] and meta['generation']==51 and meta['identity']=='rc1-r10-recovery1'
    for bank,address in OWNED:
        off=address-0x8000
        assert banks[bank][off:off+4096]==before[bank*32768+off:bank*32768+off+4096],f'Unknown BF1 source B{bank}:{address:04X}'
    assert banks[3][0x1000:0x1c00]==before[0x19000:0x19c00]==target[0x11000:0x11c00]
    cfg=r.clean_journal(banks)[2][8:24]
    assert int.from_bytes(cfg[9:13],'little')==48
    page=cfg[8] if cfg[7]==ord('P') else 0xb0
    config=r.preference(cfg,page,51)
    desired=list(map(bytearray,banks))
    for bank,address in OWNED:
        off=address-0x8000;start=(bank-1)*32768+off
        desired[bank][off:off+4096]=target[start:start+4096]
    tx,data,expected=r.transaction(banks,list(map(bytes,desired)),config,'Owner-authorized 2512 BF1 -> RC1 r10 recovery1')
    allowed=set(map(tuple,OWNED))|{(3,0xc000),(3,0xd000)}
    assert all((op['bank'],op['address']&0xf000) in allowed for op in tx['operations'])
    assert expected[0]==banks[0] and expected[1][:0x1000]==banks[1][:0x1000] and expected[3][0x1000:0x2000]==banks[3][0x1000:0x2000]
    assert config[:9]==cfg[:9] and config[13]==cfg[13]
    return banks,ram,tx,data,expected

def verify(build,plan):
    build,plan=map(Path,(build,plan));info=r.read(plan/'plan.json')
    banks,ram,tx,data,expected=derive(build,plan/'capture')
    assert info['board']=='2512' and info['usb_serial']=='A10MQFLCA' and info['transaction']==tx
    assert info['firmware_sha256']==r.sha((build/'firmware.bin').read_bytes())
    assert info['source_sha256']==r.hashes(banks) and info['expected_sha256']==r.hashes(expected)
    assert info['installer_sha256']==r.sha((plan/'installer-model-only.s19').read_bytes())
    with tempfile.TemporaryDirectory(prefix='r10-verify-',dir=plan.parent) as tmp:
        path=Path(tmp)/'plan';r.compose(TEMPLATE,path,banks,tx,data,expected)
        for p in path.iterdir():
            if p.name!='plan.json':assert p.read_bytes()==(plan/p.name).read_bytes(),p.name
    return info

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();build=args.build.resolve();out=args.out.resolve()
    banks,ram,tx,data,expected=derive(build,args.capture)
    info=r.compose(TEMPLATE,out,banks,tx,data,expected);shutil.copytree(args.capture,out/'capture')
    info.update(board='2512',usb_serial='A10MQFLCA',firmware_sha256=r.sha((build/'firmware.bin').read_bytes()),source_firmware_sha256=SOURCE_SHA)
    save(out/'plan.json',info);verify(build,out)
    # Reuse the unchanged linked-installer CPU execution and wear oracle,
    # supplying this stricter exact-BF1 private-plan verifier.
    template=build/'installer/engine/template';template.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(TEMPLATE,template)
    rows=[]
    for is816 in (False,True):
        for fault in (None,'stale','corrupt'):
            rows.append(model.execute(build,out,banks,is816=is816,deps02=ROOT/'BUILD/v1.30/local/test-deps',deps816=ROOT/'BUILD/test-deps-816',
                          fault=fault,verifier=verify,owner_erased_b0=()))
            save(out/'model-progress.json',rows);print('PASS linked installer',is816,fault,flush=True)
    save(out/'model-proof.json',dict(passed=True,hardware=False,plan_sha256=r.sha((out/'plan.json').read_bytes()),firmware_sha256=info['firmware_sha256'],models=rows))
    print('PASS 2512 exact-source transaction',len(tx['operations'])-1,'transfers; source + preservation and fault rehearsals',flush=True)

if __name__=='__main__':main()
