"""Seal the2512 storage/AUTO/large-return review; no port or write driver."""
import json,sys
from pathlib import Path
import install_2512_native_utilities as d
t=d.t;ROOT=t.ROOT;Q=ROOT/'output/qualification'
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot


def run():
    build=ROOT/'BUILD/storage-installed-auto-r2';mf=json.loads((build/'manifest.json').read_text())
    assert mf['EDU_reader_and_shared_help_exact'] and mf['STATUS_details_exact'] and not mf['F_rebuilt']
    proofs=[Q/'2512-storage-installed-AUTO-RAM-20261101-r1/report.json',Q/'2512-storage-loader-RAM-20261101-r1/report.json']
    for path in proofs:
        r=json.loads(path.read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    oldbuild=ROOT/'BUILD/storage-installed-auto-r1'
    for name in ('FLASH-RECORD-6B00.bin','FLASH-GATE-7300.bin','WB2-gE-4800.bin'):
        assert (build/name).read_bytes()==(oldbuild/name).read_bytes(),'Reuse accepted RAM-path evidence only for identical bytes'
    marker=json.loads((Q/'device-operations/2512.json').read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
    assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    old={0:(Q/'NAMED-EDU-2512-scope-20261101-r1/B0-original.bin').read_bytes()}
    old[1]=bytearray((Q/'NAMED-EDU-2512-scope-20261101-r1/B1-original.bin').read_bytes())
    old[1][:0x3000]=(ROOT/'BUILD/named-edu-g3-r8/BANK-MAINT-EDU-flash.bin').read_bytes()
    old[1][0x3000:0x6000]=(ROOT/'BUILD/named-edu-g3-r8/SRAM-WORK-X-flash.bin').read_bytes();old[1]=bytes(old[1])
    for bank in (2,3):old[bank]=(Q/f'2512-TIME-PREP-cold-installed-20261101-r1/B{bank}-after.bin').read_bytes()
    assert all(t.sha(body)==marker['current_physical_bank_sha256'][f'B{bank}'] for bank,body in old.items())
    assert old[0][0x1000:0x2000]==b'\xff'*4096 and old[0][0x2000:0x3000]!=b'\xff'*4096
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    out=Q/'2512-storage-BATCH-AUTO-scope-20261101-r1';out.mkdir(exist_ok=False);(out/'.gitignore').write_text('*\n')
    images={bank:(build/f'B{bank}-candidate.bin').read_bytes() for bank in (1,2,3)}
    for bank,body in images.items():assert t.sha(body)==mf['artifacts'][f'B{bank}-candidate.bin']['sha256']
    order=[(3,0x80),(1,0xA0),(1,0xB0),(1,0xC0),(1,0xD0),(2,0x80),(2,0x90),(2,0xE0),(2,0xF0),(3,0xE0)]
    state=old[3];targets=[];ops=[]
    for bank,page in order:
        off=(page-0x80)*256;body=images[bank][off:off+4096];before=old[bank][off:off+4096];assert body!=before
        filename=f'B{bank}-{page:02X}-target.bin';(out/filename).write_bytes(body);(out/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=filename,sha256=t.sha(body),before_sha256=t.sha(before)))
        state,op=reserve(state,bank*8+(page-0x80)//16);ops.append(op)
        if bank==3:b=bytearray(state);b[off:off+4096]=body;state=bytes(b)
    # A must first become blank;9 is already blank. Both original sectors are
    # restored after AUTO tests. No setup erase of9 and no interrupted writes.
    fixtures=[]
    for page,phase in ((0xA0,'blank-occupied-A'),(0x90,'restore-blank-9'),(0xA0,'restore-original-A')):
        state,op=reserve(state,(page-0x80)//16);ops.append(op);fixtures.append(dict(bank=0,page=page,phase=phase))
    before=t.classify_journal(old[3]);after=t.classify_journal(state)
    erases=[x for op in ops for x in op['journal_sector_erases']];assert erases==['B3:C']
    rows=[off for off in range(0x4000,0x6000,256) if valid_snapshot(old[3][off:off+256])]
    replaced=[off for off in rows if old[3][off:off+256]!=state[off:off+256]]
    assert len(rows)==25 and len(replaced)==16 and all(0x4000<=off<0x5000 for off in replaced)
    assert after['sequence']==1164 and after['valid_records']==23 and after['counts'][28:]==[57,37,37,24]
    for key in ('default','enabled_mask','entries','unknown_mask'):assert after[key]==before[key]
    assert state[0x1C00:0x2000]==old[3][0x1C00:0x2000] and state[-4096:]==old[3][-4096:]
    assert state[0xE90:0xFFE]==old[3][0xE90:0xFFE]
    for bank,body in old.items():(out/f'B{bank}-original.bin').write_bytes(body)
    (out/'B3-final-predicted.bin').write_bytes(state);(out/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
    rest=ROOT/'BUILD/storage-large-restorer-r1';rm=json.loads((rest/'manifest.json').read_text())
    rb=(rest/rm['filename']).read_bytes();assert t.sha(rb)==rm['sha256'] and rm['temporary_bytes']==8256
    (out/rm['filename']).write_bytes(rb)
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',port='COM4',total_erases=14,image_erases=10,
        scratch_erases=3,journal_erases=1,journal_sector_erases=erases,targets=targets,fixture_operations=fixtures,
        operations=ops,journal_appends=sum(len(op['journal_appends']) for op in ops),sequence_before=1150,sequence_after=1164,
        valid_records_before=25,valid_records_after=23,old_rows_archived=25,old_rows_retained_on_chip=9,
        old_record_pages_replaced=[f'{off+0x8000:04X}' for off in replaced],counts_before=before['counts'],counts_after=after['counts'],
        F_writes=0,F_rebuilt=False,F_sha256=f['sha256'],MON_A_B_writes=0,boot_policy_changes=0,metadata_appends=0,
        physical_resets=0,power_cuts=0,RTC_setting_writes=0,PF_ACK=0,WORKSPACE_writes=0,
        SPI_temporary=dict(slot=4,directory_start='00140',directory_end='0017F',payload_start='09800',payload_end='0B7FF',bytes=8256,
            admission='Fresh directory/header/payload capture; slot4 and all32 pages free, LG4 absent; refuse any changed allocation; no format/reclaim/resize',
            restorer_sha256=rm['sha256'],restoration='Exact8256 preimage bytes and retained directory; never WORKSPACE'),
        AUTO_trial='AREA0 9000-AFFF;6400-byte Store AUTO at9000, tail append atA918 despite FF payload, Table and load-only Restore; original B0:9/A restored exactly',
        large_BATCh_trial='8KiB BT1/2 program4700-66FF in PROGRAM at9800; RESTORE P LG4;D18FF; public HOLD returns and queue continues; fixture removed by exact restoration',
        RAM_proofs=[dict(path=str(path),sha256=t.sha(path.read_bytes())) for path in proofs],build_manifest_sha256=t.sha((build/'manifest.json').read_bytes()),
        physical_bank_sha256=marker['current_physical_bank_sha256'],preserve_owner_RAM='Fresh0200-66FF/ZP00-DF escrow and exact readback restoration',
        fresh_live_preimages_required=True,RTC_priority=True,final_prompt='REC>',other_boards=['2205','2604','2609'],published_download_changes=False)
    t.save(out/'plan.json',plan)
    text='''#2512 installed storage BATCH, large AUTO and large returning BATCH

Review ready; **not approved**. November1,2026. Only2512/COM4 is in scope.

## Exact erase and journal allowance

**14 erases total:** ten permanent utility replacements, one native B3:C
journal rotation, and three temporary B0:9/A fixture/restoration erases.

| Role | Target sectors |
|---|---|
| Checked native loader; old storage refused under BATCH | B3:8 |
| Reused dense-S19 library, high AUTO worker and gate | B1:A |
| RAM-qualified SRAM/WORK g4, unchanged STORE helper | B1:B/C/D |
| WB gE with manager BATCH and saved AREA | B2:8/9 |
| Updated dense-library fragment addresses and component seal | B2:E/F |
| Dispatcher with current WB/transfer capability pins | B3:E |

**B3:F has zero writes.** B2:F contains utility/status data; it is distinct
from golden Foundation in B3:F. MON A/B are untouched, remain gF, and saved
default B/gF is unchanged. Saved EDU, board name/offset, boot enables/entries/
delay/preference, battery metadata and RTC time/trim/PF/history stay unchanged.

The journal has25 valid old records, seq1150. All25 raw records are archived
on the host. Native rotation replaces16 old C-sector records on chip; nine
old D records remain exact. Every latest boot field and wear count is carried
forward. Fourteen new rows include13 target-erase reservations and one peer-
erase intent. Expected finish: seq1164,23 valid rows; C/D/E/F counts57/37/37/24.
No D erase, manual journal rewrite, generation binding or metadata append.

## Temporary positive tests

**B0:A is occupied.** Its complete original4K is archived and restored.
B0:9 is verified blank. One A erase prepares a blank9000-AFFF AREA; after the
AUTO tests, one erase each restores9 to FF and A to its exact original image.
These are the three fixture erases; there is no additional9 setup erase.
The tests use a6400-byte source spanning4E00-66FF, verify AUTO starts at9000,
then verify a later append starts atA918 rather than inside FF payload. TABLE,
source preservation, data readback and load-only RESTORE are checked. No SR01
payload-CRC claim is added.

The separate large-return test temporarily uses PROGRAM slot4 at SPI00140-
0017F and32 payload pages09800-0B7FF: **8256 writable SPI bytes**. Capture fresh
preimages first; verify all pages are unallocated, slot4 is the allocator's
free slot and LG4 is absent. Abort if admission differs; never pick another
target or format/reclaim/resize. Store an8KiB BT1/2 return program at4700-66FF,
verify its record and payload CRC, run it through BATCH, and verify public HOLD
returns to the monitor and the following command executes. Restore all8256
bytes and the retained directory exactly afterward. No WORKSPACE writes.

## Preservation and stop conditions

Fresh live flash preimages must match the reviewed targets before any write.
Utility images outside the ten listed replacements remain exact; the previous
utility sectors are archived on the host. B0 fixtures are restored byte for
byte. The accepted EDU reader/shared help in8E90-8FFD and STATUS/RTC details in
B2:FA50-FFF9 remain exact. The652-byte loader fits before the EDU reader;
only that component required a corrective rebuild, while other newly linked
components were reused. The12853-byte SRAM/WORK body was not rebuilt.

Owner RAM0200-66FF and ZP00-DF receive fresh escrow and exact restoration with
readback. No resets or power cuts; no RTC setting/history writes, no other
board access, no published-download changes. Stop for unexpected state or
failed verification, keep restoration markers active, and do not spend a new
erase allowance on an automatic retry. RTC collection retains serial priority;
finish any dirty-fixture restoration before releasing its lease.

RAM preparation already passed19 AREA/overlap/carry cases, full AUTO refusal
and live-NO preview, saved AREA/Q, safe old-loader refusal and queue stop, and
the compacted loader's real CRC/capability refusal path. Owner RAM was restored
after both trials. Positive installed decoding, flash writes and large-return
PROGRAM execution are still pending this approval. Success ends at REC> with
COM4 released.
'''
    (out/'review-document.md').write_text(text.replace('#2512','# 2512',1))
    review=dict(plan_sha256=t.sha((out/'plan.json').read_bytes()),review_document_sha256=t.sha((out/'review-document.md').read_bytes()))
    t.save(out/'review.json',review)
    print(json.dumps({k:plan[k] for k in ('status','total_erases','journal_sector_erases','journal_appends','sequence_after','valid_records_after','old_record_pages_replaced')},indent=2))


if __name__=='__main__':run()
