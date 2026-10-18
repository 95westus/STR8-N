"""New local review revision with bounded 2512 migration evidence; no device images."""
import json,hashlib,zipfile,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    prior=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r4.zip'
    assert sha(prior.read_bytes())=='2bf9606ff79fed2f9b762ab33b3b3c83efc41624efc49ac27d11c817566a83a2'
    archive=prior.with_name('str8n-2.0bf1-local-review-2026-10-17-r5.zip');kit=ROOT/'tmp/bf1k5'
    assert not archive.exists() and not kit.exists()
    with zipfile.ZipFile(prior) as z:files={n:z.read(n) for n in z.namelist() if n not in ('review-manifest.json','review-allowlist.json')}
    receipts={}
    for route in ('2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1'):
        ptr=read(Q/(route+'-acceptance-current.json'));path=Path(ptr['checkpoint']);raw=path.read_bytes();assert sha(raw)==ptr['sha256'];r=json.loads(raw)
        keys=('passed','offline_qualified','hardware_qualified','original_RAM_restored','clocks_trims_unchanged','retained_storage_preserved','conservative_wear_retained','both_bf1_monitor_slots_exercised','original_beta35_payload_restored')
        assert all(r[k] is True for k in keys) and r['route_id']==route and r['board']=='2512'
        children={}
        for name,item in r['evidence'].items():
            child=Path(item['path']);assert sha(child.read_bytes())==item['sha256'] and read(child)['passed'];children[name]=item['sha256']
        receipts[route]={k:r[k] for k in keys};receipts[route].update(route_id=route,board='2512',target_version=r['target_version'],scope=r['scope'],baseline_sha256=r['baseline_sha256'],original_receipt_sha256=ptr['sha256'],evidence_sha256=children)
    final_path=Q/'bf1-2512-hardware-2026-10-17-r1/final-bf1-hardware/report.json';final=read(final_path)
    assert final['passed'] and final['full_flash_verified'] and final['retained_storage_preserved'] and final['clocks_trims_unchanged'] and final['application_ram_restored'] and final['ports_released']
    # Deliberately project bounded results, never copy local paths, device data or logs.
    evidence=dict(routes=receipts,final_bf1=dict(board='2512',target_version=final['target_version'],passed=True,full_flash_verified=True,retained_storage_preserved=True,clocks_trims_unchanged=True,application_ram_restored=True,original_receipt_sha256=sha(final_path.read_bytes()),checks=final['checks']),deferred=['native 816','ACIA','crypto'],release_qualified=False,generic_installation_permitted=False,publication_permitted=False)
    files['evidence/migrations/2512-summary.json']=(json.dumps(evidence,indent=2)+'\n').encode()
    old='Exact captured 2604 and 2609 lineages, each with separately pinned bf1 B-first/A-second route; no generic stock, legacy, core or private-ABI conversion claim'
    new='Exact captured 2604/2609 B-first/A-second lineages and exact staged 2512 WDCMONV2 and published beta4 profiles with separate restoration acceptance; no arbitrary legacy or generic preserving installer claim'
    scope=json.loads(files['release/bf1-prerelease/acceptance-scope.json']);assert scope['migration_scope']==old;scope['migration_scope']=new
    files['release/bf1-prerelease/acceptance-scope.json']=(json.dumps(scope,indent=2)+'\n').encode()
    verifier=files['verify_review.py'].decode();assert old in verifier;verifier=verifier.replace(old,new)
    needle='    physical=verify_physical(root,require)';assert needle in verifier
    verifier=verifier.replace(needle,needle+'\n    from verify_migrations import verify_migrations\n    verify_migrations(root,require)')
    files['verify_review.py']=verifier.encode()
    files['verify_migrations.py']=b'''import json
def verify_migrations(root,require):
    r=json.loads((root/'evidence/migrations/2512-summary.json').read_text())
    require(set(r['routes'])=={'2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1'},'Both 2512 routes required')
    for route,v in r['routes'].items():
        require(v['route_id']==route and v['board']=='2512' and v['target_version']=='2.0bf1','Migration identity')
        require(all(v[k] is True for k in ('passed','offline_qualified','hardware_qualified','original_RAM_restored','clocks_trims_unchanged','retained_storage_preserved','conservative_wear_retained','both_bf1_monitor_slots_exercised','original_beta35_payload_restored')),'Migration qualification')
        require({'offline','hardware','restoration'}.issubset(v['evidence_sha256']),'Separate qualification evidence')
        require(all(len(x)==64 for x in v['evidence_sha256'].values()),'Evidence digest lengths')
    require(all(r['final_bf1'][k] is True for k in ('passed','full_flash_verified','retained_storage_preserved','clocks_trims_unchanged','application_ram_restored')),'Final bf1 completion')
    require(all(c['passed'] for c in r['final_bf1']['checks']),'Final bf1 hardware checks')
    require(all(r[k] is False for k in ('release_qualified','generic_installation_permitted','publication_permitted')),'Review cannot authorize publication')
    require(set(r['deferred'])=={'native 816','ACIA','crypto'},'Deferrals')
'''
    files['README.md']+=b'\n\nRevision r5 adds accepted exact-profile 2512 WDCMONV2 and published beta4 migration/restoration results and the final bf1 hardware check. See [bounded migration evidence](evidence/migrations/2512-summary.json). Prior firmware/build evidence is reused unchanged. No captured device image or generic legacy installer is included. Four-hour 2609, 72-hour/300-cycle 2604 and seven-day RTC gates are independently evaluated; this review does not grant publication permission.\n'
    summary=json.loads(files['review-evidence-summary.json']);summary.update(migration_receipt='evidence/migrations/2512-summary.json',migration_results='Both exact 2512 source-profile routes and final complete bf1 hardware verified',next_gate='Four-hour 2609 completion/restoration, healthy ongoing 2604, fresh RTC and separate scoped publication readiness; longer qualification remains pending')
    files['review-evidence-summary.json']=(json.dumps(summary,indent=2)+'\n').encode()
    files['review-allowlist.json']=(json.dumps(sorted([*files,'review-allowlist.json']),indent=2)+'\n').encode()
    manifest=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,installation_permitted=False,release_qualified=False,publication_permitted=False,deferred=['native 816','ACIA','crypto'],files={n:dict(bytes=len(v),sha256=sha(v)) for n,v in sorted(files.items())})
    files['review-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(archive,'x') as z:
        for n,data in sorted(files.items()):
            info=zipfile.ZipInfo(n,(2026,10,18,0,0,0));info.external_attr=0o100644<<16;z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None;z.extractall(kit)
    result=subprocess.run([sys.executable,'-B',str(kit/'verify_review.py'),str(kit)],capture_output=True,text=True)
    receipt=dict(verified=result.returncode==0,archive=str(archive.resolve()),archive_sha256=sha(archive.read_bytes()),files=len(files),previous_archive_sha256=sha(prior.read_bytes()),stdout=result.stdout,stderr=result.stderr,board_access=False,created_utc=datetime.now(timezone.utc).isoformat(),packager_sha256=sha(Path(__file__).read_bytes()))
    archive.with_suffix('.package.json').write_text(json.dumps(receipt,indent=2)+'\n');assert result.returncode==0,(result.stdout,result.stderr);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
