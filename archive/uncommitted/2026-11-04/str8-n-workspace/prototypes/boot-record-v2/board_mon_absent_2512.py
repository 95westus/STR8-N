"""Owner-authorized MON A/B removal on 2512 only; F remains unchanged.

The fixed restore kit is qualified offline and launched read-only on hardware
after MON removal. The T restore command is deliberately never sent here.
"""
import argparse,json,time,hashlib,traceback,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import capture_mon_absent_preflight as pf
b=pf.board;r=b.r
BUILD=pf.ROOT/'BUILD/pr04-b14-mon-absent-r5'
BACKUP=pf.ROOT/'output/qualification/mon-absent-2512-backup-r2'
AUTH=pf.ROOT/'output/qualification/mon-absent-2512-authorization'
KIT=b'MON KIT X=eraseAB T=restoreAB Q=boot> '
SVC=b'RAM SERVICE> '

def exact(link,n):
    data=bytes(link.pending[:n]);del link.pending[:len(data)]
    return data+link.exact(n-len(data)) if len(data)<n else data

def read_service(link,command,n):
    r.require(not link.pending,'Unexpected service tail before request')
    link.send(command);data=exact(link,n+2)
    r.require(b.wire.crc(data[:n])==int.from_bytes(data[n:],'little'),'RAM service binary CRC mismatch')
    r.require(link.until(SVC,10)==SVC,'RAM service prompt framing differs')
    return data[:n]

def raw_load(link,body,prompt):
    r.require(0<len(body)<=0x6300,'Invalid fixed raw BIN length')
    r.require(link.command('L',b'SEND BIN\r\n')==b'L\r\nSEND BIN\r\n','Exact b14 L ready marker required')
    for off in range(0,len(body),64):
        link.send(body[off:off+64]);time.sleep(.01)
    r.require(link.until(prompt,30)==prompt,'Unexpected raw tool launch output')

def write_owner_ram(link,body):
    r.require(len(body)==0x6300 and not link.pending,'Fixed complete RAM restore required')
    link.send(b'W')
    packet=body+b.wire.crc(body).to_bytes(2,'little')
    for off in range(0,len(packet),64):
        link.send(packet[off:off+64]);time.sleep(.01)
    r.require(link.until(SVC,30)==SVC,'Owner RAM restoration did not acknowledge exact CRC')

def qualification(build):
    report=r.read(build/'mon-absent-build.json');proof=r.read(build/'mon-absent-tests.json')
    r.require(proof['passed'] and not proof['hardware'] and proof['checks']>=16 and proof['failures']==0
        and proof['build_report_sha256']==r.sha((build/'mon-absent-build.json').read_bytes())
        and proof['checker_sha256']==r.sha((HERE/'test_mon_absent.py').read_bytes()),'Exact current CPU/NOR qualification required')
    for name,digest in report['sources'].items():r.require(r.sha((HERE/name).read_bytes())==digest,'Tool source changed: '+name)
    for name,digest in report['artifacts'].items():r.require(r.sha((build/'payload'/name).read_bytes())==digest,'Tool payload changed: '+name)
    host=r.read(HERE/'mon-absent-host-tests.json')
    r.require(host['passed'] and host['checks']>=6 and not host['hardware']
        and host['helper_sha256']==r.sha(Path(__file__).read_bytes())
        and host['checker_sha256']==r.sha((HERE/'test_board_mon_absent.py').read_bytes()),'Exact buffered host qualification required')
    return report,proof

def auth_check(auth,report):
    r.require(auth.get('owner_authorized') is True and auth.get('action')=='erase-only-2512-MON-A-B'
        and auth.get('board')=='2512' and auth.get('usb_serial')==b.USB
        and auth.get('targets')==['B3:A','B3:B'] and auth.get('other_boards_authorized') is False
        and auth.get('F_writes_authorized') is False and auth.get('RTC_writes_authorized') is False
        and auth.get('wear_reservation_authorized') is True
        and auth.get('build_report_sha256')==r.sha((BUILD/'mon-absent-build.json').read_bytes())
        and auth.get('helper_sha256')==r.sha(Path(__file__).read_bytes()),'Exact owner MON-removal authorization required')

def checkpoint(args,marker,state,phase,active=True):
    state.update(phase=phase,updated_utc=b.now());pf.save(args.run/'state.json',state)
    marker.update(state='mon-absent-'+phase,mon_absent_run=str(args.run),recovery_worker_active=active,
        application_RAM_restore_pending=state['application_RAM_restore_pending'],
        application_ram_restored=not state['application_RAM_restore_pending'],block_snapshot=True,
        physical_reset_pending=False)
    pf.save(args.marker,marker)

def verify_banks(args,link,expected,phase):
    reads=[]
    for repeat in range(2):
        banks=[read_service(link,b'F'+bytes([n]),32768) for n in range(4)]
        r.require(banks==expected,'Exact full-bank postimage differs; keep restore escrow')
        for n,data in enumerate(banks):pf.atomic(args.run/f'{phase}-r{repeat+1}-b{n}.bin',data)
        reads.append([r.sha(bank) for bank in banks])
    pf.save(args.run/(phase+'.json'),dict(passed=True,hardware=True,repeat_readbacks=2,bank_sha256=reads,
        F_unchanged=True,MON_A_erased=True,MON_B_erased=True,other_flash_matches_CPU_postimage=True))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();args.run=args.run.resolve();args.marker=pf.MARKER;args.coordination=b.DEFAULT_COORDINATION;args.stage='remove-mon'
    report,proof=qualification(BUILD);auth_check(r.read(AUTH/'remove.json'),report)
    r.require(not args.run.exists(),'Fresh MON-removal run required');args.run.mkdir(parents=True);(args.run/'.gitignore').write_text('*\n')
    backup=r.read(BACKUP/'backup.json');r.require(backup['passed'] and backup['RAM_restored'] and backup['ZP_preserved'],'Fresh completed backup required')
    cap=BACKUP/'capture';b.capture.validate(cap)
    source=pf.expected_banks();expected=[(BUILD/f'mon-absent-expected-b{n}.bin').read_bytes() for n in range(4)]
    r.require([r.sha(x) for x in expected]==proof['expected_bank_sha256'],'Offline expected postimage changed')
    r.require([r.sha(x) for x in source]==report['source_bank_sha256'],'Source plan differs from tool binding')
    r.require([r.sha((cap/f'b{n}.bin').read_bytes()) for n in range(4)]==report['source_bank_sha256'],'Hardware backup differs from tool preimage')
    ram=(cap/'application-ram.bin').read_bytes();zp=(cap/'owner-zp.bin').read_bytes()
    for name in ('2604','2609'):
        r.require((AUTH/(name+'-marker-before.json')).read_bytes()==(pf.MARKER.parent/(name+'.json')).read_bytes(),'Other board marker changed')
    state=dict(board='2512',USB=b.USB,passed=False,application_RAM_restore_pending=False,physical_reset_pending=False,
        source_backup=str(cap),restore_kit=str(BUILD/'payload/mon-kit.bin'),flash_written=False,physical_reset_used=False)
    before=args.marker.read_bytes();pf.atomic(args.run/'device-marker-before.json',before)
    try:
        with pf.link_for(args) as (link,marker):
            pf.identity(link)
            r.require(b.workflow.read_range(link,0x200,0x64ff)==ram and link.dump(0,0xdf)==zp,'Fresh owner RAM/ZP changed since backup')
            state['application_RAM_restore_pending']=True;checkpoint(args,marker,state,'escrowed-before-G')
            # Qualified exact FTDI shim is used only while MON B still exists.
            b.select_ftdi(link,pf.BUILD,source,args.run,'before-removal')
            for _ in range(2):r.require(b.workflow.flash(link)==source,'Fresh source flash changed; no erase permitted')
            body=(BUILD/'payload/mon-kit.bin').read_bytes();b.load_ram_span(link,0x200,body)
            link.send(b'G 0200\r');r.require(link.until(KIT,30)==b'G 0200\r\n'+KIT,'Verified RAM MON kit launch differs')
            checkpoint(args,marker,state,'before-two-MON-erases')
            state['flash_written']=True;checkpoint(args,marker,state,'two-MON-erases-issued')
            link.send(b'X');boot=link.until(b.REC_PROMPT,60)
            pf.atomic(args.run/'F-only-software-boot.bin',boot)
            tokens=[b'MON KIT DONE\r\n',b'\r\nWAIT...\r\n',b.CHOICES,b'Boot : 6 5 4 3 2 1 0\r\n',b'Recovery L A/B 0-3 C1/2/3 ?\r\nREC> ']
            offsets=[boot.find(x) for x in tokens]
            r.require(all(x>=0 for x in offsets) and offsets==sorted(offsets) and b'STR8-N' not in boot,'F-only timeout boot failed')
            state['software_boot_to_F_verified']=True
            refusal=b''
            for key in ('A','B'):
                reply=link.command(key,b.REC_PROMPT);r.require(b'Recovery L A/B' in reply and b'STR8-N' not in reply,'Erased MON still launched')
                refusal+=reply
            pf.atomic(args.run/'absent-A-B-selection.bin',refusal)
            state['A_B_unavailable_verified']=True
            loader=(BUILD/'payload/mon-service-load.bin').read_bytes()
            link.command('C1',b.REC_PROMPT);raw_load(link,loader,SVC)
            verify_banks(args,link,expected,'post-erase-full-flash')
            link.send(b'Q');link.until(b.REC_PROMPT,10)
            # Launch the exact rescue tool through F with BOTH monitors erased;
            # quit without sending T or performing another flash mutation.
            raw_load(link,body,KIT);link.send(b'Q');rescue_boot=link.until(b.REC_PROMPT,60)
            pf.atomic(args.run/'F-only-restore-kit-launch-quit.bin',KIT+rescue_boot)
            r.require(b'Boot : 6 5 4 3 2 1 0\r\n' in rescue_boot and b'STR8-N' not in rescue_boot,'Restore kit read-only quit failed')
            state['restore_kit_F_raw_load_verified']=True
            link.command('C1',b.REC_PROMPT);raw_load(link,loader,SVC)
            verify_banks(args,link,expected,'after-rescue-probe-full-flash')
            write_owner_ram(link,ram)
            for _ in range(3):r.require(read_service(link,b'M',len(ram))==ram,'Full owner RAM restore differs')
            for _ in range(2):r.require(read_service(link,b'Z',len(zp))==zp,'Owner zero page changed')
            link.send(b'Q');r.require(b'Recovery L A/B' in link.until(b.REC_PROMPT,10),'Final F recovery missing')
            help_reply=link.command('?',b.REC_PROMPT);pf.atomic(args.run/'final-F-help.bin',help_reply)
            r.require(b'L' in help_reply and help_reply.endswith(b.REC_PROMPT),'Final help boundary differs')
            state.update(application_RAM_restore_pending=False,RAM_restored=True,ZP_preserved=True,final_console_mode='BOTH',
                final_prompt='REC> ',MON_A='erased',MON_B='erased',F_unchanged=True,passed=True,
                final_bank_sha256=[r.sha(x) for x in expected],RAM_comparisons=3,ZP_comparisons=2)
            checkpoint(args,marker,state,'completed',active=False)
            marker.update(block_snapshot=False,firmware='2.0proto b14 (F only; MON A/B erased)',
                monitor_generation=None,previous_monitor_generation=0x8000000e,current_firmware_profile='experimental-F-only-MON-absent',
                current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),state['final_bank_sha256'])),
                previous_complete_firmware_sha256=marker['current_firmware_sha256'],current_firmware_sha256=r.sha(b''.join(expected[1:])),
                MON_A_present=False,MON_B_present=False,RTC_collection_pending_monitor_recovery=True,
                application_RAM_restore_verified=True,last_preservation_report=str(args.run/'test-results.json'),
                reason='Owner requested MON A/B removal; F-only raw loader and restore-kit launch verified; RAM restored')
            pf.save(args.marker,marker)
        state.update(serial_released=True,completed_utc=b.now())
        for name in ('2604','2609'):r.require((AUTH/(name+'-marker-before.json')).read_bytes()==(pf.MARKER.parent/(name+'.json')).read_bytes(),'Other board marker changed')
        state.update(other_board_markers_unchanged=True,phase='completed')
        pf.save(args.run/'state.json',state)
        pf.save(args.run/'test-results.json',dict(state,offline_checks=proof['checks'],offline_failures=proof['failures'],
            hardware=True,physical_flash_targets=['B3:A','B3:B'],MON_erases=2,
            journal_changes='Two durable wear reservations; exact CPU-predicted full-bank postimage',
            live_MON_restore_performed=False,limitation='T restore tested in CPU/NOR models; live kit launch only; no physical power-loss test'))
        print('PASS 2512 MON A/B erased; F recovery/restore kit available; RAM restored; serial released',flush=True)
    except BaseException:
        if state['application_RAM_restore_pending']:
            state.update(phase='stopped-preserve-escrow',passed=False,error=traceback.format_exc())
            pf.save(args.run/'state.json',state)
            marker=r.read(args.marker);marker['recovery_worker_active']=False;pf.save(args.marker,marker)
        raise

if __name__=='__main__':main()
