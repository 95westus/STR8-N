"""Forecast BOOT and CLOCK-metadata positives; no board access/build/simulation."""
import binascii,json,sys
from pathlib import Path
import install_startup_traditional_2512 as prior

t=prior.t;Q=prior.Q;ROOT=t.ROOT
sys.path.insert(0,str(t.REPO/'tools'))
from native_journal_room import valid_snapshot
from journal_rotation_plan import reserve

OUT=Q/'2512-BOOT-CLOCK-scope-20261101-r2'
PREF=Q/'2512-BOOT-CLOCK-preflight-20261101-r1'

def append_policy(bank3,changes,label):
    """JE_SPACE/SEAL/WRITE forecast with pending policy in the erase intent."""
    seq,off,raw=max((int.from_bytes(bank3[i+8:i+12],'little'),i,bank3[i:i+256])
                    for i in range(0x4000,0x6000,256) if valid_snapshot(bank3[i:i+256]))
    frame=bytearray(raw);image=bytearray(bank3);writes=[];erases=[]
    for index,value in changes.items():frame[index]=value
    def append(where,kind):
        assert image[where:where+256]==b'\xff'*256
        sequence=int.from_bytes(frame[8:12],'little')+1;frame[8:12]=sequence.to_bytes(4,'little')
        frame[30:32]=binascii.crc_hqx(frame[:30],65535).to_bytes(2,'little')
        frame[252:254]=binascii.crc_hqx(frame[:252],65535).to_bytes(2,'little');frame[255]=0
        assert valid_snapshot(frame);image[where:where+256]=frame
        writes.append(dict(page=f'{where+0x8000:04X}',sequence=sequence,kind=kind))
    sector=off&0xF000;peer=sector^0x1000;dest=off+256
    while dest<sector+0xF00 and image[dest:dest+256]!=b'\xff'*256:dest+=256
    if dest>=sector+0xF00:
        if image[peer:peer+4096]!=b'\xff'*4096:
            assert dest==sector+0xF00
            counter=28 if peer==0x4000 else 29;at=0x40+counter*3
            frame[at:at+3]=(int.from_bytes(frame[at:at+3],'little')+1).to_bytes(3,'little')
            append(dest,'peer-erase-intent-with-pending-policy')
            image[peer:peer+4096]=b'\xff'*4096;erases.append('B3:C' if peer==0x4000 else 'B3:D')
        dest=peer
    append(dest,'policy-append')
    return bytes(image),dict(command=label,journal_appends=writes,journal_sector_erases=erases)

def metadata_row(magic,sequence,payload):
    row=bytearray(b'\xff'*32);row[:4]=magic;row[4:8]=sequence.to_bytes(4,'little')
    row[8:8+len(payload)]=payload;row[28:30]=binascii.crc_hqx(row[:28],65535).to_bytes(2,'little');row[31]=0
    return bytes(row)

def run():
    pre=json.loads((PREF/'report.json').read_text())
    assert pre['passed'] and pre['owner_RAM_restored'] and pre['owner_ZP_restored'] and pre['COM4_released']
    assert pre['B0_9_blank'] and (PREF/'B0-9000-original.bin').read_bytes()==b'\xff'*4096
    marker=json.loads((Q/'device-operations/2512.json').read_text())
    assert marker['application_ram_restored'] and not marker['block_snapshot'] and not marker['physical_reset_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    old=(prior.OUT/'B3-after.bin').read_bytes()
    assert t.sha(old)==marker['current_physical_bank_sha256']['B3']
    assert old[0x1C00:0x2000]==(PREF/'B3-metadata-9C00.bin').read_bytes()
    assert old[0x1000:0x1004]==b'PJ\x06\x01'
    before=t.classify_journal(old);assert before['sequence']==1168 and before['valid_records']==27
    assert before['default']=='B' and before['enabled_mask']==15 and before['entries']==[8]*4
    assert old[0x4A0C]==10 and old[0x4A12:0x4A16]==(16).to_bytes(4,'little')
    frozen=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha(old[-4096:])==frozen['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in frozen['sources'].items())
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    state=old;operations=[]
    policies=[('BOOT OFF 1',{13:13}),('BOOT B 1 8000',{13:15,15:8}),
              ('BOOT DELAY B',{12:11}),('BOOT B 0 9000',{14:9}),
              ('BOOT B 0 8000',{14:8}),('BOOT DELAY A',{12:10})]
    for command,changes in policies:
        state,operation=append_policy(state,changes,command);operations.append(operation)
        (OUT/f'journal-after-{len(operations)}.bin').write_bytes(state[0x4000:0x6000])
    state,operation=reserve(state,1);operation['command']='B0:9 exact-FF cleanup erase';operations.append(operation)
    state,operation=reserve(state,25);operation['command']='B3:9 original-provider/metadata cleanup erase';operations.append(operation)
    after=t.classify_journal(state)
    assert (after['sequence'],after['valid_records'])==(1177,20)
    assert after['counts'][28:]==[57,38,37,24]
    assert after['counts'][1]==26 and after['counts'][25]==21
    latest=max((state[i:i+256] for i in range(0x4000,0x6000,256) if valid_snapshot(state[i:i+256])),key=lambda row:int.from_bytes(row[8:12],'little'))
    assert latest[7]==ord('B') and latest[12:30]==old[0x4A0C:0x4A1E]
    assert old[:0x4000]==state[:0x4000] and old[0x6000:]==state[0x6000:]
    retained=sum(valid_snapshot(old[i:i+256]) and old[i:i+256]==state[i:i+256] for i in range(0x4000,0x6000,256))
    assert retained==11
    metas=bytearray(old[0x1000:0x2000]);slots=[i for i in range(0xC00,0x1000,32) if metas[i:i+32]==b'\xff'*32]
    assert slots[:3]==[0xDC0,0xDE0,0xE00]
    assert not any(metas[i:i+4]==b'EI\x01\x00' and metas[i+31]==0 for i in range(0xC00,0x1000,32))
    battery=metas[0xCE0+32:0xCE0+64]  # BA seq2 at9D00
    assert battery[:4]==b'BA\x01\x00' and int.from_bytes(battery[4:8],'little')==2
    payload=bytearray(battery[8:15]);assert payload[2:5]==bytes((12,24,0));payload[2:4]=bytes((13,25))
    meta_records=[('ACCEPT EUI',metadata_row(b'EI\x01\x00',1,bytes.fromhex('54 10 EC B6 74 3C'))),
        ('OFFSET -05:00',metadata_row(b'TZ\x01\x00',8,(-300).to_bytes(2,'little',signed=True))),
        ('BATTERY LIMITS 13 25',metadata_row(b'BA\x01\x00',3,payload))]
    records=[]
    for offset,(command,row) in zip(slots,meta_records):
        metas[offset:offset+32]=row;records.append(dict(command=command,address=f'B3:{0x9000+offset:04X}',bytes=32,hex=row.hex(),sha256=t.sha(row)))
    fixture=bytes.fromhex('A9 47 8D FF 18 4C 67 7E');scratch=fixture+b'\xff'*(4096-len(fixture))
    (OUT/'B0-9000-fixture.bin').write_bytes(scratch);(OUT/'B0-9000-original.bin').write_bytes(b'\xff'*4096)
    (OUT/'B3-9000-original.bin').write_bytes(old[0x1000:0x2000]);(OUT/'B3-9000-trial-metadata.bin').write_bytes(metas)
    (OUT/'B3-original.bin').write_bytes(old);(OUT/'B3-expected-final.bin').write_bytes(state)
    (OUT/'boot-wear-history-original.bin').write_bytes(old[0x4000:0x6000])
    (OUT/'EEPROM-00-7F-original.bin').write_bytes((PREF/'EEPROM-00-7F-original.bin').read_bytes())
    (OUT/'boot9000.asm').write_text('''; Qualification-only opaque entry at B0:9000. IRQ masked, decimal clear.
; Golden Foundation public HOLD selects B3 and returns to active MON B.
        LDA #$47
        STA $18FF       ; marker in freshly escrowed owner RAM
        JMP $7E67       ; STR8V2_RAM_HOLD; no hardware reset
''')
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',port='COM4',
        preflight_receipt=str(PREF/'report.json'),preflight_sha256=t.sha((PREF/'report.json').read_bytes()),
        total_erases=3,erases=['B3:D native rotation','B0:9 cleanup','B3:9 metadata/provider restoration'],
        F_writes=0,MON_A_B_writes=0,C_erases=0,D_erases=1,boot_policy_appends=6,wear_reservations=2,peer_erase_intents=1,total_journal_appends=9,
        operations=operations,metadata_records=records,metadata_appends=3,metadata_byte_program_limit=96,
        fixture_program_bytes=8,fixture_entry='B0:9000',fixture_hex=fixture.hex(),fixture_marker='RAM18FF=47',fixture_return='public HOLD7E67 -> active MON B g10',
        current_physical_bank_sha256=marker['current_physical_bank_sha256'],B3_before_sha256=t.sha(old),B3_after_sha256=t.sha(state),
        sequence_before=1168,sequence_after=1177,records_before=27,records_after=20,
        old_rows_archived_on_host=27,old_D_rows_replaced_on_chip=16,old_C_rows_retained_exact=11,
        counts_before=before['counts'],counts_after=after['counts'],
        EEPROM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,SPI_data_writes=0,resets=0,power_cuts=0,firmware_builds=0,
        expected_metadata_after='Original full B3:9 sector restored exactly; unbound EUI, offset-06:00, battery12/24 and every14 original metadata rows retained',
        expected_EEPROM_after='All128 bytes exact, including3 committed outage events and sequence4 tombstone',
        expected_boot_after='Original B/g10 default, enabled mask0F, all entries8000 and stored delay0A; wear/history advances only',
        acceptance=['BOOT OFF disables1; RUN1 refuses; B1 re-enables original entry; DELAY9 refuses below minimum0A',
            'DELAYB andA commit exact legacy byte; fixed BASE1 countdown unchanged',
            'BOOT RUN0 executes8-byte flash fixture, writes marker and returns to MON B without reset',
            'CLOCK ACCEPT EUI writes verified real identity; repeat is no-op',
            'OFFSET-05 changes local display only; repeat is no-op; UTC/control/trim unchanged',
            'BATTERY LIMITS13/25 writes verified policy with existing installation date; no claim battery replaced',
            'Exact scratch/provider/metadata/EEPROM and fresh owner RAM/ZP restoration; final REC>,COM4 free; RTC resumes'],
        deferred=['real latched-SET/ACK needs isolated RAM device-fault fixtures or separately approved real event',
            'Actual changed-TRIM writer remains outside live scope to preserve ongoing calibration; no no-op claimed as write acceptance',
            'EEPROM clear/delete, battery replacement date, full app release/extracted-kit acceptance'],
        F_sha256=frozen['sha256'],excluded_boards=['2205','2604','2609'],published_download_changes=False,
        source_sha256={n:t.sha((t.REPO/n).read_bytes()) for n in ('monitors/native/board-tool.asm','monitors/native/clock.asm','src/core/config-engine.inc')})
    t.save(OUT/'plan.json',plan)
    document='''# 2512 BOOT/CLOCK positive scope

Review ready; not approved or executed. Read-only inventory passed and owner
RAM/ZP is restored at REC>, COM4 free. No new BIN or F build is needed.

## Proposed writes and restoration

Three erases total: one native B3:D rotation, B0:9 cleanup and B3:9 restoration.
Zero C erases, F writes, MON A/B writes, CPU resets or power cuts.

Program only8 bytes into freshly verified blank B0:9000: A9478DFF184C677E.
The opaque fixture writes47 to escrowed RAM18FF and returns through public
HOLD7E67 to the active MON B. It is a trial fixture, not a shipping app.

Use the installed FLASH BOOT commands: OFF1 (verify RUN1 refusal), B1/8000
to re-enable, DELAYB, B0/9000, RUN0/marker/HOLD return, B0/8000 and DELAYA.
Six policy appends restore every boot field, including B/g10 default.
The B0:9 fixture is then erased once and verified exactly FF again.

Native CLOCK: ACCEPT EUI54:10:EC:B6:74:3C, OFFSET-05:00, BATTERY LIMITS13/25.
These are three real32-byte metadata appends at B3:9DC0/9DE0/9E00; verify
each and idempotent EUI/OFFSET repeats. The battery installation date is not
changed or falsely recorded as a replacement. Current trim-12/control80,
running UTC and live PF latch/timestamps are untouched. The final B3:9 erase
restores its exact original full sector, including provider code and all14
old metadata rows. That restores the original unbound EUI,-06:00 offset and
12/24-month battery policy. Archive trial metadata on the host before cleanup.

The boot journal gets nine rows: six policy appends, two cleanup-erase wear
reservations and one D-erase intent. CB00-CE00 are seq1169-1172; CF00/1173
commits the pending restored B0 entry and D count before native rotation.
D000-D300 finish seq1174-1177. All27 original rows are archived on the host;
rotation replaces16 old D rows on chip and retains11 old C rows exactly.
Final20 valid rows; B0:9 count25->26, B3:9 count20->21, D37->38.
C57/E37/F24 stay unchanged. No implicit retries or additional erase allowance.

## Evidence limits and excluded writes

Frozen BASE1 intentionally has a fixed three-second chooser. BOOT DELAY
changes only the legacy stored byte (minimum0A hex, original0A; trial0B);
this trial proves storage/readback, not
an adjustable Foundation countdown. F stays golden.

The real PF latch is clear and EEPROM holds three real outage events plus a
sequence4 tombstone. Preserve all128 EEPROM bytes exactly. No SET, trim
change, ACK, EEPROM CLEAR/DELETE or manufactured physical power-fail event is
included. A no-event/no-op reply will not be reported as positive write
acceptance. Necessary isolated RAM fault cases for latched SET/ACK and trim
remain a separate step; the current live scope closes BOOT handoff and three
actual CLOCK metadata writers, not every CLOCK gate.

## Preservation and RTC coordination

Freshly escrow owner RAM0200-66FF and ZP00-DF before borrowing; restore/read
back exactly after tests. Admit live targets/history against pinned preimages.
Stop on a changed preimage or unexpected append/stage. No B0/B1 owner image
outside the exact restored B0:9 target changes. B2, F and MON A/B stay exact.
The real RTC time/control/trim/latch, all EEPROM history and SPI PROGRAM/
WORKSPACE remain unchanged. Preserve current name2512/saved EDU ON and final
boot/offset/battery/identity state. All original metadata/provider bytes are
restored; the only final flash changes are the reviewed C/D journal advances.

RTC collection owns the serial lease and due window. Pause only2512 while
borrowed; yield before the first write if collection is due. No collector
code, baseline, point or segment changes are required: this scope never sets
time or changes trim. Verify native TIME/current fields after cleanup and
release2512 for normal collection. Other boards and published downloads are
untouched. Finish REC>, owner RAM/ZP restored and COM4 released.

plan.json pins exact source, binary preimages, intermediate journal snapshots,
metadata rows, final journal/counters and eight-byte fixture. Any expanded
write/erase target or unresolved history conflict needs a new review.
'''
    (OUT/'review-document.md').write_text(document,encoding='utf-8',newline='\n')
    t.save(OUT/'review.json',dict(status='REVIEW_READY_NOT_APPROVED',hardware_access=False,
        plan_sha256=t.sha((OUT/'plan.json').read_bytes()),review_document_sha256=t.sha((OUT/'review-document.md').read_bytes())))
    print('REVIEW READY2512:3 erases;9 journal appends;3 metadata appends;seq1177;20 rows;0 F/RTC/EEPROM writes',flush=True)

if __name__=='__main__':run()
