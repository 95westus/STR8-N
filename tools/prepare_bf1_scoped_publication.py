"""Prepare a new named draft revision under the owner's accepted recorded-results scope."""
import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';BASE=ROOT/'output/releases/bf1-github-prerelease-2026-10-17';OUT=BASE/'revisions/full-system-platform-kits-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
def main():
    assert not OUT.exists();OUT.mkdir(parents=True)
    auth=Q/'bf1-scoped-prerelease-owner-authorization-2026-10-18-r1.json';assert not auth.exists()
    save(auth,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),source='Direct human messages in this chat',
        RTC_message='we are going to notate but continue with rtc issue. and we are running the the soaks as is',
        clarification_question='Accept recorded results for tonight scoped prerelease: 2604 8.29h/30cycles; 2609 3.88h/11cycles, and keep both soaks and RTC sampling stopped, or resume?',
        clarification_answer='Accept recorded results; keep stopped (Recommended)',
        prior_publication_authorization='GitHub prerelease in this repo; publish bf1 when gates pass',
        accepted_as_recorded=True,RTC_issue_accepted_for_disclosed_prerelease=True,RTC_failure_resolved=False,
        keep_soaks_stopped=True,keep_RTC_sampling_stopped=True,full_release_qualified=False,
        repo='95westus/STR8-N',tag='v2.0bf1',release_id=416090350,expires_utc='2026-10-18T05:00:00+00:00'))
    pointer=read(Q/'bf1-acceptance-policy-current.json');prior=Path(pointer['policy']);assert sha(prior)==pointer['sha256'];policy=read(prior)
    pilots={}
    for board,name in [('2604','bf1-powered-soak-2604-2026-10-17-r1/owner-stop-verified-2026-10-18.json'),('2609','bf1-powered-soak-2609-2026-10-17-r1/owner-stop-for-windows-migration.json')]:
        path=Q/name;receipt=read(path);pilots[board]=dict(receipt=str(path),sha256=sha(path),accepted_as_recorded=True)
    policy['supersedes_policy_sha256']=pointer['sha256'];policy['amended_utc']=datetime.now(timezone.utc).isoformat()
    policy['amendment']='Owner accepts actual recorded stopped soak results for tonight scoped prerelease and continues with RTC issue disclosed. No workload/RTC restart or full endurance/rate pass is inferred.'
    policy['prerelease'].update(recorded_results_scope=True,owner_scope_authorization=str(auth),owner_scope_authorization_sha256=sha(auth),accepted_soak_receipts=pilots,requires_active_2604_worker=False,requires_current_RTC_sampling=False,RTC_preservation_failure_accepted_as_known_issue=True,full_release_qualified=False,generic_installation_permitted=False)
    path=Q/'bf1-acceptance-policy-2026-10-18-r9.json';assert not path.exists();save(path,policy);save(Q/'bf1-acceptance-policy-current.json',dict(policy=str(path),sha256=sha(path)))
    packages=ROOT/'output/releases/str8n-2.0bf1-migration-candidate-2026-10-18-r2';pack=read(packages/'packages.json');tests=Q/'bf1-candidate-packages-tests-2026-10-18-r3.json';assert read(tests)['passed'] and read(tests)['packages']==pack['packages']
    dp=read(Q/'bf1-distribution-qualification-current.json');qualification=Path(dp['checkpoint']);assert sha(qualification)==dp['sha256'];assert read(qualification)['passed']
    assets={}
    names=['str8n-2.0bf1-windows-migration.zip','str8n-2.0bf1-linux-migration.zip','str8n-2.0bf1-linux-migration.tar.gz','str8n-2.0bf1-apps-str8n-only.bin','str8n-2.0bf1-b3-f000-ffff.bin']
    for name in names:
        source=packages/name;dest=OUT/name;shutil.copyfile(source,dest);assets[name]=dict(path=str(dest),bytes=dest.stat().st_size,sha256=sha(dest))
    checksum=OUT/'str8n-2.0bf1-SHA256SUMS.txt';checksum.write_text(''.join(v['sha256']+'  '+n+'\n' for n,v in sorted(assets.items())),encoding='ascii');assets[checksum.name]=dict(path=str(checksum),bytes=checksum.stat().st_size,sha256=sha(checksum))
    old=read(BASE/'draft.json');sealed=OUT/'superseded-sealed-assets';sealed.mkdir();preserved={}
    for name,info in old['assets'].items():
        src=Path(info['path']);assert sha(src)==info['sha256'] and src.stat().st_size==info['bytes'];dest=sealed/name;shutil.copyfile(src,dest);preserved[name]=dict(path=str(dest),bytes=info['bytes'],sha256=info['sha256'])
    assert not set(assets)&set(preserved)
    notes='''# STR8-N 2.0bf1 — scoped prerelease

One generation-48 firmware set for **65C02 and 65C816 emulation runtime**.
The existing startup CPU-detection exception remains accepted. Native 816
applications/tests, ACIA and crypto are deferred. This is a limited prerelease,
not a fully qualified release or a generic occupied-bank upgrade.

## Downloads

- Windows migration ZIP; Linux migration ZIP or executable-script tar.gz.
- Complete **96 KiB STR8-N-only application firmware**, B1/B2/B3, including
  UCHESS, CLOCK 1.11, ASM 0.5, all supported providers/utilities, MON A/MON B,
  recovery/core and S/R/T. File offset zero maps to full-device offset 0x8000.
- Separate 4 KiB **B3 F000-FFFF** component, full-device offset 0x1F000.
- SHA-256 checksums. All packages include required S19 templates/tools,
  14 manuals/quick starts, ABI tables, rendered Mermaid diagrams, and uChess
  source with the full Peter Jennings license and Daryl Rictor/Bill Forster credits.

No WDCMONV2/intermediate beta4 firmware, board captures, EEPROM/SRAM images,
serial logs or private host data are included. The raw programmer images use
provisioning defaults; they are not preserving upgrades or captured board dumps.

## Exact tested migration scope

Direct original **SXB6 65C816 WDCMONV2-to-full-bf1** and published
**STR8-N v2.0b4 generation-13-to-full-bf1** scripts require already-erased
**B0/B1/B2** and the admitted source in B3. The public tools do not stage
legacy firmware or erase occupied user banks to make a refusal pass. All four
source banks are checked on-device before the first flash mutation.

Both physical empty-bank RAM migrations passed all **22 device-verified
transfers**, full bf1 boot, UCHESS execution and native-utility/CLOCK BATCH
checks (2609 WDC/65C816; 2604 beta4/65C02). The shared transfer engine/worker
was tested on hardware. The portable complete workflows were tested with
simulated serial endpoints after clean extraction on native Windows and
Ubuntu Linux via WSL. A Linux physical serial migration has not been performed.
SXB2 65C02 WDC recognition/planning remains offline-only in this package.

Extra host RAM readbacks were disabled in the physical trials at the owner's
request. Saved application RAM was reloaded with loader acknowledgment, not
host readback verification. Default user tools retain extra RAM readbacks;
the optional --no-host-readback does not remove source acquisition or full
on-device flash preflight/verification. Keep the exact kit and private backup
directory. Bounded forward recovery and beta4-origin restoration are included;
unknown partial states refuse. Early WDC cuts without a valid bf1 fallback/
tracked journal can need an external programmer and the private original backup.

## Known RTC issue and accepted recorded soak results

An earlier WDCMONV2 migration trial lost RTC continuity. Its cause remains
unresolved. The owner authorized clock recovery with the originally recorded
trim; a later corrected empty-bank trial retained a running valid RTC. Neither
recovery nor that later trial closes general RTC-preservation qualification.
The owner explicitly accepted proceeding with this issue disclosed. The tools
issue no time, trim or offset setters; back up clock/trim information first.

The owner accepted the recorded soak results for this prerelease:

| Board | Monitored hours | Passed units | Complete 34-unit cycles |
|---|---:|---:|---:|
| 2604 | 8.290165 | 1047 | 30 |
| 2609 | 3.880169 | 389 | 11 |

Both workloads stopped safely with their original application RAM restoration
verified at stop. Both soaks and RTC sampling remain owner-stopped. These
results are accepted **as recorded**, not relabeled as a four-hour pilot pass,
72-hour/300-cycle endurance pass, or seven-day RTC-rate acceptance. No current
RTC freshness claim is made. The immutable original baseline and prior samples
are retained, including the separate post-recovery measurement segment.

## F component and bank jumps

The F component is **B3-only** and depends on the complete bf1 layout; it is
not an independent monitor for B0/B1/B2. J0/J1/J2 select their bank and follow
its reset vector; they do not relocate this bootstrap. J3 restarts the full
bf1 system. Do not overwrite the B1/B2 F-page application/provider data with
this component merely to create another jump destination.
'''
    (OUT/'release-notes.md').write_text(notes,encoding='utf-8')
    plan=dict(schema=1,scope='owner-accepted-recorded-results',repo='95westus/STR8-N',tag='v2.0bf1',release_id=416090350,source_commit=old['source_commit'],expires_utc='2026-10-18T05:00:00+00:00',owner_authorization=str(auth),owner_authorization_sha256=sha(auth),policy=str(path),policy_sha256=sha(path),distribution_checkpoint=str(qualification),distribution_checkpoint_sha256=sha(qualification),platform_test=str(tests),platform_test_sha256=sha(tests),assets=assets,superseded_sealed_assets=preserved,original_draft=str(BASE/'draft.json'),original_draft_sha256=sha(BASE/'draft.json'),notes=str(OUT/'release-notes.md'),notes_sha256=sha(OUT/'release-notes.md'),same_release_only=True,no_same_name_asset_replacement=True,retain_prior_sealed_bytes=True,full_release_qualified=False,installation_permission_scope='Exact admitted empty-bank user workflows only',soaks_and_RTC_must_remain_stopped=True,publication_not_yet_attempted=True)
    save(OUT/'publication-plan.json',plan);save(Q/'bf1-scoped-publication-plan-current.json',dict(plan=str(OUT/'publication-plan.json'),sha256=sha(OUT/'publication-plan.json')))
    save(OUT/'preparation.json',dict(passed=True,plan_sha256=sha(OUT/'publication-plan.json'),asset_count=len(assets),prior_sealed_assets_preserved=len(preserved),board_access=False,publication=False))
    work=read(Q/'bf1-distribution-work-state.json');work.update(owner_accepted_RTC_known_issue=True,owner_accepted_recorded_soaks=True,soaks_and_RTC_restart_permitted=False,current_scoped_publication_plan=str(OUT/'publication-plan.json'),publication_stage='Prepared new named six-asset revision; no sealed bytes changed; remote staging/publication pending');save(Q/'bf1-distribution-work-state.json',work)
    print('PASS new six-asset draft revision and owner-amended policy prepared; prior eight assets preserved; no publication')
if __name__=='__main__':main()
