"""Verify and publish the owner-authorized single-ZIP v2.0rc1 prerelease."""
import hashlib,json,re,subprocess,sys,time,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/rc1-2026-10-18-r1';REPO='95westus/STR8-N';TAG='v2.0rc1'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def gh(*args):
    r=subprocess.run(['gh',*map(str,args)],capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stderr;return r.stdout
def api(method,endpoint,data=None,optional=False):
    if method=='GET':endpoint+=('&' if '?' in endpoint else '?')+'rc1_verify='+str(time.time_ns())
    args=['gh','api','--method',method,endpoint]
    if data is not None:
        request=OUT/'github-request.json';save(request,data);args+=['--input',str(request)]
    r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
    if optional and r.returncode and '404' in r.stderr:return None
    assert r.returncode==0,r.stderr
    return json.loads(r.stdout)
def main():
    source=read(OUT/'source-commit.json');package=read(OUT/'package-report.json');archive=Path(package['path']);commit=source['source_commit']
    assert source['passed'] and package['passed'] and sha(archive.read_bytes())==package['sha256'] and package['source_commit']==commit
    receipts={}
    for path in [Q/'rc1-clean-build-report.json',Q/'rc1-empty-models/CPU-report.json',Q/'rc1-beta4-recovery-models/CPU-report.json',Q/'rc1-firmware-model/report.json',Q/'rc1-boot-core-model/report.json',Q/'rc1-uchess-model-r2/report.json',Q/'rc1-runtime-equivalence.json',Q/'rc1-live-transport.json',Q/'rc1-zip-audit-sealed/report.json',OUT/'platform-tests.json']:
        assert read(path)['passed'],path;receipts[str(path.relative_to(ROOT))]=sha(path.read_bytes())
    assert read(OUT/'platform-tests.json')['zip_sha256']==package['sha256']
    assert read(Q/'rc1-zip-audit-sealed/report.json')['zip_sha256']==package['sha256']
    assert read(OUT/'final-notice-reuse.json')['all_firmware_tools_templates_examples_byte_identical']
    for name,digest in source['files'].items():assert sha((ROOT/name).read_bytes())==digest,'Source changed after commit: '+name
    for p in (OUT/'firmware').glob('*.bin'):assert p.read_bytes()==(ROOT/'tmp/rc1images-reproduce'/p.name).read_bytes()
    public=(ROOT/'release/candidates/rc1/source/assembler/str8n-v2-public.inc').read_text();abi=(ROOT/'docs/rc1/ABI_REFERENCE.md').read_text();table=re.findall(r'^\| (\w+) \| `\$(\w+)` \| `\$(\w+)` \|',abi,re.M);assert len(table)==13
    eq={n:int(v,16) for n,v in re.findall(r'^(\w+)\s+EQU\s+\$([0-9A-F]+)',public,re.M)}
    for name,ram,rom in table:assert eq['STR8V2_RAM_'+name]==int(ram,16) and eq['STR8V2_'+name]==int(rom,16)
    with zipfile.ZipFile(ROOT/'output/releases/bf1-complete-release-2026-10-18-r2/str8n-2.0bf1-release-r2.zip') as z:prior=z.read('str8n-2.0bf1/docs/TECHNICAL_MANUAL.md').decode()
    current=(ROOT/'docs/rc1/TECHNICAL_MANUAL.md').read_text(encoding='utf-8');assert re.findall(r'```mermaid\n(.*?)```',prior,re.S)==re.findall(r'```mermaid\n(.*?)```',current,re.S)
    active=read(Q/'active-rtc-campaign.json');campaign=read(Path(active['campaign_state']));assert campaign['soak_active'] is False and campaign['RTC_sampling_active'] is False and campaign['automatic_workload_restart_permitted'] is False
    assert sha(Path(active['baseline_index']).read_bytes())==active['baseline_index_sha256']=='5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e'
    assert set(active['powered_off_boards'])=={'2205','2512'}
    readiness=dict(passed=True,version='2.0rc1',generation=49,source_commit=commit,zip_sha256=package['sha256'],receipts=receipts,ABI_entries_verified=13,Mermaid_rendered_outputs_reused_for_identical_diagram_sources=True,all_five_BINs_reproduced=True,RTC_deferred=True,soaks_and_RTC_sampling_stopped=True,board_access=False,rc1_hardware_tested=False)
    save(OUT/'readiness.json',readiness)
    notes=OUT/'release-notes.md';notes.write_text(f'''# STR8-N v2.0rc1

**One complete release ZIP: [str8n-v2.0rc1-release.zip](https://github.com/{REPO}/releases/download/{TAG}/str8n-v2.0rc1-release.zip).** Extract the entire folder and start with README.md.

Firmware is **2.0rc1, generation 49**. The actual monitor banner, MON A/B descriptors, migration target preferences, manuals, source and tag agree. Two independent source builds are byte-identical; only the version/generation and dependent CRC bytes differ from bf1. One firmware set serves **65C02 and 65C816 emulation-mode runtime**; the accepted startup CPU-detector exception is retained.

The ZIP contains:

- Full 96 KiB STR8-N-only B1/B2/B3 system BIN with every supported app/provider, CLOCK 1.11, ASM 0.5, UCHESS and S/R/T; no B0/vendor image.
- B3 boot/core BIN plus matching MON A, MON B and F component BINs, with programmer offsets/dependencies documented.
- Windows and Linux direct WDCMONV2/beta4 migration and bounded recovery launchers, required S19 templates/tools and checksums.
- Installed-board/platform migration quick starts, user/operator/ASM/technical guides, public ABI tables and Mermaid source/rendered diagrams.
- `uchess.a`, credited Microchess source and full Peter Jennings license with Daryl Rictor/Bill Forster credits; an actual ASM 0.5 and Store/Table/Restore walkthrough that creates UCHDEMO while retaining UCHESS. The game displays its copyright notice.

## Installation scope

Scripted full-system migration requires the exact admitted SXB6 original 65C816 WDCMONV2 or published generation-13 beta4 source in B3, with B0/B1/B2 already erased. The tool validates complete bank preimages on-device, installs all providers/apps and verifies transfers. It does not prepare or erase an arbitrary occupied source. WDC vendor and beta4 binaries, private captures, retained-device images and serial logs are excluded. Keep your recovery archives private.

Raw BINs are fresh provisioning images with generic configuration/wear defaults, not preserving upgrades. Full image offset zero maps to device $08000; core-only to $18000. The F component depends on B3 core/slots; it is not a standalone J0/J1/J2 monitor. J3 restarts the complete B3 layout. Early WDC interruptions without a valid fallback/journal may require an external programmer.

## Verification and deferrals

rc1 passed fresh source builds, both monitor-slot boot/app/BATCH checks, full 22-transfer WDC/beta4 CPU/flash migrations, interrupted/late forward recovery and beta4 restoration, actual uChess ASM/S/T/R sessions, source/ABI/content/privacy/vendor audits, and clean Windows cmd/Ubuntu Linux software workflows with simulated serial endpoints. Prior bf1 physical shared-CPU/transport evidence is retained by version; **no new rc1 hardware installation or Linux physical serial migration is claimed**.

RTC qualification and the known continuity issue are deferred. The owner accepted recorded stopped soak results (2604: 8.290165 hours/30 cycles; 2609: 3.880169 hours/11 cycles); this is not a full endurance/RTC pass. **Soaks and RTC sampling remain stopped. Native 816 applications/tests, ACIA and crypto are deferred.** This is a release candidate, not a claim of generic occupied-bank installation or full qualification.

Previous releases remain available: [beta4](https://github.com/{REPO}/releases/tag/v2.0b4), [bf1](https://github.com/{REPO}/releases/tag/v2.0bf1).

SHA-256: `{package['sha256']}`
Source commit: `{commit}`
''',encoding='utf-8')
    save(OUT/'publication-intent.json',dict(owner_authorized=True,tag=TAG,source_commit=commit,asset=archive.name,sha256=package['sha256'],ready_receipt_sha256=sha((OUT/'readiness.json').read_bytes()),recorded_utc=datetime.now(timezone.utc).isoformat()))
    base='repos/'+REPO
    tree=api('GET',base+f"/git/trees/{source['source_tree']}?recursive=1");assert not tree['truncated'];remote_blobs={p['path']:p['sha'] for p in tree['tree'] if p['type']=='blob'}
    for name in source['files']:
        data=(ROOT/name).read_bytes();assert remote_blobs[name]==hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'Remote source differs: '+name
    tag=api('GET',base+'/git/ref/tags/'+TAG,optional=True)
    if tag is None:tag=api('POST',base+'/git/refs',dict(ref='refs/tags/'+TAG,sha=commit))
    assert tag['object']['type']=='commit' and tag['object']['sha']==commit
    release=api('GET',base+'/releases/tags/'+TAG,optional=True)
    if release is None:
        matches=[x for x in api('GET',base+'/releases?per_page=100') if x['tag_name']==TAG]
        assert len(matches)<=1
        if matches:release=matches[0]
    if release is None:
        gh('release','create',TAG,'--repo',REPO,'--verify-tag','--target',commit,'--title','STR8-N v2.0rc1 — complete release candidate','--draft','--prerelease','--notes-file',notes)
        release=next(x for x in api('GET',base+'/releases?per_page=100') if x['tag_name']==TAG)
    assert release['prerelease'] and release['target_commitish']==commit
    assets=release['assets'];assert len(assets)<=1
    if not assets:gh('release','upload',TAG,archive,'--repo',REPO)
    release=api('GET',base+f"/releases/{release['id']}");assert len(release['assets'])==1
    asset=release['assets'][0];assert asset['name']==archive.name and asset['size']==archive.stat().st_size and asset['digest']=='sha256:'+package['sha256']
    # Verify main can advance without overwriting intervening remote work.
    head=api('GET',base+'/git/ref/heads/main')['object']['sha'];assert head in (source['parent_main'],commit),'Remote main advanced; preserve it and reconcile before publication'
    if release['draft']:release=api('PATCH',base+f"/releases/{release['id']}",dict(draft=False,prerelease=True,make_latest='false',body=notes.read_text(encoding='utf-8')))
    if head!=commit:api('PATCH',base+'/git/refs/heads/main',dict(sha=commit,force=False))
    assert api('GET',base+'/git/ref/heads/main')['object']['sha']==commit
    public_req=urllib.request.Request(f'https://api.github.com/{base}/releases/tags/{TAG}?rc1_verify={time.time_ns()}',headers={'User-Agent':'STR8-N-rc1-verification'})
    with urllib.request.urlopen(public_req,timeout=45) as response:public_release=json.load(response)
    assert public_release['id']==release['id'] and not public_release['draft'] and public_release['prerelease'] and len(public_release['assets'])==1
    public_asset=public_release['assets'][0];assert public_asset['digest']=='sha256:'+package['sha256']
    req=urllib.request.Request(public_asset['browser_download_url'],headers={'User-Agent':'STR8-N-rc1-verification'})
    with urllib.request.urlopen(req,timeout=60) as response:body=response.read()
    assert body==archive.read_bytes() and sha(body)==package['sha256'];(OUT/'published-release.zip').write_bytes(body)
    receipt=dict(published=True,repo=REPO,tag=TAG,release_id=release['id'],url=public_release['html_url'],download=public_asset['browser_download_url'],source_commit=commit,main_commit=commit,sha256=package['sha256'],bytes=len(body),single_complete_release_zip=True,asset_count=1,public_anonymous_download_verified=True,readiness_sha256=sha((OUT/'readiness.json').read_bytes()),RTC_deferred=True,soaks_and_RTC_sampling_stopped=True,native_816_ACIA_crypto_deferred=True,board_access=False,published_at=public_release['published_at'])
    save(OUT/'publication.json',receipt);save(Q/'rc1-github-publication-current.json',dict(receipt=str(OUT/'publication.json'),sha256=sha((OUT/'publication.json').read_bytes())))
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
