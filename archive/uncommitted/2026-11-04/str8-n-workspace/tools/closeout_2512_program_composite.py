"""Report functional PROGRAM pass plus exact recovery, preserving the scope error."""
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
CASE=t.ROOT/'output/qualification/2512-PROGRAM-positive-trial-20261030-r1'
FIX=t.ROOT/'output/qualification/2512-PROGRAM-preserving-repair-20261030-r1'
SCOPE=t.ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'
r=json.loads((CASE/'report.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
fix=json.loads((FIX/'report.json').read_text());repair=json.loads((FIX/'repair-plan.json').read_text())
assert not r['passed'] and len(r['stores'])==4 and 'CRC-repair-and-restore' in r['checks']
assert fix['passed'] and fix['all_131072_SRAM_bytes_restored'] and not fix['SRAM_restore_pending']
assert fix['owner_RAM_restored'] and fix['owner_ZP_restored'] and fix['COM4_released'] and fix['all_flash_banks_unchanged']
assert r['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())
snapshot=(SCOPE/p['original_SRAM']).read_bytes()
assert snapshot==(CASE/'SRAM-fresh-before-131072.bin').read_bytes()==(FIX/'SRAM-repaired-131072.bin').read_bytes()
assert t.sha((CASE/'report.json').read_bytes())==repair['failed_report_sha256']
receipt=dict(schema=1,board='2512',CPU='65C02',passed=True,phase='PROGRAM_PASSED_HOST_SCOPE_ERROR_EXACTLY_RESTORED',
    initial_trial_passed=False,initial_temporary_scope_met=False,firmware_defect_found=False,
    host_failure='Plan assumed first free directory slots; provider selects last free slots',
    planned_directory_slots=[0,1,2,3],actual_directory_slots=[7,4,3,2],
    planned_temporary_byte_scope=1280,actual_trial_and_restoration_address_scope=1408,
    observed_remaining_byte_differences=91,restoration_only_extra_addresses=['0140','0200'],restoration_only_extra_bytes=128,
    original_failed_report_preserved=True,initial_owner_RAM_restoration_deferred_by_host_exception=True,
    monitor_generation='00000008',service_generation='00000004',workbench_generation='00000005',program_generation='00000001',
    PROGRAM_format='SS1',PROGRAM_boundary='10000',temporary_payload_range='C000-C3FF',stores=r['stores'],
    AUTO_preview='0800; NO; no write',positive_AUTO_store_retested=False,explicit_Store_Restore_run_qualified=True,
    latest_version_qualified=True,payload_CRC_refusal_before_copy_qualified=True,full_directory_refusal_in_scope=False,
    retained_slots_5_6_unchanged=True,original_slot7_retirement_restored=True,all_131072_SRAM_bytes_restored=True,
    SRAM_sha256=t.sha(snapshot),WORKSPACE_unchanged=True,primary_header_unchanged=True,
    all_flash_banks_unchanged=True,bank_sha256=p['source_bank_sha256'],journal_sequence=1033,valid_records=20,
    default_boot='B',saved_generation='00000008',counts_unchanged=p['counts_unchanged'],F_sha256=p['F_sha256'],
    flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,
    firmware_builds=0,assembler_invocations=0,CPU_simulations=0,
    original_restorer_sha256=p['restorer']['sha256'],repair_restorer_sha256=repair['restorer_sha256'],
    restorer_instruction_bytes_unchanged=True,private_allowlist_and_CRC_resealed=True,
    owner_RAM_ZP_restored_verified=True,final_context=fix['final_context'].strip(),COM4_released=True,
    checks=r['checks']+['exact-extra-slot-restoration','complete-SRAM-equality','all-bank-equality','native-owner-RAM-ZP-restored'],
    plan_sha256=r['plan_sha256'],failed_trial_report_sha256=t.sha((CASE/'report.json').read_bytes()),
    preserving_repair_report_sha256=t.sha((FIX/'report.json').read_bytes()),repair_plan_sha256=t.sha((FIX/'repair-plan.json').read_bytes()),
    driver_sha256=p['driver_sha256'],published_downloads_unchanged=True,finished_utc=fix['finished_utc'])
t.save(CASE/'composite-receipt.json',receipt)
t.save(t.REPO/'monitors/validation/2512-program-positive.json',receipt)
doc='''# 2512 current PROGRAM: functional pass and exact preservation closeout

October 30, 2026. **65C02 / FT245**, installed MON B g8, services g4, WB2 g5
and PROGRAM/SP1 g1. [Public composite receipt](../monitors/validation/2512-program-positive.json),
[original temporary scope](2512_PROGRAM_POSITIVE_SCOPE.md). Functional checks
passed. The original narrow directory scope was not met because of a host
planning error; the preserving continuation restored every original byte.
The original failed report remains unchanged.

## Functional results

Fresh complete SRAM matched its preserved snapshot before Store. AUTO
previewed0800 and NO canceled it without writing. Four explicit Stores at
C000/C100/C200/C300 passed: a16-character name, a short name, a newer same-name
version and a separate record. Occupied-payload refusal and Table passed.
Checked load-only selected the newer UP version and restored its exact23
bytes. Positive run printed UP and returned through public HOLD to MON B.
A deliberate first-byte change in the temporary C200 payload caused CRC
error45 before destination copying; all23 sentinel bytes remained intact.
Repair restored successful checked loading. No retained CLK/CLOCK program
was run. Positive AUTO Store and directory-full checks remain outside this
trial; the2609 receipt retains its separate current-SP1 evidence for them.

## Host planning error and preserving repair

The planner assumed free directory slots0/1/2/3. PROGRAM's existing scanner
keeps updating FREE_SLOT and therefore selects the last free slot: the four
Stores actually used7/4/3/2. Restoring only the initially planned blocks left
91 differing bytes in slots4 and7, caught by the complete-array comparison.
The functional binary behaved correctly; this was a host scope-planning
error. The exception also deferred owner-RAM restoration while the board
stayed at WORKBENCH>, with RTC sampling blocked and all original bytes
already escrowed. No reset or flash transaction followed the failure.

The preserving continuation restored exact original64-byte blocks0140-017F
and0200-023F, including slot7's retired commit byte00. It reused the same
private restorer instruction bytes; only its data allowlist was restricted
to those two addresses and its image CRC resealed. No assembler or firmware
build. Both blocks were independently read back, followed by complete SRAM
comparison. The union of trial/restoration addresses was1408 bytes, including
128 bytes outside the original1280-byte plan. This is explicitly recorded
as a scope error, not described as compliance with the original plan.

## Final preservation

All131072 SRAM bytes now match the original:
`580a60e314e7c91703a319f03516bd803f36a8202f773e4206b6d4aa69d227aa`.
Primary header, CLK/CLOCK payloads, original directory bytes, WORKSPACE and
tail are exact. Four-bank double comparisons also match: frozen F, images,
boot/wear history and saved B/g8 are unchanged. The journal remains20 rows,
C300/seq1033; C=53/D=33/E=28/F=24. Zero flash/journal/WORKSPACE writes,
clock/trim/PF changes, power cuts, resets or firmware builds.

Fresh pre-helper native owner RAM0200-66FF/ZP00-DF escrow was restored and
independently compared through native Dump. Original MON B/B3> returned,
COM4 released, and the unchanged native TIME RTC/NTP profile can resume.
The source planner/driver now check the allocator's actual slot order before
any future Store. 2609's AP/02 work waited until this preservation closeout.
2205 and2604 were outside the trial. Published Foundation/preview archives,
tags and F remain unchanged; ASM/DBG remain deferred and nonblocking.

Private original failed captures and the separate repair receipt remain in
the parent project's `output/qualification/2512-PROGRAM-*` directories.
'''
for a,b in [('previewed0800','previewed 0800'),('a16-character','a 16-character'),('exact23','exact 23'),
    ('all23','all 23'),('error45','error 45'),('the2609','the 2609'),('slots0/1/2/3','slots 0/1/2/3'),
    ('used7/4/3/2','used 7/4/3/2'),('slots4 and7','slots 4 and 7'),('original64-byte blocks0140','original 64-byte blocks 0140'),
    ('and0200','and 0200'),("slot7's","slot 7's"),('byte00','byte 00'),('was1408','was 1408'),
    ('original1280','original 1280'),('All131072','All 131072'),('remains20','remains 20'),('and2604','and 2604')]:doc=doc.replace(a,b)
(t.REPO/'docs/2512_PROGRAM_POSITIVE_ACCEPTANCE.md').write_text(doc)
marker=json.loads(t.MARK.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
marker['last_PROGRAM_positive_acceptance']=str(CASE/'composite-receipt.json');t.save(t.MARK,marker)
print('PASS composite receipt: functional checks passed; host scope error disclosed; all original bytes restored')
