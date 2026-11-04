"""Seal three-sector2512 TIME/PREP review and private RTC adapters; no ports."""
import binascii,json,sys
from pathlib import Path
import install_2512_native_utilities as d
t=d.t;Q=t.ROOT/'output/qualification';OUT=Q/'TIME-PREP-2512-scope-20261101-r1'
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot

def rtc_candidates(folder):
    src=t.ROOT/'tools';files={}
    for old,new in [('rtc_led_collect_ge.py','rtc_led_collect_gf.py'),('rtc_mon_ui1_ge_trim.py','rtc_mon_ui1_gf_trim.py')]:
        s=(src/old).read_text();assert '0000000E' in s;s=s.replace('0000000E','0000000F').replace('MON-UI1-GE-TIME-TRIM','MON-UI1-GF-TIME-TRIM')
        s=s.replace('MON gD TIME','MON gF TIME').replace('fresh gD TIME','fresh gF TIME');files[new]=s
    files['rtc_led_dispatch_gf.py']='''"""Preserve gD/gE receipt audits; add only2512 gF."""
import rtc_drift_campaign as c
import rtc_led_dispatch as previous
import rtc_led_collect_gf as gf
def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2512' and r['driver_sha256']==c.sha(gf.__file__):return gf.audit_board(item,state)
    return previous.audit_board(item,state)
'''
    files['rtc_led_mode_gf.py']='''"""2512 gF qualification gate; prior modes/instruments remain intact."""
import rtc_drift_campaign as c
import rtc_led_mode_ge as previous
import rtc_led_mode as original_mode
import rtc_led_collect as original
import rtc_led_collect_gf as gf
import rtc_led_dispatch_gf as dispatch
CONFIG=c.Q/'rtc-led-gf-2512.json'
def enabled(state):return previous.enabled(state)
def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2512' and cfg['monitor_generation']=='0000000F'
    assert cfg['driver_sha256']==c.sha(gf.__file__)
    assert cfg['qualification']['board']=='2512'
    gf.audit_board(cfg['qualification'],state)
    return True
def campaign(state,admitted,skipped):
    if state['board_admission']['2512'].get('monitor_generation')!='0000000F':return previous.campaign(state,admitted,skipped)
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    if '2512' in selected and not ready(state):
        selected.remove('2512');skipped.append(dict(board='2512',error='MON gF RTC readmission pending; no port opened'))
    saved_collect,saved_audit=original.collect,original.audit_board
    def collect(board,folder):return gf.collect(board,folder) if board=='2512' else saved_collect(board,folder)
    try:
        original.collect=collect;original.audit_board=dispatch.audit_board
        return original_mode.campaign(state,selected,skipped)
    finally:original.collect=saved_collect;original.audit_board=saved_audit
'''
    original=(src/'rtc_drift_campaign.py').read_text();candidate=original
    replacements=[('from rtc_led_dispatch import audit_board as led_audit','from rtc_led_dispatch_gf import audit_board as led_audit'),
        ('from rtc_led_mode_ge import enabled as led_enabled, campaign as led_campaign','from rtc_led_mode_gf import enabled as led_enabled, campaign as led_campaign'),
        ("            if selected_profile.get('profile')=='MON-UI1-GE-TIME-TRIM':", """            if selected_profile.get('profile')=='MON-UI1-GF-TIME-TRIM':
                from rtc_mon_ui1_gf_trim import collect as gf_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:gf_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GE-TIME-TRIM':"""),
        ("            if item.get('capture_profile')=='MON-UI1-GE-TIME-TRIM':", """            if item.get('capture_profile')=='MON-UI1-GF-TIME-TRIM':
                from rtc_mon_ui1_gf_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GE-TIME-TRIM':""")]
    for before,after in replacements:assert candidate.count(before)==1;candidate=candidate.replace(before,after,1)
    files['rtc_drift_campaign.candidate.py']=candidate;(folder/'rtc_drift_campaign.original.py').write_text(original)
    for n,s in files.items():compile(s,n,'exec');(folder/n).write_text(s)
    return dict(status='PREPARED_NOT_REGISTERED',original_campaign_sha256=t.sha((src/'rtc_drift_campaign.py').read_bytes()),
        original_readers_sha256={n:t.sha((src/n).read_bytes()) for n in ('rtc_led_collect.py','rtc_led_mode.py','rtc_led_collect_ge.py','rtc_led_mode_ge.py','rtc_mon_ui1_gd_trim.py','rtc_mon_ui1_ge_trim.py')},
        files={n:t.sha((folder/n).read_bytes()) for n in files},admission='Installed gF cold startup, strict native nine TIME/NIST and unchanged62-second LED agent;2512 only',
        preserved=['all gD/gE instruments and audits','clock/trim/PF/history','baselines/points','schedule/cadence','other board admissions'])

def run():
    ram=Q/'2512-TIME-PREP-RAM-20261101-r2';cold=Q/'2512-TIME-PREP-cold-RAM-20261101-r2'
    for folder in (ram,cold):
        r=json.loads((folder/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released'] and r['B2_B3_unchanged']
    marker=json.loads((Q/'device-operations/2512.json').read_text());assert marker['application_ram_restored'] and not marker['block_snapshot'] and not marker['physical_reset_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    old={b:(cold/f'B{b}-after.bin').read_bytes() for b in (2,3)};assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert all(t.sha((t.REPO/n).read_bytes())==v for n,v in freeze['sources'].items())
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    images={b:bytearray(v) for b,v in old.items()}
    build=t.ROOT/'BUILD/status-autoprep-r1';mf=json.loads((build/'manifest.json').read_text());detail=(build/'STATUS-ROM.bin').read_bytes();assert t.sha(detail)==mf['artifacts']['STATUS-ROM.bin']['sha256']
    assert old[2][0x7A50:0x7FFA]==(t.ROOT/'BUILD/status-g1-r4/STATUS-FA50.bin').read_bytes()
    assert binascii.crc_hqx(old[2][0x6000:],65535)==0
    images[2][0x7A50:0x7FFA]=detail;images[2][-2:]=binascii.crc_hqx(images[2][0x6000:-2],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(images[2][0x6000:],65535)==0
    for off,(a,b) in enumerate(zip(old[2],images[2])):assert a==b or 0x7A50<=off<0x7FFA or off>=0x7FFE
    mon=t.ROOT/'BUILD/mon-gF-time-r1';mm=json.loads((mon/'manifest.json').read_text());assert mm['generation']=='0000000F'
    for slot,page in [('A',0xA0),('B',0xB0)]:
        n=next(n for n,v in mm['artifacts'].items() if v['variant']==slot);body=(mon/n).read_bytes();assert t.sha(body)==mm['artifacts'][n]['sha256']
        off=(page-0x80)*256;images[3][off:off+4096]=body
    state=old[3];targets=[];ops=[]
    for bank,page in ((2,0xF0),(3,0xA0),(3,0xB0)):
        off=(page-0x80)*256;body=bytes(images[bank][off:off+4096]);before=old[bank][off:off+4096];assert body!=before
        name=f'B{bank}-{page:02X}-target.bin';(OUT/name).write_bytes(body);(OUT/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
        state,op=reserve(state,bank*8+(page-0x80)//16);assert not op['journal_sector_erases'];ops.append(op)
        if bank==3:a=bytearray(state);a[off:off+4096]=body;state=bytes(a)
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=name,sha256=t.sha(body),before_sha256=t.sha(before)))
    a=bytearray(state);seq,off,row=max((int.from_bytes(a[i+8:i+12],'little'),i,bytearray(a[i:i+256])) for i in range(0x4000,0x6000,256) if valid_snapshot(a[i:i+256]))
    bind=off+256;assert a[bind:bind+256]==b'\xff'*256 and bind==0x5800
    row[8:12]=(seq+1).to_bytes(4,'little');row[18:22]=(15).to_bytes(4,'little');row[30:32]=binascii.crc_hqx(row[:30],65535).to_bytes(2,'little');row[252:254]=binascii.crc_hqx(row[:252],65535).to_bytes(2,'little');assert valid_snapshot(row)
    a[bind:bind+256]=row;images[3]=a;before=t.classify_journal(old[3]);after=t.classify_journal(a)
    assert before['sequence']==1146 and after['sequence']==1150 and before['valid_records']==21 and after['valid_records']==25
    for i in range(0x4000,0x6000,256):
        if valid_snapshot(old[3][i:i+256]):assert old[3][i:i+256]==a[i:i+256]
    assert old[3][:0x2000]==a[:0x2000] and old[3][0x6000:]==a[0x6000:]
    assert after['counts'][28:]==before['counts'][28:]==[56,37,36,24]
    for bank in (2,3):(OUT/f'B{bank}-original.bin').write_bytes(old[bank]);(OUT/f'B{bank}-target.bin').write_bytes(images[bank])
    (OUT/'boot-wear-history-original.bin').write_bytes(old[3][0x4000:0x6000])
    folder=OUT/'RTC-candidates';folder.mkdir();rtc=rtc_candidates(folder)
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',targets=targets,operations=ops,total_erases=3,journal_sector_erases=0,F_writes=0,
        wear_appends=3,binding_append=dict(page='D800',sequence=1150,default='B',generation_before='0000000E',generation_after='0000000F'),
        sequence_before=1146,sequence_after=1150,old_rows_retained_on_chip=21,records_after=25,counts_before=before['counts'],counts_after=after['counts'],
        before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},after_bank_sha256={f'B{b}':t.sha(bytes(v)) for b,v in images.items()},
        whole_marker_bank_sha256=marker['current_physical_bank_sha256'],RAM_receipt=str(ram/'report.json'),RAM_receipt_sha256=t.sha((ram/'report.json').read_bytes()),
        cold_receipt=str(cold/'report.json'),cold_receipt_sha256=t.sha((cold/'report.json').read_bytes()),
        build_manifest_sha256={str(p):t.sha(p.read_bytes()) for p in (build/'manifest.json',mon/'manifest.json')},RTC=rtc,
        physical_resets=1,power_cuts=0,metadata_appends=0,SRAM_data_writes=0,RTC_settings_writes=0,published_download_changes=False,
        preserved=['golden F','all21 current C/D records on chip','wear carried forward','default B enables/entries/delay','saved EDU ON/name/zone/battery metadata','B0/B1 and all other images','RTC time/control/trim/PF/history','all SPI SRAM/WORKSPACE','fresh owner RAM0200-66FF/ZP00-DF'],
        tests=['Installed MON A/B and TIME','Physical default-B gF cold startup/capacity without PREP','R SRAM TABLE and existing apps read-only/cancel routes','Strict nine native TIME/NIST samples','Unchanged62-second LED sampler and host readmission','Exact image/journal and owner restoration'],
        excluded_boards=['2205','2604','2609'],evidence_limit='Cold reset owner-reported; startup receiver expired. Actual pending IFR18/IER80 captured before RAM candidate; no manual PREP. Earlier TIME04 raw invalid bytes were not captured; bounded behavior CPU-fault-tested and live-time-tested.')
    t.save(OUT/'plan.json',plan)
    print(json.dumps({k:plan[k] for k in ('status','total_erases','wear_appends','binding_append','sequence_after','old_rows_retained_on_chip','records_after')},indent=2));print('B2:F count',before['counts'][23],'->',after['counts'][23]);print('A/B',before['counts'][26:28],'->',after['counts'][26:28])

if __name__=='__main__':run()
