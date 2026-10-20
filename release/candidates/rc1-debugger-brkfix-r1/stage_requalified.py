"""Package existing v1g requalification evidence. No board or network access."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];Q=ROOT/'output/qualification'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
IMAGE_SHA='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
KIT_SHA='42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf'
HW_SHA='5d3c2832355725bf9558d3c5415efd0eeb6679d8230f81a9a8762e629ae19730'
def require(value,message):
 if not value:raise ValueError(message)
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def copy(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
def edit(path,old,new):
 text=path.read_text(encoding='utf-8');require(old in text,'Missing documentation text: '+str(path));path.write_text(text.replace(old,new),encoding='utf-8')
def section(path,start,end,new):
 text=path.read_text(encoding='utf-8');before,found,tail=text.partition(start);require(found,'Missing section '+start);_,found,after=tail.partition(end);require(found,'Missing section '+end);path.write_text(before+new+'\n\n'+end+after,encoding='utf-8')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--record',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 record=a.record.resolve();out=a.out.resolve();archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256');scope=READ(record/'owner-scope.json')
 require(scope['owner_authorized'] and scope['promotion_held'] and not scope['board_access'] and not scope['native_debugging'],'Wrong scope')
 require(not out.exists() and not archive.exists() and not checksum.exists(),'Use a fresh staging output')
 require(READ(Q/'rc1-dbg1-promotion-hold.json')['held'],'Promotion must remain held')
 protected=READ(record/'protected-inputs-before.json')
 for path,digest in protected.items():require(SHA(path)==digest,'Changed protected input: '+path)
 base=Path(scope['prior_distribution']);old=READ(base/'package-manifest.json')
 require(old['distribution_revision']==4 and old['firmware_sha256']==IMAGE_SHA,'Wrong base snapshot')
 result=subprocess.run([sys.executable,str(base/'verify_package.py')],capture_output=True,text=True);require(result.returncode==0,result.stdout+result.stderr)
 hardware=Path(scope['hardware_run']);source=READ(hardware/'report.json');source_index=READ(hardware/'evidence-checksums.json')
 require(SHA(hardware/'report.json')==scope['hardware_report_sha256']==HW_SHA and source['passed'] and source['firmware_sha256']==IMAGE_SHA and source['package_manifest_sha256']==KIT_SHA,'Wrong hardware proof')
 for name,digest in source_index['files'].items():require(SHA(hardware/name)==digest,'Changed hardware source: '+name)
 shutil.copytree(base,out,ignore=shutil.ignore_patterns('__pycache__'))
 (out/'qualification/hardware/pending.json').unlink()
 for path in (HERE/'package-requalified').rglob('*.md'):copy(path,out/path.relative_to(HERE/'package-requalified'))
 exported={}
 def evidence(path,name):
  relative=path.relative_to(hardware).as_posix();require(relative in source_index['files'] and SHA(path)==source_index['files'][relative],'Unbound hardware evidence')
  body=path.read_bytes()
  if path.suffix in ('.json','.py'):require(not re.search(rb'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',body),'Host path in hardware receipt '+relative)
  copy(path,out/name);exported[name]=dict(bytes=len(body),sha256=SHA(path),source_receipt=relative)
 for board in ('2604','2609'):
  for oldphase,newphase in (('candidate-regression','initial'),('final-regression','final')):evidence(hardware/board/oldphase/'report.json',f'qualification/hardware/{board}/{newphase}.json')
  for phase in ('v1f-rollback','v1g-install','v1g-rollback','v1g-reinstall'):
   for suffix,folder in (('execute','receipt'),('flash','flash-check'),('RAM','RAM-restored')):evidence(hardware/board/(phase+'-'+folder)/'report.json',f'qualification/hardware/{board}/transactions/{phase}-{suffix}.json')
   boot=READ(hardware/board/(phase+'-reset-observation.json'));path=Path(boot['observation_receipt']);require(path.resolve().is_relative_to(hardware),'Escaping boot receipt')
   evidence(path,f'qualification/hardware/{board}/transactions/{phase}-boot.json')
 for directory,target in (('registration-images','diagnostics/registrations'),('edge-images','diagnostics/brk82-84')):
  for path in (hardware/directory).glob('*.s19'):evidence(path,target+'/'+path.name)
 evidence(hardware/'edge_cases.py','diagnostics/brk82-84/cases.py')
 for cpu in ('02','816'):evidence(hardware/f'board-case-model-{cpu}.json',f'qualification/offline/hardware-case-model-{cpu}.json')
 hw={key:source[key] for key in ('passed','firmware_sha256','package_manifest_sha256','candidate','generation','registration_scenario_executions','BRK82_84_hardware_edge_checks','breakpoint_hits','verified_transfers','hardware_test_failures','promotion_held','native_debugging','native_applications_tested','finished_utc')}
 hw.update(source_report_sha256=HW_SHA,operator_wait_timeouts=len(source['operator_wait_timeouts']),boards={})
 for board,b in source['boards'].items():hw['boards'][board]=dict(b,original_RAM_bytes=25344)
 save(out/'qualification/hardware/summary.json',hw);exported['qualification/hardware/summary.json']=dict(bytes=(out/'qualification/hardware/summary.json').stat().st_size,sha256=SHA(out/'qualification/hardware/summary.json'),source_receipt='report.json; selected hardware fields')
 save(out/'qualification/hardware/source-evidence.json',dict(source_run=hardware.name,source_report_sha256=HW_SHA,source_evidence_index_sha256=SHA(hardware/'evidence-checksums.json'),source_files_verified=len(source_index['files']),board_access_during_packaging=False,files=exported))
 stop=source['v1f_safe_stop'];drift=stop['final_drift_snapshot']
 save(out/'qualification/history/v1f-safe-stop-summary.json',dict(historical_only=True,qualifies_v1g=False,owner_requested_safe_stop=True,six_hour_pass=False,workload_seconds=stop['workload_seconds'],passed_cycles={b:v['passed_cycles'] for b,v in stop['boards'].items()},original_RAM_restored_both=True,flash_settings_preserved=True,final_drift_snapshot_passed=drift['passed'],offset_seconds={b['board']:b['offset_seconds'] for b in drift['boards']},baseline_preserved=True,measurement_segment_2609_preserved=True))
 raw=(Path(scope['soak_run'])/'status.json').read_bytes();soak=json.loads(raw)
 require(soak['state']=='running' and soak['candidate']=='rc1-debugger-v1g-BRK82-84-corrected' and soak['authorized_hours']==3 and not soak.get('workload_failure'),'Soak is not the healthy running v1g job')
 save(record/'soak-status-at-build.json',soak)
 pending=dict(status='running-not-qualified',candidate_build=old['candidate_build'],firmware_sha256=IMAGE_SHA,package_manifest_sha256=KIT_SHA,authorized_hours=3,source_run=Path(scope['soak_run']).name,source_status_sha256=hashlib.sha256(raw).hexdigest(),snapshot_utc=datetime.fromtimestamp(soak['updated_unix'],timezone.utc).isoformat(),started_utc=soak['started_utc'],deadline_utc=datetime.fromtimestamp(soak['deadline_unix'],timezone.utc).isoformat(),passed_cycles_snapshot={b:v['passed_cycles'] for b,v in soak['boards'].items()},snapshot_only=True,soak_qualified=False,completed_authorized_duration=False,final_drift_snapshot_passed=None,parent_results_reused=False,board_access_during_packaging=False,native_debugging=False,native_applications_tested=False,promotion_held=True)
 save(out/'qualification/soak/pending.json',pending)
 summary=READ(out/'qualification/summary.json');summary.update(hardware_requalification_passed=True,hardware_registration_scenarios=144,hardware_BRK82_84_edge_checks=168,hardware_breakpoint_hits=128,device_verified_hardware_transfers=88,source_hardware_report_sha256=HW_SHA,three_hour_soak_passed=None,six_hour_soak_passed=None,final_drift_snapshot_passed=None,soak_state='running-not-qualified',pending=['three-hour-v1g-soak-completion','final-v1g-drift-review','explicit-promotion-decision'])
 save(out/'qualification/summary.json',summary)
 update_docs(out)
 verifier=(HERE/'package-staged/verify_package.py').read_text()
 verifier=verifier.replace('offline-only v1g staging snapshot','hardware-qualified, promotion-held v1g staging snapshot').replace("m['distribution_revision']==4","m['distribution_revision']==5").replace("not m['hardware_qualified'] and not m['soak_qualified']","m['hardware_qualified'] and not m['soak_qualified']")
 begin=verifier.index("    require(summary['hardware_requalification_passed'] is None");end=verifier.index("    require(offline['passed']",begin)
 verifier=verifier[:begin]+"    verify_hardware(root,summary)\n"+verifier[end:]
 verifier=verifier.replace("hardware='pending',soak='pending'","hardware='passed',soak='running-not-qualified'")
 helper=(HERE/'package-requalified/verify_hardware.inc').read_text().replace('REPLACE_HARDWARE_INDEX_SHA',SHA(out/'qualification/hardware/source-evidence.json'))
 verifier=verifier.replace("if __name__=='__main__':",helper+"\nif __name__=='__main__':")
 (out/'verify_package.py').write_text(verifier,encoding='utf-8')
 seal(record,out,archive,checksum,old,protected)

def update_docs(out):
 p=out/'docs/rc1/DEBUGGER_BOARD_RESULTS.md';text=p.read_text();text=text.replace('# v1g DBG1 offline results and pending board qualification','# v1g DBG1 offline and hardware requalification results').replace('**This image has offline results only; physical-board results are pending.**','**Both boards passed physical requalification; the three-hour v1g soak and final drift review remain pending.**')
 p.write_text(text,encoding='utf-8')
 section(p,'## Hardware and soak status','## Offline scope and limits',HARDWARE_RESULTS)
 edit(p,'[pending qualification]','[current qualification]')
 p=out/'docs/rc1/DEBUGGER_GUIDE.md'
 section(p,'## Candidate review status','## Enter automatically with BRK xx',GUIDE_STATUS)
 edit(p,'No v1g hardware soak or drift snapshot is claimed. Earlier v1e eight-hour\nresults and the ongoing v1f six-hour run are separate evidence. They cannot\nqualify this image. See [qualification limits](DEBUGGER_BOARD_RESULTS.md).','Both-board hardware requalification passed, including rollback/reinstall. The current three-hour v1g soak is still running; its completion and final drift review remain pending. The owner-stopped v1f partial soak and earlier v1e evidence do not qualify v1g. See [qualification limits](DEBUGGER_BOARD_RESULTS.md).')
 edit(out/'docs/rc1/OPERATOR_GUIDE.md','Earlier candidate trials passed on 2604 and 2609 and restored their original\npreferences/RAM. This staged v1g build has offline model results only; its\nphysical-board checks are pending. Native applications/debugging are','V1g passed initial and post-reinstall checks on 2604 and 2609 in MON A/B, with original preferences/RAM restored at hardware closeout. The current three-hour v1g soak and final drift review remain pending. Promotion stays held. Native applications/debugging are')
 edit(out/'docs/rc1/FIRMWARE_CONTENTS.md','Both CPU models verified\npreservation; physical v1g verification is pending.','Both CPU models and both physical boards verified preservation, including v1g rollback/reinstall in MON A/B.')
 edit(out/'docs/rc1/README.md','regressions pass; physical-board requalification, soak and final drift results\nare pending. Promotion remains held. Earlier generations/builds have separate','regressions pass, and both-board/both-slot hardware requalification with rollback/reinstall passed. The three-hour v1g soak is running; completion and final drift review remain pending. Promotion remains held. Earlier generations/builds have separate')
 p=out/'docs/rc1/TECHNICAL_MANUAL.md';p.write_text(p.read_text()+'\n\n## DBG1 v1g hardware checkpoint\n\nBoth-board MON A/B requalification and rollback/reinstall passed with 88 device-verified transfers, full-bank verification and original RAM restoration. Firmware and installer bytes are unchanged in distribution r5. The three-hour v1g soak and final drift review remain pending; promotion stays held and native applications/debugging remain excluded. See [board results](DEBUGGER_BOARD_RESULTS.md) and [ASM/BRK supplement](ASM_DBG1_REQUALIFICATION.md).\n',encoding='utf-8')
 p=out/'INSTALL_ROLLBACK.md';text=p.read_text();start=text.index('This is a staged,');end=text.index('The commands below',start);text=text[:start]+INSTALL_STATUS+'\n\n'+text[end:]
 old='Do not run a BRK smoke after removing DBG1. For this v1g image, install/rollback passed on both CPU models only, with\neleven transfers per simulated transaction. Physical v1g rollback/reinstall\nis pending; earlier v1f hardware receipts do not establish it.'
 require(old in text,'Missing rollback scope');text=text.replace(old,'Do not run a BRK smoke after removing DBG1. V1g install/rollback passed on both CPU models and both physical boards. Every hardware transaction verified eleven transfers; each target was checked across all four flash banks, with original RAM restored.')
 start=text.index('## Existing generation-50 boards and pending qualification');text=text[:start]+INSTALL_EXISTING+'\n';p.write_text(text,encoding='utf-8')
 (out/'release/candidates/rc1-debugger-brkfix-r1/README.md').write_text('# v1g source identity\n\nDistribution r5 retains the exact v1g debugger source and firmware, with completed both-board hardware requalification. The three-hour v1g soak and final drift review remain pending, promotion stays held and native applications/debugging are excluded.\n\nSee the [package README](../../../README.md), [board results](../../../docs/rc1/DEBUGGER_BOARD_RESULTS.md) and [install/rollback](../../../INSTALL_ROLLBACK.md). The archive contains matching debugger source; full rebuild commands require the source checkout and its dependencies.\n',encoding='utf-8')

HARDWARE_RESULTS='''## Hardware and soak status

The exact v1g image passed on both physical boards in MON A and MON B before and after rollback/reinstall.

| Board | CPU | Registration scenarios | BRK $82/$84 checks | Breakpoint hits | Device-verified transfers |
| --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 | 72 | 84 | 64 | 44 |
| 2609 | 65C816 E=1 | 72 | 84 | 64 | 44 |
| Total | | 144 | 168 | 128 | 88 |

Both slots passed MAINT, ASM, UCHESS, SRAM, WORK, EDU and CLOCK checks, system/user registration capacity and refusal cases, callback arguments/results, nested-BRK protection, BRK/C/S/N, shared D/M/U, all eight persistent breakpoints, ninth refusal and cleanup. The 816 remained E=1 before/after each slot. Focused $82/$84 hardware cases used each board's actual $64FF limit without changing optional-service ownership; released $66FF remains offline coverage.

Four transactions per board followed v1f -> generation 49 -> v1g -> generation 49 -> v1g. Every transaction verified eleven transfers, a fresh boot, all four flash banks and original RAM restoration. Both original full 25,344-byte application RAM archives and monitor preferences were restored at hardware closeout. Flash/settings guards, erase accounting and RTC controls/trims passed. No hardware-test failures occurred. Two waits for physical RESET expired harmlessly and were resumed after the operator acted; those waits are not firmware-test failures.

Actual [hardware receipts](../../qualification/hardware/summary.json), their [source binding](../../qualification/hardware/source-evidence.json) and the [ASM/BRK results supplement](ASM_DBG1_REQUALIFICATION.md) accompany this archive. Private board RAM/flash captures, serial logs and board-specific plans are excluded.

The separately authorized **three-hour v1g soak is running** at this snapshot. Its completion and final drift review are pending; see the timestamped [soak status](../../qualification/soak/pending.json). This archive does not update automatically. The owner stopped v1f's preceding soak after 2 h 33 min 11.859 s; restoration and drift snapshots passed, but that partial run is neither a six-hour pass nor v1g evidence. Earlier v1e/v1f results remain historical.

Promotion remains held pending the v1g soak/drift review and an explicit release decision. Staging opens no port and changes no firmware, settings, clocks, trims or active workload. Native applications/debugging remain excluded.'''
GUIDE_STATUS='''## Candidate review status

This manual describes the **v1g BRK edge-fix candidate**, generation 50 / BRK ABI 1. Distribution r5 adds both-board hardware evidence without changing firmware or installer bytes. MON A/B passed initial and post-reinstall checks on 2604 and 2609, including MAINT, registrations, C/S/N and all eight persistent breakpoints. The 816 checks remained E=1.

Invalid $82 unregister IDs outside $C0-$FE return C=0,A=1 before lookup. Valid $84 text ending at the discovered application RAM limit preserves saved registers/flags; crossing ranges print nothing and refuse. Offline results retain all 88 original edge checks and 7,256 expanded cases. Hardware adds 168 focused $82/$84 checks across both boards and initial/final slot passes.

The three-hour v1g soak is running; completion and final drift review remain pending. Promotion is held and native applications/debugging remain excluded. See [board results](DEBUGGER_BOARD_RESULTS.md), [ASM/BRK supplement](ASM_DBG1_REQUALIFICATION.md) and [candidate status](V1G_STAGING_STATUS.md).'''
INSTALL_STATUS='''This staged, promotion-held **v1g** image passed offline and physical requalification on 2604 and 2609 in MON A/B, including rollback/reinstall. The independently authorized three-hour v1g soak is running as of this snapshot; completion and final drift review remain pending. No hardware operation is authorized or started by packaging or verification.'''
INSTALL_EXISTING='''## Existing generation-50 boards and recorded qualification

This exact-source route admits generation 49 with erased B1:A. It refuses currently installed generation-50 candidates, including v1g. Both boards now run v1g and belong to the active soak; do not open their ports or repeat installation while it runs.

The completed qualification used four transactions per board: v1f rollback to 49, v1g installation, v1g rollback to 49, then v1g reinstall. Every transaction verified eleven transfers and required a physical RESET: 44 verified transfers and four resets per board, 88 transfers total. The RAM installer deliberately halts after verification and has no monitor command loop; J3 cannot be issued there. Automatic restart is not part of this frozen kit.

For a future authorized rollback, first complete the soak or request its safe stop and verify full RAM restoration. Preserve the board's original v1g install plan and source archive. Take a fresh current capture and derive rollback using that exact original plan, then follow sections 7 and 8 above. After generation-49 flash/RAM verification, take another fresh generation-49 capture before any authorized v1g reinstall. Never replay a stale plan or old C/D journal image. If the original escrow is missing, stop for a recovery assessment.

Rollback returns to the captured generation-49 source, preserves current owner settings/data outside target sectors and advances wear accounting. It does not reinstall v1f. Keep power on during transactions and use physical RESET only after device-verified completion.

Both-slot hardware, MAINT/app, system/user registration, debugger and rollback/reinstall checks are complete. The remaining promotion gates are the current three-hour v1g soak, its final drift review and an explicit release decision. Native applications/debugging remain out of scope.'''

def seal(record,out,archive,checksum,old,protected):
 sys.path.insert(0,str(ROOT/'tools'));from audit_rc1_dbg_docs import audit
 docs=audit(out,list(out.rglob('*.md')));require(docs['passed'],'Documentation links failed: '+str(docs['errors']));save(out/'qualification/documentation-audit.json',docs)
 files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('package-manifest.json','SHA256SUMS.txt')}
 for name in files:
  require(not any(part in ('__pycache__','private','capture','before','after') for part in Path(name).parts) and not name.endswith(('.jsonl','.pyc','.zip')),'Private/cache artifact included')
  if Path(name).suffix in ('.py','.md','.json','.txt'):require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',(out/name).read_text(encoding='utf-8')),'Host path leaked: '+name)
 m=dict(old);m.update(distribution_revision=5,hardware_qualified=True,soak_qualified=False,staged_utc=datetime.now(timezone.utc).isoformat(),package_markdown_links_checked=docs['links_and_anchors_checked'],source_hardware_report_sha256=HW_SHA,files=files);save(out/'package-manifest.json',m)
 sums=dict(files);sums['package-manifest.json']=dict(bytes=(out/'package-manifest.json').stat().st_size,sha256=SHA(out/'package-manifest.json'))
 (out/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in sorted(sums.items())),encoding='ascii')
 check=subprocess.run([sys.executable,str(out/'verify_package.py')],capture_output=True,text=True);require(check.returncode==0,check.stdout+check.stderr)
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
  for name in sorted([*sums,'SHA256SUMS.txt']):
   entry=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,20,0,0,0));entry.create_system=3;entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,(out/name).read_bytes())
 with tempfile.TemporaryDirectory(prefix='dbg-v1g-r5-extract-',dir=ROOT/'tmp') as temp:
  with zipfile.ZipFile(archive) as z:require(z.testzip() is None,'ZIP CRC failure');z.extractall(temp)
  test=subprocess.run([sys.executable,str(Path(temp)/out.name/'verify_package.py')],capture_output=True,text=True);require(test.returncode==0,test.stdout+test.stderr)
 checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
 for path,digest in protected.items():require(SHA(path)==digest,'Protected input changed during staging: '+path)
 save(record/'package-report.json',dict(integrity_passed=True,hardware_requalification_passed=True,soak_qualified=False,soak='running-not-qualified',final_drift='pending',promotion_held=True,release_qualification_passed=False,firmware_sha256=IMAGE_SHA,tested_kit_manifest_sha256=KIT_SHA,source_hardware_report_sha256=HW_SHA,archive=str(archive),archive_sha256=SHA(archive),archive_bytes=archive.stat().st_size,archive_checksum=str(checksum),package_manifest_sha256=SHA(out/'package-manifest.json'),distribution=str(out),files_verified=len(sums)+1,markdown_links_and_anchors_checked=docs['links_and_anchors_checked'],extracted_archive_verified=True,protected_files_verified=len(protected),board_access=False,native_debugging=False,native_applications_tested=False))
 print(check.stdout.strip());print(json.dumps(READ(record/'package-report.json'),indent=2))

if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError) as exc:raise SystemExit('REFUSED: '+str(exc))
