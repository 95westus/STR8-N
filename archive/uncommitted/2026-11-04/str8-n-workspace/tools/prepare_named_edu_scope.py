"""Seal a reviewable2512 plan; no serial access or executable flash driver."""
import binascii,json,sys
from pathlib import Path
import install_2512_native_utilities as d

t=d.t;Q=t.ROOT/'output/qualification';OUT=Q/'NAMED-EDU-2512-scope-20261101-r1'
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot,inspect
from trial_edu_settings_ram import record


def prepare_collectors(folder):
    # Prepare new versioned readers without editing the active old readers,
    # scheduler, baseline, points, LED configuration or campaign state.
    files={};src=t.ROOT/'tools'
    led=(src/'rtc_led_collect.py').read_text()
    led=led.replace("b'g0000000D / MON '","b'g0000000E / MON '")
    led=led.replace(" assert duration==62", " assert board=='2512','This reader is only for2512 MON gE'\n assert duration==62",1)
    led=led.replace(" assert c.sha(p)==item['sha256']", " assert item['board']=='2512'\n assert c.sha(p)==item['sha256']",1)
    led=led.replace("    assert cpu in version,'CPU identification missing; no RAM borrowed'",
        "    assert cpu in version,'CPU identification missing; no RAM borrowed'\n    assert b'EDU ON' in version,'Saved/session EDU OFF; do not borrow RAM'")
    led=led.replace("choices=f.IDS","choices=['2512']").replace('args.board or c.BOARDS',"args.board or ['2512']")
    files['rtc_led_collect_ge.py']=led
    native=(src/'rtc_mon_ui1_gd_trim.py').read_text().replace('MON-UI1-GD-TIME-TRIM','MON-UI1-GE-TIME-TRIM')
    native=native.replace("m['monitor_generation']=='0000000D'","m['monitor_generation']=='0000000E'")
    native=native.replace('g0000000D / MON','g0000000E / MON')
    native=native.replace('    assert board in IDENTITIES','    assert board==\'2512\' and board in IDENTITIES',1)
    native=native.replace('    path=Path(item[\'report\'])','    assert item[\'board\']==\'2512\'\n    path=Path(item[\'report\'])',1)
    files['rtc_mon_ui1_ge_trim.py']=native
    files['rtc_led_dispatch.py']='''"""Preserve historical gD audits; dispatch only qualified gE2512 receipts."""
import rtc_drift_campaign as c
import rtc_led_collect as old
import rtc_led_collect_ge as ge
OLD_AUDIT=old.audit_board
def audit_board(item,state):
    report=c.read(item['report'])
    if item['board']=='2512' and report['driver_sha256']==c.sha(ge.__file__):return ge.audit_board(item,state)
    return OLD_AUDIT(item,state)
'''
    files['rtc_led_mode_ge.py']='''"""Versioned2512 MON gE admission; original instruments/config stay intact."""
import rtc_drift_campaign as c
import rtc_led_mode as oldmode
import rtc_led_collect as old
import rtc_led_collect_ge as ge
import rtc_led_dispatch as dispatch
OLD_COLLECT=old.collect
CONFIG=c.Q/'rtc-led-ge-2512.json'
def enabled(state):return oldmode.enabled(state)
def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2512' and cfg['monitor_generation']=='0000000E'
    assert cfg['driver_sha256']==c.sha(ge.__file__)
    item=cfg['qualification'];assert item['board']=='2512'
    ge.audit_board(item,state)
    return True
def campaign(state,admitted,skipped):
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    is_ge=state['board_admission']['2512'].get('monitor_generation')=='0000000E'
    if is_ge and '2512' in selected and not ready(state):
        selected.remove('2512');skipped.append(dict(board='2512',error='MON gE RTC readmission pending; no port opened'))
    def collect(board,folder):
        return ge.collect(board,folder) if board=='2512' and is_ge else OLD_COLLECT(board,folder)
    before_collect,before_audit=old.collect,old.audit_board
    try:
        old.collect=collect;old.audit_board=dispatch.audit_board
        return oldmode.campaign(state,selected,skipped)
    finally:old.collect=before_collect;old.audit_board=before_audit
'''
    original=(src/'rtc_drift_campaign.py').read_text();candidate=original
    replacements=[('from rtc_led_collect import audit_board as led_audit','from rtc_led_dispatch import audit_board as led_audit'),
        ('from rtc_led_mode import enabled as led_enabled, campaign as led_campaign','from rtc_led_mode_ge import enabled as led_enabled, campaign as led_campaign'),
        ("            if selected_profile.get('profile')=='MON-UI1-GD-TIME-TRIM':", """            if selected_profile.get('profile')=='MON-UI1-GE-TIME-TRIM':
                from rtc_mon_ui1_ge_trim import collect as ge_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:ge_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GD-TIME-TRIM':"""),
        ("            if item.get('capture_profile')=='MON-UI1-GD-TIME-TRIM':", """            if item.get('capture_profile')=='MON-UI1-GE-TIME-TRIM':
                from rtc_mon_ui1_ge_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GD-TIME-TRIM':""")]
    for before,after in replacements:
        assert candidate.count(before)==1;candidate=candidate.replace(before,after,1)
    files['rtc_drift_campaign.candidate.py']=candidate
    (folder/'rtc_drift_campaign.original.py').write_text(original)
    for n,text in files.items():
        compile(text,n,'exec');(folder/n).write_text(text)
    return dict(status='PREPARED_NOT_REGISTERED',files={n:t.sha((folder/n).read_bytes()) for n in files},
        original_campaign_sha256=t.sha((src/'rtc_drift_campaign.py').read_bytes()),
        unchanged=['original gD collectors','original LED agent/image/configuration','cadence/schedule','baselines','points/history','other board admissions'],
        admission='Only after installed gE startup/TIME and preserving native/LED read-only qualification; otherwise2512 defers without blocking other boards')


def run():
    proof=Q/'2512-named-EDU-RAM-20261101-r5/report.json';r=json.loads(proof.read_text());assert r['passed'] and len(r['checks'])==9
    pre=Q/'2512-named-EDU-review-preflight-20261101-r1';pr=json.loads((pre/'report.json').read_text());assert pr['passed']
    marker=json.loads((Q/'device-operations/2512.json').read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not marker['block_snapshot'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    build=t.ROOT/'BUILD/named-edu-g3-r8';mf=json.loads((build/'manifest.json').read_text())
    def art(n):
        body=(build/n).read_bytes();assert t.sha(body)==mf['artifacts'][n]['sha256'];return body
    old={b:(Q/f'2512-named-EDU-RAM-20261101-r2/B{b}-before.bin').read_bytes() for b in (0,1)}
    old[3]=(pre/'B3-before.bin').read_bytes()
    assert old[3]==(proof.parent/'B3-before.bin').read_bytes()
    assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
    frozen=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert old[3][-4096:]==frozen
    assert old[0][0x1000:0x2000]==b'\xff'*4096
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    images={b:bytearray(v) for b,v in old.items()}
    images[1][:0x3000]=art('BANK-MAINT-EDU-flash.bin');images[1][0x3000:0x6000]=art('SRAM-WORK-X-flash.bin')
    helper=t.ROOT/'BUILD/edu-settings-g1-ram-r1';hm=json.loads((helper/'manifest.json').read_text())
    h=(helper/'EDU-SETTINGS-ROM.bin').read_bytes();assert t.sha(h)==hm['artifacts']['EDU-SETTINGS-ROM.bin']['sha256']
    text=(helper/'MON-SHARED-HELP.bin').read_bytes();nl=bytearray(old[3][0xC00:0x1000])
    assert binascii.crc_hqx(nl,65535)==0 and nl[0x290:0x3FE]==b'\xff'*(0x3FE-0x290)
    nl[0x290:0x290+len(h)]=h;nl[0x380:0x380+len(text)]=text;nl[-2:]=binascii.crc_hqx(nl[:-2],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(nl,65535)==0;images[3][0xC00:0x1000]=nl
    mon=t.ROOT/'BUILD/mon-gE-settings-r1';mm=json.loads((mon/'manifest.json').read_text());assert mm['generation']=='0000000E'
    for slot,page in (('A',0xA0),('B',0xB0)):
        n=next(n for n,v in mm['artifacts'].items() if v['variant']==slot);body=(mon/n).read_bytes();assert t.sha(body)==mm['artifacts'][n]['sha256']
        off=(page-0x80)*256;images[3][off:off+4096]=body
    before=t.classify_journal(old[3]);state=old[3];targets=[];ops=[]
    pages=[(1,p) for p in (0x80,0x90,0xA0,0xB0,0xC0,0xD0)]+[(3,0x80),(3,0xA0),(3,0xB0)]
    for bank,page in pages:
        off=(page-0x80)*256;body=bytes(images[bank][off:off+4096]);original=old[bank][off:off+4096];assert body!=original
        name=f'B{bank}-{page:02X}-target.bin';(OUT/name).write_bytes(body);(OUT/f'B{bank}-{page:02X}-original.bin').write_bytes(original)
        state,op=reserve(state,bank*8+(page-0x80)//16);ops.append(op)
        if bank==3:a=bytearray(state);a[off:off+4096]=body;state=bytes(a)
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=name,sha256=t.sha(body),before_sha256=t.sha(original)))
    for _ in range(2):state,op=reserve(state,1);ops.append(op)
    a=bytearray(state);_,off,row=max((int.from_bytes(a[i+8:i+12],'little'),i,bytearray(a[i:i+256])) for i in range(0x4000,0x6000,256) if valid_snapshot(a[i:i+256]))
    bind=off+256;assert a[bind:bind+256]==b'\xff'*256 and (bind&0xF00)<0xF00
    row[8:12]=(int.from_bytes(row[8:12],'little')+1).to_bytes(4,'little');row[18:22]=(14).to_bytes(4,'little')
    row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little');row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little');assert valid_snapshot(row)
    a[bind:bind+256]=row
    meta=a[0x1C00:0x2000];assert not any(meta[i:i+4]==b'ED\x01\0' for i in range(0,1024,32))
    free=[0x1C00+i for i in range(0,1024,32) if meta[i:i+32]==b'\xff'*32];assert len(free)>=2
    for off,body in zip(free,(record(1,0),record(2,1))):a[off:off+32]=body
    state=bytes(a);images[3]=a;after=t.classify_journal(state)
    erases=[v for op in ops for v in op['journal_sector_erases']];assert erases==['B3:D']
    rows=[i for i in range(0x4000,0x6000,256) if valid_snapshot(old[3][i:i+256])]
    removed=[i+0x8000 for i in rows if old[3][i:i+256]!=state[i:i+256]];assert len(removed)==16
    for b,v in old.items():(OUT/f'B{b}-original.bin').write_bytes(v)
    for b,v in images.items():(OUT/f'B{b}-target.bin').write_bytes(v)
    (OUT/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
    (OUT/'PROGRAM-directory-original.bin').write_bytes((pre/'PROGRAM-directory.bin').read_bytes())
    (OUT/'PROGRAM-page0800-original.bin').write_bytes((pre/'PROGRAM-free-page.bin').read_bytes())
    assert pr['temporary_slot']==4 and pr['first_free_page']==8
    profiles=OUT/'RTC-candidates';profiles.mkdir();rtc=prepare_collectors(profiles)
    p=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',targets=targets,operations=ops,image_erases=9,
        fixture_restoration_erases=2,journal_sector_erases=erases,total_erases=12,F_writes=0,C_erases=0,power_cuts=0,
        before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},after_bank_sha256={f'B{b}':t.sha(bytes(v)) for b,v in images.items()},
        counts_before=before['counts'],counts_after=after['counts'],sequence_before=before['sequence'],sequence_after=after['sequence'],
        records_before=before['valid_records'],records_after=after['valid_records'],old_rows_retained_on_chip=len(rows)-len(removed),old_record_pages_replaced=[f'{i:04X}' for i in removed],
        binding_append=dict(page=f'{bind+0x8000:04X}',generation_before='0000000D',generation_after='0000000E',default='B'),
        metadata_appends=[dict(address=f'B3:{off+0x8000:04X}',sequence=i+1,mode=mode) for i,(off,mode) in enumerate(zip(free[:2],['OFF','ON']))],
        SPI_temporary=dict(slot=4,directory_start='00140',directory_end='0017F',payload_start='00800',payload_end='008FF',bytes=320,
            directory_sha256=t.sha((pre/'PROGRAM-directory.bin').read_bytes()),payload_sha256=t.sha((pre/'PROGRAM-free-page.bin').read_bytes()),restoration='Exact original320 bytes; all old program slots and WORKSPACE unchanged'),
        flash_fixture='Only B0:9000-9FFF, originally allFF. Flash->PROGRAM copy; erase; PROGRAM->flash copy; erase to restore FF. All source records retained until restoration.',
        physical_resets=2,RTC=rtc,journal_room_before=inspect(old[3]),RAM_report=str(proof),RAM_report_sha256=t.sha(proof.read_bytes()),
        preflight_report=str(pre/'report.json'),build_manifest_sha256=t.sha((build/'manifest.json').read_bytes()),
        preserved=['F','B2','B0 exact after fixture cleanup','B1:E/F','all prior metadata records','boot bank mask/entries/delay/default B',
            'wear totals carried forward','RTC time/control/trim/PF/history','original PROGRAM directory/page','WORKSPACE','fresh owner RAM0200-66FF/ZP00-DF'],
        remaining_post_install=['Actual ROM decode and MAINT-X-native-handoff','Positive flash/PROGRAM copy and exact cleanup','Real ED/1 saves and physical-reset persistence',
            'Default B/gE startup','Native TIME and unchanged LED-agent readmission','Final bounded bank/owner-RAM preservation'],
        excluded_boards=['2205','2604','2609'],published_download_changes=False)
    assert after['sequence']==1146 and after['valid_records']==21 and after['counts'][28:]==[56,37,36,24]
    t.save(OUT/'plan.json',p)
    print(json.dumps({k:p[k] for k in ('status','total_erases','journal_sector_erases','sequence_after','records_after','old_rows_retained_on_chip','old_record_pages_replaced','metadata_appends','binding_append')},indent=2))


if __name__=='__main__':run()
