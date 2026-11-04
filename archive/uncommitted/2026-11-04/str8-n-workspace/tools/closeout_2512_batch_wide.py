"""Sanitize passed BATCH evidence and update only 2512 metadata; no board access."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';BASE=ROOT/'output/qualification/2512-batch-wide-20261030-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
phases=['RAM-trial-r2','native-RAM-r2','CLOCK-error-RAM','context-fix-RAM','context-repair','cancel-RAM-r3','cancel-repair','AP02-one-erase-resume','physical-default']
rs={n:read(BASE/n/'report.json') for n in phases};assert all(r['passed'] for r in rs.values())
positive=read(BASE/'positive-trial/report.json');assert len(positive['checks'])==6 and positive['owner_RAM_restored'] and not positive['SRAM_restore_pending']
f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert len(f)==4096 and sha(f)==read(REPO/'F_FREEZE.json')['sha256']
b3=(BASE/'physical-default/B3-final.bin').read_bytes();j=rs['physical-default']['journal'];assert j['sequence']==1087 and j['valid_records']==26 and b3[0x7000:]==f
components={'MON':'g0000000b-batch','WB2':'wb2-g0000000a-batch','PROGRAM':'program-sp1-g00000002-wide-r5','services':'services-g00000008-batch-r2','native':'native-g00000001-r16'}
checks=[]
for n,r in rs.items():checks.extend(dict(phase=n,check=c) for c in r.get('checks',[]))
checks.extend(dict(phase='positive-trial-before-cancel-message-repair',check=c) for c in positive['checks'][:5])
receipt=dict(schema=1,status='2512_BATCH_WIDE_ACCEPTED_NOT_FULL_B35_RELEASE',date_local='2026-10-30',board='2512',CPU='65C02',transport='FT245',passed=True,
 components=components,component_manifests={k:sha((REPO/'monitors/candidates'/v/'manifest.json').read_bytes()) for k,v in components.items()},F_sha256=sha(f),F_bytes=4096,F_writes=0,F_rebuilt=False,CPU_simulations=0,
 checks=checks,system_image_erases=19,native_D_rotation_erases=1,B0_9_erases=1,total_erases=21,C_erases=0,power_cuts=0,RTC_SET=0,trim_writes=0,PF_ACK=0,WORKSPACE_writes=0,
 temporary_SRAM_bytes=14272,all_temporary_SRAM_restored=True,B0_9_original_FF_restored=True,owner_RAM_restored=True,owner_ZP_restored=True,
 owner_RAM_sha256=rs['physical-default']['RAM_sha256'],owner_ZP_sha256=rs['physical-default']['ZP_sha256'],physical_default_B_verified=True,volatile_queue_cleared_by_reset=True,EDU_session_ON=True,final_prompt='B3>',COM4_released=True,
 journal=j,original_raw_history_archived=True,history='Original C rows remain on chip; original D rows archived before native rotation. Latest boot/wear snapshot retained and extended.',boot_policy='B retained, bound to new MON generation 0000000B; bank enables/entries/delay retained.',
 other_boards_accessed=False,published=False,published_downloads_changed=False,terminal='Unchanged published Foundation console 0.1.0',full_b35_release_closed=False,
 evidence_limits=['Qualified common 65C02/FT245 path; targeted 65C816 checks remain.','No new whole-board capture campaign; exact admitted writes/readbacks and unchanged write boundaries preserve owner images.','Large PROGRAM load/run accepted; large STORE-source staging remains.','CLOCK SET/ACK/trim/policy positive writes, remaining CONFIG forms and full-b35 management/factory workflows remain open. ASM/DBG deferred.'],
 corrections=['Stale workbench-origin flag and native UI scratch overlap repaired in four sectors after RAM qualification.','Cancellation was safe but its message was muted by Foundation cancel state; three-byte RX_RESET acknowledgment repaired two PROGRAM sectors.','RAM cancellation sentinel initially invalidated WB cache and reloaded older provider; corrected harness passed.','First AP/02 host assertion expected a RAM-only message after successful flash-byte programming; resumed exact known partial preimage and completed one-erase scope.'],
 approval_scope='Automatic review rejected two AP/02 erases. Safer alternative programmed blank target 1-to-0 and used the prior approved single cleanup erase.')
save(REPO/'monitors/validation/2512-batch-wide.json',receipt);save(BASE/'final-receipt.json',receipt)
mark=ROOT/'output/qualification/device-operations/2512.json';m=read(mark);m.update(monitor_generation='0000000B',MON_A_generation='0000000B',MON_B_generation='0000000B',current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],current_F_sha256=sha(f),current_F_reservation_count=24,current_wear_counts=j['counts'],native_utilities_revision='r16',native_utilities_loader_revision='r15',services_generation='00000008',workbench_generation='0000000A',PROGRAM_generation='00000002',PROGRAM_revision='r5',batch_wide_qualification_complete=True,batch_wide_worker_active=False,batch_wide_installation_pending=False,BATCH_PROGRAM_restore_pending=False,BATCH_APP_restore_pending=False,application_RAM_restore_pending=False,application_ram_restored=True,application_RAM_restore_verified=True,physical_reset_pending=False,owner_application_running=False,EDU_session_ON=True,final_prompt='B3>',block_snapshot=False,last_batch_wide_receipt=str(BASE/'final-receipt.json'),RTC_UI1_readmission_passed=False,RTC_UI1_readmission_pending=True)
if 'current_physical_bank_sha256' in m:m['current_physical_bank_sha256']['B3']=sha(b3)
save(mark,m)
cp=BASE/'host-source-checkpoint';cp.mkdir(exist_ok=True)
for pattern in ('*2512*batch*.py','rtc_mon_ui1_gb_2512.py'):
 for q in (ROOT/'tools').glob(pattern):shutil.copyfile(q,cp/q.name)
shutil.copyfile(BASE/'acceptance-prepared.md',REPO/'docs/2512_BATCH_WIDE_ACCEPTANCE.md')
print('PASS sanitized receipt and 2512 metadata; no board access')
