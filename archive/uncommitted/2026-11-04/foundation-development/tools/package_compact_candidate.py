"""Package the qualified compact profile once; no assembly, serial or publish."""
import argparse,hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parents[1]
LABEL='STR8N-UNIFIED-MON-g00000010-ASMDBG-g2-candidate4'
sha=lambda b:hashlib.sha256(b).hexdigest()

def package(out):
    out=Path(out).resolve()
    if not out.is_relative_to(WORK/'BUILD') or out.exists():raise ValueError('Use a fresh BUILD output directory')
    protected={p:sha(p.read_bytes()) for p in (ROOT/'dist').rglob('*') if p.is_file()}
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text());f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f)==4096 and sha(f)==freeze['sha256']=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
    assert all(sha((ROOT/name).read_bytes())==value for name,value in freeze['sources'].items())
    q=WORK/'output/qualification';cleanup=json.loads((q/'2604-2609-REC-cleanup-complete-20261102.json').read_text());assert cleanup['passed']
    banks={board:{b:(q/f'{board}-REC-utility-cleanup-installed-20261102-r1/B{b}-after.bin').read_bytes() for b in range(4)} for board in ('2604','2609')}
    for board,parts in banks.items():
        marker=json.loads((q/f'device-operations/{board}.json').read_text());assert {f'B{b}':sha(v) for b,v in parts.items()}==marker['current_physical_bank_sha256']
    assert banks['2604'][1]==banks['2609'][1] and banks['2604'][2]==banks['2609'][2]
    out.mkdir(parents=True);stage=out/LABEL;stage.mkdir()
    def put(name,body):
        p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    def text(name,body):put(name,body.encode('utf-8'))
    original=ROOT/'dist/base1-0.3.0/STR8N-F-BASE1-0.3.0.zip';foundation_files={}
    with zipfile.ZipFile(original) as z:
        for info in z.infolist():
            parts=Path(info.filename).parts;assert parts[0]=='STR8N-F-BASE1-0.3.0' and not info.is_dir()
            relative=Path(*parts[1:]);dest=(stage/'foundation'/relative).resolve();assert dest.is_relative_to((stage/'foundation').resolve())
            body=z.read(info);put('foundation/'+relative.as_posix(),body);foundation_files[relative.as_posix()]=sha(body)
    assert (stage/'foundation/firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()==f
    put('F.bin',f);put('LICENSE',(ROOT/'LICENSE').read_bytes())
    for name in ('nf_console.py','console_core.py'):put('terminal/'+name,(ROOT/'tools'/name).read_bytes())
    put('requirements-console.txt',(ROOT/'requirements-console.txt').read_bytes())
    text('terminal.py','''"""Launch the unchanged current console with Foundation's asset directory."""
from pathlib import Path
import runpy,sys
r=Path(__file__).resolve().parent
p=r/'terminal/nf_console.py'
sys.path.insert(0,str(p.parent))
sys.argv=[str(p),'--kit',str(r/'foundation')]+sys.argv[1:]
runpy.run_path(str(p),run_name='__main__')
''')
    text('Start-Terminal.cmd','''@echo off
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0terminal.py" %*
) else (
  py -3 "%~dp0terminal.py" %*
)
'''.replace('\n','\r\n'))
    rec={}
    for name,folder in (('MAINT',WORK/'BUILD/loadable-maint-full-r2'),('FLASH',WORK/'firmware/ram-tools/flash-g2')):
        meta=json.loads((folder/'manifest.json').read_text());body=(folder/(name+'.bin')).read_bytes();assert sha(body)==meta['sha256']
        put(f'rec/{name}.bin',body);rec[name]=dict(file=f'rec/{name}.bin',load='0200',entry='0200',bytes=len(body),sha256=sha(body),end=f'{0x1ff+len(body):04X}',MON_required=False,SPI_required=False)
        put(f'provenance/{name}-RAM-manifest.json',(folder/'manifest.json').read_bytes())
    catalog=dict(schema=3,profile='Compact unified MON/ASM/DBG with REC utilities',Foundation='0.3.0 g00000001 BASE1/PR05',F_sha256=sha(f),MON='0.1.0-dev g00000010',WB='g0000000E',PROGRAM='g3',SRAM_WORK='g4',ASM_DBG='g2',startup='Traditional',profile_allocated_KiB=92,erased_sector_KiB_on_reference_boards=36,REC_utilities=rec,targets=[],retirement_targets=[])
    def target(bank,address,role,body=None,variants=None,**flags):
        item=dict(bank=bank,address=f'{address:04X}',role=role,**flags)
        if variants:
            item['variants']={}
            for cpu,b in variants.items():
                file=f'native/payload/B{bank}-{address:04X}-{cpu}.bin';put(file,b);item['variants'][cpu]=dict(file=file,sha256=sha(b))
        else:
            file=f'native/payload/B{bank}-{address:04X}.bin';put(file,body);item.update(file=file,sha256=sha(body))
        catalog['targets'].append(item)
    for page in (0xa0,0xb0,0xc0,0xd0):
        offset=(page-0x80)*256;v={cpu:banks[board][0][offset:offset+4096] for cpu,board in (('65c02','2604'),('65c816e','2609'))}
        role='ASM AP/02 and helper' if page<0xc0 else 'DBG AP/02 and paired SF/1 provider'
        if page in (0xa0,0xc0):
            assert v['65c02'][:8]==v['65c816e'][:8]==b'AP\x02 PR05'
            assert v['65c02'][15]==2 and v['65c816e'][15]==0x16
            target(0,page*256,role,variants=v)
        else:assert v['65c02']==v['65c816e'];target(0,page*256,role,body=v['65c02'])
    for page in (0xa0,0xb0,0xc0,0xd0):
        offset=(page-0x80)*256;target(1,page*256,'Shared transfer' if page==0xa0 else 'SRAM/WORK',body=banks['2604'][1][offset:offset+4096])
    for page in (0x80,0x90,0xa0,0xb0,0xc0,0xd0,0xf0):
        offset=(page-0x80)*256;target(2,page*256,'STATUS' if page==0xf0 else ('CLOCK' if page>=0xb0 else 'WB/PROGRAM/loaders'),body=banks['2604'][2][offset:offset+4096])
    for page in (0x80,0x90,0xa0,0xb0,0xe0):
        offset=(page-0x80)*256;length=3072 if page==0x90 else 4096
        a=banks['2604'][3][offset:offset+length];b=banks['2609'][3][offset:offset+length];assert a==b
        target(3,page*256,{0x80:'RTC/I2C',0x90:'RTC history code; retain final1KiB metadata',0xa0:'MON A g10',0xb0:'MON B g10',0xe0:'Shared dispatcher/maps/APPS'}[page],body=a,**({'preserve_RTC_metadata':True} if page==0x90 else {}))
    assert len(catalog['targets'])==20
    ff=b'\xff'*4096;put('native/payload/ERASED-4096.bin',ff)
    for bank,pages in ((0,(0x80,0x90,0xe0,0xf0)),(1,(0x80,0x90,0xe0,0xf0)),(2,(0xe0,))):
        for page in pages:catalog['retirement_targets'].append(dict(bank=bank,address=f'{page*256:04X}',role='Explicitly reviewed obsolete/owner image retirement',file='native/payload/ERASED-4096.bin',sha256=sha(ff)))
    text('NATIVE-COMPONENTS.json',json.dumps(catalog,indent=2)+'\n')
    for name,build in (('ASM-RAM.bin','asm-flash-source-g2-r4'),('DBG-RAM.bin','dbg-base1-g2-r1')):
        folder=WORK/'BUILD'/build;meta=json.loads((folder/'manifest.json').read_text());body=(folder/name).read_bytes();assert sha(body)==meta['artifacts'][name]['sha256'];put('developer/'+name,body)
    for name in ('nf_compact_images.py','nf_factory_image.py','journal_rotation_plan.py','native_journal_room.py'):put('tools/'+name,(ROOT/'tools'/name).read_bytes())
    for name in ('NATIVE_UTILITIES_MANUAL.md','DEVELOPER_MANUAL.md','UNIFIED_CANDIDATE_STATUS.md','SERIAL_CONSOLE.md'):put('docs/'+name,(ROOT/'docs'/name).read_bytes())
    text('README.md',README)
    text('examples/HELLO.asm','''10 ; Print a marker, then return through Foundation HOLD.
20 ORG $0200
30 LDA #$23
40 JSR $7E6D
50 JMP $7E67
60 END
''')
    for name in ('NFCOPY.asm','BATCH-DEMO.asm'):put('examples/'+name,(ROOT/'examples'/name).read_bytes())
    put('examples/NFCOPY-3000.bin',bytes.fromhex('A950206D7E4C677E'))
    row=bytes.fromhex('0735004B455953');put('examples/KEY-S19-3500.s19',b'S1'+(row+bytes((~sum(row)&255,))).hex().upper().encode()+b'\r\nS9033500C7\r\n')
    # Project source only; never carry captured banks, vendor firmware, logs,
    # device markers, RTC campaign data or a private source program into ZIP.
    for folder in ('src','monitors/src','monitors/native','monitors/status','monitors/devtools/base1','tools','migration-host','examples'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.asm','.inc','.py') and not any(x.lower() in ('vendor','__pycache__') for x in p.parts):put('source/'+p.relative_to(ROOT).as_posix(),p.read_bytes())
    put('source/F_FREEZE.json',(ROOT/'F_FREEZE.json').read_bytes())
    put('source/host-tools/build_loadable_maint.py',(WORK/'tools/build_loadable_maint.py').read_bytes())
    for folder,label in ((WORK/'BUILD/native-apps-g1-maint-r1','reference'),(WORK/'BUILD/loadable-maint-full-r2','adapter')):
        for p in folder.iterdir():
            if p.suffix in ('.asm','.inc'):put('source/rec-maint/'+label+'/'+p.name,p.read_bytes())
    qa=dict(status='CURRENT_COMPONENTS_QUALIFIED_NEW_ZIP_LIVE_PENDING',F_sha256=sha(f),REC_utilities=rec,CPU_paths={'65c02':['2512','2604'],'65c816e':['2609']},native_816=False,
        compact_cleanup=dict(total_erases=21,F_writes=0,MON_writes=0,SPI_writes=0,RTC_setting_writes=0,old_2604_D_rows_host_archived=16,old_2609_rows_retained_on_chip=17),
        source_receipts={name:sha((q/name).read_bytes()) for name in ('2604-2609-REC-cleanup-complete-20261102.json','2512-loadable-full-MAINT-20261102-r2/report.json','2609-REC-cleanup-tools-20261102-r1/report.json')},
        fixture_limits=['Positive source-write acceptance remains scoped to2512','ASM encodes65C02;816 emulation common subset only','Persistent EDU SAVE/named X REC front door not present','New ZIP extracted live/physical-key/migration trial not performed'])
    text('evidence/QUALIFICATION.json',json.dumps(qa,indent=2)+'\n')
    text('verify_candidate.py',VERIFIER)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest=dict(schema=4,label=LABEL,status='LOCAL_CANDIDATE4_EXTRACTED_LIVE_ACCEPTANCE_PENDING',F_sha256=sha(f),F_frozen=True,firmware_builds_for_packaging=0,serial_access=False,published=False,
        source_base_commit=head,source_working_tree_snapshot=True,source_rebuild_qualified=False,terminal='0.1.2 exact current files; root launcher uses --kit foundation',foundation_operator_ZIP_sha256=sha(original.read_bytes()),foundation_files_unchanged=foundation_files,
        current_component_CPU_paths_accepted=['65c02','65c816e'],new_ZIP_live_accepted=False,new_ZIP_migration_accepted=False,
        files={p.relative_to(stage).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(stage.rglob('*')) if p.is_file()})
    text('CANDIDATE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    path=out/(LABEL+'.zip')
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,Path(LABEL)/p.relative_to(stage))
    extracted=out/'extracted';extracted.mkdir()
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for info in z.infolist():
            dest=(extracted/info.filename).resolve();assert dest.is_relative_to(extracted.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
    kit=extracted/LABEL;checks=[]
    commands=[[sys.executable,'verify_candidate.py'],[sys.executable,'terminal.py','--help'],[sys.executable,'terminal.py','--version'],[sys.executable,'tools/nf_compact_images.py','--help'],[sys.executable,'tools/nf_factory_image.py','--help']]
    for command in commands:
        done=subprocess.run(command,cwd=kit,capture_output=True,text=True);checks.append(dict(command=command,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr));assert done.returncode==0,done.stdout+done.stderr
    for cpu,board in (('65c02','2604'),('65c816e','2609')):
        fixture=q/f'{board}-REC-utility-cleanup-installed-20261102-r1';prepared=out/f'host-prepared-{cpu}'
        cmd=[sys.executable,str(kit/'tools/nf_compact_images.py'),'--cpu',cpu,'--retire-obsolete']
        for b in range(4):cmd += [f'--current-b{b}',str(fixture/f'B{b}-after.bin')]
        done=subprocess.run(cmd+['--out',str(prepared)],cwd=kit,capture_output=True,text=True);checks.append(dict(CPU=cpu,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr));assert done.returncode==0,done.stdout+done.stderr
        plan=json.loads((prepared/'install-plan.json').read_text());assert len(plan['targets'])==29 and plan['total_erases']==plan['journal_appends']==0
        assert all(v['identical_to_capture'] for v in plan['targets'])
        assert (prepared/'B3-9000.bin').read_bytes()[3072:]==banks[board][3][0x1c00:0x2000]
        assert (prepared/'retained-CD-history.bin').read_bytes()==banks[board][3][0x4000:0x6000]
    # A missing occupied-bank capture is rejected before any output exists.
    negative=out/'missing-B0-refused';command=[sys.executable,str(kit/'tools/nf_compact_images.py'),'--cpu','65c02','--current-b1','x','--current-b2','x','--current-b3','x','--out',str(negative)]
    done=subprocess.run(command,cwd=kit,capture_output=True,text=True);assert done.returncode!=0 and '--current-b0' in done.stderr and not negative.exists()
    assert {p:sha(p.read_bytes()) for p in (ROOT/'dist').rglob('*') if p.is_file()}==protected
    assert all(sha((ROOT/name).read_bytes())==value for name,value in freeze['sources'].items()) and sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==sha(f)
    (out/'SHA256SUMS.txt').write_text(sha(path.read_bytes())+'  '+path.name+'\n',encoding='ascii')
    receipt=dict(passed=True,ZIP=str(path),ZIP_sha256=sha(path.read_bytes()),ZIP_bytes=path.stat().st_size,files=len(manifest['files'])+1,extracted_kit=str(kit),extraction_verified=True,terminal_CLI_passed=True,both_CPU_host_preparation_passed=True,missing_bank_refused=True,RTC_metadata_exact=True,CD_history_exact=True,firmware_builds=0,CPU_simulations=0,board_access=False,published_downloads_unchanged=True,F_unchanged=True,new_ZIP_live_acceptance_pending=True,checks=checks)
    (out/'packaging-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='checks'},indent=2));return path

README='''# Unified STR8-N candidate4

**A 4 KB foundation for your own environments.**
Up to four selectable banked environments, one at a time on shared CPU/RAM.

Frozen Foundation **0.3.0 g00000001 BASE1/PR05**, MON A/B **0.1.0-dev g10**,
WB2/PROGRAM, CLOCK, SRAM/WORK, **ASM/DBG g2**, and full **REC-loaded MAINT/FLASH**.
For W65C02SXB/65C02 and W65C816SXB/816 emulation, with optional matching EDU.
The compact profile allocates 92 KiB and leaves 36 KiB in erased sectors on the
qualified cleaned boards. It does not assume a user's owner sectors are free.

Start with [the operator manual](docs/NATIVE_UTILITIES_MANUAL.md),
[ASM/DBG guide](docs/DEVELOPER_MANUAL.md), and
[qualification/remaining gates](docs/UNIFIED_CANDIDATE_STATUS.md).

    python verify_candidate.py
    python -m pip install -r requirements-console.txt
    python terminal.py

Or open Start-Terminal.cmd on Windows. The current Python terminal is in
terminal/; the launcher selects Foundation presets using --kit foundation.
It does not connect or flash automatically. F2 chooses rec/MAINT.bin or
rec/FLASH.bin; F4 loads at an observed REC>. Both start at $0200 and work
without stored utility copies or SPI SRAM. Main Q restarts Foundation using
the saved policy; MON Q returns to REC>.

native/payload contains twenty active component sectors, with explicit CPU
envelopes for ASM/DBG. F and C/D are excluded. The history-code prefix retains
the target board's final 1 KiB metadata when prepared. tools/nf_compact_images.py
requires all four private captures and only prepares/reviews a plan; it opens
no port. --retire-obsolete proposes nine additional sectors and requires
occupied-image/history review. It never grants permission to erase.

The published Foundation operator subkit in foundation/ is byte-for-byte
unchanged, including its legal WDC RAM migration workflow and original
manifest. F.bin is its exact 4096-byte F. No vendor WDC firmware, private board
capture, settings, journal or calibration is distributed. Keep an original WDC
host backup; this full ASM/DBG layout uses B0:A-D.

This is a new local candidate ZIP, not a published release. Its extraction,
hashes, terminal CLI and host preparation are checked; its own live extracted
acceptance remains pending. The qualified component/older archive passes are
recorded separately. The REC g1 MAINT lacks the later EDU SAVE/named X front
doors; native816, physical factory restoration and source-only rebuilding are
separate gates. Source and provenance are included, not a claim of a qualified
standalone source rebuild. No firmware compilation, flashing, tag/ref update
or publication occurs in packaging. Existing downloads stay unchanged.
'''

VERIFIER='''"""Verify this extracted kit only; no serial/application imports."""
import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parent;m=json.loads((r/'CANDIDATE-MANIFEST.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
actual={p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert actual==set(m['files'])|{'CANDIDATE-MANIFEST.json'}
for name,meta in m['files'].items():
 p=(r/name).resolve();assert p.is_relative_to(r) and not p.is_symlink();b=p.read_bytes()
 assert len(b)==meta['bytes'] and sha(b)==meta['sha256'],name
assert (r/'F.bin').read_bytes()==(r/'foundation/firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
assert len((r/'F.bin').read_bytes())==4096 and sha((r/'F.bin').read_bytes())==m['F_sha256']
for name,pin in m['foundation_files_unchanged'].items():assert sha((r/'foundation'/name).read_bytes())==pin
c=json.loads((r/'NATIVE-COMPONENTS.json').read_text());assert len(c['targets'])==20 and len(c['retirement_targets'])==9
assert not any(x['bank']==3 and x['address'] in ('C000','D000','F000') for x in c['targets']+c['retirement_targets'])
for name,x in c['REC_utilities'].items():assert x['load']==x['entry']=='0200' and sha((r/x['file']).read_bytes())==x['sha256']
print('PASS candidate4 file set, exact Foundation/F, CPU assets and REC BIN pins; no device access')
'''

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);package(p.parse_args().out)
