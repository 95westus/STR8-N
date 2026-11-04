"""Exact Candidate3 upgrade review for2609; no port, firmware build or CPU model."""
import importlib.util,json
from pathlib import Path
import install_named_edu_2512 as ins
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
from prepare_boot_clock_scope_2512 import append_policy
t=ins.t;Q=ins.Q;ROOT=t.ROOT
OUT=Q/'2609-candidate3-scope-20261102-r1'
KIT=ROOT/'BUILD/unified-g10-candidate3-20261101-r3/fresh-extraction/STR8N-MON-g00000010-candidate3'

def run():
    marker=json.loads((Q/'device-operations/2609.json').read_text())
    assert not marker['RTC_LED_owner_hold'] and not marker['RTC_collection_pending_monitor_recovery']
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    recovery=Path(marker['last_RTC_LED_recovery']);proof=json.loads(recovery.read_text())
    assert proof['passed'] and proof['owner_RAM_restored'] and proof['owner_ZP_restored'] and proof['port_released']
    mf=json.loads((KIT/'CANDIDATE-MANIFEST.json').read_text())
    for name,info in mf['files'].items():assert t.sha((KIT/name).read_bytes())==info['sha256'],name
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((KIT/'F.bin').read_bytes())==f['sha256']==marker['current_F_sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    sources={1:Q/'2609-native-storage-installed-20261101-r1/B1-after.bin',
      2:Q/'2609-STATUS-literals-repair-20261101-r1/B2-target.bin',
      3:Q/'2609-native-storage-installed-20261101-r1/B3-after.bin'}
    old={b:p.read_bytes() for b,p in sources.items()}
    assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    for b,v in old.items():(OUT/f'B{b}-original.bin').write_bytes(v)
    (OUT/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
    spec=importlib.util.spec_from_file_location('candidate3_prepare',KIT/'tools/nf_native_images.py')
    prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
    prepared=prep.prepare(KIT,sources[3],OUT/'prepared',sources[2],sources[1])
    order=[(3,0xA000)]+[(1,a) for a in range(0x8000,0xE000,0x1000)]+[(2,a) for a in range(0x8000,0x10000,0x1000)]+[(3,a) for a in (0x8000,0x9000,0xE000,0xB000)]
    lookup={(x['bank'],int(x['address'],16)):x for x in prepared['targets']}
    state=old[3];after={b:bytearray(v) for b,v in old.items()};operations=[];targets=[];skipped=[]
    for bank,address in order:
      item=lookup[(bank,address)];off=address-0x8000;body=(OUT/'prepared'/item['image']).read_bytes()
      if body==old[bank][off:off+4096]:skipped.append(f'B{bank}:{address:04X}');continue
      state,op=reserve(state,bank*8+(address-0x8000)//4096);operations.append(op)
      targets.append(dict(bank=bank,address=f'{address:04X}',file='prepared/'+item['image'],sha256=t.sha(body),before_sha256=t.sha(old[bank][off:off+4096])))
      after[bank][off:off+4096]=body
      if bank==3:a=bytearray(state);a[off:off+4096]=body;state=bytes(a)
    before=t.classify_journal(old[3]);assert before['default']=='B'
    state,binding=append_policy(state,{18+i:v for i,v in enumerate((16).to_bytes(4,'little'))},'BOOT C B: retain B default, bind g10')
    operations.append(binding);after[3]=bytearray(state)
    end=t.classify_journal(state)
    erases=[e for op in operations for e in op['journal_sector_erases']]
    assert len(targets)==15 and erases==['B3:C']
    rows=[i for i in range(0x4000,0x6000,256) if valid_snapshot(old[3][i:i+256])]
    replaced=[i for i in rows if state[i:i+256]!=old[3][i:i+256]]
    assert len(rows)==26 and len(replaced)==16 and all(i<0x5000 for i in replaced)
    assert end['sequence']==1089 and end['valid_records']==27
    assert state[-4096:]==old[3][-4096:] and state[0x1000:0x2000]==old[3][0x1000:0x2000]
    assert before['entries']==end['entries'] and before['enabled_mask']==end['enabled_mask']
    for b,v in after.items():(OUT/f'B{b}-expected.bin').write_bytes(v)
    # Versioned2609 reader candidates only; active collectors and2512 untouched.
    rtc=OUT/'RTC-candidates';rtc.mkdir()
    native=(ROOT/'tools/rtc_mon_ui1_g10_trim.py').read_text()
    assert native.count("assert board=='2512'")==1 and native.count("assert item['board']=='2512'")==1
    native=native.replace("assert board=='2512'","assert board=='2609'").replace("assert item['board']=='2512'","assert item['board']=='2609'")
    native=native.replace("PROFILE='MON-UI1-G10-TIME-TRIM'","PROFILE='MON-UI1-G10-2609-TIME-TRIM'")
    led=(ROOT/'tools/rtc_led_collect_g10.py').read_text()
    assert led.count("assert board=='2512'")==1 and led.count("assert item['board']=='2512'")==1
    led=led.replace("assert board=='2512'","assert board=='2609'").replace("assert item['board']=='2512'","assert item['board']=='2609'")
    led=led.replace('only for2512 MON g10','only for2609 MON g10')
    for name,body in [('rtc_mon_ui1_g10_2609.py',native),('rtc_led_collect_g10_2609.py',led)]:
      compile(body,name,'exec');(rtc/name).write_text(body,encoding='utf-8',newline='\n')
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2609',port='COM8',candidate_archive_sha256='6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789',
      targets=targets,identical_skipped=skipped,image_erases=15,journal_sector_erases=erases,total_erases=16,
      operations=operations,journal_appends=sum(len(op['journal_appends']) for op in operations),
      records_before=26,old_rows_archived=26,old_C_rows_replaced=16,old_D_rows_retained=10,
      sequence_before=before['sequence'],sequence_after=end['sequence'],records_after=end['valid_records'],
      counts_before=before['counts'],counts_after=end['counts'],F_writes=0,metadata_writes=0,
      firmware_builds=0,CPU_simulations=0,power_cuts=0,physical_resets=1,SPI_writes=0,WORKSPACE_writes=0,
      boot_choice='B unchanged; generation binding0D->10 only',bank_enables_and_entries='unchanged target values',
      preservation=['B0 and B1:E/F owner images','B3:9 provider and all metadata','RTC time/trim/control/outage/EEPROM',
        'SPI PROGRAM/WORKSPACE','fresh owner RAM0200-66FF and ZP00-DF','all tracked counts carried forward','archived old C/D raw history'],
      tests=['MON A/B CPU16/emulation admission and Traditional startup/VERSION','TIME current trim/control, unchanged board metadata',
        'EDU/SRAM/WORK read-only admission; stored-record TABLE','RAM S19/BIN cancellation/load; RAM public-HOLD return',
        'APPS/native tools, storage-manager returning BATCH and error/cancel paths','one physical saved-B startup after complete install',
        'versioned2609-only native TIME/NIST and unchanged62-second LED image readmission'],
      excluded=['F or B0 replacement','new flash/SPI write fixtures or format/reclaim','RTC SET/trim/ACK/EEPROM writes',
        'other-board access','published/candidate ZIP changes','full migration/factory restore','automatic erase retry'],
      original_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},expected_bank_sha256={f'B{b}':t.sha(v) for b,v in after.items()},
      original_marker_block_snapshot=marker['block_snapshot'],fresh_preimages_required=True,RTC_priority=True,
      recovery_receipt=str(recovery),recovery_receipt_sha256=t.sha(recovery.read_bytes()),
      RTC_candidate_sha256={p.name:t.sha(p.read_bytes()) for p in rtc.glob('*.py')},RTC_registration='Only after successful installed profile checks; preserve old instruments/baselines/other boards')
    assert plan['journal_appends']==17;t.save(OUT/'plan.json',plan)
    targets_text=', '.join(f'B{x["bank"]}:{x["address"]}' for x in targets)
    text=f'''#2609 Candidate3 upgrade and targeted816 acceptance

November2,2026. Review ready; NOT APPROVED. No port opened. Use the exact
2512-qualified Candidate3 system components, retaining2609 data.

## Exact scope

15 image erases: {targets_text}.
One native B3:C rotation: **16 erases total**, **17 journal appends**.
Four identical components are skipped: {', '.join(skipped)}.
Zero F writes; frozen BASE1/PR05 remains exact. No new firmware build.

Archive all26 old journal rows. Rotation replaces16 old C rows on chip and
retains10 old D rows. Carry every tracked count forward. Final seq1089 has27
rows; C/D/E/F={end['counts'][28:]}. Default remains B; only its generation
binding advances0D->10. Target bank enables/entries remain unchanged.

Preserve B0, B1:E/F, all B3:9 metadata, board name/offset/EDU/battery policy,
RTC time/trim/control/outage/EEPROM, all SPI data and fresh owner RAM/ZP.
The16-row C replacement is incompatible with retaining all old rows on chip;
this exact history-replacement scope requires approval. Old image sectors
and journal are archived in this private review directory.

## Execution and tests

Fresh USB identity/admission and live preimage comparisons must pass before
any write. A mismatch stops for re-review; the old historical allowance is
not combined with this new scope. No automatic erase retry. Use REC> and the
unchanged qualified OPAQUE worker. Install inactive A first, dependencies,
shared services, and B last; bind saved B only after its image is verified.

Targeted CPU16/emulation startup/ABI, native TIME/trim, EDU/SPI read-only,
APPS/native tools, storage BATCH return, RAM loading/cancellation and public
HOLD checks supplement2512's common functional evidence. No new positive
flash or SPI fixtures are included. One physical RESET is included for
saved-B startup after installation. No power cut or other-board operation.

RTC collection keeps priority.2609's hold is now cleared; the owner-reset
recovery receipt verifies RAM restoration and a later62-second sample passed.
Prepare versioned2609 g10 TIME/LED readers; the old gD collector must not be
used after this upgrade. Register only after new profile/readmission passes.
Preserve old instruments, baseline, time/trim/history and other-board routing.
The board's existing generic snapshot block is not silently cleared; the
admitted trial preserves/restores fresh RAM and returns it to REC>.

Restore/read back owner RAM/ZP and release COM8 at each unit/end. A failed
readmission leaves2609 held for review while other collectors continue.
No publication, ZIP change, full migration or factory restoration is included.
'''
    (OUT/'review-document.md').write_text(text,encoding='utf-8',newline='\n')
    t.save(OUT/'review.json',dict(plan_sha256=t.sha((OUT/'plan.json').read_bytes()),review_document_sha256=t.sha((OUT/'review-document.md').read_bytes()),
      hardware_access=False,approved=False))
    print('REVIEW READY:15 image erases+1 C rotation;17 appends;seq1089/27 rows;C/D/E/F',end['counts'][28:])

if __name__=='__main__':run()
