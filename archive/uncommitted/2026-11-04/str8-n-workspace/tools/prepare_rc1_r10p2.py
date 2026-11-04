"""Exact current-RC1 -> g0034 preserving plan and linked-installer rehearsal."""
import argparse,shutil,tempfile
from pathlib import Path
from installer import capture,model
from installer.common import REGISTRY,save
from installer.engine import runtime as r
ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/'tools/installer/engine/template'
SOURCE_SHA='c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e'
EARLIER_2512_SHA='0c27595db9fdabedbecebb6992f71053ad20a7365a7444bd595ac0246f8046cc'

def derive(build,base,cap):
    identity,banks=capture.validate(cap);source=(base/'firmware.bin').read_bytes();target=(build/'firmware.bin').read_bytes();meta=r.read(build/'r10-build.json')
    source_sha=r.sha(source)
    assert source_sha==SOURCE_SHA or (identity['board']=='2512' and source_sha==EARLIER_2512_SHA)
    source_generation=51 if source_sha==EARLIER_2512_SHA else 50
    assert meta['parent_sha256']==SOURCE_SHA and meta['current_features_retained']
    assert meta['generation']==52 and meta['boot_header']=='STR8-N 2.0rc1 g0034' and r.sha(target)==meta['firmware_sha256']
    for bank,address in REGISTRY['owned_sectors']:
        off=address-0x8000;start=(bank-1)*32768+off
        assert banks[bank][off:off+4096]==source[start:start+4096],f'Unknown current RC1 B{bank}:{address:04X}'
    assert banks[3][0x1000:0x1c00]==source[0x11000:0x11c00]==target[0x11000:0x11c00]
    cfg=r.clean_journal(banks)[2][8:24];assert int.from_bytes(cfg[9:13],'little')==source_generation
    assert cfg[7]==ord('P') and cfg[8] in (0xa0,0xb0)
    config=r.preference(cfg,cfg[8],52);desired=list(map(bytearray,banks))
    for bank,address in REGISTRY['owned_sectors']:
        off=address-0x8000;start=(bank-1)*32768+off;desired[bank][off:off+4096]=target[start:start+4096]
    tx,data,expected=r.transaction(banks,list(map(bytes,desired)),config,f'Owner-authorized {identity["board"]} current RC1 -> g0034 F recovery/header')
    allowed=set(map(tuple,REGISTRY['owned_sectors']))|{(3,0xc000),(3,0xd000)}
    assert all((op['bank'],op['address']&0xf000) in allowed for op in tx['operations'])
    assert expected[0]==banks[0] and expected[1][:0x1000]==banks[1][:0x1000] and expected[3][0x1000:0x2000]==banks[3][0x1000:0x2000]
    assert cfg[:9]==config[:9] and cfg[13]==config[13]
    return identity,banks,tx,data,expected

def verify(build,folder):
    build,folder=map(Path,(build,folder));info=r.read(folder/'plan.json');base=Path(info['source_build'])
    identity,banks,tx,data,expected=derive(build,base,folder/'capture')
    assert (info['board'],info['usb_serial'])==(identity['board'],identity['usb_serial'])
    assert info['transaction']==tx and info['source_sha256']==r.hashes(banks) and info['expected_sha256']==r.hashes(expected)
    assert info['firmware_sha256']==r.sha((build/'firmware.bin').read_bytes()) and info['installer_sha256']==r.sha((folder/'installer-model-only.s19').read_bytes())
    with tempfile.TemporaryDirectory(prefix='g0034-verify-',dir=folder.parent) as tmp:
        check=Path(tmp)/'plan';r.compose(TEMPLATE,check,banks,tx,data,expected)
        for p in check.iterdir():
            if p.name!='plan.json':assert p.read_bytes()==(folder/p.name).read_bytes(),p.name
    return info

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    build,base,out=map(lambda x:x.resolve(),(a.build,a.base,a.out))
    identity,banks,tx,data,expected=derive(build,base,a.capture)
    info=r.compose(TEMPLATE,out,banks,tx,data,expected);shutil.copytree(a.capture,out/'capture')
    info.update(board=identity['board'],usb_serial=identity['usb_serial'],source_build=str(base),firmware_sha256=r.sha((build/'firmware.bin').read_bytes()))
    save(out/'plan.json',info);verify(build,out)
    template=build/'installer/engine/template'
    if not template.exists():template.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(TEMPLATE,template)
    results=[]
    for is816 in (False,True):
        for fault in (None,'stale','corrupt'):
            result=model.execute(build,out,banks,is816=is816,deps02=ROOT/'BUILD/v1.30/local/test-deps',deps816=ROOT/'BUILD/test-deps-816',
                                 fault=fault,verifier=verify,owner_erased_b0=())
            results.append(result);save(out/'model-progress.json',results);print('PASS',identity['board'],'linked installer',is816,fault,flush=True)
    save(out/'model-proof.json',dict(passed=True,hardware=False,board=identity['board'],plan_sha256=r.sha((out/'plan.json').read_bytes()),firmware_sha256=info['firmware_sha256'],models=results))
    print('PASS exact preserving plan',identity['board'],len(tx['operations'])-1,'transfers',flush=True)

if __name__=='__main__':main()
