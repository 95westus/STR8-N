"""One complete user release ZIP assembled from already verified public assets."""
import hashlib,json,posixpath,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-complete-release-2026-10-18-r1';sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
    assert not OUT.exists();OUT.mkdir(parents=True);pointer=read(Q/'bf1-github-publication-current.json');receipt_path=Path(pointer['receipt']);assert sha(receipt_path.read_bytes())==pointer['sha256'];receipt=read(receipt_path);assert receipt['published'];assets=receipt['assets'];files={}
    def archive(name):
        p=Path(assets[name]['path']);assert sha(p.read_bytes())==assets[name]['sha256']
        with zipfile.ZipFile(p) as z:return {'/'.join(n.split('/')[1:]):z.read(n) for n in z.namelist()}
    win=archive('str8n-2.0bf1-windows-migration.zip');linux=archive('str8n-2.0bf1-linux-migration.zip');manuals=archive('str8n-2.0bf1-docs.zip')
    for name,body in win.items():
        if name in ('README.md','provenance.json','package-manifest.json','SHA256SUMS'):continue
        files[name]=body
    for name,body in linux.items():
        if name.endswith('.sh'):files[name]=body
        elif name.startswith('migration/'):assert files[name]==body,'Platform runtime differs'
    for name,body in manuals.items():
        if name.startswith(('docs/','uchess-source/')) or name=='LICENSE':files[name]=body
    # Standard ZIP extraction tools retain executable bits; chmod is explicit
    # for extractors that discard them.
    doc=files['docs/QUICK_START_LINUX.md'].decode();doc=doc.replace('python3 -m pip install pyserial==3.5','chmod +x ./*.sh\npython3 -m pip install pyserial==3.5',1);files['docs/QUICK_START_LINUX.md']=doc.encode()
    for name in ('str8n-2.0bf1-apps-str8n-only.bin','str8n-2.0bf1-boot-core-b3.bin','str8n-2.0bf1-monitor-a.bin','str8n-2.0bf1-monitor-b.bin','str8n-2.0bf1-b3-f000-ffff.bin'):
        p=Path(assets[name]['path']);body=p.read_bytes();assert sha(body)==assets[name]['sha256'];files['firmware/'+name]=body
    files['requirements.txt']=b'pyserial==3.5\n'
    files['README.md']='''# STR8-N 2.0bf1 release package

**This ZIP contains the complete release. Extract the entire folder first.**
Start with [the installed-board quick start](docs/QUICK_START.md) or choose
your installation route below. No other bf1 package download is required.

| Starting point / purpose | Start here |
| --- | --- |
| WDCMONV2 or published beta4, using Windows | [Windows migration quick start](docs/QUICK_START_WINDOWS.md); launchers are in this folder |
| WDCMONV2 or published beta4, using Linux | [Linux migration quick start](docs/QUICK_START_LINUX.md); launchers are in this folder |
| Full system with utilities/apps, using a programmer | `firmware/str8n-2.0bf1-apps-str8n-only.bin`; [address map](docs/RELEASE_PATHS.md) |
| Bootloader/monitor core only, using a programmer | `firmware/str8n-2.0bf1-boot-core-b3.bin`; [scope and address map](docs/RELEASE_PATHS.md) |
| Matching MON A/MON B/F components | All three `.bin` files are in `firmware`; [dependencies and offsets](docs/RELEASE_PATHS.md) |

The full system includes CLOCK 1.11, ASM 0.5, all supported utilities/providers,
UCHESS, both monitors, recovery/core and S/R/T. One firmware set serves 65C02
and 65C816 emulation runtime. Core-only provisioning was tested in the CPU
model; full-system empty-bank migrations passed physical board checks.

## Package contents

- Both Windows `.cmd` and Linux `.sh` migration/recovery launchers here.
- Shared required tools, bf1 payloads and RAM S19 templates in `migration`.
- All firmware BINs in `firmware` (STR8-N only; no WDCMONV2/beta4 images).
- Quick starts, user/operator/ASM/technical manuals, ABI reference, firmware
  maps and Mermaid source/rendered diagrams in `docs`.
- Full credited uChess source and Peter Jennings license in `uchess-source`.
- `LICENSE`, `requirements.txt`, `release-manifest.json` and `SHA256SUMS.txt`.

Use Python 3.10+ and install the one Python dependency with
`python -m pip install -r requirements.txt` (Windows may use `py -3`;
Linux uses `python3`). Read the platform quick start before selecting a port.

## Current prerelease scope

Live migration requires the exact admitted original SXB6 WDCMONV2 or published
beta4 source in B3 and already-erased B0/B1/B2. The RAM tool checks every
source-bank byte before flash mutation. Raw programmer images use provisioning
defaults and are not preserving upgrade scripts. Both layouts use B3 boot/J3;
the F component does not create standalone J0/J1/J2 monitors.

The earlier RTC continuity issue is open and disclosed. The owner accepted the
recorded stopped soak results (2604: 8.290165 hours/30 cycles; 2609: 3.880169
hours/11 cycles). Soaks and RTC sampling remain stopped; no full endurance or
seven-day RTC pass is claimed. Linux extracted software workflows passed;
Linux physical serial migration has not been performed. Native 816 apps/tests,
ACIA and crypto remain deferred. Read [migration/recovery](docs/MIGRATION_RECOVERY.md)
and [all manuals](docs/README.md) for the tested scope and recovery limits.
'''.encode()
    for name,body in files.items():
        assert not name.startswith('/') and '..' not in Path(name).parts
        assert Path(name).name.lower() not in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl')
        if name.endswith(('.md','.py','.json')):assert not re.search(r'C:[\\/](SRC|Users)[\\/]|output[\\/]qualification',body.decode(),re.I)
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)',body.decode()):
                if re.match('[a-z]+:',link):continue
                target=posixpath.normpath((Path(name).parent/link.split('#')[0]).as_posix());assert target in files,(name,target)
    manifest=dict(version='2.0bf1',generation=48,platforms=['Windows','Linux'],source_commit=receipt['source_commit'],single_complete_release=True,
        same_target_for_65C02_and_65C816_emulation=True,full_release_qualified=False,RTC_known_issue_disclosed=True,soaks_accepted_as_recorded=True,
        files={n:dict(bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())})
    files['release-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode();files['SHA256SUMS.txt']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(files.items())).encode()
    path=OUT/'str8n-2.0bf1-release.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,body in sorted(files.items()):
            entry=zipfile.ZipInfo('str8n-2.0bf1/'+name,date_time=(2026,10,18,0,0,0));entry.create_system=3;entry.external_attr=((0o100755 if name.endswith('.sh') else 0o100644)<<16);entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,body)
    with zipfile.ZipFile(path) as z:
        assert len(z.namelist())==len(files) and all(z.read('str8n-2.0bf1/'+n)==b for n,b in files.items())
    report=dict(passed=True,filename=path.name,path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()),files=len(files),source_publication=str(receipt_path),source_publication_sha256=sha(receipt_path.read_bytes()),both_platform_runtime_bytes_unchanged=True,all_source_asset_digests_verified=True,all_manual_links_resolve=True,no_nested_archives=True,board_access=False,publication_pending=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
