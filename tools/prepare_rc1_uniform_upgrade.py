"""Prepare a new portable source-aware RC1 kit without changing frozen installers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'release/candidates/rc1-debugger-brkfix-r1'
SHA = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); out = args.out.resolve()
    if out.exists(): raise ValueError('Never overwrite a kit')
    original = ROOT/'BUILD/rc1-debugger-v1g-boardtest-r1'
    if SHA(original/'board-test-manifest.json') != '42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf':
        raise ValueError('Changed original kit')
    shutil.copytree(original, out)
    for name in ('uniform_upgrade.py','upgrade.py','bootstrap_routes.py'): shutil.copyfile(HERE/name, out/name)
    # Derive a separate generation50 migration kit. Never edit the published
    # generation49 inputs, templates or their frozen qualification records.
    legacy_root=ROOT/'release/rc1-migration-r1'; legacy_out=out/'migration'
    original_manifest=json.loads((legacy_root/'kit-manifest.json').read_text())
    for name,info in original_manifest['files'].items():
        if SHA(legacy_root/name)!=info['sha256']:raise ValueError('Changed migration input: '+name)
    shutil.copytree(legacy_root,legacy_out)
    for source in (legacy_out/'payload').rglob('*'):
        target=ROOT/'BUILD/rc1-debugger-v1g/payload'/source.relative_to(legacy_out/'payload')
        if source.is_file() and target.is_file():shutil.copyfile(target,source)
    shutil.copyfile(ROOT/'BUILD/rc1-debugger-v1g/payload/debugger-a000.bin',legacy_out/'payload/debugger-a000.bin')
    layout=json.loads((legacy_out/'layout.json').read_text())
    layout['segments'].append(dict(bank=1,address=0xa000,file='debugger-a000.bin',offset=0,bytes=4096))
    (legacy_out/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    for name in ('migrate.py','factory_wdc.py'):
        path=legacy_out/name;text=path.read_text()
        edits=({"manifest['generation']==49":"manifest['generation']==50", "r.preference(cfg,0xb0,49)":"r.preference(cfg,cfg[8] if cfg[7]==ord('P') else 0xb0,50)"}
               if name=='migrate.py' else {"r.preference(config,0xa0,49)":"r.preference(config,config[8] if config[7]==ord('P') else 0xa0,50)"})
        for before,after in edits.items():
            expected=2 if before.startswith('r.preference(cfg') else 1
            if text.count(before)!=expected:raise ValueError('Unexpected inherited migration source: '+name)
            text=text.replace(before,after)
        if name=='migrate.py':
            before="    return cfg\n\ndef beta4_target"
            if text.count(before)!=1:raise ValueError('Unexpected beta4 admission return')
            text=text.replace(before,"    r.require(not (cfg[1] and cfg[6]==0 and int.from_bytes(cfg[3:5],'little')>=0x6500), 'Autostart overlaps target service RAM; no write permitted')\n"+before)
        path.write_text(text,encoding='utf-8',newline='\n')
    # Live acceptance is set only by a new route-specific qualification; old
    # hardware receipts cannot authorize the changed target by inheritance.
    qualification=json.loads((legacy_out/'hardware-qualification.json').read_text())
    qualification.update(generation=50,rc1_hardware_tested=False,target_model_passed=False,live_WDC_debugger_identities=[],
                         scope='Unqualified direct WDCMONV2/beta4 to generation50 v1g development target')
    (legacy_out/'hardware-qualification.json').write_text(json.dumps(qualification,indent=2)+'\n')
    generated={p.relative_to(legacy_out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(legacy_out.rglob('*')) if p.is_file() and p.name!='kit-manifest.json'}
    (legacy_out/'kit-manifest.json').write_text(json.dumps(dict(candidate_id='rc1',version='2.0rc1',generation=50,
        files=generated,live_installation_enabled=False,distribution_qualified=False,requires_qualification=True),indent=2)+'\n')
    baseline = json.loads((out/'board-test-manifest.json').read_text())
    profiles = {}
    profiles['rc1-gen49'] = dict(generation=49, sectors=[dict(bank=s['bank'], address=s['address'], file=s['baseline']) for s in baseline['sectors']])
    for version in ('v1e', 'v1f', 'v1g'):
        image = ROOT/f'BUILD/rc1-debugger-{version}/firmware.bin'
        report = json.loads((image.parent/'debugger-build.json').read_text())
        if SHA(image) != report['firmware_sha256']: raise ValueError('Changed source build: '+version)
        folder=out/'profiles'/version; folder.mkdir(parents=True)
        rows=[]; body=image.read_bytes()
        for s in baseline['sectors']:
            first=(s['bank']-1)*32768+s['address']-0x8000
            path=folder/f"b{s['bank']}-{s['address']:04x}.bin"
            path.write_bytes(body[first:first+4096])
            rows.append(dict(bank=s['bank'],address=s['address'],file=path.relative_to(out).as_posix()))
        profiles[version]=dict(generation=50,firmware_sha256=SHA(image),sectors=rows)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(out.rglob('*')) if p.is_file()}
    manifest=dict(schema=1,default_target='v1g',profiles=profiles,files=files,native_debugging=False,
                  RTC_drift_in_release_qualification=False,intermediate_generation49=False,hardware_qualified=False,
                  required_source_routes=['wdcmonv2-65C02','wdcmonv2-65C816','beta4','rc1-gen49','v1e','v1f','v1g'])
    (out/'uniform-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(passed=True,board_access=False,kit=str(out),manifest_sha256=SHA(out/'uniform-manifest.json'),profiles=list(profiles)),indent=2))


if __name__=='__main__': main()
