"""Verify an expanded beta35 review extraction, offline using stdlib only."""
import argparse,hashlib,importlib.util,json,re,sys
from pathlib import Path,PurePosixPath
def require(value,message):
    if not value:raise ValueError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(root):
    root=Path(root).resolve();manifest=json.loads((root/'review-manifest.json').read_text())
    require(manifest['version']=='2.0b35' and manifest['generation']==47,'Wrong candidate')
    require(manifest['installation_permitted'] is False and manifest['release_qualified'] is False,'Review permission flags')
    require(manifest['deferred']==['ACIA','crypto'],'Deferred scope')
    scope=json.loads((root/'release/beta35-prerelease/beta35-route-scope.json').read_text())
    require(scope['owner_scope_approved'] is True and scope['target_monitor_page']==0xb0,'B-target scope required')
    require(scope['version']=='2.0b35' and scope['generation']==47 and scope['deferred']==['ACIA','crypto'],'Scope identity')
    require(scope['installation_permitted'] is False and scope['release_qualified'] is False and scope['hardware_qualified'] is False,'Scope permission flags')
    names=set(manifest['files']);allow=json.loads((root/'review-allowlist.json').read_text())
    require(names==set(allow),'Manifest differs from explicit allowlist')
    require(len(names)==len({n.casefold() for n in names}),'Case collisions')
    for name,info in manifest['files'].items():
        path=PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name,'Unsafe path: '+name)
        require(path.name.lower() not in ['b0.bin','b1.bin','b2.bin','b3.bin'],'Full-bank dump forbidden')
        file=root/name;require(file.stat().st_size==info['bytes'] and sha(file)==info['sha256'],'Size/hash mismatch: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual==names|{'review-manifest.json'},'Missing or unexpected review files')
    sys.path.insert(0,str(root/'release/beta35'));spec=importlib.util.spec_from_file_location('nested_beta35_verify',root/'release/beta35/verify.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    nested=module.verify(root/'release/beta35');require(nested['passed'],'Nested source/payload verification')
    links=0
    for name in names:
        if not name.endswith('.md'):continue
        raw=(root/name).read_bytes()
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:text=raw.decode('cp1252')
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if re.match(r'[a-z]+:',link):continue
            target=(root/name).parent/link.split('#')[0];resolved=target.resolve()
            require(resolved.is_relative_to(root) and resolved.is_file(),'Broken/escaping document link: '+name+' -> '+link);links+=1
    sys.path.insert(0,str(root/'tools'))
    # These three imported tools contain no serial/device operations. Test the
    # actual extracted imports and target/catalog integrity with no board data.
    for name in ['inspect_beta35_source','plan_beta35_offline','plan_beta35_journal_transaction']:sys.modules.pop(name,None)
    import inspect_beta35_source as inspect
    import plan_beta35_offline as planner
    import plan_beta35_journal_transaction as semantic
    require(inspect.ROOT==root,'Offline tool root escaped extraction')
    source,destination,layout,files=planner.load_inputs(root/'release/beta35/payload')
    try:inspect.identify([bytes(32768)]*4,0xa0,source)
    except ValueError as error:require('Unregistered' in str(error),'Unexpected unknown-source refusal')
    else:raise ValueError('Unknown source accepted')
    try:semantic.record(bytes(16),[0]*32,0)
    except ValueError:pass
    else:raise ValueError('Invalid journal sequence accepted')
    example=(root/'examples/asm-print-a.bin').read_bytes();require(example==bytes.fromhex('78d8a941206d7e4c677e'),'Example bytes')
    require(module.read_s19(root/'examples/asm-print-a.s19')==dict(enumerate(example,0x200)),'Example S19 mismatch')
    return dict(passed=True,files=len(names)+1,sources=nested['sources'],payloads=nested['payloads'],mapped_ranges=nested['mapped_ranges'],local_links=links,
        extracted_offline_tool_imports=3,unknown_source_refused=True,invalid_journal_sequence_refused=True,example_bytes=len(example),
        version='2.0b35',generation=47,installation_permitted=False,release_qualified=False,board_access=False)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',type=Path);args=ap.parse_args();print(json.dumps(verify(args.root),indent=2))
