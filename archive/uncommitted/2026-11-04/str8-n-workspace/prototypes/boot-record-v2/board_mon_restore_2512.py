"""Restore the saved b14 MON A/B through F on 2512 only; F is never written."""
import argparse,contextlib,json,time,traceback
from pathlib import Path
import board_opaque_absent_2512 as shared
b=shared.b;r=b.r;pf=shared.pf;prior=shared.prior
SOURCE=pf.ROOT/'output/qualification/opaque-absent-2512-install-run-restore-r2'
MODEL=pf.ROOT/'BUILD/pr04-b14-mon-restore-live'
AUTH=pf.ROOT/'output/qualification/mon-restore-2512-authorization'
BANNER=b'STR8-N 2.0proto b14 B3 65C02'

def source_banks():return [(SOURCE/f'restored-independent-flash-r2-b{n}.bin').read_bytes() for n in range(4)]
def expected_banks():return [(MODEL/f'expected-b{n}.bin').read_bytes() for n in range(4)]

def source_binding(marker):
    state=r.read(SOURCE/'state.json');proof=r.read(SOURCE/'test-results.json')
    r.require(state['passed'] and state['RAM_restored'] and state['serial_released'] and proof['audited'],
        'Completed audited current F-only source required')
    r.require(marker.get('board')=='2512' and marker.get('firmware')=='2.0proto b14 (F only; MON A/B erased)'
        and marker.get('MON_A_present') is False and marker.get('MON_B_present') is False
        and marker.get('current_physical_bank_sha256')==dict(zip(('B0','B1','B2','B3'),r.hashes(source_banks())))
        and marker.get('completion_receipt')==dict(path=str(SOURCE/'state.json'),sha256=r.sha((SOURCE/'state.json').read_bytes())),
        'Exact current 2512 absent-MON source binding required')
    r.require(not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        and not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending','physical_reset_pending',
            'opaque_sector_restore_pending','mon_restore_pending','current_soak_worker_pid','owner_application_running',
            'power_off_reported','poweroff_pending_owner_confirmation'))
        and marker.get('soak_owner_stopped') is True and marker.get('RTC_sampling_owner_stopped') is True,
        'Device owner/preservation guard refuses access')

def owner_scope(auth):
    r.require(auth.get('owner_authorized') is True and auth.get('action')=='restore-saved-b14-MON-AB-through-F'
        and auth.get('board')=='2512' and auth.get('usb_serial')==b.USB
        and auth.get('targets')==['B3:A','B3:B'] and auth.get('generation_hex')=='8000000E'
        and auth.get('other_boards_authorized') is False and auth.get('F_writes_authorized') is False
        and auth.get('RTC_writes_authorized') is False and auth.get('wear_reservation_authorized') is True
        and auth.get('helper_sha256')==r.sha(Path(__file__).read_bytes())
        and auth.get('model_proof_sha256')==r.sha((MODEL/'mon-restore-model-tests.json').read_bytes()),
        'Exact owner MON-restore scope required')

def admission():
    prior.qualification(prior.BUILD)
    proof=r.read(MODEL/'mon-restore-model-tests.json')
    r.require(proof['passed'] and proof['checks']==6 and proof['failures']==0 and not proof['hardware']
        and proof['checker_sha256']==r.sha((shared.HERE/'test_mon_restore_live.py').read_bytes())
        and proof['source_completion_sha256']==r.sha((SOURCE/'state.json').read_bytes())
        and proof['source_bank_sha256']==r.hashes(source_banks())
        and proof['expected_bank_sha256']==r.hashes(expected_banks())
        and proof['restore_kit_sha256']==r.sha((prior.BUILD/'payload/mon-kit.bin').read_bytes())
        and proof['retained_kit_proof_sha256']==r.sha((prior.BUILD/'mon-absent-tests.json').read_bytes()),
        'Exact current-source restoration model qualification required')
    original=(pf.ROOT/'output/qualification/mon-absent-2512-backup-r2/capture/b3.bin').read_bytes()
    r.require(original==(pf.ROOT/'output/qualification/mon-absent-2512-backup-r2/capture/b3-repeat.bin').read_bytes(),
        'Original twice-captured MON backup differs')
    body=(prior.BUILD/'payload/mon-kit.bin').read_bytes();sy=r.read(prior.BUILD/'symbols.json')['core/mon-kit']
    r.require(b.wire.crc(body[:-2])==int.from_bytes(body[-2:],'little'),'Restore kit self CRC differs')
    for page,label in ((0xa0,'MA_IMAGE_A'),(0xb0,'MA_IMAGE_B')):
        offset=(page-0x80)*256;slot=original[offset:offset+4096];start=sy[label]-0x200
        r.require(body[start:start+4096]==slot==expected_banks()[3][offset:offset+4096]
            and b.wire.slot_valid(slot,page) and int.from_bytes(slot[8:12],'little')==0x8000000e,
            'Embedded slot does not match original valid b14 backup')
    host=r.read(shared.HERE/'mon-restore-host-tests.json')
    r.require(host['passed'] and host['checks']>=6 and not host['hardware']
        and host['helper_sha256']==r.sha(Path(__file__).read_bytes())
        and host['checker_sha256']==r.sha((shared.HERE/'test_board_mon_restore.py').read_bytes()),
        'Fresh exact host restoration qualification required')
    owner_scope(r.read(AUTH/'authorization.json'));return proof

def checkpoint(args,marker,state,phase,active=True):
    state.update(phase=phase,updated_utc=b.now());pf.save(args.run/'state.json',state)
    marker.update(state='mon-restore-'+phase,mon_restore_run=str(args.run),recovery_worker_active=active,
        mon_restore_pending=state['mon_restore_pending'],block_snapshot=not state.get('passed',False),
        application_RAM_restore_pending=state['application_RAM_restore_pending'],
        application_ram_restored=not state['application_RAM_restore_pending'],physical_reset_pending=False)
    pf.save(pf.MARKER,marker)

@contextlib.contextmanager
def live(args):
    from serial_test_coordination import serial_lease
    from serial.tools.list_ports import comports
    with serial_lease('restore-MON-AB-through-F-2512',timeout=30):
        marker=r.read(pf.MARKER);source_binding(marker)
        ports=[p for p in comports() if p.serial_number==b.USB]
        r.require(len(ports)==1,'Unique 2512 USB serial required; other boards excluded')
        with (args.run/'serial.jsonl').open('x') as log:
            link=b.wire.Link(ports[0].device,log)
            try:pf.atomic(args.run/'initial-F-recovery.bin',shared.sync_recovery(link));yield link,marker
            finally:link.serial.close()

def flash_readback(args,link,expected,phase):
    for repeat in (1,2):
        banks=[prior.read_service(link,b'F'+bytes([n]),32768) for n in range(4)]
        r.require(banks==expected,'Exact full flash differs at '+phase+'; retain escrow')
        for n,body in enumerate(banks):pf.atomic(args.run/f'{phase}-r{repeat}-b{n}.bin',body)
    pf.save(args.run/(phase+'.json'),dict(passed=True,hardware=True,repeat_full_reads=2,bank_sha256=r.hashes(expected)))

def identity(link,slot):
    r.require(link.dump(0x7d01,0x7d02)==b'\x02\x03' and link.dump(0x7d30,0x7d30)==bytes([slot]),
        'Restored b14 65C02/BOTH/active-slot identity differs')

def restore_and_boot(link):
    link.send(b'T');raw=link.until(b.MON_PROMPT,60)
    tokens=[b'MON KIT DONE\r\n',b'\r\nWAIT...\r\n',b.CHOICES,b'Boot : 6 5 4 3 2 1 0\r\n',BANNER,b.MON_PROMPT]
    positions=[raw.find(token) for token in tokens]
    r.require(all(n>=0 for n in positions) and positions==sorted(positions),'Restoration/complete default boot evidence differs')
    return raw

def restart_S(link,run,label):
    prefix=b.software_startup(link,run,label);link.send(b'S');recovery=link.until(b.REC_PROMPT,20)
    r.require(b'Recovery L A/B 0-3 C1/2/3 ?\r\nREC> ' in recovery,'J3 -> S recovery missing')
    pf.atomic(run/('J3-S-'+label+'.bin'),prefix+recovery)

def select_MON(link,label):
    r.require(label in ('A','B'),'Only MON A/B selections allowed')
    reply=link.command(label,b.MON_PROMPT)
    r.require(BANNER in reply,'Exact restored b14 MON banner missing');identity(link,0xa0 if label=='A' else 0xb0)
    return reply

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);args=p.parse_args();args.run=args.run.resolve()
    proof=admission();source_binding(r.read(pf.MARKER));r.require(not args.run.exists(),'Fresh restoration run required')
    args.run.mkdir(parents=True);(args.run/'.gitignore').write_text('*\n')
    pf.atomic(args.run/'device-marker-before.json',pf.MARKER.read_bytes())
    for name in ('2604','2609'):pf.atomic(args.run/(name+'-marker-before.json'),(pf.MARKER.parent/(name+'.json')).read_bytes())
    baseline=(SOURCE/'owner-RAM-baseline.bin').read_bytes();zp=(SOURCE/'owner-ZP-baseline.bin').read_bytes()
    r.require(r.sha(baseline)==r.read(SOURCE/'state.json')['owner_RAM_baseline_sha256'],'Last verified owner RAM baseline differs')
    pf.atomic(args.run/'prior-owner-RAM-baseline.bin',baseline);pf.atomic(args.run/'prior-owner-ZP-baseline.bin',zp)
    state=dict(passed=False,board='2512',USB=b.USB,application_RAM_restore_pending=False,mon_restore_pending=False,
        physical_reset_pending=False,physical_reset_used=False,source_run=str(SOURCE),source_bank_sha256=r.hashes(source_banks()),
        target_identity='2.0proto b14',generation_hex='8000000E',F_written=False,
        initial_RAM_prefix_read_before_L=False,RAM_policy='First disposable F-load prefix from last verified owner image; freshly repeated remainder/ZP preserved')
    try:
        with live(args) as (link,marker):
            state['application_RAM_restore_pending']=True;checkpoint(args,marker,state,'RAM-prefix-escrowed-before-first-L')
            loader=shared.load(link,'mon-service-load.bin',prior.SVC)
            flash_readback(args,link,source_banks(),'fresh-source-flash')
            observed=[prior.read_service(link,b'M',0x6300) for _ in range(2)]
            for n,data in enumerate(observed,1):pf.atomic(args.run/f'fresh-RAM-after-service-load-r{n}.bin',data)
            baseline,changes=shared.preserved_RAM(baseline,loader,observed)
            zps=[prior.read_service(link,b'Z',0xe0) for _ in range(2)]
            r.require(zps[0]==zps[1] and len(zps[0])==0xe0,'Fresh owner zero page differs');zp=zps[0]
            pf.atomic(args.run/'owner-RAM-baseline.bin',baseline);pf.atomic(args.run/'owner-ZP-baseline.bin',zp)
            state.update(owner_RAM_sha256=r.sha(baseline),owner_ZP_sha256=r.sha(zp),fresh_RAM_changes_from_prior=changes)
            checkpoint(args,marker,state,'fresh-flash-and-RAM-preservation-verified')
            shared.quit_service(link);kit=shared.load(link,'mon-kit.bin',prior.KIT)
            state.update(mon_restore_pending=True,restore_kit_sha256=r.sha(kit),restore_kit_bytes=len(kit))
            checkpoint(args,marker,state,'before-T-restores-only-MON-A-B')
            boot=restore_and_boot(link);pf.atomic(args.run/'F-kit-restoration-default-B-boot.bin',boot);identity(link,0xb0)
            state.update(default_B_boot_verified=True,restore_T_sent=True);checkpoint(args,marker,state,'MON-B-boot-verified')
            restart_S(link,args.run,'from-B');pf.atomic(args.run/'MON-A-boot.bin',select_MON(link,'A'))
            restart_S(link,args.run,'from-A')
            state.update(MON_A_boot_verified=True,J3_S_from_B_verified=True,J3_S_from_A_verified=True)
            shared.load(link,'mon-service-load.bin',prior.SVC)
            expected=expected_banks();flash_readback(args,link,expected,'restored-independent-flash')
            state['mon_restore_pending']=False;checkpoint(args,marker,state,'exact-A-B-readback-verified')
            prior.write_owner_ram(link,baseline)
            for _ in range(3):r.require(prior.read_service(link,b'M',0x6300)==baseline,'Full owner RAM restoration differs')
            for _ in range(2):r.require(prior.read_service(link,b'Z',0xe0)==zp,'Owner zero page changed')
            shared.quit_service(link);pf.atomic(args.run/'final-MON-B-boot.bin',select_MON(link,'B'))
            ram=b.workflow.read_range(link,0x200,0x64ff);pf.atomic(args.run/'final-MON-owner-RAM.bin',ram)
            r.require(ram==baseline,'Independent final MON RAM readback differs')
            for n in (1,2):
                current=link.dump(0,0xdf);pf.atomic(args.run/f'final-MON-ZP-r{n}.bin',current)
                r.require(current==zp,'Independent final MON owner ZP differs')
            state.update(passed=True,application_RAM_restore_pending=False,RAM_restored=True,ZP_preserved=True,F_unchanged=True,
                MON_A_B_valid=True,final_MON='B',final_console_mode='BOTH',final_prompt='B3> ',
                final_bank_sha256=r.hashes(expected),full_flash_comparisons=4,service_RAM_comparisons=3,independent_MON_RAM_comparisons=1)
            checkpoint(args,marker,state,'completed',active=False)
            marker.update(firmware='2.0proto b14',firmware_build='pr04-b14-bench-core',current_firmware_profile='experimental-bench-core',
                monitor_generation=0x8000000e,MON_A_present=True,MON_B_present=True,RTC_collection_pending_monitor_recovery=False,
                current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),state['final_bank_sha256'])),
                current_firmware_sha256=r.sha(b''.join(expected[1:])),application_RAM_restore_verified=True,
                last_preservation_report=str(args.run/'test-results.json'),last_recovery_report=str(args.run/'state.json'),
                last_software_timeout_boot_report=str(args.run/'state.json'),software_full_countdown_boot_verified=True,
                physical_reset_boot_banner_captured=False,physical_boot_status='No physical reset used; F kit software reset-vector boot captured',
                last_recovery_scope='MON A/B restored through F raw RAM kit; default B and A boot; J3 -> S from both; exact flash; owner RAM/ZP preserved',
                reason='Original b14 MON A/B restored through F; software boot and J3/S passed; RAM/ZP restored; F/settings preserved')
            pf.save(pf.MARKER,marker)
        for name in ('2604','2609'):r.require((args.run/(name+'-marker-before.json')).read_bytes()==(pf.MARKER.parent/(name+'.json')).read_bytes(),'Other board marker changed')
        state.update(serial_released=True,other_boards_unchanged=True,completed_utc=b.now());pf.save(args.run/'state.json',state)
        marker=r.read(pf.MARKER);marker.update(recorded_utc=state['completed_utc'],completion_receipt=dict(path=str(args.run/'state.json'),sha256=r.sha((args.run/'state.json').read_bytes())))
        pf.save(pf.MARKER,marker);pf.atomic(args.run/'restored-b1-b3.bin',b''.join(expected[1:]))
        pf.save(args.run/'test-results.json',dict(state,hardware=True,failures=0,offline_current_source_groups=proof['checks'],
            retained_kit_groups=16,host_checks=r.read(shared.HERE/'mon-restore-host-tests.json')['checks'],
            targets=['B3:A','B3:B'],MON_erases=2,RTC_writes=False,
            source_F_sha256=r.sha(source_banks()[3][-4096:]),final_F_sha256=r.sha(expected[3][-4096:]),
            limitations=['No physical reset or power-cut test; current-source CPU/NOR tests plus retained kit interruption cases',
                'First disposable L prefix restored from last verified owner image; fresh remaining RAM/ZP preserved']))
        print('PASS 2512 saved b14 MON A/B restored through F; boot/A/B/J3-S/RAM verified; other boards unchanged; lease released',flush=True)
    except BaseException:
        state.update(passed=False,phase='stopped-preserve-escrow',error=traceback.format_exc());pf.save(args.run/'state.json',state)
        marker=r.read(pf.MARKER);marker['recovery_worker_active']=False;pf.save(pf.MARKER,marker)
        raise

if __name__=='__main__':main()
