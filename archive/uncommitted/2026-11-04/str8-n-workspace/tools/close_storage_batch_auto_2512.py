"""Reconcile accepted live receipts and seal closeout; never open a board port."""
import json
from pathlib import Path
from storage_release_trial_2512 import *
from continue_storage_large_return_2512 import OUT,carry_auto
from native_journal_room import valid_snapshot


def run():
    p=approved();ir=json.loads((INST/'report.json').read_text());ar=json.loads((POS/'report.json').read_text());rr=json.loads((OUT/'report.json').read_text())
    assert ir['passed'] and rr['passed'] and rr['scope_checks_complete']
    for r in (ir,ar,rr):assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released'] and r['NVM_verified']
    assert ar['B0_restored'] and not ar['SPI_restore_pending'] and rr['SPI_restored'] and not rr['SPI_restore_pending']
    assert (ir['flash_erase_requests'],ar['flash_erase_requests'],rr['flash_erase_requests'])==(10,3,0)
    native=[v for op in ir['operations']+ar['operations'] for v in op['journal_sector_erases']];assert native==['B3:C']
    assert sum(len(op['journal_appends']) for op in ir['operations']+ar['operations'])==14
    carried,_=carry_auto();assert carried==rr['carried_AUTO']
    expected,_=forecast_install(p);expected[3]=(SCOPE/'B3-final-predicted.bin').read_bytes()
    final={bank:(OUT/f'B{bank}-after.bin').read_bytes() for bank in range(4)};assert final==expected
    old=(SCOPE/'B3-original.bin').read_bytes();now=final[3]
    assert t.sha(now[-4096:])==p['F_sha256']
    assert now[-4096:]==old[-4096:] and now[0x2000:0x4000]==old[0x2000:0x4000]
    assert now[0xE90:0xFFE]==old[0xE90:0xFFE] and now[0x1C00:0x2000]==old[0x1C00:0x2000]
    rows=[i for i in range(0x4000,0x6000,256) if valid_snapshot(old[i:i+256])]
    retained=[i for i in rows if old[i:i+256]==now[i:i+256]];assert len(rows)==25 and len(retained)==9
    j=t.classify_journal(now);assert j['sequence']==1164 and j['valid_records']==23 and j['counts']==p['counts_after']
    def latest(bank):
        return max((int.from_bytes(bank[i+8:i+12],'little'),bank[i:i+256]) for i in range(0x4000,0x6000,256) if valid_snapshot(bank[i:i+256]))[1]
    assert latest(old)[12:30]==latest(now)[12:30],'Boot policy/generation/delay must remain exact'
    m=json.loads((Q/'device-operations/2512.json').read_text())
    assert not m['block_snapshot'] and not m['application_RAM_restore_pending'] and m['application_ram_restored']
    assert not any(v for k,v in m.items() if k.endswith('_worker_active')) and not m.get('storage_large_SPI_restore_pending') and not m.get('storage_large_B0_restore_pending')
    assert m['current_physical_bank_sha256']=={f'B{k}':t.sha(b) for k,b in final.items()}
    receipt=dict(status='ACCEPTED_2512_INSTALLED_STORAGE_BATCH_WIDE_AUTO_LARGE_RETURN',board='2512',
        reports=[dict(path=str(path),sha256=t.sha(path.read_bytes())) for path in (INST/'report.json',POS/'report.json',OUT/'report.json')],
        approval_sha256=t.sha((SCOPE/'approval.json').read_bytes()),total_erases=14,image_erases=10,scratch_erases=3,journal_erases=1,
        journal_appends=14,sequence=1164,valid_records=23,old_records_archived=25,old_records_retained_on_chip=9,
        counts_C_D_E_F=j['counts'][28:],F_sha256=p['F_sha256'],F_writes=0,MON_A_B_writes=0,metadata_appends=0,
        boot_default='B/g0000000F',SPI_test_bytes_restored=8256,owner_RAM_restored=True,owner_ZP_restored=True,
        current_bank_sha256={f'B{k}':t.sha(b) for k,b in final.items()},RAM_sha256=rr['RAM_sha256'],ZP_sha256=rr['ZP_sha256'],
        final_prompt='REC>',COM4_released=True,RTC_setting_writes=0,resets=0,power_cuts=0,other_boards_access=False,published_download_changes=False,
        gate_status=dict(installed_SRAM_WORK_BATCH='accepted',large_flash_AUTO='accepted',large_returning_PROGRAM_BATCH='accepted'),
        evidence_limit=carried['limitation'],CPU_simulations=0,F_rebuilt=False)
    t.save(SCOPE/'completion.json',receipt)
    m.update(storage_batch_auto_qualification_pending=False,last_storage_batch_auto_closeout=str(SCOPE/'completion.json'),
        installed_storage_BATCH_qualified=True,large_flash_AUTO_qualified=True,large_returning_PROGRAM_BATCH_qualified=True)
    t.save(Q/'device-operations/2512.json',m)
    print(json.dumps({k:receipt[k] for k in ('status','total_erases','journal_appends','sequence','valid_records','counts_C_D_E_F','gate_status','COM4_released')},indent=2))


if __name__=='__main__':run()
