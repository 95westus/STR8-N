"""Review exact retained-WDC-sector install/restore and two wear appends; no port."""
import binascii
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
from journal_rotation_plan import reserve

CAP=t.ROOT/'output/qualification/2609-AP02-readonly-20261030-r1'
OUT=t.ROOT/'output/qualification/2609-AP02-scope-20261030-r1'
assert not OUT.exists()
r=json.loads((CAP/'report.json').read_text())
assert r['passed'] and r['owner_RAM_restored'] and r['COM8_released']
banks=[(CAP/f'before-pass1-B{n}.bin').read_bytes() for n in range(4)]
for n,body in enumerate(banks):
    for name in (f'before-pass2-B{n}.bin',f'after-pass1-B{n}.bin',f'after-pass2-B{n}.bin'):
        assert body==(CAP/name).read_bytes()
assert list(map(t.sha,banks))==r['bank_sha256']
old=t.classify_journal(banks[3]); assert old['sequence']==1031 and old['valid_records']==17
original=banks[0][4096:8192]
assert original!=b'\xff'*4096 and banks[0][:3]==b'WDC'
source=t.REPO/'apps/candidates/appdemo-ap02-g1'
m=json.loads((source/'manifest.json').read_text()); image=(source/m['image']['filename']).read_bytes()
assert t.sha(image)==m['image']['sha256'] and len(image)==120
assert image[:8]==b'AP\x02\x20PR05' and image[15]==2
assert binascii.crc_hqx(image[:28],65535)==int.from_bytes(image[28:30],'little')
assert binascii.crc_hqx(image[32:],65535)==int.from_bytes(image[30:32],'little')
body=image[32:]; header=bytearray(image[:32]); header[15]=0x16
header[28:30]=binascii.crc_hqx(header[:28],65535).to_bytes(2,'little')
assert header[28:30]!=b'\xff\xff' and header[30:32]!=b'\xff\xff'
valid=(bytes(header)+body).ljust(4096,b'\xff')
unsealed=bytearray(valid); unsealed[28:32]=b'\xff'*4; unsealed=bytes(unsealed)
header_only=bytearray(valid); header_only[30:32]=b'\xff'*2; header_only=bytes(header_only)
assert valid[32:120]==image[32:] and all(a&b==b for a,b in zip(unsealed,header_only))
assert all(a&b==b for a,b in zip(header_only,valid))
after_install,j1=reserve(banks[3],1); after_restore,j2=reserve(after_install,1)
assert j1['journal_sector_erases']==j2['journal_sector_erases']==[]
assert j1['journal_appends']==[dict(page='D100',sequence=1032,kind='target-erase-reservation')]
assert j2['journal_appends']==[dict(page='D200',sequence=1033,kind='target-erase-reservation')]
final=t.classify_journal(after_restore)
assert final['counts'][1]==old['counts'][1]+2==4
assert final['sequence']==1033 and final['valid_records']==19
assert final['default']==old['default']=='S'
for key in ('entries','enabled_mask','unknown_mask'): assert final[key]==old[key]
assert final['counts'][28:32]==old['counts'][28:32]==[78,48,45,31]
OUT.mkdir(parents=True); (OUT/'.gitignore').write_text('*\n')
for name,data in [('original-sector.bin',original),('fixture-unsealed.bin',unsealed),
                  ('fixture-header-only.bin',header_only),('fixture-valid.bin',valid),
                  ('original-WDC-B0-32768.bin',banks[0]),('journal-after-install-B3.bin',after_install),
                  ('journal-after-restore-B3.bin',after_restore)]: (OUT/name).write_bytes(data)
for name,sector,journal in [('unsealed',unsealed,after_install),('header-only',header_only,after_install),
                            ('valid',valid,after_install),('restored',original,after_restore)]:
    expected=list(banks); b0=bytearray(banks[0]); b0[4096:8192]=sector; expected[0]=bytes(b0); expected[3]=journal
    for n,data in enumerate(expected): (OUT/f'{name}-expected-B{n}.bin').write_bytes(data)
plan=dict(schema=1,status='PREPARED_AWAITING_TARGET_APPROVAL',board='2609',port='COM8',
    usb_serial='A10MPQXCA',CPU='65C816 emulation',target='B0:9000',
    source_capture=str(CAP),source_report_sha256=t.sha((CAP/'report.json').read_bytes()),
    source_bank_sha256=list(map(t.sha,banks)),original_sector_sha256=t.sha(original),
    target_is_erased=False,target_contains_retained_WDC=True,WDC_full_bank_sha256=t.sha(banks[0]),
    source_APP_image_sha256=t.sha(image),unchanged_application_body_sha256=t.sha(body),
    CPU_header_only_change='02 -> 16; recalculate header CRC; existing 88-byte body unchanged',
    fixture_SHA256={n:t.sha(v) for n,v in [('unsealed',unsealed),('header-only',header_only),('valid',valid)]},
    total_sector_erases=2,sector_erases={'B0:9':2},native_checksum_1_to_0_cells=['901C','901D','901E','901F'],
    journal_appends=[*j1['journal_appends'],*j2['journal_appends']],C_D_erases=0,F_writes=0,MON_A_B_E_writes=0,
    all_17_original_journal_records_retained=True,final_journal=final,
    expected_final_bank_sha256=[t.sha((OUT/f'restored-expected-B{n}.bin').read_bytes()) for n in range(4)],
    SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
    resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
    saved_default='S',saved_enabled_mask=0,owner_RAM_ZP_fresh_restore_required=True,
    final_context='REC>',F_sha256=t.sha(banks[3][-4096:]),
    tests=['header-CRC-refusal','payload-CRC-refusal','valid-APPS-inventory',
           'APP-APPDEMO-execute-from-flash','help-redisplay','bare-Q-public-HOLD-to-MON-B',
           'native-owner-RAM-ZP-unchanged-after-app','exact-original-WDC-bank-restoration',
           'all-final-banks-and-history','RTC-admission-advance-same-instrument'],
    RTC_admission_update='Advance validation for new D100/D200 rows; retain profile, sampler bytes, settings, baselines and schedule; read-only requalification',
    other_boards_excluded=True,published_downloads_changed=False)
t.save(OUT/'plan.json',plan)
print(json.dumps(plan,indent=2)); print('Plan SHA256',t.sha((OUT/'plan.json').read_bytes()))
