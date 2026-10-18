"""Verify a bf1 local review extraction using Python stdlib, without devices."""
import argparse,hashlib,json,os,re
from pathlib import Path,PurePosixPath

def require(value,message):
    if not value:raise ValueError(message)
def digest(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def safe(name):
    p=PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and p.as_posix()==name and not any(v in ('.','..') for v in p.parts) and '\\' not in name and ':' not in name,'Unsafe path: '+name)
    require(p.name.lower() not in ('b0.bin','b1.bin','b2.bin','b3.bin'),'Full-bank dump forbidden')
    return p
def s19(data):
    cells={};entry=None
    for line in data.decode('ascii').splitlines():
        require(bool(re.fullmatch(r'S[019][0-9A-F]+',line)),'Invalid S-record syntax')
        raw=bytes.fromhex(line[2:]);require(len(raw)==raw[0]+1 and sum(raw)&255==255,'Invalid S-record checksum')
        address=int.from_bytes(raw[1:3],'big')
        if line[1]=='1':
            for n,v in enumerate(raw[3:-1],address):require(n not in cells,'Overlapping S-record');cells[n]=v
        elif line[1]=='9':require(entry is None,'Duplicate entry');entry=address
    return cells,entry
def verify(root):
    root=Path(root).resolve();m=read(root/'review-manifest.json')
    require((m['candidate_id'],m['version'],m['generation'])==('batchfix-r1','2.0bf1',48),'Wrong candidate')
    require(all(m[k] is False for k in ('installation_permitted','release_qualified','publication_permitted')),'Review permission flags')
    require(set(m['deferred'])=={'native 816','ACIA','crypto'},'Deferred scope')
    names=list(m['files']);allow=read(root/'review-allowlist.json')
    require(len(allow)==len(set(allow)) and set(names)==set(allow),'Manifest/allowlist mismatch')
    require(len(names)==len({v.casefold() for v in names}),'Case collisions')
    for name in names:
        safe(name);file=root/name
        require(file.resolve().is_relative_to(root),'Escaping file')
        for item in (file,*file.parents):
            if item==root:break
            require(not item.is_symlink() and not getattr(item,'is_junction',lambda:False)(),'Link/reparse point forbidden')
        require(file.is_file(),'Missing file: '+name)
        data=file.read_bytes();info=m['files'][name]
        require(len(data)==info['bytes'] and digest(data)==info['sha256'],'Size/hash mismatch: '+name)
    actual=set()
    for folder,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(folder)/name
            require(not p.is_symlink() and not getattr(p,'is_junction',lambda:False)(),'Link/reparse point forbidden')
            require(p.resolve().is_relative_to(root),'Escaping file')
        actual.update((Path(folder)/name).relative_to(root).as_posix() for name in files)
    require(actual==set(names)|{'review-manifest.json'},'Missing or unexpected review files')
    scope=read(root/'release/bf1-prerelease/acceptance-scope.json')
    require(scope['candidate_id']=='batchfix-r1' and scope['display_version']=='2.0bf1' and scope['generation']==48 and scope['clock_version']=='1.11','Scope identity')
    require(scope['processor_execution_scope']=='65C02 and 65C816 emulation-mode runtime' and scope['console_profile']=='FT245/F30D','Processor/profile scope')
    require(scope['migration_scope']=='Exact captured 2604 and 2609 lineages, each with separately pinned bf1 B-first/A-second route; no generic stock, legacy, core or private-ABI conversion claim','Migration scope')
    require(set(scope['deferred'])=={'native 816','ACIA','crypto'},'Scope deferrals')
    require(all(scope[k] is False for k in ('installation_permitted','release_qualified','publication_permitted')),'Scope permission flags')
    require(scope['campaign']['clock_trim_changes_permitted'] is False and scope['campaign']['baseline_replacement_permitted'] is False,'Campaign preservation scope')
    require(scope['campaign']['soak_board']=='2604' and set(scope['campaign']['rtc_snapshot_boards'])=={'2512','2604','2609'} and set(scope['campaign']['powered_off_boards'])=={'2205'},'Campaign board scope')
    require(scope['startup_detection_exception']=='Unchanged F30D detection briefly enters native mode then restores emulation; owner explicitly accepted','Startup exception scope')
    hardware=read(root/'evidence/shared-cpu-acceptance.json')
    require(hardware['passed'] and hardware['one_firmware_set'] and hardware['emulation_runtime_observations']==14,'Shared hardware acceptance')
    require(all(hardware[k] is False for k in ('release_qualified','installation_permitted','publication_permitted','clocks_trims_settings_changed')),'Hardware permission flags')
    preflight=(root/'evidence/shared-firmware-preflight.json').read_bytes()
    require(digest(preflight)==hardware['shared_preflight_sha256'],'Hardware preflight binding')
    prior=(root/'evidence/2604-A-report.json').read_bytes()
    require(digest(prior)==hardware['prior_65C02_report_sha256']==json.loads(preflight)['prior_2604_hardware_report_sha256'],'Prior hardware binding')
    for phase in ('B','A'):
        data=(root/f'evidence/2609-{phase}-report.json').read_bytes();r=json.loads(data)
        require(digest(data)==hardware['phase_receipts'][phase]['report_sha256'],'Hardware report binding')
        require(r['passed'] and r['full_flash_verified'] and r['application_ram_restored'] and r['ports_released'],'Hardware completion')
        require(len(r['checks'])==12 and all(c['passed'] for c in r['checks']),'Hardware check groups')
        confirmation=(root/f'evidence/2609-{phase}-reset.json').read_bytes()
        require(digest(confirmation)==r['reset_confirmation_sha256'] and json.loads(confirmation)['user_confirmed_physical_reset'],'Hardware reset binding')
        modes=[r[k] for k in ('cpu_mode_before','cpu_after_clock','cpu_after_batch','cpu_mode_after')]+list(r['cpu_exit_checks'].values())
        require(len(modes)==7,'Runtime observation count')
        for mode in modes:
            require(mode['detected_cpu']=='65C816' and mode['emulation_mode_before_probe'] and mode['dbr']==mode['pbr']==mode['direct_page']==0 and mode['entry_irq_disabled'] and mode['entry_decimal_clear'] and not mode['probe_enters_native_mode'] and not mode['native_monitor_calls_advertised'],'Emulation runtime contract')
    base='release/candidates/batchfix-r1/';provenance=read(root/(base+'source-provenance.json'));reference=read(root/'reference-build.json')
    require(reference['candidate_id']=='batchfix-r1' and reference['generation']==48,'Reference identity')
    require({v for v in names if v.startswith(base+'source/')}=={base+v for v in provenance},'Source inventory')
    for name,info in provenance.items():
        require(digest((root/(base+name)).read_bytes())==info['sha256']==reference['source_files'][name],'Source provenance mismatch')
    require(digest((root/(base+'build.py')).read_bytes())==reference['builder_sha256'],'Builder binding')
    require(digest((root/(base+'release.json')).read_bytes())==reference['release_manifest_sha256'],'Release binding')
    require(len(reference['artifacts'])==19,'Artifact count')
    require({v for v in names if v.startswith(base+'payload/')}=={base+'payload/'+v for v in reference['artifacts']},'Payload inventory')
    for name,info in reference['artifacts'].items():
        data=(root/(base+'payload/'+name)).read_bytes()
        require(dict(bytes=len(data),sha256=digest(data))==info,'Payload binding')
    helper=read(root/'helper-reference.json')
    require(helper['bytes']==585 and helper['entry']==0x3000,'Helper identity')
    for name,expected in helper['source_files'].items():
        require(digest((root/('release/candidates/batchfix-route-r1/source/'+name)).read_bytes())==expected,'Helper source binding')
    links=0
    for name in names:
        if not name.endswith('.md'):continue
        text=(root/name).read_text(encoding='utf-8')
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if re.match(r'[a-z]+:',link):continue
            target=((root/name).parent/link.split('#')[0]).resolve()
            require(target.is_relative_to(root) and target.is_file(),'Broken/escaping document link: '+name);links+=1
    example=(root/'examples/asm-print-a.bin').read_bytes()
    require(example==bytes.fromhex('78d8a941206d7e4c677e'),'Example bytes')
    for slot in ('A','B'):
        cells,entry=s19((root/f'examples/{slot}-example.s19').read_bytes())
        require(cells==dict(enumerate(example,0x200)) and entry==0x200,'Example S19 mismatch')
    guide=(root/'docs/bf1/ASM_GUIDE.md').read_text(encoding='utf-8')
    require(re.search(r'```asm\n(.*?)```',guide,re.S).group(1).encode()==(root/'examples/asm-print-a.numbered.txt').read_bytes(),'Example source mismatch')
    from verify_physical import verify_physical
    physical=verify_physical(root,require)
    return dict(passed=True,candidate_id='batchfix-r1',files=len(names)+1,sources=len(provenance),artifacts=19,local_links=links,example_bytes=len(example),physical=physical,board_access=False,release_qualified=False,installation_permitted=False,publication_permitted=False,deferred=['native 816','ACIA','crypto'])
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',type=Path);a=ap.parse_args();print(json.dumps(verify(a.root),indent=2))
