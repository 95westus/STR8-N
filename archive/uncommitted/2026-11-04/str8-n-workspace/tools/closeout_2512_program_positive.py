"""Create hash-only PROGRAM acceptance after exact 2512 restoration passes."""
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
CASE=t.ROOT/'output/qualification/2512-PROGRAM-positive-trial-20261030-r1'
SCOPE=t.ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'
r=json.loads((CASE/'report.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
assert r['passed'] and r['all_131072_SRAM_bytes_restored'] and not r['SRAM_restore_pending']
assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['COM4_released']
assert r['all_flash_banks_unchanged'] and len(r['stores'])==4
assert r['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())
snapshot=(SCOPE/p['original_SRAM']).read_bytes()
assert snapshot==(CASE/'SRAM-fresh-before-131072.bin').read_bytes()==(CASE/'SRAM-restored-131072.bin').read_bytes()
receipt=dict(schema=1,board='2512',CPU='65C02',passed=True,phase='PROGRAM_65C02_PASSED',
    monitor_generation='00000008',service_generation='00000004',workbench_generation='00000005',program_generation='00000001',
    PROGRAM_format='SS1',PROGRAM_boundary='10000',temporary_directory_slots=[0,1,2,3],
    temporary_payload_range='C000-C3FF',temporary_byte_scope=1280,stores=r['stores'],
    AUTO_preview='0800; NO; no write',positive_AUTO_store_retested=False,
    explicit_Store_Restore_run_qualified=True,latest_version_qualified=True,
    payload_CRC_refusal_before_copy_qualified=True,full_directory_refusal_in_scope=False,
    retained_slots_5_6_and_free_slots_4_7_unchanged=True,all_131072_SRAM_bytes_restored=True,
    SRAM_sha256=t.sha(snapshot),WORKSPACE_unchanged=True,primary_header_unchanged=True,
    all_flash_banks_unchanged=True,bank_sha256=p['source_bank_sha256'],journal_sequence=1033,valid_records=20,
    default_boot='B',saved_generation='00000008',counts_unchanged=p['counts_unchanged'],
    F_sha256=p['F_sha256'],flash_writes=0,journal_writes=0,WORKSPACE_writes=0,
    RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
    existing_restorer_bytes=767,existing_restorer_sha256=p['restorer']['sha256'],
    owner_RAM_ZP_restored_verified=True,final_context=r['final_context'].strip(),COM4_released=True,
    checks=r['checks'],plan_sha256=r['plan_sha256'],source_report_sha256=t.sha((CASE/'report.json').read_bytes()),
    driver_sha256=p['driver_sha256'],published_downloads_unchanged=True,finished_utc=r['finished_utc'])
t.save(t.REPO/'monitors/validation/2512-program-positive.json',receipt)
doc='''# 2512 current PROGRAM Store/Restore/run: passed

October 30, 2026. **65C02 / FT245**, installed MON B g8, services g4, WB2 g5
and PROGRAM/SP1 g1. [Public receipt](../monitors/validation/2512-program-positive.json),
[exact temporary scope](2512_PROGRAM_POSITIVE_SCOPE.md).

The fresh complete SRAM read matched the latest preserved snapshot before
any Store. AUTO correctly previewed0800; NO canceled it without writing.
Four explicit Stores passed atC000/C100/C200/C300: a16-character name, a
short name, a newer same-name version and a separate record. An overlapping
payload was refused before another commit. Table listed the records, checked
load-only selected the newer UP version and restored its exact23 bytes, and
positive run printed UP and returned through public HOLD to MON B/CPU02.

A deliberate first-byte change in the temporary C200 payload produced CRC
error45 before copying destination RAM; all23 sentinel bytes remained intact.
Repair restored successful checked loading. No retained CLK/CLOCK program
was run. Directory-full and positive AUTO Store are outside this trial;
its additional free slots were preserved. 2609's separate current-SP1
acceptance retains its AUTO and full-directory evidence.

All20 allowed64-byte blocks were restored and individually read back. The
complete131072-byte SRAM then matched the original, including slots5/6,
unused slots4/7, primary header, all other PROGRAM data, WORKSPACE and tail:
`580a60e314e7c91703a319f03516bd803f36a8202f773e4206b6d4aa69d227aa`.
All four flash banks match both before/after double captures. The journal
remains20 valid rows, C300/seq1033, default B/g8; C=53/D=33/E=28/F=24.
There were zero flash/journal/WORKSPACE writes, clock/trim/PF changes,
resets, power cuts, firmware builds or CPU simulations. The existing767-byte
guarded restorer and existing OK/UP binaries were reused unchanged.

Owner RAM0200-66FF and ZP00-DF were freshly double-captured through native
Dump before a helper upload, restored and independently compared again.
Original MON B/B3> returned; COM4 released. The native TIME RTC/NTP profile,
clock settings, baselines and schedule remain unchanged. This trial uses
2512 only. 2609's separately approved AP/02 trial grants no wider target
permission; 2205 and2604 remain excluded.

This closes current-SP1 positive SS1 Store/Restore/run on65C02. Together with
the2609 acceptance it adds explicitly scoped evidence for both CPU types;
SS2 writes, native816 mode, new ASM/DBG or full b35 parity remain separate
work. Published Foundation/preview archives, release tags and frozen F
remain unchanged. Private captures and the exact restoration originals stay
under the parent project's `output/qualification/2512-PROGRAM-positive-*`.
'''
for a,b in [('previewed0800','previewed 0800'),('atC000','at C000'),('a16-character','a 16-character'),
    ('exact23','exact 23'),('all23','all 23'),('All20 allowed64-byte','All 20 allowed 64-byte'),
    ('complete131072','complete 131072'),('slots5/6','slots 5/6'),('slots4/7','slots 4/7'),
    ('remains20','remains 20'),('existing767','existing 767'),('on65C02','on 65C02'),
    ('the2609','the 2609'),('native816','native 816'),('and2604','and 2604')]: doc=doc.replace(a,b)
(t.REPO/'docs/2512_PROGRAM_POSITIVE_ACCEPTANCE.md').write_text(doc)
print('PASS public 2512 PROGRAM receipt written; no owner bytes included')
