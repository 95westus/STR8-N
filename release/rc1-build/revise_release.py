"""Reproduce rc1 package revision 2 from the original ZIP and a fresh source build.

No device access. The original tagged ZIP is input by digest; only the RTC
banner sector, bound inventories, two manuals and revision notices may change.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from build_full_image import compose

BASE_SHA = '8e717a3672aded069a6498f0f0fa5a6c572b5b9bfb8926792b46749f5d60caa5'
COMPONENT = 'str8n-rtc-component-8000-8fff.bin'
sha = lambda b: hashlib.sha256(b).hexdigest()
encode = lambda x: (json.dumps(x, indent=2)+'\n').encode('utf-8')


def revise(base, payload, reference, source_commit, out):
    assert sha(base.read_bytes()) == BASE_SHA, 'Wrong original release ZIP'
    assert len(source_commit) == 40 and all(c in '0123456789abcdef' for c in source_commit)
    with zipfile.ZipFile(base) as z:
        files = {n.split('/', 1)[1]: z.read(n) for n in z.namelist()}
    original = dict(files)
    old_manifest = json.loads(files['release-manifest.json'])
    assert set(files) == set(old_manifest['files']) | {'release-manifest.json', 'SHA256SUMS.txt'}
    for n, info in old_manifest['files'].items():
        assert sha(files[n]) == info['sha256'] and len(files[n]) == info['bytes'], n
    ref = json.loads(reference.read_text())
    assert ref['passed'] and ref['version'] == '2.0rc1' and ref['generation'] == 49
    full, _ = compose(payload, ref)
    image = bytearray(full[32768:])
    record = files['migration/applications/uchess-record.bin']
    assert len(record) == 1463 and image[:len(record)] == b'\xff'*len(record)
    image[:len(record)] = record
    image = bytes(image)
    old_image = files['firmware/str8n-2.0rc1-apps-str8n-only.bin']
    assert image[:65536] == old_image[:65536] and image[69632:] == old_image[69632:]
    assert b' [power-fail UTC]\0' in image[65536:69632]
    assert b' [power-fail]\0' not in image[65536:69632]
    files['firmware/str8n-2.0rc1-apps-str8n-only.bin'] = image
    for name, offset, size in [('boot-core-b3', 65536, 32768),
                               ('monitor-a', 73728, 4096), ('monitor-b', 77824, 4096),
                               ('b3-f000-ffff', 94208, 4096)]:
        files[f'firmware/str8n-2.0rc1-{name}.bin'] = image[offset:offset+size]
    # The migration runtime and every other firmware payload stay identical.
    for n in list(files):
        if n.startswith('migration/payload/'):
            new = (payload/n.removeprefix('migration/payload/')).read_bytes()
            if new != files[n]:
                assert n == 'migration/payload/'+COMPONENT, n
                files[n] = new
    kit = 'migration/'
    qname = kit+'hardware-qualification.json'
    qualification = json.loads(files[qname])
    qualification.update(package_revision=2, rc1_hardware_tested=False,
                         scope=qualification['scope'].replace('version-only rc1 target', 'rc1 target with UTC-label correction'),
                         revision_note='UTC banner text only; offline regression execution; no revised hardware installation claimed')
    qualification['required_files'] = {
        n[len(kit):]: sha(b) for n, b in sorted(files.items()) if n.startswith(kit)
        and n not in (qname, kit+'kit-manifest.json')}
    files[qname] = encode(qualification)
    km = json.loads(files[kit+'kit-manifest.json'])
    km['package_revision'] = 2
    km['files'] = {n[len(kit):]: dict(bytes=len(b), sha256=sha(b))
                   for n, b in sorted(files.items()) if n.startswith(kit)
                   and n != kit+'kit-manifest.json'}
    files[kit+'kit-manifest.json'] = encode(km)
    root = Path(__file__).resolve().parents[2]
    for name in ('README.md', 'TECHNICAL_MANUAL.md'):
        files['docs/'+name] = (root/'docs/rc1'/name).read_bytes()
    files['README.md'] += b'\nPackage revision 2 restores `[power-fail UTC]` in startup output. Only banner\ntext, its data references and the sector checksum changed; no revised hardware installation is\nclaimed. The original rc1 tag is retained; see release-manifest.json for the\ncorrection source commit and original ZIP digest.\n'
    manifest = dict(old_manifest)
    manifest.update(source_commit=source_commit, package_revision=2,
                    original_tag_source_commit=old_manifest['source_commit'],
                    supersedes_zip_sha256=BASE_SHA,
                    correction='Restore power-fail UTC heading; equal-length text pool; control flow and helper addresses unchanged',
                    rc1_hardware_tested=False)
    manifest['files'] = {n: dict(bytes=len(b), sha256=sha(b)) for n, b in sorted(files.items())
                         if n not in ('release-manifest.json', 'SHA256SUMS.txt')}
    files['release-manifest.json'] = encode(manifest)
    files['SHA256SUMS.txt'] = ''.join(sha(b)+'  '+n+'\n' for n, b in sorted(files.items())
                                     if n != 'SHA256SUMS.txt').encode()
    out.mkdir(parents=True, exist_ok=False)
    archive = out/'str8n-v2.0rc1-release.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for n, b in sorted(files.items()):
            item = zipfile.ZipInfo('str8n-2.0rc1/'+n, (2026, 10, 18, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (0o100755 if n.endswith('.sh') else 0o100644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(item, b)
    changed = [n for n in files if files[n] != original[n]]
    assert set(changed) == {
        'firmware/str8n-2.0rc1-apps-str8n-only.bin', 'firmware/str8n-2.0rc1-boot-core-b3.bin',
        kit+'payload/'+COMPONENT, qname, kit+'kit-manifest.json', 'docs/README.md',
        'docs/TECHNICAL_MANUAL.md', 'README.md', 'release-manifest.json', 'SHA256SUMS.txt'}
    report = dict(passed=True, package_revision=2, source_commit=source_commit,
                  sha256=sha(archive.read_bytes()), bytes=archive.stat().st_size,
                  full_image_sha256=sha(image), changed_files=changed, total_files=len(files),
                  all_other_files_identical=True, board_access=False)
    (out/'package-report.json').write_bytes(encode(report))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-zip', required=True, type=Path)
    p.add_argument('--payload', required=True, type=Path)
    p.add_argument('--reference', required=True, type=Path)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    revise(a.base_zip, a.payload, a.reference, a.source_commit, a.out)
