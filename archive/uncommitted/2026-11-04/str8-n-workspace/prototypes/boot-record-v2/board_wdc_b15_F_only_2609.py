"""Explicit owner-authorized 2609 F-only hardware step; stop at first REC>.

Uses the already qualified native RAM migrator without changing its bytes.
No journal, MON, opaque-image or ACIA test is performed.
"""
import argparse,json,os,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import wdc_b15_2609 as planning
from installer.engine import legacy_transport as wire,runtime as r,install_transport as transport
from installer.common import save
from serial_test_coordination import serial_lease
ROOT,HERE=planning.ROOT,planning.HERE
sys.path.insert(0,str(ROOT/'tmp/migration-python'))
now=lambda:datetime.now(timezone.utc).isoformat()

def durable(path,body):
    with path.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    assert path.read_bytes()==body

def program_and_wait(link,plan,run,state,checkpoint,reset_wait=600):
    print('PROGRESS RAM: loading 8192 bytes; every 256-byte block is read back before EXEC',flush=True)
    def progress(n,op):
        assert n==1 and (op['bank'],op['address'])==(3,0xf000)
        state.update(transfers_sent=1,last_destination='B3:F000',phase='F-transfer-sent-device-verifying');checkpoint()
        print('PROGRESS FLASH: 4096/4096 F bytes sent; waiting for device erase/program/readback verification',flush=True)
    result=transport.execute(link,plan,stock=True,host_readback=True,progress=progress)
    assert result['transaction_device_verified'] and result['transfers_completed']==1
    state.update(result,flash_written=True,phase='F-device-verified-awaiting-reset');checkpoint()
    (run/'device-result.txt').write_text(result['result'],encoding='utf-8')
    print('PROGRESS FLASH: device verification passed; only B3:F was an allowed destination',flush=True)
    # The stock WDC debugger uses RTS asserted. Match the separately qualified
    # F USB-console link before the physical RESET. This does not issue RESET.
    link.serial.rts=False
    print('RESET REQUIRED: press 2609 S2/RESB once; receive-only capture is armed. Stop target is REC>.',flush=True)
    boot=link.until(b'REC> ',seconds=reset_wait)
    durable(run/'first-F-only-REC.txt',boot)
    assert b'Recovery L A/B 0-3 C1/2/3 ?' in boot and b'STR8-N 2.0proto' not in boot
    state.update(REC_verified=True,physical_reset_pending=False,phase='REC-verified-stopped',
        stop_after_REC_honored=True,post_REC_commands=0,USB_console_verified=True,ACIA_board_tested=False)
    checkpoint()
    print('PASS REC> verified through USB; stopped with no further commands',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--qualification',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();plan=args.plan.resolve();run=args.run.resolve()
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists()
    info=planning.verify(plan);qualification=r.read(args.qualification)
    assert qualification['passed'] and qualification['plan_sha256']==planning.digest(plan/'plan.json')
    assert qualification['installer_sha256']==info['installer_sha256'] and qualification['offline_checks']==44
    for path,digest in qualification['references'].items():assert planning.digest(path)==digest
    assert info['transaction']['planned_erase_order']==[[3,15]] and len(info['transaction']['operations'])==1
    assert info['transaction']['counts_before'][31]==29 and info['transaction']['reserved_counts'][31]==30
    for name in ('test_wdc_b15_2609.py','test_wdc_b15_F_only_boot.py'):
        proof_path=next(Path(path) for path in qualification['references'] if ('boot-proof' in path)==('boot' in name))
        assert r.read(proof_path)['test_source_sha256']==planning.digest(HERE/name)
    markerpath=ROOT/'output/qualification/device-operations/2609.json'
    marker=r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='original-WDCMONV2-65C816' and marker['stock_boot_verified']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running'))
    assert marker['current_physical_bank_sha256']=={f'B{n}':v for n,v in enumerate(info['source_sha256'])}
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n')
    save(run/'marker-before.json',marker)
    save(run/'authorization.json',dict(owner_authorized=True,board='2609',usb_serial=planning.USB,
        user_text='flash only the 4096 byte b15 F image on 2609 using the ram migrator. keep b0 and all other sectors unchanged, show progress, and stop after we verify REC>',
        plan_sha256=planning.digest(plan/'plan.json'),F_sha256=info['F_sha256'],stop='first verified REC>',
        ACIA_board_test_authorized=False,other_flash_sectors_authorized=False,RTC_or_EEPROM_write_authorized=False))
    state=dict(board='2609',passed=False,phase='fresh-WDC-source-check',started_utc=now(),flash_written=False,
        execution_started=False,physical_reset_pending=False,REC_verified=False,
        plan=str(plan/'plan.json'),plan_sha256=planning.digest(plan/'plan.json'),F_sha256=info['F_sha256'],F_bytes=4096,
        source_hashes=info['source_sha256'],expected_hashes=info['expected_sha256'],
        planned_flash_destinations=['B3:F000-FFFF'],B0_backup_preserved_by_scope=True,
        C_D_written=False,MON_written=False,RTC_written=False,EEPROM_written=False,
        ACIA_board_tested=False,console_test_scope='USB FT245 only',wear_F_before=29,wear_F_reserved=30,
        onboard_wear_initialized=False,RAM_disposition='Affected RAM archived; migrator/new F use disposable runtime RAM')
    def checkpoint():
        save(run/'report.json',state)
        current=dict(marker,state='F-only-'+state['phase'],F_only_worker_active=not state.get('closed',False),
            F_only_run=str(run),block_snapshot=True,physical_reset_pending=state['physical_reset_pending'],
            application_RAM_restore_pending=False,ACIA_board_tested=False)
        if state.get('transaction_device_verified'):
            current.update(firmware='2.0proto b15 F only',current_firmware_profile='b15-F-only',monitor_generation=None,
                current_firmware_sha256=None,current_F_sha256=info['F_sha256'],MON_A_present=False,MON_B_present=False,
                current_physical_bank_sha256={f'B{n}':v for n,v in enumerate(info['expected_sha256'])},
                snapshot_block_reason='F-only recovery; no compatible MON-based RTC sampler',
                application_ram_restored=False,application_RAM_disposition=state['RAM_disposition'])
        if state.get('REC_verified'):current.update(F_only_REC_verified=True,last_F_only_REC_receipt=str(run/'report.json'))
        save(markerpath,current)
    save(run/'report.json',state)
    from serial.tools.list_ports import comports
    with serial_lease('2609-WDC-to-b15-F-only',timeout=30,priority=True):
        assert r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==planning.USB];assert len(ports)==1
        with (run/'serial.jsonl').open('x') as log:
            link=wire.Link(ports[0].device,log,stock=True);selected=False;pcr=None
            def select(value):
                link.protocol(2);link.send((0x7fec).to_bytes(3,'little')+(1).to_bytes(3,'little')+bytes([value]))
                assert link.exact(1)==b'\0' and link.stock_read(0x7fec,1)==bytes([value])
            try:
                print('PROGRESS 1/4: connecting to original 65C816 WDC debugger; no flash mutation',flush=True)
                identity=link.stock_info_after_reset(seconds=45);assert identity[:4]==b'SXB6';durable(run/'WDC-identity.bin',identity)
                pcr=link.stock_read(0x7fec,1)[0];assert pcr&0xee in (0,0xee)
                for bank in (3,0):
                    if bank==0:selected=True;select((pcr&0x11)|0xcc)
                    for n in range(2):
                        data=link.stock_read(0x8000,32768);assert r.sha(data)==info['source_sha256'][bank]
                        durable(run/f'fresh-B{bank}-{n}.bin',data)
                select(pcr);selected=False
                for first,count in ((0x2000,0x2000),(0x6200,0x40),(0x6800,0x1400)):
                    a=link.stock_read(first,count);b=link.stock_read(first,count);assert a==b
                    durable(run/f'RAM-{first:04X}-before.bin',a);durable(run/f'RAM-{first:04X}-repeat.bin',b)
                state.update(source_B0_B3_double_read_verified=True,affected_RAM_escrow_verified=True,phase='source-verified')
                save(run/'report.json',state)
                print('PROGRESS 2/4: fresh B0/B3 double read and RAM escrow passed; device guard will recheck all four banks',flush=True)
                save(run/'wear-reservation.json',dict(board='2609',source='Verified owner-local tracked lower bounds; lifetime history remains unknown',
                    counts_before=info['transaction']['counts_before'],reserved_counts=info['transaction']['reserved_counts'],
                    added_erase_attempts=[dict(bank=3,sector='F',count=1)],onboard_journal_write=False,
                    reserved_before_EXEC=True,plan_sha256=state['plan_sha256']))
                state.update(execution_started=True,physical_reset_pending=True,phase='RAM-migrator-starting');checkpoint()
                print('PROGRESS 3/4: starting exact qualified F-only RAM migrator',flush=True)
                program_and_wait(link,plan,run,state,checkpoint)
                state.update(passed=True,phase='REC-verified-stopped')
            except BaseException:
                state.update(failure=traceback.format_exc(),phase='inspection-required');raise
            finally:
                if selected and not state['execution_started'] and pcr is not None:
                    try:select(pcr)
                    except BaseException:state['bank_select_restore_failure']=traceback.format_exc()
                link.serial.close();state.update(port_released=True,closed=True,finished_utc=now());checkpoint()
    print('RESULT',run/'report.json',flush=True)

if __name__=='__main__':main()
