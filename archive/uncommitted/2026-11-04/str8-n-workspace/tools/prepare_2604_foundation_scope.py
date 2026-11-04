"""Prepare exact 2604 WC->SNBT/full-profile review. No port, build or simulation."""
import binascii,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'release/str8nf-v0.2.0'
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools'),str(REPO/'migration-host')]
from inspect_2604_rc1g34_capture import ARCHIVE,CAPTURE,inspect
from installer.engine.runtime import record,sha
from nf_migrate import snapshot,valid_snapshot,classify_journal
from journal_rotation_plan import reserve
from prepare_boot_clock_scope_2512 import append_policy
from inventory_boards_readonly import durable

OUT=ROOT/'output/qualification/2604-foundation-rollout-scope-20261102-r1'
KIT=ROOT/'BUILD/unified-g10-candidate3-20261101-r3/fresh-extraction/STR8N-MON-g00000010-candidate3'
F_HASH='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'


def seal(row):
    row=bytearray(row)
    row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little')
    row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little')
    assert valid_snapshot(row)
    return bytes(row)


def run():
    original=inspect(CAPTURE)
    banks=[(CAPTURE/f'b{n}.bin').read_bytes() for n in range(4)]
    cfg=bytes.fromhex(original['config_hex']);seq=original['sequence']
    # Active application autostart or saved EDU OFF requires a separate mapping.
    assert not original['config_decoded']['application_autostart_enabled']
    assert cfg[13]==0 and original['config_decoded']['preferred_monitor']=='B'
    assert seq<0xffffff00
    freeze=json.loads((REPO/'F_FREEZE.json').read_text())
    frozen=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(frozen)==freeze['sha256']==F_HASH
    assert all(sha((REPO/name).read_bytes())==digest for name,digest in freeze['sources'].items())
    catalog=json.loads((KIT/'NATIVE-COMPONENTS.json').read_text())
    assert catalog['F_sha256']==F_HASH and catalog['MON']=='0.1.0-dev g00000010'
    desired={}
    for item in catalog['targets']:
        bank,address=item['bank'],int(item['address'],16)
        body=(KIT/item['file']).read_bytes();assert sha(body)==item['sha256']
        if item.get('preserve_RTC_metadata'):
            assert (bank,address,len(body))==(3,0x9000,3072)
            body+=banks[3][0x1c00:0x2000]
        assert len(body)==4096 and (bank,address) not in desired
        desired[bank,address]=(body,'qualified Candidate3 native profile')
    e=(ROOT/'BUILD/devtools-AP02-g1-r2/SERVICES-E.bin').read_bytes()
    assert sha(e)=='9cc566e24c3ac9b0092617aaf3c4f2c0a5e004e52d8479cf70bfce4fa2519fd3'
    desired[3,0xe000]=(e,'qualified R ASM/DBG services')
    for name,folder,digest,address in (
        ('ASM','asm-flash-source-g2-r4','ac75d79c8fe85b5949663d42f9600b12b1aae45b8c1b9f81a133d75f5dd98c1a',0xa000),
        ('DBG','dbg-base1-g2-r1','b42891b51c7f7f8acc53e2980f7bb13df3591151cf4f1a4b1c2af2fa8910c818',0xc000)):
        body=(ROOT/'BUILD'/folder/f'{name}-FLASH.bin').read_bytes()
        assert len(body)==8192 and sha(body)==digest and body[15]==2
        assert binascii.crc_hqx(body[:28],65535)==int.from_bytes(body[28:30],'little')
        for off in (0,4096):desired[0,address+off]=(body[off:off+4096],name+' g2 CPU02 AP/02')
    assert len(desired)==23
    # First reserve all three conversion erases in the old, still readable WC.
    retained=int(original['latest_address'].split(':')[1],16)&0xf000
    peer=retained^0x1000
    assert retained in (0xc000,0xd000)
    free=[a for a in range(retained,retained+0xf80,128)
          if banks[3][a-0x8000:a-0x8000+128]==b'\xff'*128]
    assert free,'No ordinary WC reservation slot; review a different path'
    conversion_counts=original['counts'].copy()
    for address in (peer,0xf000,retained):
        i=24+(address-0x8000)//4096;assert conversion_counts[i]<0xffffff
        conversion_counts[i]+=1
    reserve_row=record(cfg,conversion_counts,seq+1)
    state=list(map(bytearray,banks))
    state[3][free[0]-0x8000:free[0]-0x8000+128]=reserve_row
    conversion=[]
    for address,sequence in ((peer,seq+2),(0xf000,None),(retained,seq+3)):
        if sequence is None:body=frozen;commit=None
        else:
            root=bytearray(snapshot(conversion_counts,sequence))
            root[18:22]=(16).to_bytes(4,'little')
            root[32:48]=cfg  # Explicit archival import; no new execution inferred.
            body=seal(root)+b'\xff'*3840;commit=address+255
        off=address-0x8000
        conversion.append(dict(bank=3,address=f'{address:04X}',commit_address=commit,
            before_sha256=sha(state[3][off:off+4096]),sha256=sha(body),body=body))
        state[3][off:off+4096]=body
    assert classify_journal(state[3])['kind']=='valid-snbt'
    # Each actual native image replacement must use the native reservation path.
    # Its peer rotation is counted too, even though both C/D were just provisioned.
    order=[(3,0xa000),(3,0xb000)]+sorted(k for k in desired if k not in ((3,0xa000),(3,0xb000)))
    targets=[];operations=[];skipped=[]
    for bank,address in order:
        body,label=desired[bank,address];off=address-0x8000
        before=bytes(state[bank][off:off+4096])
        if before==body:skipped.append(f'B{bank}:{address:04X}');continue
        journal,op=reserve(bytes(state[3]),bank*8+(address-0x8000)//4096)
        state[3]=bytearray(journal);operations.append(op)
        state[bank][off:off+4096]=body
        targets.append(dict(bank=bank,address=f'{address:04X}',label=label,
            file=f'targets/B{bank}-{address:04X}.bin',sha256=sha(body),before_sha256=sha(before)))
    state[3],binding=append_policy(bytes(state[3]),{7:ord('B'),**{18+i:v for i,v in enumerate((16).to_bytes(4,'little'))}},'restore B default, bind replacement MON g10')
    operations.append(binding)
    final=classify_journal(state[3]);assert final['kind']=='valid-snbt' and final['default']=='B'
    rotations=[x for op in operations for x in op['journal_sector_erases']]
    assert all(bytes(state[n][a:a+4096])==banks[n][a:a+4096] for n,a in
               [(0,x) for x in (0,4096,24576,28672)]+[(1,24576),(1,28672)])
    assert bytes(state[3][0x1c00:0x2000])==banks[3][0x1c00:0x2000]
    assert bytes(state[3][-4096:])==frozen
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'targets').mkdir()
    def put(name,body):durable(OUT/name,body)
    for n,body in enumerate(banks):put(f'B{n}-original.bin',body)
    for n,body in enumerate(state):put(f'B{n}-expected.bin',bytes(body))
    for item in targets:put(item['file'],desired[item['bank'],int(item['address'],16)][0])
    put('legacy-reservation-128.bin',reserve_row)
    put('legacy-CD-original-8192.bin',banks[3][0x4000:0x6000])
    for n,item in enumerate(conversion):
        put(f'conversion-{n}-B3-{item["address"]}.bin',item.pop('body'))
        item['file']=f'conversion-{n}-B3-{item["address"]}.bin'
    plan=dict(board='2604',USB_serial='A10MQGVHA',port='COM5',status='REVIEW_READY_NOT_APPROVED_OR_EXECUTABLE',
        permanent_archive=str(ARCHIVE),source_inspection=original,conversion=conversion,
        legacy_reservation_address=f'{free[0]:04X}',legacy_reservation_sequence=seq+1,
        conversion_erases=3,image_erases=len(targets),native_journal_rotations=rotations,
        total_erases=3+len(targets)+len(rotations),targets=targets,identical_skipped=skipped,
        native_operations=operations,native_appends=sum(len(x['journal_appends']) for x in operations),
        journal_before=original,journal_after=final,F_replacements=1,F_image_changed_or_rebuilt=False,
        original_WC_records_archived=len(original['original_records']),original_WC_records_retained_on_chip=0,
        boot_choice='B retained; g0034 binding becomes replacement MON g00000010; S only during migration/install',
        legacy_disabled_autostart='Original 16-byte config retained in SNBT bytes32-47; no bank automatically enabled',
        metadata='All B3:9C00-9FFF bytes exact; board name/offset/battery/EUI history retained',
        source_F_sha256=original['source_F_sha256'],target_F_sha256=F_HASH,
        expected_bank_sha256={f'B{n}':sha(b) for n,b in enumerate(state)},
        preservation=['Permanent full-chip/image/raw journal archive','B0:8/9/E/F and B1:E/F exact on chip',
          'RTC time/trim/control/power-fail history and EEPROM','all SPI PROGRAM/WORKSPACE bytes',
          'fresh owner RAM0200-66FF/ZP00-DF/provider cache6B00-77FF/hooks7E00-7E8F',
          'all32 counters carried forward as tracked lower bounds; prior/direct history unknown'],
        physical_resets=2,power_cuts=0,SPI_writes=0,RTC_setting_writes=0,automatic_retries=0,
        new_firmware_builds=0,CPU_simulations=0,other_boards=[],published_download_changes=0,
        admission_pending=['Attach legacy S19/G live proof and owner-restoration closeout',
          'Attach static review of unchanged engine and WC/SNBT conversion tables',
          'Exact owner approval of this conversion/image/history replacement scope',
          'Fresh re-admission after RTC-priority acquisition; versioned2604 RTC profile/readmission'],
        installed_checks=['Traditional MON A/B startup/VERSION/TIME including trim','R CLOCK/MAINT/FLASH and APPS',
          'EDU, SRAM/WORK read-only; STORE/TABLE/RESTORE/BATCH/loader smoke tests in RAM',
          'ASM/DBG CPU02 installed checks without new persistent source fixtures',
          'all-bank readback and fresh owner-memory restoration; RTC readmission'])
    put('plan.json',(json.dumps(plan,indent=2)+'\n').encode())
    rows='\n'.join(f'| B{x["bank"]}:{x["address"]} | {x["label"]} |' for x in targets)
    text=f'''# 2604 Foundation/full-tools rollout: exact draft scope

November 2, 2026. REVIEW READY; NO FLASHING AUTHORIZED BY THIS DOCUMENT.
The owner's “continue, approved” covers continued preparation. The concrete
legacy C/D format conversion and on-chip history replacement below still
require a decision. A separately serialized review-only installer must pass
its static checks before execution can be authorized; no live flash driver
is created by this preparer.

Permanent, untracked original: {ARCHIVE}
Fresh four-bank captures independently match, owner RAM/ZP/cache/hooks are
unchanged, and COM5 is released. Actual rc1 g0034 F: {original['source_F_sha256']}.

## Writes and accounting

**{plan['total_erases']} erases total:** three conversion erases, {len(targets)} image
replacements, and {len(rotations)} native rotation ({', '.join(rotations) or 'none'}).
No power cuts, automatic retries, SPI-data or RTC-setting writes. No access
to 2205,2512 or2609. No build or changes to published files.

First append WC seq{seq+1} at B3:{free[0]:04X}, reserving both conversion journal
erases and the one F replacement in the old format. Then replace B3:{peer:04X}
with committed SNBT/S, replace legacy F with the exact frozen4096-byte
BASE1/PR05 binary, and replace B3:{retained:04X} with the newer SNBT/S root.
The standalone engine must verify source/preimage and payload hashes and
commit each journal last. It must not depend on either old or new ROM code.
RESET into S/recovery before native image installation.

All {len(original['original_records'])} original WC records and every original image remain in the
permanent host archive; **zero WC rows remain on chip after conversion**.
All32 maximum historical tracked counts survive. Prior/direct lifetime stays
unknown. Each subsequent image erase has a native SNBT reservation; the
forecast also includes the native peer rotation. No claim that history is
retained on chip in its old format is made.

Final sequence {final['sequence']}, {final['valid_records']} valid SNBT rows.
Final C/D/E/F counters: {final['counts'][28:]}.
Saved monitor remains B, bound to replacement g10. S is temporary. Original
disabled application-autostart config is retained verbatim in SNBT32-47;
bank mask stays00, entries8000, no implicit autostart inferred. Legacy's
application delay and Foundation's fixed chooser window are separate.

## Image targets

| Sector | Accepted component |
|---|---|
{rows}

Original contents of these sectors are preserved on the host. B0:8/9/E/F
and B1:E/F stay exact on chip. Retained older app images are not automatically
qualified against the new ABI. B3:9C00-9FFF metadata stays byte-for-byte,
including name/offset/battery/EUI history. RTC time/trim/PF/EEPROM and every
SPI byte stay unchanged. No FORMAT, reclaim, clock SET/TRIM/ACK, or positive
persistent source-write fixture is included.

F is not thawed: one legacy-to-Foundation replacement with SHA256 {F_HASH}.
Afterward F stays golden, including all utility/tool operations. The existing
public b15/SNBT upgrader continues to refuse this WC/rc1 source.

## Required admission and acceptance

Prove legacy load-only S19/readback/explicit-G return in RAM before flashing.
Independently inspect the bounded conversion plan/engine. Acquire the shared
RTC-priority lease and freshly verify images/settings; abort on mismatch.
Capture fresh owner RAM/ZP/full provider cache/hooks immediately before
borrowing them; the permanent copy alone does not replace fresh escrow.

Two physical CPU resets are budgeted: conversion recovery and final saved-B
startup. No power cuts. Installed checks cover MON A/B, CLOCK/MAINT/FLASH,
APPS, EDU, SRAM/WORK and returning storage/BATCH/loader/ASM/DBG paths using
RAM fixtures. Extra persistent write tests require their own target review.
Read back all banks and restored owner memory, then use a versioned2604 RTC
profile for readmission with unchanged time/trim/history and LED policy.

This is a host forecast, not a claim of live migration qualification. Do not
execute a generic WDC migration or bypass the public F guard to apply it.
'''
    put('review-document.md',text.encode())
    print(json.dumps({k:plan[k] for k in ('status','total_erases','image_erases','native_journal_rotations','native_appends','journal_after')},indent=2))


if __name__=='__main__':run()
