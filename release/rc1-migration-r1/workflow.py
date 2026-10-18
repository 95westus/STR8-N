"""Portable explicit-port empty-bank migration workflow and durable recovery data."""
import hashlib,json,time
from pathlib import Path
import migrate as m
import runtime as r
import factory_wdc
import install_transport
import legacy_transport as wire

def save(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush()
        import os;os.fsync(stream.fileno())
    temporary.replace(path)

def gate(kit):
    manifest=m.verify_kit(kit)
    r.require(manifest['live_installation_enabled'] is True,'This kit has no admitted live workflow; no port was opened')
    qualification=r.read(kit/'hardware-qualification.json')
    r.require(qualification['prior_engine_hardware_passed'] and qualification['target_model_passed'] and qualification['portable_transport_tests_passed'],
        'Missing route/transport qualification; no port was opened')
    for name,digest in qualification['required_files'].items():
        r.require(r.sha(m.safe(kit,name).read_bytes())==digest,'Changed qualified runtime/payload; no port was opened')
    return manifest

def selected_port(port,usb_serial):
    r.require(bool(port) and bool(usb_serial),'Explicit port and USB serial required')
    from serial.tools.list_ports import comports
    matches=[p for p in comports() if p.device==port and p.serial_number==usb_serial]
    r.require(len(matches)==1,'Selected port/USB identity mismatch; no port was opened')
    return port

def prompt(link):
    time.sleep(.3);link.pending.clear();link.serial.reset_input_buffer()
    text=link.command('',b'> ')
    if any(v in text for v in (b'CLOCK>',b'BM>',b'EDU>',b'SRAM>',b'WORK>')):link.command('Q',b'> ')
    return link.command('B3')

def capture_empty(link,board,out,stock,usb_serial=None):
    """B3 is independently read twice; B0-B2 are assumptions checked by RAM preflight."""
    m.board_identity(board);r.require(not out.exists(),'Capture output exists');out.mkdir(parents=True)
    first=link.stock_read(0x8000,32768) if stock else link.dump(0x8000,0xffff)
    repeat=link.stock_read(0x8000,32768) if stock else link.dump(0x8000,0xffff)
    r.require(first==repeat and len(first)==32768,'Independent source B3 reads differ; no installer executed')
    files={}
    for n,body in enumerate([b'\xff'*32768]*3+[first]):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(out/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    identity=dict(schema=2,board=board,usb_serial=usb_serial,repeat_verified=False,assumed_erased_banks=[0,1,2],
        independently_repeated_banks=[3],device_full_bank_preflight_required=True,files=files)
    save(out/'capture.json',identity)
    # One archive, no restoration into the native WDC debugger's live stack.
    original=link.stock_read(0x200,0x6300) if stock else b''.join(link.dump(a,min(a+4095,0x64ff)) for a in range(0x200,0x6500,4096))
    r.require(len(original)==0x6300,'Incomplete application RAM archive')
    (out/'application-ram.bin').write_bytes(original)
    (out/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(original,0x200)),0x200))
    for name in ('application-ram.bin','restore-application-ram.s19'):
        body=(out/name).read_bytes();files[name]=dict(bytes=len(body),sha256=r.sha(body))
    save(out/'capture.json',identity)
    return identity

def restore_ram(link,archive,host_readback):
    path=archive/'restore-application-ram.s19';body=(archive/'application-ram.bin').read_bytes()
    manifest=r.read(archive/'capture.json')
    for name in ('application-ram.bin','restore-application-ram.s19'):
        data=(archive/name).read_bytes();info=manifest['files'][name]
        r.require(len(data)==info['bytes'] and r.sha(data)==info['sha256'],'Changed RAM archive')
    link.command('L',b'S19')
    for row in path.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
    text=link.until(b'\r\nB3> ')
    r.require(b'Entry 0200' in text and not any(v in text for v in (b'Bad',b'Protected',b'Wrap',b'Error')),'Application RAM archive load failed')
    if host_readback:
        actual=b''.join(link.dump(a,min(a+4095,0x64ff)) for a in range(0x200,0x6500,4096))
        r.require(actual==body,'Application RAM restoration mismatch')
    return dict(write_completed=True,loader_acknowledged=True,host_verified=host_readback,sha256=r.sha(body))

def install(route,kit,port,usb_serial,board,out,*,empty_banks=False,unknown_wear=False,host_readback=True,ask=input):
    gate(kit);m.board_identity(board)
    r.require(route in ('wdcmonv2','beta4') and empty_banks,'Live routes require explicit --empty-banks (erased B0/B1/B2)')
    if route=='wdcmonv2':r.require(unknown_wear,'Factory source requires --accept-unknown-wear-history')
    selected_port(port,usb_serial);r.require(not out.exists(),'Choose a fresh private --out directory');out.mkdir(parents=True)
    (out/'.gitignore').write_text('*\n');state=dict(board=board,route=route,passed=False,port=port,usb_serial=usb_serial,
        clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,host_memory_readbacks=host_readback,
        B0_B1_B2_admission='Assumed erased; checked across all banks by RAM preflight before any flash write',
        physical_reset_pending=False,application_RAM_restore_pending=False)
    def checkpoint():save(out/'workflow.json',state)
    checkpoint();link=None;stock=route=='wdcmonv2'
    with (out/'serial.jsonl').open('x') as log:
        try:
            link=wire.Link(port,log,stock=stock)
            if stock:
                print('Debugger armed. Press physical RESET now; keep power on.',flush=True)
                identity=link.stock_info_after_reset(seconds=240);r.require(identity[:4] in (b'SXB2',b'SXB6'),'Unsupported source hardware')
                qualification=r.read(kit/'hardware-qualification.json')
                r.require(identity[:4].decode() in qualification['live_WDC_debugger_identities'],'This WDC source has no admitted live hardware route in this kit')
                state['stock_identity_hex']=identity.hex()
            else:prompt(link)
            cap=out/'capture';capture_empty(link,board,cap,stock,usb_serial)
            plan_root=out/'plan'
            if stock:
                plan=factory_wdc.prepare(cap,kit,plan_root,accept_unknown_history=True)
                expected_id=b'SXB6' if plan['source_cpu']=='65C816' else b'SXB2'
                r.require(bytes.fromhex(state['stock_identity_hex'])[:4]==expected_id,'Source CPU/profile identity mismatch')
                factory_wdc.validate_plan(plan_root,kit)
            else:plan=m.prepare_beta4(cap,kit,plan_root);m.validate_beta4_plan(plan_root,kit)
            state.update(plan_sha256=r.sha((plan_root/'plan.json').read_bytes()));checkpoint()
            print('Exact source admitted. B0 stays erased; RAM tool installs all rc1 providers, MON A/B and UCHESS.',flush=True)
            if ask('Type INSTALL RC1 to proceed: ').strip()!='INSTALL RC1':
                state['canceled']=True;checkpoint();return state
            def progress(n,op):
                state['transfers_completed']=n;checkpoint();print(f"Verified transfer request {n}: B{op['bank']}:{op['address']>>12:X}",flush=True)
            state['application_RAM_restore_pending']=True;checkpoint()
            result=install_transport.execute(link,plan_root,stock=stock,host_readback=host_readback,progress=progress)
            state.update(result);checkpoint();link.serial.close();link=None
            ask('Device verification passed. Press physical RESET once, keep power on, then press Enter: ')
            time.sleep(2);link=wire.Link(port,log);prompt(link)
            link.send(b'VERSION\r');version=link.until(b'STR8-N 2.0rc1')
            # VERSION may include an early prompt left by a previous command.
            # Collect through the final bank prompt, then inspect the full text.
            version+=link.until(b'\r\nB3> ');(out/'version.txt').write_bytes(version)
            r.require(b'2.0rc1' in version,'Target rc1 boot not confirmed')
            listing=link.command('T 1');(out/'stored-apps.txt').write_bytes(listing);r.require(b'UCHESS' in listing,'UCHESS not discovered')
            r.require(r.sha((cap/'capture.json').read_bytes())==plan['capture_manifest_sha256'],'Changed original RAM/capture binding')
            restore=restore_ram(link,cap,host_readback);save(out/'RAM-restoration.json',restore)
            state.update(passed=True,physical_reset_pending=False,application_RAM_restore_pending=False,
                boot_verified=True,RAM_restoration=restore,RTC_preservation_qualified=False);checkpoint()
            print('PASS full rc1 tool/boot and RAM archive restoration. Keep all private recovery files. No clock/trim setter was issued.',flush=True)
            return state
        except BaseException as error:
            state.update(error=str(error),inspection_required=True);checkpoint();raise
        finally:
            if link:link.serial.close()

def capture_monitor(kit,port,usb_serial,board,out):
    gate(kit);m.board_identity(board);selected_port(port,usb_serial)
    r.require(not out.exists(),'Choose a fresh capture directory');out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    files={}
    with (out/'serial.jsonl').open('x') as log:
        link=wire.Link(port,log)
        try:
            prompt(link)
            for repeat in range(2):
                for bank in range(4):
                    bp=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',bp)
                    body=link.dump(0x8000,0xffff,bp);name=f'b{bank}'+('-repeat' if repeat else '')+'.bin'
                    if repeat:r.require(body==(out/f'b{bank}.bin').read_bytes(),'Repeated flash capture differs')
                    (out/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
            link.command('B3');body=b''.join(link.dump(a,min(a+4095,0x64ff)) for a in range(0x200,0x6500,4096))
            (out/'application-ram.bin').write_bytes(body)
            (out/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(body,0x200)),0x200))
            for name in ('application-ram.bin','restore-application-ram.s19'):
                data=(out/name).read_bytes();files[name]=dict(bytes=len(data),sha256=r.sha(data))
            save(out/'capture.json',dict(schema=1,board=board,usb_serial=usb_serial,repeat_verified=True,files=files))
        finally:link.serial.close()
    print('PASS repeated flash/source and application RAM archive; no flash, RTC, EEPROM or SRAM writes',flush=True)

def recovery_live(operation,kit,original,current,out,port,usb_serial,board,*,host_readback=True,ask=input):
    gate(kit);m.board_identity(board)
    import recover
    identity,_=m.capture(current);r.require(identity['board']==board and identity.get('usb_serial')==usb_serial,'Recovery board/USB capture mismatch')
    original_identity=r.read(original/'source-capture.json')
    r.require(original_identity.get('usb_serial')==usb_serial,'Recovery USB identity differs from original live capture')
    plan=recover.prepare_recovery('prepare-'+operation,kit,original,current,out)
    if plan.get('write_required') is False:
        print('No write required by supplied capture; no port was opened. This is a capture-based receipt.',flush=True);return plan
    original_ram=original.parent/'capture';original_plan=r.read(original/'plan.json')
    r.require(r.sha((original_ram/'capture.json').read_bytes())==original_plan['capture_manifest_sha256'],'Original application RAM capture is missing or changed')
    for name in ('application-ram.bin','restore-application-ram.s19'):
        body=(original_ram/name).read_bytes();info=original_identity['files'][name]
        r.require(len(body)==info['bytes'] and r.sha(body)==info['sha256'],'Original application RAM archive is missing or changed')
    selected_port(port,usb_serial)
    if ask('Type RECOVER RC1 to execute this bound forward/restoration plan: ').strip()!='RECOVER RC1':return dict(canceled=True)
    with (out/'serial.jsonl').open('x') as log:
        link=wire.Link(port,log)
        try:
            prompt(link);result=install_transport.execute(link,out,host_readback=host_readback)
        finally:link.serial.close()
        save(out/'device-result.json',result)
        ask('Device recovery verified. Press physical RESET, keep power on, then press Enter: ')
        time.sleep(2);link=wire.Link(port,log)
        try:
            prompt(link)
            r.require(r.sha((original_ram/'capture.json').read_bytes())==original_plan['capture_manifest_sha256'],'Changed original RAM capture binding')
            restored=restore_ram(link,original_ram,host_readback);save(out/'RAM-restoration.json',restored)
        finally:link.serial.close()
    print('PASS bounded recovery tool and application RAM restoration; retain all evidence',flush=True)
    return result
