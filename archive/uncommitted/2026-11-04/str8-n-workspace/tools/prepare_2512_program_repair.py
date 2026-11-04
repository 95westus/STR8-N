"""Restrict existing PB restorer data to the two actually changed free slots."""
import binascii
import json
import re
from pathlib import Path
import qualify_services_g4_2512_ram as t
BASE=t.ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'
FAILED=t.ROOT/'output/qualification/2512-PROGRAM-positive-trial-20261030-r1'
OUT=t.ROOT/'output/qualification/2512-PROGRAM-preserving-repair-20261030-r1'
assert not OUT.exists()
before=(BASE/'SRAM-approved-original-131072.bin').read_bytes()
observed=(FAILED/'SRAM-restored-131072.bin').read_bytes()
delta=[i for i,(a,b) in enumerate(zip(before,observed)) if a!=b]
assert len(delta)==91 and all(0x140<=i<0x180 or 0x200<=i<0x240 for i in delta)
fixture=bytearray((BASE/'PRIVATE-PROGRAM-RESTORE-RAM.bin').read_bytes())
symbols=(t.ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source/sram-bench.map').read_text()
sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',symbols,re.M)}
lo=sy['BENCH_ALLOW']-0x200; hi=sy['Q_IMAGE_CRC']-0x200
assert (lo,hi,len(fixture))==(725,765,767)
old=json.loads((BASE/'plan.json').read_text())
assert fixture[lo:hi]==b''.join(int(v,16).to_bytes(2,'little') for v in old['allowed_64_byte_writes'])
patched=bytearray(fixture)
patched[lo:hi]=b''.join(a.to_bytes(2,'little') for a in [0x140,0x200]*10)
patched[hi:hi+2]=binascii.crc_hqx(patched[:hi],65535).to_bytes(2,'big')
assert binascii.crc_hqx(patched,65535)==0 and patched[:lo]==fixture[:lo]
OUT.mkdir(parents=True);(OUT/'.gitignore').write_text('*\n')
(OUT/'PRIVATE-RESTORE-SLOTS-4-7-RAM.bin').write_bytes(patched)
for a in (0x140,0x200):
    (OUT/f'original-{a:04X}.bin').write_bytes(before[a:a+64])
    (OUT/f'observed-{a:04X}.bin').write_bytes(observed[a:a+64])
plan=dict(board='2512',purpose='Restore exact originals after host directory-allocation planning error',
    authority='Owner requested positive PROGRAM test with preservation; correcting our unintended temporary-slot changes',
    original_plan_sha256=t.sha((BASE/'plan.json').read_bytes()),
    failed_report_sha256=t.sha((FAILED/'report.json').read_bytes()),
    restoration_only_addresses=['0140','0200'],restoration_only_bytes=128,observed_remaining_differences=91,
    actual_Store_directory_slots=[7,4,3,2],original_assumed_slots=[0,1,2,3],
    initial_temporary_scope_met=False,total_trial_and_restoration_address_scope_bytes=1408,
    original_SRAM_sha256=t.sha(before),observed_SRAM_sha256=t.sha(observed),
    restorer_filename='PRIVATE-RESTORE-SLOTS-4-7-RAM.bin',restorer_sha256=t.sha(patched),
    original_restorer_sha256=t.sha(fixture),executable_instruction_bytes_unchanged=True,
    data_only_changes='40-byte private address allowlist now contains only0140/0200; resealed two-byte image CRC',
    firmware_builds=0,assembler_invocations=0,flash_writes=0,journal_writes=0,
    WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0)
t.save(OUT/'repair-plan.json',plan)
print(json.dumps(plan,indent=2))
