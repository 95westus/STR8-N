"""Prepare named monitor/core/manual downloads without changing published assets."""
import hashlib,json,re,shutil,zipfile,posixpath
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17/revisions/monitor-core-docs-r1';sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
    assert not OUT.exists();OUT.mkdir(parents=True);published_pointer=read(Q/'bf1-github-publication-current.json');base_path=Path(published_pointer['receipt']);assert sha(base_path.read_bytes())==published_pointer['sha256'];base=read(base_path);assert base['published']
    image=Path(base['assets']['str8n-2.0bf1-apps-str8n-only.bin']['path']).read_bytes();assert sha(image)==base['assets']['str8n-2.0bf1-apps-str8n-only.bin']['sha256'];assets={}
    for name,offset,part in [('str8n-2.0bf1-monitor-a.bin',0x12000,'a0'),('str8n-2.0bf1-monitor-b.bin',0x13000,'b0')]:
        body=image[offset:offset+4096];pinned=(ROOT/f'tmp/bf1-distribution-r18/migration/payload/str8n-v2-recovery-slot-{part}.bin').read_bytes();assert body==pinned and len(body)==4096
        path=OUT/name;path.write_bytes(body);assets[name]=dict(path=str(path),bytes=len(body),sha256=sha(body))
    core_dir=Q/'bf1-boot-core-image-2026-10-18-r1';proof=read(core_dir/'report.json');assert proof['passed'] and proof['model_only'] and not proof['board_access'];source=core_dir/proof['filename'];assert sha(source.read_bytes())==proof['sha256'] and source.read_bytes()==image[0x10000:]
    path=OUT/source.name;shutil.copyfile(source,path);assets[path.name]=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()))
    package=Path(base['assets']['str8n-2.0bf1-windows-migration.zip']['path']);assert sha(package.read_bytes())==base['assets'][package.name]['sha256'];files={}
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            relative='/'.join(name.split('/')[1:])
            if relative.startswith(('docs/','uchess-source/')) or relative=='LICENSE':files[relative]=archive.read(name)
    guide=(ROOT/'docs/STR8N_BF1_RELEASE_PATHS.md').read_bytes();files['docs/RELEASE_PATHS.md']=guide
    files['docs/README.md']+=b'\n\n[Choose boot/core, full-system or component downloads](RELEASE_PATHS.md).\n'
    files['README.md']=b'# STR8-N 2.0bf1 documentation\n\nStart with [installation choices and component offsets](docs/RELEASE_PATHS.md),\nthen [the manual index](docs/README.md). The full-system and core-only choices\nshare the same generation-48 core. Use the matching Windows/Linux migration\npackage to run host commands. Full original uChess source/license/credits are\nin `uchess-source`. Known RTC and recorded-soak limits are documented.\n'
    for name,body in files.items():
        if name.endswith('.md'):
            text=body.decode();assert not re.search(r'C:[\\/](SRC|Users)[\\/]|output[\\/]qualification',text,re.I)
            for link in re.findall(r'\]\(([^)]+)\)',text):
                if re.match('[a-z]+:',link):continue
                target=posixpath.normpath((Path(name).parent/link.split('#')[0]).as_posix());assert target in files,(name,target)
    files['SHA256SUMS']=''.join(sha(body)+'  '+name+'\n' for name,body in sorted(files.items())).encode()
    path=OUT/'str8n-2.0bf1-docs.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,body in sorted(files.items()):archive.writestr('str8n-2.0bf1-docs/'+name,body)
    with zipfile.ZipFile(path) as archive:assert len(archive.namelist())==len(files) and all(archive.read('str8n-2.0bf1-docs/'+n)==b for n,b in files.items())
    assets[path.name]=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()))
    all_assets={**base['assets'],**assets};sums=OUT/'str8n-2.0bf1-all-assets-SHA256SUMS.txt';sums.write_text(''.join(info['sha256']+'  '+name+'\n' for name,info in sorted(all_assets.items())),encoding='ascii');assets[sums.name]=dict(path=str(sums),bytes=sums.stat().st_size,sha256=sha(sums.read_bytes()))
    addition='''\n\n## Boot/core, full-system and component choices

The **documentation ZIP** is available separately. Start with RELEASE_PATHS
and the manual index inside it; it includes all quick starts, guides/manuals,
ABI tables, Mermaid diagrams and credited uChess source.

| Choice | File | Mapping / scope |
|---|---|---|
| Bootloader / monitor core | `str8n-2.0bf1-boot-core-b3.bin` | 32 KiB B3-only provisioning at full-device offset 0x18000: F boot/recovery, E/S/R/T, MON A/B, RTC/journal services and generic records. No B1/B2 utilities/apps. Both-slot core boot/fallback and J3 passed in the W65C02 model; a separate physical core-only install has not been performed. |
| Full system with utilities/apps | `str8n-2.0bf1-apps-str8n-only.bin` | 96 KiB B1/B2/B3 provisioning at offset 0x8000; complete app/provider inventory, including UCHESS. The matching migration packages install this full-system scope. |
| MON A component | `str8n-2.0bf1-monitor-a.bin` | 4096 bytes, B3:A000-AFFF, full-device offset 0x1A000. |
| MON B component | `str8n-2.0bf1-monitor-b.bin` | 4096 bytes, B3:B000-BFFF, full-device offset 0x1B000. |
| Fixed F component | `str8n-2.0bf1-b3-f000-ffff.bin` | 4096 bytes, B3:F000-FFFF, full-device offset 0x1F000. |

MON A/B are the user-facing names; A0/B0 refer to internal B3 pages, not flash
banks. Individual A/B/F files require the matching core/layout and are not
complete standalone monitors or preserving upgrade scripts. J3 restarts the
complete bf1 layout. J0/J1/J2 do not relocate this B3 bootstrap; another-bank
standalone firmware would require a separate build. Raw provisioning images
replace covered settings/wear records; use the admitted full migration route
where preservation is required. The all-assets checksum file covers the
original and added downloads. Earlier published asset bytes remain unchanged.
'''
    (OUT/'release-notes-addition.md').write_text(addition,encoding='utf-8')
    plan=dict(passed=True,repo=base['repo'],tag=base['tag'],release_id=base['release_id'],source_commit=base['source_commit'],owner_request='include A/B monitor bins in the release, and docs; different paths: STR8-N boot loader and STR8-N with utils',base_publication=str(base_path),base_publication_sha256=sha(base_path.read_bytes()),existing_assets=base['assets'],new_assets=assets,core_test=str(core_dir/'report.json'),core_test_sha256=sha((core_dir/'report.json').read_bytes()),notes_addition_sha256=sha((OUT/'release-notes-addition.md').read_bytes()),source_request_guide_sha256=sha(guide),docs_checks=dict(passed=True,markdown_documents=sum(n.endswith('.md') for n in files),all_links_resolve=True,Mermaid_SVGs=sum(n.endswith('.svg') for n in files),copyright_source_included=True,all_archive_bytes_compared=True),no_existing_asset_replacement=True,board_access=False,full_release_qualified=False)
    (OUT/'preparation.json').write_text(json.dumps(plan,indent=2)+'\n');print('PASS five named release additions, exact monitor/core parts and self-contained manuals ZIP; no published bytes modified')
if __name__=='__main__':main()
