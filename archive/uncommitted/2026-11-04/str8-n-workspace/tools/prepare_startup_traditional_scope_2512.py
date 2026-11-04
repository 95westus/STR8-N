"""Review three presentation image erases on2512; no board or live RTC edits."""
import binascii, json, sys
from pathlib import Path
import install_named_edu_2512 as ins

t=ins.t; Q=ins.Q; ROOT=t.ROOT
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot

OUT=Q/'2512-startup-traditional-scope-20261101-r1'
BUILD=ROOT/'BUILD/startup-traditional-r2'

def rtc_candidates(folder):
    """Versioned readers only; prior readers/receipts and active routing stay intact."""
    src=ROOT/'tools';files={}
    native=(src/'rtc_mon_ui1_gf_trim.py').read_text()
    native=native.replace('0000000F','00000010').replace('MON-UI1-GF-TIME-TRIM','MON-UI1-G10-TIME-TRIM')
    native=native.replace("rb'g00000010 / MON ([AB])'","rb'STR8-N MON ([AB])  gen 00000010'")
    native=native.replace('gF TIME','g10 TIME')
    assert "rb'STR8-N MON ([AB])  gen 00000010'" in native
    files['rtc_mon_ui1_g10_trim.py']=native
    led=(src/'rtc_led_collect_gf.py').read_text()
    assert led.count("b'g0000000F / MON '")==2
    led=led.replace("b'g0000000F / MON '","b'  gen 00000010'").replace('2512 MON gE','2512 MON g10')
    files['rtc_led_collect_g10.py']=led
    files['rtc_led_dispatch_g10.py']='''"""Retain old receipt audits; add only2512 g10."""
import rtc_drift_campaign as c
import rtc_led_dispatch_gf as previous
import rtc_led_collect_g10 as current
def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2512' and r['driver_sha256']==c.sha(current.__file__):return current.audit_board(item,state)
    return previous.audit_board(item,state)
'''
    mode=(src/'rtc_led_mode_gf.py').read_text()
    mode=mode.replace('rtc_led_mode_ge as previous','rtc_led_mode_gf as previous')
    mode=mode.replace('rtc_led_collect_gf','rtc_led_collect_g10').replace('rtc_led_dispatch_gf','rtc_led_dispatch_g10')
    mode=mode.replace('0000000F','00000010').replace('rtc-led-gf-2512.json','rtc-led-g10-2512.json').replace('gF','g10')
    files['rtc_led_mode_g10.py']=mode
    original=(src/'rtc_drift_campaign.py').read_text();candidate=original
    replacements=[
        ('from rtc_led_dispatch_gf import audit_board as led_audit','from rtc_led_dispatch_g10 import audit_board as led_audit'),
        ('from rtc_led_mode_gf import enabled as led_enabled, campaign as led_campaign','from rtc_led_mode_g10 import enabled as led_enabled, campaign as led_campaign'),
        ("            if selected_profile.get('profile')=='MON-UI1-GF-TIME-TRIM':", """            if selected_profile.get('profile')=='MON-UI1-G10-TIME-TRIM':
                from rtc_mon_ui1_g10_trim import collect as g10_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:g10_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GF-TIME-TRIM':"""),
        ("            if item.get('capture_profile')=='MON-UI1-GF-TIME-TRIM':", """            if item.get('capture_profile')=='MON-UI1-G10-TIME-TRIM':
                from rtc_mon_ui1_g10_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GF-TIME-TRIM':""")]
    for before,after in replacements:
        assert candidate.count(before)==1;candidate=candidate.replace(before,after,1)
    files['rtc_drift_campaign.candidate.py']=candidate
    (folder/'rtc_drift_campaign.original.py').write_text(original)
    for name,body in files.items():
        compile(body,name,'exec');(folder/name).write_text(body,encoding='utf-8',newline='\n')
    return dict(status='PREPARED_NOT_REGISTERED',original_campaign_sha256=t.sha((src/'rtc_drift_campaign.py').read_bytes()),
        original_readers_sha256={n:t.sha((src/n).read_bytes()) for n in ('rtc_mon_ui1_gf_trim.py','rtc_led_collect_gf.py','rtc_led_mode_gf.py','rtc_led_dispatch_gf.py')},
        files={n:t.sha((folder/n).read_bytes()) for n in files},
        admission='2512 installed/default-B startup, strict nine native TIME/NIST samples and unchanged794-byte62-second LED agent',
        preserved=['current trim/control/time/PF','all old instruments/audits','baseline/points/segments','schedule','all other board admissions'])

def run():
    ram=Q/'2512-startup-traditional-RAM-20261101-r3/report.json';receipt=json.loads(ram.read_text())
    assert receipt['passed'] and receipt['owner_RAM_restored'] and receipt['owner_ZP_restored'] and receipt['COM4_released']
    assert receipt['flash_erases']==receipt['journal_appends']==receipt['RTC_SET']==0
    marker=json.loads((Q/'device-operations/2512.json').read_text())
    assert marker['application_ram_restored'] and not marker['block_snapshot']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    previous=Q/'2512-storage-large-return-continuation-20261101-r1'
    old={b:(previous/f'B{b}-after.bin').read_bytes() for b in (2,3)}
    assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in freeze['sources'].items())
    mf=json.loads((BUILD/'manifest.json').read_text());mm=json.loads((BUILD/'MON/manifest.json').read_text())
    assert mm['generation']=='00000010' and mf['F_sha256']==freeze['sha256']
    images={b:bytearray(v) for b,v in old.items()}
    core=(BUILD/'STATUS-ROM.bin').read_bytes();assert t.sha(core)==mf['artifacts']['STATUS-ROM.bin']['sha256']
    assert old[2][0x2C00:0x3000]==(ROOT/'BUILD/status-g1-r4/STATUS-AC00.bin').read_bytes()
    images[2][0x2C00:0x3000]=core
    for slot,page in [('A',0xA0),('B',0xB0)]:
        name,info=next((n,i) for n,i in mm['artifacts'].items() if i['variant']==slot)
        body=(BUILD/'MON'/name).read_bytes();assert t.sha(body)==info['sha256']
        off=(page-0x80)*256;images[3][off:off+4096]=body
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    state=old[3];targets=[];operations=[]
    for bank,page in ((2,0xA0),(3,0xA0),(3,0xB0)):
        off=(page-0x80)*256;before=old[bank][off:off+4096];body=bytes(images[bank][off:off+4096]);assert before!=body
        name=f'B{bank}-{page:02X}-target.bin';(OUT/name).write_bytes(body);(OUT/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
        state,operation=reserve(state,bank*8+(page-0x80)//16)
        assert not operation['journal_sector_erases'];operations.append(operation)
        if bank==3:a=bytearray(state);a[off:off+4096]=body;state=bytes(a)
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=name,sha256=t.sha(body),before_sha256=t.sha(before)))
    a=bytearray(state)
    seq,off,row=max((int.from_bytes(a[i+8:i+12],'little'),i,bytearray(a[i:i+256])) for i in range(0x4000,0x6000,256) if valid_snapshot(a[i:i+256]))
    bind=off+256;assert bind==0x4A00 and a[bind:bind+256]==b'\xff'*256
    assert row[7]==ord('B') and int.from_bytes(row[18:22],'little')==15
    row[8:12]=(seq+1).to_bytes(4,'little');row[18:22]=(16).to_bytes(4,'little')
    row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little')
    row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little');assert valid_snapshot(row)
    a[bind:bind+256]=row;images[3]=a
    before=t.classify_journal(old[3]);after=t.classify_journal(a)
    assert (before['sequence'],after['sequence'],before['valid_records'],after['valid_records'])==(1164,1168,23,27)
    for i in range(0x4000,0x6000,256):
        if valid_snapshot(old[3][i:i+256]):assert old[3][i:i+256]==a[i:i+256]
    assert after['counts'][28:]==before['counts'][28:]==[57,37,37,24]
    assert old[3][:0x2000]==a[:0x2000] and old[3][0x6000:]==a[0x6000:]
    assert old[2][:0x2C00]==images[2][:0x2C00] and old[2][0x3000:]==images[2][0x3000:]
    assert row[12:18]==old[3][0x460C:0x4612]  # latest original record is C600
    for bank in (2,3):
        (OUT/f'B{bank}-original.bin').write_bytes(old[bank]);(OUT/f'B{bank}-target.bin').write_bytes(images[bank])
    (OUT/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
    rtc=OUT/'RTC-candidates';rtc.mkdir()
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',port='COM4',targets=targets,operations=operations,
        total_erases=3,journal_sector_erases=0,F_writes=0,wear_appends=3,
        binding_append=dict(page='CA00',sequence=1168,default='B',generation_before='0000000F',generation_after='00000010'),
        sequence_before=1164,sequence_after=1168,old_rows_retained_on_chip=23,records_after=27,
        counts_before=before['counts'],counts_after=after['counts'],whole_marker_bank_sha256=marker['current_physical_bank_sha256'],
        before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},after_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},
        RAM_receipt=str(ram),RAM_receipt_sha256=t.sha(ram.read_bytes()),RTC=rtc_candidates(rtc),
        physical_resets=1,power_cuts=0,metadata_appends=0,SRAM_data_writes=0,RTC_settings_writes=0,published_download_changes=False,
        preserved=['golden F','all23 old C/D rows exact on chip','default B/enables/entries/delay','saved EDU ON/name2512/current offset-06/battery policy',
            'B0/B1 and all other images','TIME/SRAM-PREP code and native/shared help','RTC time/control/trim/PF/history','all SPI PROGRAM/WORKSPACE',
            'fresh owner RAM0200-66FF/ZP00-DF'],
        tests=['installed A/B startup/header and detailed VERSION','shared help and concise TIME/current trim/control',
            'CLOCK/workbench UI VERSION return','physical saved-default-B startup','native TIME/NIST and unchanged LED readmission',
            'exact reviewed image/journal postimages and owner restoration'],
        excluded_boards=['2205','2604','2609'],excluded=['BOOT OFF/DELAY/RUN writes','CLOCK administration','power cuts','factory restore','publication'],
        F_sha256=freeze['sha256'])
    t.save(OUT/'plan.json',plan)
    text='''# 2512 Traditional firmware startup scope

Review ready; not approved or executed. The earlier14-erase allowance is spent.

Replace only B2:A (the matching STATUS core at AC00-AFFF; preserve A000-ABFF)
and B3:A/B (identical MON g00000010). Three erases total. Before each erase,
append its reservation at C700/seq1165, C800/1166 and C900/1167. Then one
native BOOT C B append at CA00/seq1168 binds the existing B default to g10.
All23 current journal records remain byte-for-byte on chip; final27 rows.
No C/D erases or F writes. Final tracked counts: B2:A18, MON A48/B55,
C57/D37/E37/F24. No other saved boot field changes.

The2512 RAM presentation receipt passed. Its two host capture/syntax assertion
corrections required no firmware repair; exact owner restoration passed each
time. ROM UI calls and physical startup remain installation acceptance gates.

Capture fresh owner RAM0200-66FF and ZP00-DF, verify reviewed target preimages,
perform only these replacements, select/test both MON slots and shared-tool
VERSION/TIME/help, then capture one owner-operated CPU RESET with saved B/g10.
Restore/read back owner RAM/ZP after borrowing. No power cut.

Preserve F, every other image, all old C/D rows, counts carried forward,
saved name2512/EDU ON/current-06:00 offset/battery policy, and RTC time/control/
trim/PF/history. SPI PROGRAM/WORKSPACE receives no data writes. New versioned
host RTC adapters recognize the new header without altering old readers or
the794-byte LED agent. Admit nine strict native TIME/NIST samples and the
unchanged62-second LED run; preserve baselines, points, segments and schedule.
RTC collection keeps lease priority. Preparation has not registered any host
routing or changed the campaign. Recheck its source hashes before admission.

Leave2609 held and2205/2604 untouched. No download/tag/ZIP changes. BOOT/CLOCK
positive setting tests and factory restoration are outside this allowance.
Finish at REC>, owner RAM/ZP restored, COM4 released and RTC readmitted.

plan.json pins the exact images, original history, forecasts and RAM receipt.
Any changed preimage, forecast or additional erase requires a new review.
'''
    (OUT/'review-document.md').write_text(text,encoding='utf-8',newline='\n')
    review=dict(status='REVIEW_READY_NOT_APPROVED',plan_sha256=t.sha((OUT/'plan.json').read_bytes()),
        review_document_sha256=t.sha((OUT/'review-document.md').read_bytes()),hardware_access=False,flash_writes=0)
    t.save(OUT/'review.json',review)
    print('REVIEW READY:3 image erases;4 appends;0 C/D erases;0 F writes;seq1168;27 rows',flush=True)

if __name__=='__main__':run()
