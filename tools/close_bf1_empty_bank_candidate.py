"""Save hash-bound candidate checkpoint without publishing or claiming full release."""
import hashlib,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
    out=Q/'bf1-empty-bank-candidate-closure-2026-10-18-r1';assert not out.exists();out.mkdir()
    hardware=Q/'bf1-empty-bank-hardware-2026-10-18-r1';kit=ROOT/'tmp/bf1-distribution-r18/migration';packages=ROOT/'output/releases/str8n-2.0bf1-migration-candidate-2026-10-18-r1'
    tests=Q/'bf1-candidate-packages-tests-2026-10-18-r2.json';assert read(tests)['passed'] and read(tests)['native_Windows_tested'] and read(tests)['native_Linux_WSL_tested']
    evidence={};routes={}
    for board,route,check in [('2609','2609-WDC-to-full-bf1','2609-full-bf1-checks-r3'),('2604','2604-beta4-to-full-bf1','2604-full-bf1-checks')]:
        install=read(hardware/route/'report.json');boot=read(hardware/check/'report.json');assert install['passed'] and boot['passed'] and install['transfers_completed']==22
        assert install['packaged_install_transport_sha256']==sha(kit/'install_transport.py')
        assert install['device_full_source_preflight'] and install['device_target_verification'] and boot['application_RAM_archive_written'] and boot['loader_acknowledged'] and not boot['host_RAM_restoration_verified']
        routes[board]=dict(route=route,transfers=22,device_preflight_and_verification=True,boot_UCHESS_BATCH_passed=True,saved_RAM_loaded_and_acknowledged=True,host_RAM_readback=False,clock_trim_changes=False)
        for name in (route,check):evidence[name]=dict(report=str(hardware/name/'report.json'),sha256=sha(hardware/name/'report.json'))
    for name in ('bf1-live-transport-tests-2026-10-18-r1.json','bf1-public-empty-bank-models-2026-10-18-r1/CPU-report.json','bf1-public-beta4-recovery-models-2026-10-18-r1/CPU-report.json','bf1-candidate-packages-tests-2026-10-18-r2.json'):
        path=Q/name;assert read(path)['passed'];evidence[name]=dict(report=str(path),sha256=sha(path))
    # Reuse the actual prior CPU manual tests only where source and example inputs
    # are unchanged. Current text/CLI/link checks are bound separately below.
    prior=Q/'bf1-manual-abi-audit-2026-10-18-r1/report.json';audit=read(prior);assert audit['passed']
    for name,digest in audit['source_references'].items():assert sha(ROOT/name)==digest
    example=re.search(r'```asm\n(.*?)```',(ROOT/'docs/bf1/ASM_GUIDE.md').read_text(encoding='utf-8'),re.S).group(1)
    assert example.strip().splitlines()==['10 ORG $0200','20 SEI','30 CLD',"40 LDA #'A'",'50 JSR $7E6D','60 JMP $7E67','70 END']
    docs={p.name:sha(p) for p in (ROOT/'docs/bf1').glob('*.md')};assert len(docs)==14
    diagrams=re.findall(r'```mermaid\n(.*?)```',(ROOT/'docs/bf1/TECHNICAL_MANUAL.md').read_text(encoding='utf-8'),re.S);assert len(diagrams)==3 and all(d.startswith('flowchart ') and '-->' in d for d in diagrams)
    for name in docs:shutil.copyfile(ROOT/'docs/bf1'/name,out/name)
    manual=dict(passed=True,documents=docs,prior_fresh_CPU_manual_report=str(prior),prior_report_sha256=sha(prior),unchanged_source_references=audit['source_references'],unchanged_assembled_example_sha256=hashlib.sha256(example.encode()).hexdigest(),Mermaid_source_diagrams=len(diagrams),Mermaid_rendering_claimed=False,new_platform_commands_and_all_links_checked_by=str(tests),full_release_qualified=False)
    (out/'manual-checkpoint.json').write_text(json.dumps(manual,indent=2)+'\n',encoding='utf-8')
    image=Q/'bf1-app-image-2026-10-18-r1/str8n-2.0bf1-apps-str8n-only.bin';shutil.copyfile(image,packages/image.name)
    sums=''.join(sha(p)+'  '+p.name+'\n' for p in sorted(packages.iterdir()) if p.is_file() and p.name not in ('SHA256SUMS',))
    (packages/'SHA256SUMS').write_text(sums,encoding='ascii')
    active=read(Q/'active-rtc-campaign.json');campaign=Path(active['campaign_state']);state=read(campaign)
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256'];assert state['RTC_sampling_active'] is False and state['snapshot_boards']==[]
    state['empty_bank_full_bf1_hardware_checkpoint']=str(out/'report.json');state['firmware_current']={'2604':'2.0bf1 generation48 all-apps full system','2609':'2.0bf1 generation48 all-apps full system','2512':'2.0bf1 powered off'}
    state['workloads_owner_stopped']=True;state['automatic_workload_restart_permitted']=False
    campaign.write_text(json.dumps(state,indent=2)+'\n')
    report=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),routes=routes,evidence=evidence,kit=str(kit),kit_manifest_sha256=sha(kit/'kit-manifest.json'),packages=str(packages),package_receipts=read(packages/'packages.json'),firmware_sha256=sha(image),manual_checkpoint_sha256=sha(out/'manual-checkpoint.json'),RTC_sampling_stopped=True,workloads_stopped=True,boards_powered_on=['2604','2609'],boards_powered_off=['2205','2512'],immutable_baseline_sha256=active['baseline_index_sha256'],live_scope='Admitted exact empty B0/B1/B2 routes only',deferred=['native 816 apps/tests','ACIA','crypto'],publication_held=True,release_qualified=False,distribution_fully_qualified=False,remaining=['Earlier WDC RTC failure cause/preservation closure','Linux physical serial migration','Long soak/RTC gates not completed; owner stopped collection','Broader occupied-bank and arbitrary partial-state recovery not admitted'])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    work=read(Q/'bf1-distribution-work-state.json');work.update(status='local-empty-bank-candidate-delivered',owner_publication_hold=True,publication_permitted=False,current_prototype=str(kit),stage='Both requested physical empty-bank full-system routes passed 22 transfers and boot/U CHESS/BATCH; clean extracted Windows and Linux candidate tests passed'.replace('U CHESS','UCHESS'),live_execution_enabled=True,live_execution_scope='Exact admitted empty-bank routes; WDC SXB6; published beta4',current_user_packages=str(packages),latest_distribution_checkpoint=str(out/'report.json'),RTC_sampling_active=False,soak_2604_status='Owner-stopped; no workload restart; RTC sampling also owner-stopped',next_offline_task='No duplicate packaging job. Publication hold and remaining qualification limits recorded.',app_complete_image=str(image),str8n_only_image_sha256=sha(image),review_package_platform_checks_pending=False)
    for task in work['tasks']:
        if task['id']=='new-reviewed-assets-and-publication-readiness':task.update(status='held',reason='Owner publication hold and remaining full qualification limits')
        else:task.update(status='complete-for-bounded-local-candidate',scope='Exact empty-bank live routes; physical engine proofs and simulated endpoint/platform checks, not generic acceptance')
    work['str8n_only_image']=str(image)
    work['qualification_evidence'].append(str((out/'report.json').relative_to(Q)))
    (Q/'bf1-distribution-work-state.json').write_text(json.dumps(work,indent=2)+'\n')
    with (ROOT/'docs/STR8N_BF1_DISTRIBUTION_WORK.md').open('a',encoding='utf-8') as stream:stream.write('\n\n## October 18 empty-bank hardware and local candidate closure\n\nBoth owner-requested physical full-system RAM migrations passed: original SXB6 WDC on 2609 and published beta4 on 2604, each with erased B0/B1/B2, 22 device-verified transfers, full bf1/U CHESS/BATCH checks and saved RAM loader acknowledgment (no extra host readback). Windows cmd and native Ubuntu WSL clean extracted candidate workflows passed. Candidate packages and a STR8-N-only all-apps image are in `output/releases/str8n-2.0bf1-migration-candidate-2026-10-18-r1`. Fourteen manuals include platform/installed-board quick starts, name/clock setup, ABI tables, Mermaid source diagrams and credited uChess source. Evidence is in `output/qualification/bf1-empty-bank-candidate-closure-2026-10-18-r1`. Publication remains held; Linux physical serial, prior RTC preservation failure and broader gates are not passed. Both workloads and RTC sampling are owner-stopped; do not restart them.\n'.replace('U CHESS','UCHESS'))
    print('PASS hardware/package/manual candidate checkpoint; publication held; RTC/workloads remain stopped')
if __name__=='__main__':main()
