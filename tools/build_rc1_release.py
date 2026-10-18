"""Compose rc1 from fresh source-built payloads and reviewed user-kit inputs."""
import argparse,hashlib,importlib.util,json,posixpath,re,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/rc1-2026-10-18-r1'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def write(p,value):p.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def prepare():
    assert not OUT.exists();OUT.mkdir(parents=True)
    ref=read(ROOT/'tmp/rc1b1/build-report.json');assert ref['passed'] and ref['version']=='2.0rc1' and ref['generation']==49
    composer=ROOT/'release/rc1-build';composer.mkdir()
    text=(ROOT/'release/bf1-prerelease/build_full_image.py').read_text().replace('bf1','rc1').replace('(48)','(49)').replace('==48','==49').replace('generation=48','generation=49').replace('generation 48','generation 49')
    (composer/'build_full_image.py').write_text(text,encoding='utf-8')
    spec=importlib.util.spec_from_file_location('rc1image',composer/'build_full_image.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    image,ranges=module.compose(ROOT/'tmp/rc1b1/payload',ref);image=bytearray(image[32768:])
    record=(ROOT/'tmp/bf1-distribution-r18/migration/applications/uchess-record.bin').read_bytes();assert image[:len(record)]==b'\xff'*len(record);image[:len(record)]=record
    image=bytes(image);assert len(image)==98304
    firmware=OUT/'firmware';firmware.mkdir();full='str8n-2.0rc1-apps-str8n-only.bin';(firmware/full).write_bytes(image)
    for name,offset,size in [('boot-core-b3',0x10000,32768),('monitor-a',0x12000,4096),('monitor-b',0x13000,4096),('b3-f000-ffff',0x17000,4096)]:
        (firmware/f'str8n-2.0rc1-{name}.bin').write_bytes(image[offset:offset+size])
    write(OUT/'image-report.json',dict(passed=True,version='2.0rc1',generation=49,filename=full,bytes=len(image),sha256=sha(image),bank_order=[1,2,3],full_device_base_offset=32768,applications=['CLOCK','ASM','MAINT','SRAM','WORK','EDU','UCHESS'],providers=['RTC','journal','boot status','battery','local display','version'],sr_table_code_included=True,board_access=False,rc1_hardware_tested=False))
    kit=OUT/'migration';shutil.copytree(ROOT/'tmp/bf1-distribution-r18/migration',kit,ignore=shutil.ignore_patterns('__pycache__'))
    for src in (ROOT/'release/rc1-migration-r1').glob('*.py'):shutil.copyfile(src,kit/src.name)
    for src in (kit/'payload').rglob('*'):
        if src.is_file():shutil.copyfile(ROOT/'tmp/rc1b1/payload'/src.relative_to(kit/'payload'),src)
    prior=read(kit/'hardware-qualification.json')
    qualification=dict(schema=2,version='2.0rc1',generation=49,prior_engine_hardware_passed=True,prior_hardware_version='2.0bf1',rc1_hardware_tested=False,target_model_passed=False,portable_transport_tests_passed=True,live_WDC_debugger_identities=['SXB6'],evidence_sha256=prior['evidence_sha256'],scope='Exact SXB6 original WDC or published beta4 in B3; erased B0/B1/B2; version-only rc1 target',limitations=['rc1 target offline model qualification; inherited bf1 engine hardware evidence','Linux physical serial migration not performed','RTC issue deferred','Occupied-bank upgrades not admitted','Early WDC cuts require an external programmer'])
    write(kit/'hardware-qualification.json',qualification);seal_kit(False)
    with zipfile.ZipFile(ROOT/'output/releases/bf1-complete-release-2026-10-18-r2/str8n-2.0bf1-release-r2.zip') as z:
        files={n.split('/',1)[1]:z.read(n) for n in z.namelist()}
    docs=ROOT/'docs/rc1';assert not docs.exists();docs.mkdir()
    for name,body in files.items():
        if name.startswith('docs/'):
            p=docs/name[5:];p.parent.mkdir(parents=True,exist_ok=True)
            if name.endswith('.md'):
                s=body.decode().replace('2.0bf1','2.0rc1').replace('BF1','RC1').replace('bf1','rc1').replace('generation 48','generation 49').replace('gen 48','gen 49')
                s=s.replace('Only the exact SXB2 65C02 and SXB6 65C816\nprofiles named by the kit are admitted.','Only the exact SXB6 65C816 stock profile is admitted live; SXB2 recognition\nis offline-only. The resulting firmware supports both CPUs.')
                if Path(name).name=='README.md':s+='\n\n## rc1 qualification\n\nFirmware identity is 2.0rc1, generation 49. rc1 was built from source and\nqualified offline; prior bf1 transport and shared-CPU hardware evidence is\nretained. No fresh rc1 hardware installation is claimed. RTC qualification,\nnative 816 applications/tests, ACIA and crypto are deferred. Soaks and RTC\nsampling remain stopped; recorded soak results are accepted as recorded,\nnot a full endurance pass.\n'
                body=s.encode()
            p.write_bytes(body)
    # The published kit already has resolved self-contained manual links.
    for name,body in files.items():
        if name.startswith('uchess-source/') or name.startswith('examples/') or name=='LICENSE':
            p=OUT/'base'/name;p.parent.mkdir(parents=True,exist_ok=True)
            if name.endswith(('.md','.txt')) and name!='uchess-source/LICENSE.txt':body=body.decode().replace('bf1','rc1').encode()
            p.write_bytes(body)
    for name,body in files.items():
        if name.endswith(('.cmd','.sh')) or name=='requirements.txt':
            p=OUT/'base'/name.replace('bf1','rc1');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body.decode().replace('bf1','rc1').replace('BF1','RC1').encode())
    print('Prepared fresh rc1 image, kit and manuals; qualification gate closed pending CPU tests')
def seal_kit(passed):
    kit=OUT/'migration';q=read(kit/'hardware-qualification.json');q['target_model_passed']=passed
    q['required_files']={p.relative_to(kit).as_posix():sha(p.read_bytes()) for p in sorted(kit.rglob('*')) if p.is_file() and p.name not in ('kit-manifest.json','hardware-qualification.json') and '__pycache__' not in p.parts}
    write(kit/'hardware-qualification.json',q)
    files={p.relative_to(kit).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(kit.rglob('*')) if p.is_file() and p.name!='kit-manifest.json' and '__pycache__' not in p.parts}
    write(kit/'kit-manifest.json',dict(candidate_id='rc1',version='2.0rc1',generation=49,files=files,live_installation_enabled=passed,distribution_qualified=False,requires_qualification=True))
def package(commit):
    root=OUT/'package/str8n-2.0rc1';assert not root.exists();shutil.copytree(OUT/'base',root)
    shutil.copytree(ROOT/'docs/rc1',root/'docs');shutil.copytree(OUT/'firmware',root/'firmware')
    shutil.copytree(OUT/'migration',root/'migration',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (root/'README.md').write_text('''# STR8-N 2.0rc1 — complete release

Extract this entire folder. Start with [the board quick start](docs/QUICK_START.md),
[Windows migration](docs/QUICK_START_WINDOWS.md), or [Linux migration](docs/QUICK_START_LINUX.md).
Both platform migration/recovery launchers are here; no other package is needed.

`firmware/str8n-2.0rc1-apps-str8n-only.bin` contains the full system: MON A/B,
boot/core, all providers/utilities, CLOCK 1.11, ASM 0.5, UCHESS and S/R/T.
It is 96 KiB, B1/B2/B3, programmed at full-device offset $08000; B0 is excluded.
Matching B3-only core, MON A, MON B and F component BINs are also included.
See [layouts and dependencies](docs/RELEASE_PATHS.md). Raw BINs are fresh
provisioning images; use the scripts for an admitted preserving migration.

One firmware set supports 65C02 and 65C816 emulation-mode runtime. Live source
profiles are exact SXB6 WDCMONV2 or published beta4 in B3 with erased B0/B1/B2.
No WDCMONV2/beta4 image or private board data is distributed. Keep all local
captures and recovery archives private. Read the recovery limits before installing.

The package includes all quick starts/manuals, public ABI tables, Mermaid
source/rendered diagrams, required S19s/tools, checksums, and fully credited
uChess source/license. [Assemble uchess.a and use S/T/R](docs/UCHESS_ASM_SESSION.md).
Install Python 3.10+ and `python -m pip install -r requirements.txt` (Linux: python3).

rc1 is source-built and verified offline; bf1 hardware engine evidence is retained.
No new rc1 hardware installation is claimed. Recorded stopped soaks are accepted
as recorded (2604 8.290165 h/30 cycles; 2609 3.880169 h/11 cycles), not full
endurance passes. RTC qualification/known continuity issue, native 816 apps/tests,
ACIA and crypto are deferred. Soaks and RTC sampling remain stopped.
''',encoding='utf-8')
    files={p.relative_to(root).as_posix():p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}
    for name,body in files.items():
        assert not re.search(r'C:[\\/](SRC|Users)[\\/]|output[\\/]qualification',body.decode('utf-8','ignore'),re.I),name
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)',body.decode()):
                if re.match('[a-z]+:',link):continue
                target=posixpath.normpath((Path(name).parent/link.split('#')[0]).as_posix());assert target in files,(name,target)
    manifest=dict(version='2.0rc1',generation=49,source_commit=commit,single_complete_release=True,platforms=['Windows','Linux'],rc1_hardware_tested=False,qualification='Source build, CPU/flash models and extracted platform workflows; inherited bf1 engine hardware evidence',deferred=['RTC qualification','native 816 applications/tests','ACIA','crypto'],soaks_and_RTC_sampling_stopped=True,files={n:dict(bytes=len(b),sha256=sha(b)) for n,b in files.items()})
    write(root/'release-manifest.json',manifest);files['release-manifest.json']=(root/'release-manifest.json').read_bytes()
    (root/'SHA256SUMS.txt').write_text(''.join(sha(b)+'  '+n+'\n' for n,b in sorted(files.items())),encoding='utf-8')
    path=OUT/'str8n-v2.0rc1-release.zip'
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if not p.is_file():continue
            entry=zipfile.ZipInfo('str8n-2.0rc1/'+p.relative_to(root).as_posix(),date_time=(2026,10,18,0,0,0));entry.create_system=3;entry.external_attr=((0o100755 if p.suffix=='.sh' else 0o100644)<<16);entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,p.read_bytes())
    write(OUT/'package-report.json',dict(passed=True,path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()),files=len(files)+1,source_commit=commit,no_nested_archives=True))
    print('Built one complete release ZIP:',path)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','admit','package']);p.add_argument('--commit');a=p.parse_args()
    if a.operation=='prepare':prepare()
    elif a.operation=='admit':
        assert read(Q/'rc1-empty-models/CPU-report.json')['passed'] and read(Q/'rc1-beta4-recovery-models/CPU-report.json')['passed'];seal_kit(True);print('Admitted version-only rc1 with actual model proof and prior engine hardware evidence')
    else:assert a.commit and len(a.commit)==40;package(a.commit)
