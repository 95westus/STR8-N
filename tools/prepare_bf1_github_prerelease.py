"""Stage an allowlisted public bf1 package from unchanged pinned payloads."""
import json,hashlib,zipfile,re,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=ROOT/'output/releases/bf1-github-prerelease-2026-10-17';assert not out.exists();out.mkdir()
    package=out/'package';package.mkdir();candidate=ROOT/'release/candidates/batchfix-r1'
    pin_path=Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json';pin=read(pin_path)
    build=ROOT/'tmp/bfx5/build-report.json';assert sha(build)==pin['build_report_sha256']
    ref=read(ROOT/'tmp/bf1k4/reference-build.json');provenance=read(candidate/'source-provenance.json');assert len(provenance)==97
    def copy(src,name):
        dest=package/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    base='release/candidates/batchfix-r1/'
    for name,info in provenance.items():
        p=candidate/name;assert sha(p)==info['sha256']==ref['source_files'][name];copy(p,base+name)
    for name in ('build.py','release.json','source-provenance.json','LICENSE','README.md'):copy(candidate/name,base+name)
    assert sha(candidate/'build.py')==ref['builder_sha256'] and sha(candidate/'release.json')==ref['release_manifest_sha256']
    for name,info in pin['artifacts'].items():
        p=ROOT/'tmp/bfx5/payload'/name;assert sha(p)==info['sha256'] and p.stat().st_size==info['bytes'];copy(p,base+'payload/'+name)
    copy(ROOT/'tmp/bf1k4/reference-build.json','reference-build.json');copy(ROOT/'LICENSE','LICENSE')
    for p in (ROOT/'docs/bf1').glob('*.md'):copy(p,'docs/bf1/'+p.name)
    copy(ROOT/'docs/STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md','docs/STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md')
    qualification='''# bf1 qualification summary

2.0bf1 generation 48 fixes native-utility/CLOCK BATCH handoffs under both monitor
slots. One pinned FT245/F30D firmware set was checked on 65C02 board 2604 and
65C816 board 2609 with emulation-mode runtime. The unchanged brief native-mode
startup detector exception is accepted; native 816 applications, ACIA and crypto
remain deferred. Native utility means the monitor utility provider, not a
native-mode 65C816 application.

The source-only build produced the 19 pinned artifacts in reference-build.json.
Packaging reuses unchanged source/build and prior offline evidence; it does not
claim a fresh firmware build or ABI suite. Initial 2604 B/A and 2609 B/A checks
passed. 2609 had 12 groups per slot and 14 emulation runtime observations.
Original A40/B35 payload restoration and two verified-transfer-boundary electrical
interruptions on 2609 passed exact cut-state/fallback/recovery, utility/CLOCK
BATCH, retained-device preservation and original application RAM restoration.
Second recovery updated two journals without erasing committed A payload.
Normal boot logged expected PF events; no manual ACK/CLEAR was issued.

No mid-erase/program, arbitrary byte timing or 2604 electrical qualification is
claimed. Only exact captured 2604/2609 migration lineages were admitted; there
is no generic stock/legacy/core/private-ABI conversion permission.

Publication is gated on the six-hour 2609 preserving soak and verified RAM
restoration. The 72-hour/300-cycle 2604 and seven-day RTC gates remain pending.
Full release qualification is false. See the
[accepted policy](STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).
'''
    (package/'docs/STR8N_V2_BATCHFIX_R1.md').write_text(qualification,encoding='utf-8')
    for board,cpu in (('2604','65C02'),('2609','65C816 emulation')):
        (package/f'docs/STR8N_BF1_{board}_INSTALL_RECOVERY.md').write_text(f'''# {board} bf1 route: public summary

Board {board}, {cpu}, FT245/F30D. The exact captured B-first/A-second migration
route and both-slot initial checks passed using the pinned bf1 firmware set.
Private original backups, current wear counters and independently read preimages
are required to reproduce a preserving transaction. They are not public assets.

The binary components are not whole-bank images or a universal installer.
Do not overwrite current configuration/wear journals with historical or generic
records. No installation on an uncaptured stock/legacy layout is admitted.
The public package contains no hardware operation launcher or board backup.

The [qualification summary](STR8N_V2_BATCHFIX_R1.md) states physical coverage
and limits. The [accepted policy](STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md) states
soak, RTC and prerelease gates. Native 816 applications/tests, ACIA and crypto
remain deferred. Clocks, trims and original RTC baseline remain unchanged.
''',encoding='utf-8')
    (package/'README.md').write_text('''# STR8-N 2.0bf1 pilot prerelease

Generation 48; CLOCK 1.11; FT245/F30D. One firmware set supports 65C02 and
65C816 emulation-mode runtime. Native 816 applications/tests, ACIA and crypto
remain deferred. Existing startup CPU detection briefly enters native mode
before restoring E=1; this unchanged exception is accepted.

Start with the [manuals](docs/bf1/README.md), [qualification summary](docs/STR8N_V2_BATCHFIX_R1.md)
and [accepted soak/RTC policy](docs/STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).
Tonight's prerelease is conditional on the six-hour 2609 soak and verified RAM
restoration. The 72-hour/300-cycle 2604 and seven-day RTC gates are pending.
This is not a fully qualified release or a generic installation package.

All 19 exact pinned binary/application artifacts are under
release/candidates/batchfix-r1/payload. Monitor A0/B0 .bin files are 4096-byte
components, not complete flash bank or device programmer images. Other stored
providers must match this set. Do not combine them with older BATCH providers.
Only exact separately admitted 2604/2609 migration lineages are supported.
No automatic stock/legacy installation, settings reset or wear rollback is
provided. Retain your own full backup before any separately planned migration.

Reproduce from source with Python, WDC02AS and WDCLN on PATH:

```text
python release/candidates/batchfix-r1/build.py --out C:\\tmp\\bf1build
```

Use a fresh short output directory. Compare all artifacts against
reference-build.json and SHA256SUMS. The frozen candidate README/release.json
record original offline development permissions; current pilot publication
scope is documented in the accepted-policy guide. Firmware inputs are unchanged.
No v2.1 payloads, board dumps, EEPROM/SRAM backups, private receipts or serial
logs are distributed.
''',encoding='utf-8')
    files={p.relative_to(package).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(package.rglob('*')) if p.is_file()}
    manifest=dict(version='2.0bf1',generation=48,build_report_sha256=sha(build),sources=97,artifacts=pin['artifacts'],files=files,distribution='pilot prerelease; publication conditional on six-hour 2609 gate',full_release_qualified=False,generic_installation_permitted=False,RTC_target_ppm=5,RTC_maximum_halfwidth_ppm=2,RTC_minimum_segment_hours=168,deferred=['native 816','ACIA','crypto'])
    (package/'public-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (package/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(package).as_posix()}\n' for p in sorted(package.rglob('*')) if p.is_file()))
    archive=out/'str8n-2.0bf1-prerelease.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(package.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(package).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    assets=[archive]
    for slot in ('a0','b0'):
        p=out/f'str8n-2.0bf1-monitor-{slot}.bin';shutil.copyfile(package/base/f'payload/str8n-v2-recovery-slot-{slot}.bin',p);assets.append(p)
    checksums=out/'str8n-2.0bf1-assets.sha256';checksums.write_text(''.join(f'{sha(p)}  {p.name}\n' for p in assets));assets.append(checksums)
    for p in package.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if re.match(r'[a-z]+:',link):continue
            target=(p.parent/link.split('#')[0]).resolve();assert target.is_relative_to(package.resolve()) and target.is_file(),(p,link)
    assert not any(p.name.lower() in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl') for p in package.rglob('*'))
    receipt=dict(prepared=True,created_utc=datetime.now(timezone.utc).isoformat(),directory=str(out.resolve()),package=str(package.resolve()),source_count=97,artifact_count=19,assets={p.name:dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in assets},full_release_qualified=False,board_access=False)
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
