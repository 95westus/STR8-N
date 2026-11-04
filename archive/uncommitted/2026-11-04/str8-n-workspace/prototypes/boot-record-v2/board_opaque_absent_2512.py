"""2512-only F -> OIP1 -> opaque B0:8 install/run/restore; MON A/B stay absent."""
import argparse,contextlib,json,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import board_mon_absent_2512 as prior
import installer_build as protocol
b=prior.b;r=b.r;pf=prior.pf
MODEL=pf.ROOT/'BUILD/pr04-b14-opaque-live-absent-r2'
SOURCE=pf.ROOT/'output/qualification/mon-absent-2512-remove'
BASELINE=pf.ROOT/'output/qualification/mon-absent-2512-backup-r2/capture'
AUTH=pf.ROOT/'output/qualification/opaque-absent-2512-authorization'
MESSAGE=b'\r\nOPAQUE B0:8 EXECUTED\r\n'
HEADER=b'SEND OIP1 HEADER\r\n';PAYLOAD=b'SEND 4096\r\n';READ=b'READ SECTOR+CRC\r\n'

def files_banks(phase):return [(MODEL/f'{phase}-b{n}.bin').read_bytes() for n in range(4)]
def source_banks():return [(SOURCE/f'after-rescue-probe-full-flash-r2-b{n}.bin').read_bytes() for n in range(4)]

def source_binding(marker):
    complete=r.read(SOURCE/'state.json');proof=r.read(SOURCE/'test-results.json')
    r.require(complete['passed'] and complete['RAM_restored'] and complete['serial_released'] and proof['audited'],
        'Completed verified MON-absent source required')
    r.require(marker.get('board')=='2512' and marker.get('firmware')=='2.0proto b14 (F only; MON A/B erased)'
        and marker.get('MON_A_present') is False and marker.get('MON_B_present') is False
        and marker.get('current_physical_bank_sha256')==dict(zip(('B0','B1','B2','B3'),r.hashes(source_banks())))
        and marker.get('completion_receipt')==dict(path=str(SOURCE/'state.json'),sha256=r.sha((SOURCE/'state.json').read_bytes())),
        'Exact current F-only 2512 source binding required')
    r.require(not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        and not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending','physical_reset_pending','opaque_sector_restore_pending',
            'current_soak_worker_pid','owner_application_running','power_off_reported','poweroff_pending_owner_confirmation'))
        and marker.get('soak_owner_stopped') is True and marker.get('RTC_sampling_owner_stopped') is True,
        'Device preservation owner/pending-operation guard refuses access')
    # RTC_collection_pending_monitor_recovery is intentionally true: A/B were
    # erased by the owner, and this narrowly scoped F-only test needs no MON.

def admission():
    prior.qualification(prior.BUILD)
    proof=r.read(MODEL/'opaque-live-model-tests.json')
    r.require(proof['passed'] and proof['checks']==10 and proof['failures']==0 and not proof['hardware']
        and proof['checker_sha256']==r.sha((HERE/'test_opaque_live_absent.py').read_bytes())
        and proof['source_completion_sha256']==r.sha((SOURCE/'state.json').read_bytes())
        and proof['source_bank_sha256']==r.hashes(source_banks())
        and proof['installed_bank_sha256']==r.hashes(files_banks('installed'))
        and proof['restored_bank_sha256']==r.hashes(files_banks('restored')),
        'Exact completed round-trip CPU/NOR qualification required')
    for name,key in [('opaque-probe-b0-8000.bin','probe_sha256')]:
        r.require(r.sha((MODEL/name).read_bytes())==proof[key],'Changed probe artifact')
    for name,key in [('ram-installer-offline.bin','installer_sha256'),('mon-service-load.bin','service_loader_sha256')]:
        r.require(r.sha((prior.BUILD/'payload'/name).read_bytes())==proof[key],'Changed qualified RAM tool')
    for cpu in ('65c02','65c816-e'):
        retained=r.read(pf.BUILD/f'b14-opaque-installer-cpu-tests-{cpu}.json')
        r.require(retained['passed'] and retained['checks']==60 and retained['failures']==0 and not retained['hardware']
            and retained['component_hashes']['ram-installer-offline.bin']==proof['installer_sha256']
            and retained['component_hashes']['f-offline-component.bin']==proof['F_sha256'],
            'Unchanged qualified OIP1 protections/interruption evidence required')
    host=r.read(HERE/'opaque-absent-host-tests.json')
    r.require(host['passed'] and host['checks']>=8 and not host['hardware']
        and host['helper_sha256']==r.sha(Path(__file__).read_bytes())
        and host['checker_sha256']==r.sha((HERE/'test_board_opaque_absent.py').read_bytes()),'Fresh exact buffered host qualification required')
    owner_scope(r.read(AUTH/'authorization.json'))
    return proof

def owner_scope(auth):
    r.require(auth.get('owner_authorized') is True and auth.get('action')=='F-only-opaque-install-run-restore'
        and auth.get('board')=='2512' and auth.get('usb_serial')==b.USB
        and auth.get('target')==dict(bank=0,sector=0x80,bytes=4096)
        and auth.get('other_boards_authorized') is False and auth.get('MON_writes_authorized') is False
        and auth.get('F_writes_authorized') is False and auth.get('RTC_writes_authorized') is False
        and auth.get('wear_reservation_authorized') is True and auth.get('restore_original_sector') is True
        and auth.get('helper_sha256')==r.sha(Path(__file__).read_bytes())
        and auth.get('model_proof_sha256')==r.sha((MODEL/'opaque-live-model-tests.json').read_bytes()),
        'Exact owner F-only opaque-test scope required')

def checkpoint(args,marker,state,phase,active=True):
    state.update(phase=phase,updated_utc=b.now());pf.save(args.run/'state.json',state)
    marker.update(state='opaque-absent-'+phase,opaque_install_run=str(args.run),recovery_worker_active=active,
        block_snapshot=not state.get('passed',False),application_RAM_restore_pending=state['application_RAM_restore_pending'],
        application_ram_restored=not state['application_RAM_restore_pending'],physical_reset_pending=False,
        opaque_sector_restore_pending=state.get('opaque_sector_restore_pending',False))
    pf.save(pf.MARKER,marker)

def sync_recovery(link):
    raw=bytearray();last=time.monotonic();start=last
    while time.monotonic()-last<1:
        r.require(time.monotonic()-start<20,'No quiet recovery boundary')
        part=link.read(4096)
        if part:raw.extend(part);last=time.monotonic()
    r.require(all(c in (8,9,10,13,127) or 32<=c<=126 for c in raw),'Nontext initial state; retain capture')
    link.send(b'\r');reply=link.until(b.REC_PROMPT,20)
    r.require(reply==b'\r\nREC> ','Exact idle F recovery required; no untrusted binary state')
    return bytes(raw)+reply

@contextlib.contextmanager
def live(args):
    from serial_test_coordination import serial_lease
    from serial.tools.list_ports import comports
    with serial_lease('F-only-opaque-install-2512',timeout=30):
        marker=r.read(pf.MARKER);source_binding(marker)
        ports=[p for p in comports() if p.serial_number==b.USB]
        r.require(len(ports)==1,'Unique 2512 USB serial required; other boards excluded')
        with (args.run/'serial.jsonl').open('x') as log:
            link=b.wire.Link(ports[0].device,log)
            try:
                pf.atomic(args.run/'initial-recovery.bin',sync_recovery(link));yield link,marker
            finally:link.serial.close()

def load(link,name,prompt):
    link.command('C1',b.REC_PROMPT)
    body=(prior.BUILD/'payload'/name).read_bytes();prior.raw_load(link,body,prompt)
    return body

def service_banks(args,link,expected,phase):
    for repeat in (1,2):
        banks=[prior.read_service(link,b'F'+bytes([n]),32768) for n in range(4)]
        r.require(banks==expected,'Exact independent full-flash '+phase+' readback differs; preserve escrow')
        for n,bank in enumerate(banks):pf.atomic(args.run/f'{phase}-r{repeat}-b{n}.bin',bank)
    pf.save(args.run/(phase+'.json'),dict(passed=True,hardware=True,full_bank_readbacks=2,bank_sha256=r.hashes(expected),
        MON_A_B_absent=expected[3][0x2000:0x4000]==b'\xff'*8192,F_sha256=r.sha(expected[3][-4096:])))

def begin(link):
    r.require(link.command('I',HEADER)==b'I\r\n'+HEADER,'Exact installer header-ready marker required')

def opaque_read(link,expected):
    r.require(len(expected)==4096,'Fixed one-sector read required')
    begin(link);link.send(protocol.frame_header(0,0x80))
    r.require(link.until(READ,10)==READ,'Opaque read readiness differs')
    data=prior.exact(link,4098)
    r.require(data[:-2]==expected and b.wire.crc(data[:-2])==int.from_bytes(data[-2:],'little'),'Opaque raw readback/CRC mismatch')
    r.require(link.until(b.OI_PROMPT,10)==b'\r\nOK: read\r\n'+b.OI_PROMPT,'Opaque read completion differs')
    return data

def opaque_write(link,body,preimage_crc,expected_reply):
    r.require(len(body)==4096 and 0<=preimage_crc<=65535,'Fixed B0:8 whole-sector write required')
    header=protocol.frame_header(0,0x80,body,preimage_crc)
    begin(link);link.send(header)
    r.require(link.until(PAYLOAD,10)==PAYLOAD,'Opaque payload readiness differs')
    for off in range(0,4096,64):link.send(body[off:off+64]);time.sleep(.01)
    reply=link.until(b.OI_PROMPT,30)
    r.require(reply==expected_reply+b.OI_PROMPT,'Opaque write/refusal completion differs: '+repr(reply))
    return dict(payload_sha256=r.sha(body),preimage_crc_hex=f'{preimage_crc:04X}',payload_crc_hex=f'{b.wire.crc(body):04X}',
        bytes=4096,reply=reply.decode('ascii'),passed=True)

def quit_installer(link):link.command('Q',b.REC_PROMPT)
def quit_service(link):link.send(b'Q');link.until(b.REC_PROMPT,10)

def preserved_RAM(prior_baseline,loader,observed):
    r.require(len(prior_baseline)==0x6300 and len(observed)==2 and len(observed[0])==0x6300
        and observed[0]==observed[1] and observed[0][:len(loader)]==loader,
        'Repeated current RAM or disposable F load preimage differs')
    # L's prefix is explicitly disposable. The remaining bytes are freshly
    # observed, and must be kept even if they differ from the older escrow.
    result=prior_baseline[:len(loader)]+observed[0][len(loader):]
    changes=[dict(address_hex=f'{i+0x200:04X}',prior_hex=f'{prior_baseline[i]:02X}',current_hex=f'{result[i]:02X}')
        for i in range(len(loader),0x6300) if result[i]!=prior_baseline[i]]
    return result,changes

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);args=p.parse_args();args.run=args.run.resolve()
    proof=admission();source_binding(r.read(pf.MARKER));r.require(not args.run.exists(),'Fresh private run required')
    args.run.mkdir(parents=True);(args.run/'.gitignore').write_text('*\n')
    for name in ('2604','2609'):pf.atomic(args.run/(name+'-marker-before.json'),(pf.MARKER.parent/(name+'.json')).read_bytes())
    before=pf.MARKER.read_bytes();pf.atomic(args.run/'device-marker-before.json',before)
    baseline=(BASELINE/'application-ram.bin').read_bytes();zp=(BASELINE/'owner-zp.bin').read_bytes()
    r.require(len(baseline)==0x6300 and baseline==(BASELINE/'application-ram-repeat.bin').read_bytes()
        and len(zp)==0xe0 and zp==(BASELINE/'owner-zp-repeat.bin').read_bytes(),'Prior verified owner RAM escrow differs')
    pf.atomic(args.run/'owner-RAM-baseline.bin',baseline);pf.atomic(args.run/'owner-ZP-baseline.bin',zp)
    source=source_banks();original=source[0][:4096];probe=(MODEL/'opaque-probe-b0-8000.bin').read_bytes()
    state=dict(board='2512',USB=b.USB,passed=False,application_RAM_restore_pending=False,opaque_sector_restore_pending=False,
        physical_reset_pending=False,physical_reset_used=False,source_run=str(SOURCE),source_bank_sha256=r.hashes(source),
        owner_RAM_baseline_source=str(BASELINE),owner_RAM_baseline_sha256=r.sha(baseline),owner_ZP_sha256=r.sha(zp),
        initial_RAM_prefix_read_before_L=False,RAM_prefix_policy='Disposable F load span restored from prior verified prefix; preserve freshly repeated remaining RAM/ZP.',
        target=dict(bank=0,sector=0x80,bytes=4096),MON_A_B_remain_absent=True)
    try:
        with live(args) as (link,marker):
            state['application_RAM_restore_pending']=True;checkpoint(args,marker,state,'RAM-baseline-escrowed-before-F-L')
            loader=load(link,'mon-service-load.bin',prior.SVC)
            service_banks(args,link,source,'fresh-source-flash')
            observed=[prior.read_service(link,b'M',0x6300) for _ in range(2)]
            for n,data in enumerate(observed,1):pf.atomic(args.run/f'fresh-RAM-after-service-load-r{n}.bin',data)
            fresh,changes=preserved_RAM(baseline,loader,observed)
            current_ZP=[prior.read_service(link,b'Z',0xe0) for _ in range(2)]
            r.require(current_ZP[0]==current_ZP[1] and len(current_ZP[0])==0xe0,'Fresh repeated owner zero page differs')
            pf.atomic(args.run/'prior-owner-RAM-baseline.bin',baseline);pf.atomic(args.run/'prior-owner-ZP-baseline.bin',zp)
            baseline,zp=fresh,current_ZP[0]
            pf.atomic(args.run/'owner-RAM-baseline.bin',baseline);pf.atomic(args.run/'owner-ZP-baseline.bin',zp)
            state.update(fresh_source_flash_repeats=2,fresh_unborrowed_RAM_compared=True,fresh_ZP_compared=True,
                RAM_changes_from_prior_escrow=changes,owner_RAM_baseline_sha256=r.sha(baseline),owner_ZP_sha256=r.sha(zp),
                owner_RAM_baseline_source=str(args.run/'owner-RAM-baseline.bin'),
                owner_RAM_prefix_baseline_source=str(BASELINE/'application-ram.bin'),
                fresh_RAM_tail_source=str(args.run/'fresh-RAM-after-service-load-r1.bin'))
            checkpoint(args,marker,state,'fresh-preimage-backup-verified')
            quit_service(link);load(link,'ram-installer-offline.bin',b.OI_PROMPT)
            pf.atomic(args.run/'OIP-original-read.bin',opaque_read(link,original))
            state['opaque_sector_restore_pending']=True;checkpoint(args,marker,state,'before-opaque-write')
            result=opaque_write(link,probe,b.wire.crc(original),b'OK: verified sector\r\n');pf.save(args.run/'opaque-install.json',result)
            pf.atomic(args.run/'OIP-installed-read.bin',opaque_read(link,probe))
            pf.save(args.run/'identical-retry.json',opaque_write(link,probe,b.wire.crc(probe),b'OK: identical; no erase\r\n'))
            pf.save(args.run/'wrong-preimage-refusal.json',opaque_write(link,probe,b.wire.crc(probe)^1,b'REFUSED: preimage CRC\r\n'))
            state.update(F_loaded_OIP1=True,opaque_install_verified=True,identical_retry_verified=True,wrong_preimage_refusal_verified=True)
            checkpoint(args,marker,state,'opaque-sector-installed-and-read-back')
            quit_installer(link);boot=link.command('0',b.REC_PROMPT);pf.atomic(args.run/'opaque-bank0-execution-boot.bin',boot)
            tokens=[MESSAGE,b'\r\nWAIT...\r\n',b.CHOICES,b'Boot : 6 5 4 3 2 1 0\r\n',b'Recovery L A/B 0-3 C1/2/3 ?\r\nREC> ']
            offsets=[boot.find(token) for token in tokens]
            r.require(all(n>=0 for n in offsets) and offsets==sorted(offsets) and b'STR8-N' not in boot,'Opaque execution/software recovery return failed')
            state['opaque_bank0_execution_verified']=True
            load(link,'mon-service-load.bin',prior.SVC);service_banks(args,link,files_banks('installed'),'installed-independent-flash')
            quit_service(link);load(link,'ram-installer-offline.bin',b.OI_PROMPT)
            pf.save(args.run/'original-sector-restore.json',opaque_write(link,original,b.wire.crc(probe),b'OK: verified sector\r\n'))
            pf.atomic(args.run/'OIP-restored-read.bin',opaque_read(link,original));state['opaque_sector_restore_pending']=False
            checkpoint(args,marker,state,'original-opaque-sector-restored')
            quit_installer(link);load(link,'mon-service-load.bin',prior.SVC)
            final=files_banks('restored');service_banks(args,link,final,'restored-independent-flash')
            prior.write_owner_ram(link,baseline)
            for _ in range(3):r.require(prior.read_service(link,b'M',0x6300)==baseline,'Owner RAM restoration differs')
            for _ in range(2):r.require(prior.read_service(link,b'Z',0xe0)==zp,'Owner ZP preservation differs')
            quit_service(link);pf.atomic(args.run/'final-F-help.bin',link.command('?',b.REC_PROMPT))
            state.update(RAM_restored=True,ZP_preserved=True,application_RAM_restore_pending=False,passed=True,
                original_B0_sector_restored=True,F_unchanged=True,MON_A_B_erased_verified=True,final_console_mode='BOTH',
                final_prompt='REC> ',final_bank_sha256=r.hashes(final),full_flash_comparisons=6,RAM_comparisons=3,ZP_final_comparisons=2)
            checkpoint(args,marker,state,'completed',active=False)
            marker.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),state['final_bank_sha256'])),
                current_firmware_sha256=r.sha(b''.join(final[1:])),application_RAM_restore_verified=True,
                last_recovery_report=str(args.run/'state.json'),last_preservation_report=str(args.run/'test-results.json'),
                last_recovery_scope='F-only OIP1 opaque install/readback/execute/no-op/refusal/restore; MON A/B absent; owner RAM/ZP restored',
                reason='Opaque image installed/executed/verified with MON A/B absent, original sector and RAM restored; F unchanged')
            pf.save(pf.MARKER,marker)
        for name in ('2604','2609'):r.require((args.run/(name+'-marker-before.json')).read_bytes()==(pf.MARKER.parent/(name+'.json')).read_bytes(),'Other-board marker changed')
        state.update(serial_released=True,other_boards_unchanged=True,completed_utc=b.now());pf.save(args.run/'state.json',state)
        marker=r.read(pf.MARKER);marker.update(recorded_utc=state['completed_utc'],completion_receipt=dict(path=str(args.run/'state.json'),sha256=r.sha((args.run/'state.json').read_bytes())))
        pf.save(pf.MARKER,marker);pf.atomic(args.run/'F-only-b1-b3.bin',b''.join(final[1:]))
        pf.save(args.run/'test-results.json',dict(state,hardware=True,failures=0,offline_roundtrip_groups=proof['checks'],
            host_checks=r.read(HERE/'opaque-absent-host-tests.json')['checks'],target_erases=2,
            source_F_sha256=r.sha(source[3][-4096:]),final_F_sha256=r.sha(final[3][-4096:]),
            limitations=['No physical power interruption or reset; prior qualified OIP1 model fault coverage retained',
                'First F raw load necessarily overwrote its disposable RAM span; prior verified prefix restored and fresh remaining RAM/ZP preserved']))
        print('PASS 2512 F-only opaque install/readback/execute/restore; MON A/B absent; RAM restored; lease released',flush=True)
    except BaseException:
        state.update(passed=False,phase='stopped-preserve-escrow',error=traceback.format_exc());pf.save(args.run/'state.json',state)
        marker=r.read(pf.MARKER);marker['recovery_worker_active']=False;pf.save(pf.MARKER,marker)
        raise

if __name__=='__main__':main()
