"""Package existing g10/2512-qualified components; no build, port or publication."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parents[1]
LABEL='STR8N-MON-g00000010-candidate3'
sha=lambda b:hashlib.sha256(b).hexdigest()

def package(out):
    out=Path(out).resolve();out.mkdir(exist_ok=False);stage=out/LABEL;stage.mkdir()
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    original=ROOT/'dist/base1-0.3.0/STR8N-F-BASE1-0.3.0.zip';foundation=stage/'foundation'
    with zipfile.ZipFile(original) as z:
      for member in z.namelist():
        parts=Path(member).parts;assert parts[0]=='STR8N-F-BASE1-0.3.0'
        target=(foundation/Path(*parts[1:])).resolve();assert target.is_relative_to(foundation.resolve()) and not member.endswith('/')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(member))
    f=(foundation/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f)==4096 and sha(f)==freeze['sha256'];(stage/'F.bin').write_bytes(f)
    # The old published Foundation ZIP remains intact. Only the local extracted
    # copy gets the current console; migrator and Foundation payloads stay exact.
    overlays=['tools/nf_console.py','tools/console_core.py','requirements-console.txt','docs/SERIAL_CONSOLE.md']
    for name in overlays:(foundation/name).write_bytes((ROOT/name).read_bytes())
    build=WORK/'BUILD/storage-installed-auto-r2';bm=json.loads((build/'manifest.json').read_text())
    def artifact(name):
      b=(build/name).read_bytes();assert sha(b)==bm['artifacts'][name]['sha256'];return b
    b1=artifact('B1-candidate.bin');b2=bytearray(artifact('B2-candidate.bin'));b3=artifact('B3-candidate.bin')
    startup=WORK/'BUILD/startup-traditional-r2';sm=json.loads((startup/'manifest.json').read_text())
    status=(startup/'STATUS-ROM.bin').read_bytes();assert sha(status)==sm['artifacts']['STATUS-ROM.bin']['sha256']
    b2[0x2C00:0x3000]=status
    marker=json.loads((WORK/'output/qualification/device-operations/2512.json').read_text())
    assert sha(b1)==marker['current_physical_bank_sha256']['B1'] and sha(b2)==marker['current_physical_bank_sha256']['B2']
    mm=json.loads((startup/'MON/manifest.json').read_text());assert mm['generation']=='00000010'
    catalog=dict(schema=2,F_sha256=sha(f),Foundation='0.3.0 g00000001 BASE1/PR05',MON='0.1.0-dev g00000010',
      WB='g0000000E',storage='SRAM/WORK g4; PROGRAM g3',startup='Traditional firmware',
      profile_reserved_KiB=88,owner_banks='B0 and B1:E/F; existing contents require review before reuse',targets=[])
    payload=stage/'native/payload';payload.mkdir(parents=True)
    def target(bank,address,body,**flags):
      assert bank in (1,2,3) and len(body) in (3072,4096)
      name=f'B{bank}-{address:04X}.bin';(payload/name).write_bytes(body)
      catalog['targets'].append(dict(bank=bank,address=f'{address:04X}',file='native/payload/'+name,sha256=sha(body),**flags))
    for bank,body,pages in ((1,b1,range(6)),(2,b2,range(8))):
      for n in pages:target(bank,0x8000+n*4096,body[n*4096:(n+1)*4096])
    target(3,0x8000,b3[:4096])
    rtc=(ROOT/'monitors/candidates/native-g00000001-r16/RTC-HISTORY-B3-9000.bin').read_bytes()
    target(3,0x9000,rtc[:3072],preserve_RTC_metadata=True)
    for name,info in mm['artifacts'].items():
      if info['variant'] in ('A','B'):
        body=(startup/'MON'/name).read_bytes();assert sha(body)==info['sha256']
        target(3,0xA000 if info['variant']=='A' else 0xB000,body)
    target(3,0xE000,b3[0x6000:0x7000]);assert len(catalog['targets'])==19
    checkpoint=(WORK/'output/qualification/2512-BOOT-CLOCK-positive-20261101-r1/B3-after.bin').read_bytes()
    assert sha(checkpoint)==marker['current_physical_bank_sha256']['B3']
    for item in catalog['targets']:
      if item['bank']==3:
        body=(stage/item['file']).read_bytes();offset=int(item['address'],16)-0x8000
        assert body==checkpoint[offset:offset+len(body)],item['file']
    (stage/'NATIVE-COMPONENTS.json').write_text(json.dumps(catalog,indent=2)+'\n')
    tools=stage/'tools';tools.mkdir()
    for name in ('nf_native_images.py','nf_factory_image.py'):(tools/name).write_bytes((ROOT/'tools'/name).read_bytes())
    docs=stage/'docs';docs.mkdir()
    for name in ('NATIVE_UTILITIES_MANUAL.md','UNIFIED_SHIPPING_RELEASE.md','UNIFIED_ENVIRONMENT_REMAINING.md',
      'CLOCK_FAULT_RAM_2512_ACCEPTANCE.md','BOOT_CLOCK_2512_ACCEPTANCE.md','SERIAL_CONSOLE.md',
      'STORAGE_NATIVE_ACCEPTANCE.md','FLASH_TRANSFER_2512_ACCEPTANCE.md','MON_TRADITIONAL_ROM_ACCEPTANCE.md',
      'NAMED_EDU_2512_ACCEPTANCE.md','TIME_PREP_2512_ACCEPTANCE.md'):
      p=ROOT/'docs'/name
      if p.exists():(docs/name).write_bytes(p.read_bytes())
    # Retain local documentation links without importing captures or binaries.
    todo=list(docs.glob('*.md'));seen=set()
    import re
    while todo:
      p=todo.pop();rel=p.relative_to(stage)
      if rel in seen:continue
      seen.add(rel)
      for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
        if ':' in link or link.startswith('#'):continue
        src=(ROOT/rel.parent/link.split('#')[0]).resolve()
        if not src.is_relative_to(ROOT) or not src.is_file() or src.suffix not in ('.md','.json'):continue
        dest=stage/src.relative_to(ROOT)
        if not dest.exists():
          dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes())
          if dest.suffix=='.md':todo.append(dest)
    (stage/'LICENSE').write_bytes((ROOT/'LICENSE').read_bytes())
    examples=stage/'examples';examples.mkdir()
    # RAM S19 deliberately has no autorun; the operator can inspect the result.
    def srec(kind,address,data=b''):
      row=bytes((len(data)+3,))+address.to_bytes(2,'big')+data
      return f'S{kind}'+(row+bytes((~sum(row)&255,))).hex().upper()+'\r\n'
    (examples/'KEY-S19-3500.s19').write_bytes((srec(0,0,b'STR8N RAM key acceptance')+srec(1,0x3500,b'KEYS')+srec(9,0x3500)).encode())
    for name in ('NFCOPY.asm','BATCH-DEMO.asm'):(examples/name).write_bytes((ROOT/'examples'/name).read_bytes())
    (examples/'NFCOPY-3000.bin').write_bytes(bytes.fromhex('A9 50 20 6D 7E 4C 67 7E'))
    (stage/'README.md').write_text('''# STR8-N MON g10 unified candidate3

A 4 KB foundation for your own environments.
Frozen STR8N-F0.3.0/g1 BASE1/PR05 beneath MON A/B0.1.0-dev/g10.
This is an unpublished acceptance candidate. It has no board-specific name,
settings, journal, EEPROM/SPI contents or vendor WDC firmware.

Read docs/NATIVE_UTILITIES_MANUAL.md. The shared feature target is the familiar
b35 workflow, with ASM/DBG following separately. The newest bytes are accepted
on2512/65C02. Older816 receipts do not qualify this entire candidate on816.
Startup uses the installed, approved Traditional g10 firmware. A different
presentation would require a separate versioned candidate and qualification.

The full profile reserves88KiB: B1:8-D, B2:8-F and B3 (including C/D and F).
B0 and B1:E/F remain outside these utility image targets; inspect existing
contents before reuse. A Foundation-only installation still needs only4KiB.
The19 utility targets exclude F and C/D. Preparing B3:9 retains all1024 current
RTC metadata bytes. B1 targets require a supplied B1 capture and overwrite review.

Run python verify_candidate.py after extraction. No port is opened.
Install pyserial from foundation/requirements-console.txt, then run
python foundation/tools/nf_console.py --port COM4
Console0.1.2 includes Shift+F2/F3 RAM S19; physical-key acceptance remains pending.
The published Foundation RAM migrator/tools/payloads are retained unchanged;
the local console overlay is named in CANDIDATE-MANIFEST.json.

Prepare images only with python tools/nf_native_images.py --help.
Preparation opens no port and grants no flashing permission. Keep captures
private and review every occupied target and any journal rotation first.
No flash/install, full migration or extracted-kit live acceptance has occurred
from this candidate yet. Keep F golden during MON/tools acceptance.

Source/provenance is under source/. Firmware was not rebuilt for packaging.
Source build scripts may require separately archived build inputs; this ZIP's
source-only rebuild has not been accepted. Published ZIPs/tags are unchanged.
''')
    # Source snapshot excludes binaries, tests/vendor, captures and host drivers.
    source=stage/'source';source.mkdir()
    for folder in ('src','monitors/src','monitors/native','monitors/status','tools','migration-host','examples'):
      for p in (ROOT/folder).rglob('*'):
        if p.is_file() and p.suffix in ('.py','.asm','.inc') and 'vendor' not in p.parts and '__pycache__' not in p.parts:
          dest=source/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    (source/'F_FREEZE.json').write_bytes((ROOT/'F_FREEZE.json').read_bytes())
    verifier='''from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;m=json.loads((r/'CANDIDATE-MANIFEST.json').read_text())
actual={p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert actual==set(m['files'])|{'CANDIDATE-MANIFEST.json'}
for name,info in m['files'].items():
 p=(r/name).resolve();assert p.is_relative_to(r);b=p.read_bytes()
 assert len(b)==info['bytes'] and hashlib.sha256(b).hexdigest()==info['sha256'],name
assert (r/'F.bin').read_bytes()==(r/'foundation/firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
print('PASS extracted candidate3 file set/pins; F frozen; no device access')
'''
    (stage/'verify_candidate.py').write_text(verifier)
    manifest=dict(schema=1,status='LOCAL_G10_CANDIDATE_NOT_RELEASE_ACCEPTED',F_sha256=sha(f),F_frozen=True,
      firmware_builds_for_packaging=0,serial_access=False,published=False,source_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      source_working_tree_snapshot=True,source_rebuild_from_extracted_kit_accepted=False,terminal='0.1.2',
      foundation_operator_ZIP_sha256=sha(original.read_bytes()),foundation_overlays=overlays,
      fresh_kit_migration_accepted=False,physical_Shift_keys_accepted=False,latest_816_profile_accepted=False,
      files={p.relative_to(stage).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(stage.rglob('*')) if p.is_file()})
    (stage/'CANDIDATE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    path=out/(LABEL+'.zip')
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
      for p in sorted(stage.rglob('*')):
        if p.is_file():z.write(p,Path(LABEL)/p.relative_to(stage))
    (out/'SHA256SUMS.txt').write_text(sha(path.read_bytes())+'  '+path.name+'\n')
    print(path);print('19 utility targets;88KiB allocation;terminal0.1.2;no build/port/publication')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();package(a.out)
