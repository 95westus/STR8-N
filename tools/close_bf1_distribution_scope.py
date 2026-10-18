"""Close the bounded docs/platform-package gate; retain all separate publication holds."""
import hashlib,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=Q/'bf1-distribution-qualification-2026-10-18-r1';assert not out.exists();out.mkdir()
    package_dir=ROOT/'output/releases/str8n-2.0bf1-migration-candidate-2026-10-18-r2';packages=read(package_dir/'packages.json');platform=Q/'bf1-candidate-packages-tests-2026-10-18-r3.json'
    assert read(platform)['passed'] and read(platform)['native_Windows_tested'] and read(platform)['native_Linux_WSL_tested'];assert read(platform)['packages']==packages['packages']
    evidence={}
    for name in ('bf1-empty-bank-candidate-closure-2026-10-18-r1/report.json','bf1-live-transport-tests-2026-10-18-r1.json','bf1-public-empty-bank-models-2026-10-18-r1/CPU-report.json','bf1-public-beta4-recovery-models-2026-10-18-r1/CPU-report.json','bf1-candidate-packages-tests-2026-10-18-r3.json','bf1-mermaid-render-2026-10-18-r3/report.json'):
        path=Q/name;assert read(path)['passed'];evidence[name]=dict(path=str(path),sha256=sha(path))
    documents={p.relative_to(ROOT/'docs/bf1').as_posix():sha(p) for p in (ROOT/'docs/bf1').rglob('*') if p.is_file()};assert len([n for n in documents if n.endswith('.md')])==14
    render=read(Q/'bf1-mermaid-render-2026-10-18-r3/report.json');tech=(ROOT/'docs/bf1/TECHNICAL_MANUAL.md').read_text(encoding='utf-8');blocks=re.findall(r'```mermaid\n(.*?)```',tech,re.S)
    assert len(blocks)==3
    for block,item in zip(blocks,render['diagrams']):assert hashlib.sha256(block.encode()).hexdigest()==item['source_sha256'] and documents['diagrams/'+item['name']+'.svg']==item['svg_sha256']
    prior=read(Q/'bf1-manual-abi-audit-2026-10-18-r1/report.json')
    for name,digest in prior['source_references'].items():assert sha(ROOT/name)==digest
    image=Q/'bf1-app-image-2026-10-18-r1/str8n-2.0bf1-apps-str8n-only.bin';fixed=ROOT/'tmp/bf1-distribution-r18/migration/payload/str8n-v2-recovery-f000-ffff.bin'
    assert image.read_bytes()[0x17000:0x18000]==fixed.read_bytes() and fixed.stat().st_size==4096
    shutil.copyfile(image,package_dir/image.name);shutil.copyfile(fixed,package_dir/'str8n-2.0bf1-b3-f000-ffff.bin')
    for name in documents:
        dest=out/'manuals'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'docs/bf1'/name,dest)
    flags=['documentation_complete','portable_migration_scripts_tested','portable_recovery_scripts_tested','clean_extracted_kit_verified','quickstarts_operator_ABI_mermaid_docs_complete','windows_migration_recovery_package_tested','linux_migration_recovery_package_tested','app_complete_STR8N_only_image_verified','minimal_public_package_contents_verified','uchess_source_and_attribution_included']
    receipt=dict(passed=True,candidate_id='batchfix-r1',version='2.0bf1',generation=48,created_utc=datetime.now(timezone.utc).isoformat(),evidence=evidence,documents=documents,
        qualified_scope='Exact original SXB6 WDC and published beta4 full-system routes with erased B0/B1/B2; Windows hardware engine and native Windows/Linux extracted software workflows',
        Linux_physical_serial_migration_performed=False,physical_empty_bank_routes_passed=['WDC/65C816 2609','beta4/65C02 2604'],extra_host_RAM_readbacks=False,
        RAM_reload_claim='Loader acknowledgment only; no host verification',RTC_preservation_failure_closed=False,publication_permitted=False,release_qualified=False,generic_installation_permitted=False,
        package_receipts=packages,complete_firmware_sha256=sha(image),F_component_sha256=sha(fixed),F_component_scope='B3 F000-FFFF only; not a bank-independent J0/J1/J2 monitor',Mermaid_rendered_and_visually_inspected=True,**{k:True for k in flags})
    checkpoint=out/'report.json';checkpoint.write_text(json.dumps(receipt,indent=2)+'\n')
    pointer=dict(checkpoint=str(checkpoint),sha256=sha(checkpoint),scope=receipt['qualified_scope']);(Q/'bf1-distribution-qualification-current.json').write_text(json.dumps(pointer,indent=2)+'\n')
    blockers=dict(checked_utc=receipt['created_utc'],docs_and_bounded_platform_package_gate='passed',publication_ready=False,publication_held=True,
        remaining_owner_scope_decisions=['2609 stopped at 3.880169 monitored hours; existing four-hour gate is unmet, not waived','2604 stopped at 8.290165 hours/30 cycles; old pilot publisher still requires an active healthy worker','RTC sampling is owner-stopped; old publication freshness/active-collection condition is unmet','Earlier WDC RTC continuity failure remains unresolved despite operational recovery and later passing trial'],
        remaining_offline_release_work=['Prepare an explicit new draft asset revision using current app-complete bins/platform packages, notes and checksums; old sealed draft must not publish as-is','Bind the chosen prerelease scope and current package receipts into a new publication readiness plan'],
        recommended_scope='If owner approves, publish a limited bf1 prerelease with actual observed soak durations, stopped RTC/soak campaigns, unresolved earlier RTC issue and Linux software-only qualification disclosed; no full-release/generic-install acceptance claim',
        no_new_Linux_physical_test_requirement_inferred=True,soaks_and_RTC_remain_stopped=True,publication_window_end_local='Midnight CDT at end of October 17, 2026 (05:00 UTC October 18)')
    (out/'publication-blockers.json').write_text(json.dumps(blockers,indent=2)+'\n')
    notes='''# STR8-N 2.0bf1 — scoped prerelease proposal

Publication is held pending the owner's scope decision. This proposal does not
authorize publishing or change the accepted gates.

The same generation-48 firmware runs on 65C02 and 65C816 emulation runtime.
The accepted startup CPU detector exception remains; native 816 applications,
ACIA and crypto are deferred. Full release qualification is false.

Included: app-complete 96 KiB STR8-N-only provisioning image, separate B3
F000-FFFF component, Windows/Linux migration and bounded recovery packages,
14 manuals/quick starts with ABI tables and rendered Mermaid diagrams, uChess
source/license/credits and checksums. No vendor WDCMONV2, intermediate beta4,
board captures, serial logs, EEPROM/SRAM images or private host data are included.

Physical empty-bank tests passed: original SXB6 WDCMONV2 on 2609 and published
beta4 on 2604, with B0/B1/B2 erased before each test. Each completed 22
device-verified transfers and bf1/U CHESS/BATCH checks. Saved RAM was loaded
with acknowledgment only; extra host readbacks were disabled. The shared
transport/worker was exercised on hardware; the complete portable launchers
were tested with simulated endpoints in clean Windows and Ubuntu environments.
Linux physical serial migration has not been performed.

Live scope: the exact admitted SXB6 original WDC source or published beta4,
with already-erased B0/B1/B2. Generic occupied-bank upgrades and arbitrary
partially programmed-state recovery are not admitted. Early WDC interruptions
without a valid bf1 fallback/journal can need an external programmer.

Observed soak durations: 2609 3.880169 monitored hours, 389 passed units,
11 complete 34-unit cycles; 2604 8.290165 hours, 1047 passed units, 30 cycles.
Both were owner-stopped with original RAM restoration verified at stop. These
are not passes of the four-hour pilot or 72-hour/300-cycle endurance gates.
RTC sampling was subsequently owner-stopped. No current-freshness or seven-day
RTC acceptance claim is made. The original baseline and all historical samples
remain retained. An earlier WDC trial lost RTC continuity; owner-authorized
recovery and a later valid-running-RTC trial do not resolve its cause or qualify
general RTC preservation. Migration tools issue no clock/trim setters.

The F component is B3-only and is not a complete or relocated monitor.
J0/J1/J2 follow their bank's reset vector; J3 restarts the complete bf1 system.
Provisioning-image file offset zero maps to full-device offset 0x8000, while
the standalone F component maps to 0x1F000. Use the documented recovery route.
'''.replace('U CHESS','UCHESS')
    (out/'proposed-release-notes.md').write_text(notes,encoding='utf-8')
    (package_dir/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(package_dir.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='ascii')
    work=read(Q/'bf1-distribution-work-state.json');work.update(status='bounded-distribution-gate-passed-publication-held',current_user_packages=str(package_dir),latest_distribution_checkpoint=str(checkpoint),docs_and_platform_package_gate_complete=True,publication_permitted=False,owner_publication_hold=True,remaining_publication_decisions=blockers['remaining_owner_scope_decisions'],remaining_release_work=blockers['remaining_offline_release_work'],no_new_Linux_physical_test_requirement_inferred=True)
    for task in work['tasks']:
        if task['id']=='new-reviewed-assets-and-publication-readiness':task['status']='held-for-owner-scope-and-new-draft-revision'
        else:task['status']='passed-for-bounded-candidate-scope'
    (Q/'bf1-distribution-work-state.json').write_text(json.dumps(work,indent=2)+'\n')
    plan=read(Q/'bf1-tonight-publication-plan.json');plan['current_bounded_distribution_qualification']=pointer;plan['docs_and_bounded_packages_complete']=True;plan['publication_hold_reason']='Docs/platform-package gate now passed for bounded empty-bank scope; accepted soak/RTC conditions and earlier RTC failure remain unresolved; current packages require a new explicit draft asset revision.'
    plan['remaining_publication_conditions']=blockers;plan['publication_automation_paused']=True;plan['publication_hold']=True
    (Q/'bf1-tonight-publication-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('PASS bounded docs/Windows/Linux distribution gate; explicit publication blockers retained; no hardware or publication')
if __name__=='__main__':main()
