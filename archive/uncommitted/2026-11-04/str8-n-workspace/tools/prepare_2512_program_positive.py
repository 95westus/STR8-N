"""Seal a 1280-byte temporary PROGRAM trial using existing fixtures; no port/build."""
import binascii
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t

ROOT=t.ROOT; REPO=t.REPO
OUT=ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'
OLD=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1'
INSTALLED=ROOT/'output/qualification/2512-services-g4-installed-20261030-r1'
SRAM=ROOT/'output/qualification/2512-services-g4-RAM-20261030-r2/SRAM-after-131072.bin'

assert not OUT.exists()
r=json.loads((INSTALLED/'final-receipt.json').read_text())
assert r['passed'] and r['physical_boot_verified'] and r['owner_RAM_restored']
data=SRAM.read_bytes(); assert t.sha(data)==r['SRAM_sha256']
layout=t.inspect_sram(data)
assert layout['format']=='SS1' and layout['boundary']=='10000'
assert all(n in [v['slot'] for v in layout['free_slots']] for n in range(4))
actual_slots=[v['slot'] for v in reversed(layout['free_slots'])][:4]
assert set(actual_slots)==set(range(4)), 'Provider allocates last free slots; restorer must admit those actual directory addresses'
assert all(f'{n:02X}' in layout['free_pages'] for n in range(0xc0,0xc4))
assert layout['free_pages'][0]=='08'
fixture=(OLD/'2609-PRIVATE-PROGRAM-RESTORE-RAM.bin').read_bytes()
assert t.sha(fixture)=='5dadab107c2663f6b75b8b2267b0ca480c3dcda854219b1635063cad68ff68a1'
assert len(fixture)==767 and binascii.crc_hqx(fixture,65535)==0
OUT.mkdir(parents=True); (OUT/'.gitignore').write_text('*\n')
(OUT/'SRAM-approved-original-131072.bin').write_bytes(data)
(OUT/'PRIVATE-PROGRAM-RESTORE-RAM.bin').write_bytes(fixture)
blocks=[0x40,0x80,0xc0,0x100]+list(range(0xc000,0xc400,64))
for a in blocks: (OUT/f'original-{a:04X}.bin').write_bytes(data[a:a+64])
fixtures={n:(OLD/f'PROGRAM-{n}-23.bin').read_bytes() for n in ('OK','UP')}
for n,b in fixtures.items(): (OUT/f'PROGRAM-{n}-23.bin').write_bytes(b)
plan=dict(schema=1,board='2512',port='COM4',usb_serial='A10MQFLCA',CPU='65C02',
    status='OWNER_REQUESTED_PROGRAM_STORE_RESTORE_RUN',
    authorization='Current PROGRAM Store/Restore/run on 2512; lets do these, then think about soak',
    source_preservation_report_sha256=t.sha((INSTALLED/'final-receipt.json').read_bytes()),
    source_bank_sha256=r['final_bank_sha256'], SRAM_sha256=t.sha(data),
    original_SRAM='SRAM-approved-original-131072.bin',directory_slots=[0,1,2,3],
    allowed_64_byte_writes=[f'{a:04X}' for a in blocks],temporary_byte_scope=1280,
    payload_range='C000-C3FF',AUTO_preview_only='0800',
    store_targets=['C000','C100','C200','C300'],
    retained_record_slots=[v['slot'] for v in layout['records']],
    unmodified_free_slots=[4,7], full_directory_refusal_in_scope=False,
    PROGRAM_format='SS1',WORKSPACE_start='10000',
    flash_writes=0,journal_writes=0,boot_setting_writes=0,WORKSPACE_writes=0,
    RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
    counts_unchanged=dict(C=53,D=33,E=28,F=24),sequence=1033,default_boot='B',
    driver_sha256=t.sha((ROOT/'tools/trial_2512_program_positive.py').read_bytes()),
    restorer=dict(filename='PRIVATE-PROGRAM-RESTORE-RAM.bin',sha256=t.sha(fixture),bytes=767),
    fixture_sha256={n:t.sha(b) for n,b in fixtures.items()},
    all_test_bytes_restore_required=True,full_SRAM_live_admission_required=True,
    final_context='B3>',other_boards_excluded=True)
plan['F_sha256']='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
t.save(OUT/'plan.json',plan)
print(json.dumps(plan,indent=2))
