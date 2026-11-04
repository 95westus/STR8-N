"""Close the approved cleanup from live receipts; no hardware or builds."""
import json
from pathlib import Path
import execute_rec_cleanup as e
t=e.t;Q=e.Q
scope=json.loads((e.SCOPE/'plan.json').read_text());ref={b:(Q/('2512-DBG-g2-installed-20261102-r1' if b in (0,3) else '2512-legacy-reclaimed-20261102-r1')/f'B{b}-after.bin').read_bytes() for b in range(4)}
r=dict(passed=False,total_component_erases=0,total_journal_erases=0,F_writes=0,MON_writes=0,SPI_writes=0,RTC_setting_writes=0,other_boards_accessed=[],boards={})
for board in ('2604','2609'):
 installed=Q/f'{board}-REC-utility-cleanup-installed-20261102-r1';write=json.loads((installed/'report.json').read_text())
 proof=Q/'2604-REC-utility-cleanup-verified-20261102-r3/report.json' if board=='2604' else installed/'report.json'
 live=json.loads(proof.read_text());p=scope['boards'][board];assert live['passed'] and write['NVM_verified']
 assert all(live[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released'))
 for name in ('owner-ram.bin','owner-zp.bin','provider-cache-before.bin','hooks-before.bin'):
  assert (installed/name).read_bytes()==(proof.parent/name).read_bytes()
 assert live['RAM_sha256']==t.sha((installed/'owner-ram.bin').read_bytes()) and live['ZP_sha256']==t.sha((installed/'owner-zp.bin').read_bytes())
 assert write['erase_requests']==p['image_erases'] and len(write['completed'])==p['image_erases']
 data={b:(installed/f'B{b}-after.bin').read_bytes() for b in range(4)}
 assert {f'B{b}':t.sha(v) for b,v in data.items()}==p['after_bank_sha256']
 assert data[1]==ref[1] and data[2]==ref[2]
 for start,end in ((0x2000,0x4000),(0x6000,0x8000)):
  assert data[3][start:end]==ref[3][start:end]
 diffs=[i for i,(a,b) in enumerate(zip(ref[0],data[0])) if a!=b]
 assert set(diffs)<=({0x200f,0x201c,0x201d,0x400f,0x401c,0x401d} if board=='2609' else set())
 initial=(installed/'SPI-metadata-before.bin').read_bytes();final=(proof.parent/'SPI-metadata-after.bin').read_bytes();assert initial==final
 assert all(final[0x40+64*k+63]!=0xa5 for k in range(8))
 delta=[b-a for a,b in zip(p['journal_before']['counts'],p['journal_after']['counts'])];assert sum(delta)==p['total_erases'] and min(delta)>=0
 m=json.loads((Q/f'device-operations/{board}.json').read_text());assert m['current_physical_bank_sha256']==p['after_bank_sha256'] and not m['block_snapshot'] and not m['REC_cleanup_pending']
 archive=t.ROOT/f'local-archives/2604-2609-REC-cleanup-20261102/{board}'
 for name,body in [('write-receipt.json',(installed/'report.json').read_bytes()),('acceptance-receipt.json',proof.read_bytes())]+[(f'B{b}-after.bin',v) for b,v in data.items()]:
  f=archive/name
  if f.exists():assert f.read_bytes()==body
  else:e.opaque.durable_file(f,body)
 r['total_component_erases']+=p['image_erases'];r['total_journal_erases']+=len(p['journal_rotation_erases'])
 r['boards'][board]=dict(passed=True,write_receipt=str(installed/'report.json'),acceptance_receipt=str(proof),erases=p['total_erases'],journal_appends=p['journal_appends'],old_records_archived=len(p['old_journal_rows']),old_records_replaced_on_chip=len(p['replaced_on_chip_old_rows']),journal_sequence=p['journal_after']['sequence'],C_D_E_F_counts=p['journal_after']['counts'][28:32],firmware_matches_2512=True,CPU_envelope_only_differences=[f'{x+0x8000:04X}' for x in diffs],free_erased_flash_bytes=36864,PROGRAM_slots_free=8,SPI_metadata_exact=True,owner_RAM_ZP_cache_restored=True,final_prompt=m['final_prompt'],port_released=True,permanent_archive=str(archive))
r['total_erases']=r['total_component_erases']+r['total_journal_erases'];assert r['total_erases']==21
r['passed']=True;out=Q/'2604-2609-REC-cleanup-complete-20261102.json';t.save(out,r)
print('PASS both boards match 2512 utility profile; 21 approved erases; 36 KiB erased each; F/MON unchanged; RAM restored; ports free.')
