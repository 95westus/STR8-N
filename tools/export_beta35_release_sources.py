"""One-time, offline promotion of final beta35 assembly into a closed source tree.

The release builder does not import this exporter or use historical BUILD trees.
Executable DB includes are deliberately omitted and rebuilt from assembly.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    'core': ('asm', ['str8n-v2-worker', 'str8n-v2-vectors', 'str8n-v2-boot',
                     'str8n-v2-sr', 'monitor-b0', 'launcher']),
    'provider': ('resident-provider/asm', ['rtc-provider']),
    'gateway': ('resident-gateway/asm', ['rtc-gateway']),
    'journal': ('resident-journal/asm', ['journal']),
    'banner': ('resident-banner/asm', ['rtc-banner']),
    'status': ('storage-status/asm', ['storage-status']),
    'mode': ('status-mode-init/asm', ['status-mode-init']),
    'loader': ('loader/asm', ['version-loader']),
    'local': ('local-display/asm', ['local-display']),
    'battery': ('battery/asm', ['battery']),
    'version': ('version/asm', ['version']),
    'pf': ('pf-worker/asm', ['pf']),
    'clock': ('clock/asm', ['clock']),
    'xip': ('xip/asm', ['utilities', 'gate', 'work-stub']),
    'batch': ('batch/asm', ['batch-gate']),
    'assembler': ('assembler/asm', ['asm-app']),
    'bootstrap': ('bootstrap/asm', ['bootstrap-journal']),
    'migration': ('migrator/asm', ['rtc-migrator', 'migration-worker']),
}
GENERATED = {
    'core': {'worker-image.inc', 'vectors-image.inc', 'text-image.inc', 'batch-gate.inc'},
    'xip': {'gate-image.inc', 'work-stub.inc'},
    'migration': {'migration-worker-image.inc', 'migration-table.inc'},
    'bootstrap': {'initial-record.inc'},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def profile_boot(text):
    """Make the historical F30D profile explicit in the promoted source.

    The legacy profile builder overwrote its staged .asm later, while retaining
    this linked ABI. This is the exact source-level selector relocation from
    build_v2_beta25_profile.py, not a binary patch or disassembly.
    """
    begin = text.index('BOOT_SELECT_SKIP:')
    end = text.index('; PTR is a sector-aligned', begin)
    text = text[:begin]+'BOOT_SELECT_SKIP:       JMP BOOT_SELECT_SKIP_OUT\n\n'+text[end:]
    old = '                        JMP BOOT_SELECT_SKIP\nBOOT_SELECT_NEW:'
    assert text.count(old) == 1
    text = text.replace(old,'                        BRA BOOT_SELECT_SKIP\nBOOT_SELECT_NEW:',1)
    helper = '''BOOT_SELECT_SKIP_OUT:   LDA #$10
                        TSB BOOT_SLOT
                        BNE BOOT_SELECT_DONE_OUT
                        JMP BOOT_SELECT_NEXT
BOOT_SELECT_DONE_OUT:   RTS
                        DB $FF,$FF,$FF
'''
    return text.replace('BOOT_SR_ROUTE:',helper+'BOOT_SR_ROUTE:',1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, default=ROOT/'BUILD/v2-beta35-candidate')
    p.add_argument('--out', type=Path, default=ROOT/'release/beta35')
    args = p.parse_args()
    base, out = args.candidate.resolve(), args.out.resolve()
    assert not (out/'source').exists(), 'Refuse to overwrite promoted sources'
    provenance = {}
    for module, (folder, names) in MODULES.items():
        stage = base/folder
        search = [stage, stage.parent/'source', stage.parent, base/'asm',
                  base/'inputs', ROOT/'tmp/b34/src/v2-config', ROOT/'tmp/b34/src/asm']
        # Migrator includes live beside its .asm output; core includes are in asm.
        search += [base/'migrator/asm']
        seen = set()

        def copy(name):
            if name in GENERATED.get(module, set()) or name in seen:
                return
            seen.add(name)
            source = next((d/name for d in search if (d/name).is_file()), None)
            if source is None:
                raise FileNotFoundError((module, name))
            original = data = source.read_bytes()
            transformation = None
            if module == 'core' and name == 'str8n-v2-boot.asm':
                assert json.loads((base/'build.json').read_text())['boot']['BOOT_SLOT_CHECK'] == 0xF30D
                data = profile_boot(data.decode('ascii').replace('\r\n','\n')).encode('ascii')
                transformation = 'Explicit F30D selector profile from build_v2_beta25_profile.py'
            dest = out/'source'/module/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            provenance[dest.relative_to(out).as_posix()] = {
                'from': source.relative_to(ROOT).as_posix(), 'sha256': sha(data),
            }
            if transformation:
                provenance[dest.relative_to(out).as_posix()].update(
                    from_sha256=sha(original), transformation=transformation)
            for include in re.findall(r'\bINCLUDE\s+"([^"]+)"', data.decode('ascii'), re.I):
                copy(include)
        for name in names:
            copy(name+'.asm')
    for source, name in [(base/'source/str8n-v2-text.json', 'core/text.json'),
                         (ROOT/'tmp/b34/src/asm/opcodes.json', 'assembler/opcodes.json')]:
        dest = out/'source'/name
        dest.write_bytes(source.read_bytes())
        provenance[dest.relative_to(out).as_posix()] = {
            'from': source.relative_to(ROOT).as_posix(), 'sha256': sha(dest.read_bytes())}
    proposed = json.loads((ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/proposed-payload-allowlist.json').read_text())
    expected = proposed['files']
    for name in ['local-display/asset.bin', 'pf-worker/asset.bin', 'bootstrap/bootstrap-journal.bin']:
        data = (base/name).read_bytes()
        expected[name] = {'sha256': sha(data), 'bytes': len(data)}
    # Migration is a source-built template only; no serial installer is packaged.
    data = (base/'migrator/rtc-migrator-2000.s19').read_bytes()
    expected['migrator/rtc-migrator-2000.s19'] = {'sha256': sha(data), 'bytes': len(data)}
    manifest = {
        'version': '2.0b35', 'generation': 47, 'clock_version': '1.10',
        'boot_compatibility': 3966175489,
        'candidate_build_sha256': sha((base/'build.json').read_bytes()),
        'expected': expected, 'generated_includes': {k:sorted(v) for k,v in GENERATED.items()},
        'profile': 'FT245; W65C02 / W65C816 emulation',
        'deferred': ['ACIA', 'crypto'], 'installation_permitted': False,
    }
    (out/'release.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'source-provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    shutil.copyfile(ROOT/'LICENSE', out/'LICENSE')
    print(f'Promoted {len(provenance)} source files; {len(expected)} expected artifacts')


if __name__ == '__main__':
    main()
