"""Export code-only destination fingerprints; no board bytes or serial access."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    assert not a.out.exists()
    layout=read(ROOT/'release/beta35/layout.json');meta=read(ROOT/'release/beta35/release.json')
    old=ROOT/'BUILD/v2-beta34-candidate';new=ROOT/'tmp/c35e/payload'
    assert sha((old/'build.json').read_bytes())=='2381688f48a5aa2f0da4c8b8f8fd21cdb2087d521861db813ad0d61c936938b1'
    oldmeta=read(old/'build.json')
    fixtures=[]
    for board in ['2205','2512','2604','2609']:
        base=ROOT/'output/qualification/beta34-fleet-2026-10-16'
        folder=base/'fresh/2512' if board=='2512' else base/board/'hardware'
        prefix='flash-1-b' if board=='2512' else 'final-b'
        fixtures.append([(folder/f'{prefix}{i}.bin').read_bytes() for i in range(4)])
    ranges=[]
    for s in layout['segments']:
        filename=s['file'];n=s['bytes'];off=s['offset'];address=s['address'];bank=s['bank']
        target=(new/filename).read_bytes();assert sha(target)==meta['expected'][filename]['sha256']
        oldfile=(old/filename).read_bytes()
        oldhash=oldmeta['local_asset_sha256'] if filename=='local-display/asset.bin' else oldmeta['artifacts'][filename]
        assert sha(oldfile)==oldhash,filename
        olddata=oldfile[off:off+n]
        assert len(olddata)==n
        accepted={sha(olddata),sha(target[off:off+n]),sha(b'\xff'*n)}
        for banks in fixtures:assert sha(bytes(banks[bank][address-0x8000:address-0x8000+n])) in accepted,filename
        ranges.append(dict(bank=bank,address=address,bytes=n,file=filename,
            accepted_sha256=sorted({sha(olddata),sha(target[off:off+n])}),
            meanings=['Pinned beta34 source range','Frozen beta35 target range']))
    catalog=dict(schema=1,target_version='2.0b35',target_generation=47,profile='FT245-F30D',
        source_scope='Only registered AB monitors with the unchanged target E/F core; assets may be exact beta34, beta35, or erased',
        planning_only=True,installation_permitted=False,execution_permitted=False,
        target_metadata_sha256=sha((ROOT/'release/beta35/release.json').read_bytes()),
        target_layout_sha256=sha((ROOT/'release/beta35/layout.json').read_bytes()),
        source_metadata_sha256=sha((old/'build.json').read_bytes()),ranges=ranges)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(catalog,indent=2)+'\n')
    print('PASS 13 exact owned ranges checked against four archived fixtures; catalog SHA256',sha(a.out.read_bytes()))

if __name__=='__main__':main()
