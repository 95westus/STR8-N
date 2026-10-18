"""Create a new allowlisted local review archive; never edit the sealed ZIP."""
import argparse,hashlib,json,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--extract',required=True,type=Path);ap.add_argument('--audit',required=True,type=Path);ap.add_argument('--document-binding',type=Path);a=ap.parse_args()
    assert not a.out.exists() and not a.extract.exists(),'Use new archive/extract paths'
    prior=ROOT/'output/releases/str8n-2.0b35-review.zip';oldsha=sha(prior.read_bytes());assert oldsha=='dc7c854f71852a853eac48dbf0070560feb64c8c47df0441d496a5062d7afa1f'
    audit=read(a.audit);assert audit['passed']
    document_hashes=audit['documents'];binding=None
    if a.document_binding:
        binding=read(a.document_binding);assert binding['manual_audit_report_sha256']==sha(a.audit.read_bytes()) and binding['editorial_changes_only'] is True
        assert set(binding['documents'])==set(audit['documents']);document_hashes=binding['documents']
        assert binding['original_documents']==audit['documents']
    for name,digest in document_hashes.items():assert sha((ROOT/'docs/beta35'/name).read_bytes())==digest
    files={}
    with zipfile.ZipFile(prior) as z:
        manifest=read(ROOT/'tmp/k35a/manifest.json');assert z.read('manifest.json')==(ROOT/'tmp/k35a/manifest.json').read_bytes()
        assert set(z.namelist())==set(manifest['files'])|{'manifest.json'}
        for name in z.namelist():
            path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            data=z.read(name)
            if name!='manifest.json':assert dict(sha256=sha(data),bytes=len(data))==manifest['files'][name]
            files['release/beta35/'+name]=data
    docs=['README.md','USER_GUIDE.md','ASM_GUIDE.md','COMMAND_REFERENCE.md','TECHNICAL_MANUAL.md']
    public_notes=['STR8N_V2_BETA35_PRERELEASE_WORK.md','STR8N_V2_BETA35_MIGRATION_MATRIX.md','STR8N_V2_BETA35_RELEASE_QUALIFICATION_2026-10-16.md','issues/BETA35_A_SLOT_BATCH.md','issues/BETA35_JOURNAL_RESERVATION.md']
    public_notes.append('STR8N_V2_BETA35_SCOPED_ACCEPTANCE.md')
    tools=['inspect_beta35_source.py','plan_beta35_offline.py','plan_beta35_journal_transaction.py']
    for name in docs:files['docs/beta35/'+name]=(ROOT/'docs/beta35'/name).read_bytes()
    for name in public_notes:files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    for name in tools:files['tools/'+name]=(ROOT/'tools'/name).read_bytes()
    for name in ['source-catalog.json','destination-catalog.json','beta35-route-scope.json']:files['release/beta35-prerelease/'+name]=(ROOT/'release/beta35-prerelease'/name).read_bytes()
    for name in ['README.md','REMAINING_GATES.md','verify_review.py']:files[name]=(ROOT/'release/beta35-prerelease/review'/name).read_bytes()
    example=read(Path(audit['reused_example_report']));exampledir=Path(audit['reused_example_report']).parent
    for suffix in ['bin','s19']:files['examples/asm-print-a.'+suffix]=(exampledir/('asm-example.'+suffix)).read_bytes()
    guide=(ROOT/'docs/beta35/ASM_GUIDE.md').read_text(encoding='utf-8');import re
    files['examples/asm-print-a.numbered.txt']=(re.search(r'```asm\n(.*?)```',guide,re.S).group(1)).encode()
    summary=dict(version='2.0b35',generation=47,release_qualified=False,installation_permitted=False,deferred=['ACIA','crypto'],
        broader_manual_abi_audit=dict(passed=True,cases=audit['cases'],report_sha256=sha(a.audit.read_bytes()),checks=[v['name'] for v in audit['checks']]),
        editorial_document_binding_sha256=sha(a.document_binding.read_bytes()) if binding else None,
        approved_route_scope=read(ROOT/'release/beta35-prerelease/beta35-route-scope.json'),
        unchanged_example_receipt=dict(passed=True,cases=example['cases'],report_sha256=audit['reused_example_report_sha256'],bytes_hex=example['example_bytes_hex']),
        source_reproduction=dict(reused=True,fresh_build_claimed=False,prior_archive_sha256=oldsha,prior_build_report_sha256=read(prior.with_suffix('.json'))['build_report_sha256'],
            unchanged_sources=97,unchanged_payloads=18,previous_fresh_links=26),
        scope='Offline bounded instruction models and source/ABI/document review. No native/electrical acceptance, serial access, publication or installation.')
    files['review-evidence-summary.json']=(json.dumps(summary,indent=2)+'\n').encode()
    # No directory glob controls inclusion; the old sealed inventory and the
    # explicit additions above are the complete allowlist.
    files['review-allowlist.json']=(json.dumps(sorted(list(files)+['review-allowlist.json']),indent=2)+'\n').encode()
    outer=dict(version='2.0b35',generation=47,release_qualified=False,installation_permitted=False,deferred=['ACIA','crypto'],
        purpose='Expanded local prerelease review; no installation/publication permission',prior_archive_sha256=oldsha,
        files={name:dict(bytes=len(data),sha256=sha(data)) for name,data in sorted(files.items())})
    files['review-manifest.json']=(json.dumps(outer,indent=2)+'\n').encode()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,17,0,0,0));info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(a.out) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files);assert set(z.namelist())==set(files);z.extractall(a.extract)
    result=subprocess.run([sys.executable,'-B',str(a.extract/'verify_review.py'),str(a.extract)],capture_output=True,text=True)
    if result.returncode:
        a.out.with_suffix('.failure.json').write_text(json.dumps(dict(passed=False,stdout=result.stdout,stderr=result.stderr),indent=2)+'\n');raise RuntimeError(result.stderr)
    receipt=dict(**json.loads(result.stdout),archive=str(a.out.resolve()),archive_sha256=sha(a.out.read_bytes()),archive_bytes=a.out.stat().st_size,
        extracted=str(a.extract.resolve()),packager_sha256=sha(Path(__file__).read_bytes()),manual_audit_report_sha256=sha(a.audit.read_bytes()),
        old_archive_sha256=oldsha,editorial_document_binding_sha256=sha(a.document_binding.read_bytes()) if binding else None,finished_utc=datetime.now(timezone.utc).isoformat(),
        excluded=['board dumps/backups','private measurement and transcript evidence','vendor firmware','emulator/runtime dependencies','v2.1 source'],
        extracted_source_rebuild='Unchanged 97 sources/18 payloads reuse prior exact 26-link clean reproduction; fresh expanded-package checks performed')
    assert sha(prior.read_bytes())==oldsha;a.out.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
