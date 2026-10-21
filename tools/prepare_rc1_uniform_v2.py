"""Create a new immutable host-protocol correction; never modify sealed kits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
BASE_SHA='bb939cde69b81884d9ed0b00a484972ecf11082485931f28f72758fb16c5aba5'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();base=a.base.resolve();out=a.out.resolve()
    assert SHA(base/'uniform-manifest.json')==BASE_SHA
    assert out.is_relative_to(ROOT/'BUILD') and not out.exists()
    manifest=READ(base/'uniform-manifest.json')
    for name,info in manifest['files'].items():
        path=base/name;assert path.resolve().is_relative_to(base)
        assert path.stat().st_size==info['bytes'] and SHA(path)==info['sha256'],name
    source=ROOT/'release/candidates/rc1-debugger-brkfix-r1/uniform-v2/upgrade.py'
    shutil.copytree(base,out);shutil.copyfile(source,out/'upgrade.py')
    manifest['files']['upgrade.py']=dict(bytes=(out/'upgrade.py').stat().st_size,sha256=SHA(out/'upgrade.py'))
    manifest.update(host_protocol_revision=2,hardware_qualified=False,
        host_protocol_provenance=dict(parent_uniform_manifest_sha256=BASE_SHA,
            changed_runtime_members=['upgrade.py'],source_sha256=SHA(source),
            corrections=['Exact beta4 source admission without assuming VERSION or newer service queries',
                         'Fresh SXB6 stable RAM comparison excludes only live 0700-07FF debugger stack']))
    for name in manifest['files']:
        if name!='upgrade.py':assert (out/name).read_bytes()==(base/name).read_bytes(),name
    (out/'uniform-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,kit=str(out),manifest_sha256=SHA(out/'uniform-manifest.json'),
        changed_runtime_members=['upgrade.py'],all_other_members_byte_identical=True,board_access=False),indent=2))


if __name__=='__main__':main()
