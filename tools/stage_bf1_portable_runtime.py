"""Stage public-only bf1 migration runtime/assets; no private captures or serial access."""
import ast,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
sha=lambda b:hashlib.sha256(b).hexdigest()

class Guards(ast.NodeTransformer):
    def visit_Assert(self,node):
        return ast.copy_location(ast.Expr(ast.Call(ast.Name('require',ast.Load()),[self.visit(node.test),self.visit(node.msg) if node.msg else ast.Constant('Migration invariant failed')],[])),node)
    def visit_Attribute(self,node):
        node=self.generic_visit(node)
        if isinstance(node.value,ast.Name) and node.value.id=='p' and node.attr in ('require','crc'):
            return ast.Name(node.attr,ast.Load())
        if isinstance(node.value,ast.Name) and node.value.id=='p' and node.attr=='config_checksum':
            return ast.Attribute(ast.Name('migration',ast.Load()),'config_sum',ast.Load())
        return node

def functions(path,names):
    tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==set(names);return ast.unparse(ast.fix_missing_locations(Guards().visit(ast.Module(nodes,type_ignores=[]))))

def main():
    src=ROOT/'release/bf1-migration-r1';kit=ROOT/'tmp/bf1-distribution-r1/migration';assert not src.exists() and not kit.exists();src.mkdir();kit.mkdir(parents=True)
    transport=ROOT/'tools/beta4_migration.py';tree=ast.parse(transport.read_text());tree.body=[n for n in tree.body if not isinstance(n,ast.If) and not (isinstance(n,ast.FunctionDef) and n.name in ('main','kit_path'))]
    (src/'legacy_transport.py').write_text(ast.unparse(tree)+'\n')
    head='''"""Portable bf1 transaction core; extracted from qualified algorithms, no repository paths."""
import hashlib,json
from pathlib import Path
import legacy_transport as migration
crc=migration.crc
def require(condition,message='Migration invariant failed'):
    if not condition:raise ValueError(message)
sha=lambda data:hashlib.sha256(data).hexdigest()
hashes=lambda banks:[sha(bytes(b)) for b in banks]
read=lambda path:json.loads(Path(path).read_text())
'''
    body=functions(ROOT/'tools/beta35_model_transactions.py',['latest'])+'\n'+functions(ROOT/'tools/plan_beta35_journal_transaction.py',['record','preference'])+'\n'+functions(ROOT/'tools/plan_bf1_2512_legacy.py',['clean_journal','transaction','compose'])
    (src/'runtime.py').write_text(head+'\n'+body+'\n')
    for name in ('legacy_transport.py','runtime.py'):shutil.copyfile(src/name,kit/name)
    pin=json.loads((Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json').read_text());payload=ROOT/'tmp/bfx5/payload'
    for name,info in pin['artifacts'].items():
        p=payload/name;assert sha(p.read_bytes())==info['sha256'];dest=kit/'payload'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    build=ROOT/'tmp/blg4';mf=json.loads((build/'manifest.json').read_text());assert mf['passed'];template=(build/'integrated-template.s19').read_bytes();assert sha(template)==mf['integrated_sha256'];dest=kit/'template';dest.mkdir();(dest/'integrated-template.s19').write_bytes(template)
    public={k:mf[k] for k in ('count','commit_after','banks','commits','commit_addresses','commit_values','table','passed','integrated_sha256')};(dest/'manifest.json').write_text(json.dumps(public,indent=2)+'\n')
    layout=json.loads((ROOT/'release/beta35/layout.json').read_text());(kit/'layout.json').write_text(json.dumps(dict(segments=layout['segments']),indent=2)+'\n')
    bridge=ROOT/'BUILD/v2-beta4/kit';manifest=json.loads((bridge/'manifest.json').read_text());dest=kit/'beta4-bridge';dest.mkdir()
    for name,digest in manifest['artifacts'].items():
        assert Path(name).name==name;data=(bridge/name).read_bytes();assert sha(data)==digest;(dest/name).write_bytes(data)
    for name in ('manifest.json','migrator.json'):
        if not (dest/name).exists():shutil.copyfile(bridge/name,dest/name)
    # Recognition hashes are public metadata; never ship the vendor image itself.
    vendor=(Q/'board-2512-layout-2026-09-24/b0-final.bin').read_bytes()
    profile=dict(wdcmonv2=dict(identity_hex='535842322c010000c8000000',source_sha256=sha(vendor),outside_journal_sha256=sha(vendor[:0x4000]+vendor[0x6000:]),scope='Exact SXB2 HW3.00 MON2.00 diagnostic/monitor image; other vendor images refused'),beta4=dict(version='2.0b4',generation=13,archive_sha256='4c25bc576cbc32efd04aeea4fe80c68544a50b80685d12bfcf1e44122bacbc14'))
    (kit/'profiles.json').write_text(json.dumps(profile,indent=2)+'\n')
    files={p.relative_to(kit).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(kit.rglob('*')) if p.is_file()}
    (kit/'kit-manifest.json').write_text(json.dumps(dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,files=files,live_installation_enabled=False,distribution_qualified=False,requires_qualification=True),indent=2)+'\n')
    report=dict(passed=True,stage_only=True,kit=str(kit),files=len(files),no_private_device_images=True,board_access=False,distribution_qualified=False,source_sha256={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (src/'runtime.py',src/'legacy_transport.py',Path(__file__))})
    (Q/'bf1-portable-runtime-stage-2026-10-18-r1.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS staged portable public runtime/assets:',len(files),'files; installation remains disabled')
if __name__=='__main__':main()
