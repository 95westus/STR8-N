"""Select the hardware-verified g0034 source without rewriting old baselines."""
import argparse,json,shutil
from pathlib import Path
from str8build.formats import save,sha
ROOT=Path(__file__).resolve().parents[1]

def fingerprint(v):return sha(json.dumps(v,sort_keys=True,separators=(',',':')).encode())

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    build,base=a.build.resolve(),a.base.resolve();meta=json.loads((build/'r10-build.json').read_text())
    assert meta['current_features_retained'] and meta['firmware_sha256']=='0df4a802d618c0df5e658dcf2cd05037f0a892a209abaeac6bca0d595c468945'
    assert sha((build/'firmware.bin').read_bytes())==meta['firmware_sha256']
    for board in ('2604','2609'):
        folder=ROOT/f'output/qualification/rc1-r10p2-install-{board}/{board}'
        install=json.loads((folder/'flash-report.json').read_text());rec=json.loads((folder/'recovery/recovery-report.json').read_text())
        assert install['passed'] and install['firmware_sha256']==meta['firmware_sha256'] and rec['passed'] and rec['generation']==52
    selected=json.loads((ROOT/'src/current/target.json').read_text());assert selected['candidate']=='fixed-f-flow-size'
    parent=ROOT/'release/candidates/rc1-r10p2/parent-core';assert not parent.exists();parent.mkdir(parents=True)
    for name in ('str8n-v2-boot.asm','str8n-v2-journal.inc'):shutil.copyfile(base/'s/core'/name,parent/name)
    save(parent/'source-manifest.json',{p.name:sha(p.read_bytes()) for p in parent.iterdir() if p.is_file()})
    for name in ('core/str8n-v2-boot.asm','core/str8n-v2-journal.inc','version/version.asm','version/version-links.inc',
                 'version/boot-symbols.inc','xip/system.inc','maintenance/maint.inc','edu/edu.inc'):
        shutil.copyfile(build/'s'/name,ROOT/'src/current'/name)
    text=json.loads((ROOT/'src/current/core/text.json').read_text())
    for row in text:
        if row['name']=='V2_BANNER':row['text']='\r\nSTR8-N {version} g{generation_hex} B'
    save(ROOT/'src/current/core/text.json',text)
    layout=json.loads((ROOT/'src/current/layout.json').read_text());layout['generation']=52;layout['boot_compatibility']=meta['boot_compatibility'];save(ROOT/'src/current/layout.json',layout)
    symbols=json.loads((build/'symbols.json').read_text());source_sy=json.loads((build/'source-symbols.json').read_text())
    dbg=json.loads((build/'debugger-build.json').read_text())['debugger_symbols']
    fixture=dict(candidate='rc1-r10p2-current',version='2.0rc1',generation=52,boot_compatibility=meta['boot_compatibility'],
        firmware_sha256=meta['firmware_sha256'],artifacts={p.relative_to(build/'payload').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted((build/'payload').rglob('*')) if p.is_file()},
        symbol_fingerprints={k:fingerprint(v) for k,v in symbols.items()},source_symbol_fingerprint=fingerprint(source_sy),
        debugger_symbol_fingerprint=fingerprint(dbg))
    path=ROOT/'tests/baselines/rc1-r10p2-current.json';assert not path.exists();save(path,fixture)
    save(ROOT/'src/current/target.json',dict(candidate=fixture['candidate'],firmware_sha256=fixture['firmware_sha256'],fixture=path.relative_to(ROOT).as_posix(),fixture_sha256=sha(path.read_bytes())))
    print('PASS selected g0034 source; historical baseline manifests retained',flush=True)

if __name__=='__main__':main()
