"""Owner-authorized 2609 RAM-only ES1 preflight and two read-only SRAM exports.

No installer payload is admitted. Offline verification runs in subprocesses;
the live process imports only the existing board transport and file parser.
"""
import argparse,json,re,subprocess,sys,time,traceback
from pathlib import Path
import board_version_caps_2609 as common
import board_config_inspect_2609 as cfg
import edu_sram_backup as backup

io,p=common.io,common.io.p
ROOT,HERE=p.ROOT,p.HERE
SESSION=ROOT/'output/qualification/2609-b15-onboarding-20261027T212009Z'
BIN='2609-EDU-SRAM-PREFLIGHT-RAM.bin'
EDU=b'EDU RO> '


def admit(ready,readback):
    q=p.r.read(ready/'qualification.json');build=Path(q['preflight_build']);basebuild=Path(q['build'])
    for tool,folder in (('prepare_edu_sram_2609.py',basebuild),('prepare_edu_sram_preflight_2609.py',build)):
        result=subprocess.run([sys.executable,str(HERE/tool),'verify','--out',str(folder)],capture_output=True,text=True)
        assert result.returncode==0,'Offline admission failed: '+result.stderr
    assert q['passed'] and q['checks']==48 and q['byte_reproducible'] and not q['hardware']
    assert q['build_sha256']==p.digest(basebuild/'plan.json') and q['preflight_build_sha256']==p.digest(build/'build.json')
    for name,digest in q['sources'].items():assert p.digest(HERE/name)==digest,'Changed source '+name
    for path,digest in q['receipts'].items():assert p.digest(path)==digest,'Changed receipt '+path
    for name,info in q['artifacts'].items():assert p.digest(ready/name)==info['sha256'],'Changed artifact '+name
    image=ready/BIN;assert image.read_bytes()==(build/'payload'/BIN).read_bytes()
    assert image.stat().st_size==2264 and p.digest(image)=='3982b9bfe53a227ac4e64ec076fc1a480be28708e6d21398856c3d912649448d'
    # Reuse the separately hardware-tested, read-only flash/RAM reader.
    _,_,base,_=cfg.admit(SESSION/'step10-CONFIG-build-r1',SESSION/'step10-CONFIG-ready',readback)
    assert base['bank_sha256']==q['source_sha256'] and base['counts']==q['counts_actual'] and base['sequence']==1020
    assert backup.selftest()['passed']
    return q,base,image,build


def chunk(reply,address):
    match=re.fullmatch(rb'R '+f'{address:05X}'.encode()+rb' 40\r\nSTATUS COMPLETED MODE: 00 40 (00|40|80)\r\n((?:[0-9A-F]{2} ){64})\r\nEDU RO> ',reply)
    assert match,'SRAM read/status/count/frame mismatch at '+f'{address:05X}'+': '+repr(reply[:120])
    return bytes.fromhex(match[2].decode('ascii')),int(match[1],16)


def via(reply):
    match=re.fullmatch(rb'V\r\nDDR PCR ACR IFR IER: ((?:[0-9A-F]{2} ){4}[0-9A-F]{2})\r\nEDU RO> ',reply)
    assert match,'VIA inspection framing differs'
    return bytes.fromhex(match[1].decode())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ready',type=Path,required=True)
    parser.add_argument('--readback',type=Path,required=True);parser.add_argument('--run',type=Path)
    parser.add_argument('--admit-only',action='store_true');args=parser.parse_args()
    ready,readback=args.ready.resolve(),args.readback.resolve();q,base,image_path,build=admit(ready,readback)
    if args.admit_only:
        print('PASS admission; exact RAM-only preflight, 48-group kit, readback service and parser; no port opened',flush=True);return
    run=args.run.resolve();assert run.is_relative_to(ROOT/'output/qualification') and not run.exists(),'Fresh private output required'
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E'
    assert marker['MON_A_present'] and marker['MON_B_present'] and marker['VERSION_CAPS_installed'] and marker['journals_initialized']
    assert not any(value for key,value in marker.items() if key.endswith('_worker_active'))
    assert not any(marker.get(key) for key in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running','power_off_reported'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),base['bank_sha256']))
    sessionpath=SESSION/'session.json';session=p.r.read(sessionpath);wearpath=Path(session['wear_history']);wearraw=wearpath.read_bytes()
    wear=json.loads(wearraw);assert wear['counts']==base['counts'] and wear['sequence']==1020 and not session['configuration_changed']
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)];cfg.verify_banks(source,base)
    others={name:(markerpath.parent/(name+'.json')).read_bytes() for name in ('2205','2512','2604') if (markerpath.parent/(name+'.json')).exists()}
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n');io.save(run/'marker-before.json',marker);io.save(run/'session-before.json',session)
    io.atomic(run/'host-wear-before.json',wearraw)
    for name,raw in others.items():io.atomic(run/(name+'-marker-before.json'),raw)
    io.save(run/'authorization.json',dict(board='2609',USB=io.USB,user_text='run 2609-EDU-SRAM-PREFLIGHT-RAM.bin on 2609. take two full SRAM backups and compare them. preserve wear counts and b0, show progress and the console log with file names, return to REC>, then stop before flashing.',
        RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),flash_writes_authorized=False,saved_setting_writes_authorized=False,
        SRAM_writes_authorized=False,SRAM_mode_writes_authorized=False,other_boards_authorized=False,
        conditional_disabled_CB_ack=True,commands=['?','S','V','A only when idle disabled flags pending','R 00000 40 through R 1FFC0 40 twice','Q']))
    state=dict(board='2609',passed=False,hardware=True,started_utc=io.now(),phase='admitted-before-port',RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),
        ready=str(ready),readback=str(readback),baseline=base,flash_written=False,saved_setting_writes=0,SRAM_writes=0,SRAM_mode_writes=0,
        configuration_changed=False,ACIA_board_tested=False,presence_or_capacity_probe_performed=False)
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='EDU-preflight-'+phase,EDU_preflight_worker_active=not state.get('closed',False),EDU_preflight_run=str(run),block_snapshot=True)
        if state.get('final_REC_verified'):current.update(last_EDU_preflight_report=str(run/'report.json'),last_EDU_preflight_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    image=image_path.read_bytes();reader_path=readback/'payload/readback-RAM.bin';reader=reader_path.read_bytes()
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-b15-EDU-SRAM-preflight',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==io.USB];assert len(ports)==1,'Unique 2609 USB required'
        with (run/'serial.jsonl').open('x') as log,(run/'console-log.txt').open('x',encoding='ascii',newline='') as console:
            active_prompt=None
            def note(text):
                line='[HOST] '+text+'\n';console.write(line);console.flush();print(line.rstrip(),flush=True)
            def capture(token,name=None,show=True,seconds=45):
                nonlocal active_prompt
                raw=link.until(token,seconds);raw.decode('ascii')
                active_prompt=token
                if name:io.atomic(run/name,raw)
                console.write(raw.decode('ascii'));console.flush()
                if show:print(raw.decode('ascii').rstrip(),flush=True)
                return raw
            def command(body,token,name=None,show=True):
                nonlocal active_prompt
                if show:note('TX '+repr(body))
                active_prompt=None
                link.send(body);return capture(token,name,show)
            def load(path,body,prompt,name):
                note(f'FILE {path.name}: {len(body)} bytes; SHA-256 {p.r.sha(body)}; raw L at $0200')
                assert command(b'L\r',b'SEND BIN\r\n',name+'-L.txt')==b'L\r\nSEND BIN\r\n'
                for off in range(0,len(body),64):link.send(body[off:off+64]);time.sleep(.01)
                return capture(prompt,name+'-startup.txt')
            def full_read(phase):
                assert command(b'C1\r',io.REC,phase+'-C1.txt')==b'C1\r\nREC> '
                assert load(reader_path,reader,io.SVC,phase+'-readback')==io.SVC
                for repeat in (1,2):
                    banks=[]
                    for bank in range(4):
                        raw=io.service_read(link,b'F'+bytes([bank]),32768);io.atomic(run/f'{phase}-r{repeat}-b{bank}.bin',raw)
                        assert raw==source[bank],f'{phase} B{bank} differs; stop without retry'
                        banks.append(raw);note(f'{phase}-r{repeat}-b{bank}.bin: 32768 bytes, serial CRC verified, SHA-256 {p.r.sha(raw)}')
                    cfg.verify_banks(banks,base)
                memory=io.service_read(link,b'M',0x6300);io.atomic(run/(phase+'-service-RAM.bin'),memory);assert memory[:len(reader)]==reader
            link=p.wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync');note('USB '+ports[0].device+' serial '+io.USB+'; full console: console-log.txt')
                initial=bytearray();last=started=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-started<20
                    raw=link.read(4096)
                    if raw:initial.extend(raw);last=time.monotonic()
                assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in initial)
                if initial:io.atomic(run/'initial-unsolicited.txt',initial);console.write(initial.decode('ascii'))
                assert command(b'\r',io.REC,'initial-REC.txt') in common.IDLE_REPLIES
                note('PROGRESS 1/6: double-read all flash before SRAM inspection; preserve B0 and all journal/wear bytes')
                full_read('before');command(b'J',io.REC,'before-return-REC.txt');state['before_double_read_verified']=True
                checkpoint('source-double-read-verified')
                assert command(b'C1\r',io.REC,'EDU-C1.txt')==b'C1\r\nREC> '
                startup=load(image_path,image,EDU,'EDU-preflight');assert b'ES1 EDU/SRAM RAM PREFLIGHT / READ ONLY / 2609 b15\r\n' in startup
                help_reply=command(b'?\r',EDU,'EDU-help.txt');assert b'No SRAM write, mode change, probe, format or saved EDU switch.' in help_reply
                query=command(b'S\r',EDU,'EDU-software-info.txt');assert b'STATUS COMPLETED MODE: 00 00 FF\r\n' in query and b'physical presence UNPROVEN' in query
                before_via=via(command(b'V\r',EDU,'EDU-VIA-before.txt'));state['VIA_before']=before_via.hex()
                ddr,pcr,acr,ifr,ier=before_via
                assert not (ddr&0x2f or pcr&0xf0 or acr&0x1e or ier&0x18),'SPI pins/CB/shift owner busy; no transfer attempted'
                if ifr&0x18:
                    note('Explicit guarded A: acknowledge idle disabled CB flags once; no SRAM write or GPIO register write')
                    ack=command(b'A\r',EDU,'EDU-disabled-CB-ack.txt');assert b'STATUS COMPLETED MODE: 00 ' in ack
                    prepared=via(command(b'V\r',EDU,'EDU-VIA-prepared.txt'))
                    assert prepared[:3]==before_via[:3] and prepared[4]==ier and prepared[3]==ifr&~0x18
                    state['disabled_CB_ack_performed']=True
                else:state['disabled_CB_ack_performed']=False
                checkpoint('RAM-preflight-ready');note('PROGRESS 2/6: RAM preflight active; read-only interface; starting two 131072-byte exports')
                backups=[];modes=[]
                for repeat in (1,2):
                    destination=run/f'SRAM-pass{repeat}-131072.bin';passlog=run/f'SRAM-pass{repeat}-console.txt';began=time.monotonic();data=bytearray();mode=None
                    note(f'FILE {destination.name}; console {passlog.name}; read 00000-1FFFF in 2048 prompt-paced 64-byte chunks')
                    with passlog.open('xb') as transcript,(run/f'SRAM-pass{repeat}.partial').open('xb') as partial:
                        transcript.write(EDU)
                        for address in range(0,131072,64):
                            reply=command(f'R {address:05X} 40\r'.encode(),EDU,show=False)
                            transcript.write(reply);transcript.flush();body,observed_mode=chunk(reply,address)
                            if mode is None:mode=observed_mode
                            assert observed_mode==mode,'SRAM mode changed during export'
                            data.extend(body);partial.write(body);partial.flush()
                            if len(data)%8192==0:
                                state.update(SRAM_pass=repeat,SRAM_pass_bytes=len(data),SRAM_mode=f'{mode:02X}');checkpoint(f'SRAM-pass{repeat}')
                                note(f'PROGRESS SRAM pass {repeat}/2: {len(data)}/131072 bytes ({len(data)*100//131072}%), mode {mode:02X}, elapsed {time.monotonic()-began:.1f}s')
                        partial.flush()
                    parsed,parsed_mode=backup.parse(passlog.read_bytes());assert parsed==data and parsed_mode==mode
                    io.atomic(destination,data);backups.append(bytes(data));modes.append(mode)
                    note(f'COMPLETE FILE {destination.name}: {len(data)} bytes; SHA-256 {p.r.sha(data)}; mode {mode:02X}; all 2048 replies verified')
                    if repeat==1:note('PROGRESS 3/6: first full SRAM backup complete; starting independent second pass')
                assert backups[0]==backups[1] and modes[0]==modes[1],'Two complete SRAM arrays or modes differ'
                independent=backup.assemble(run/'SRAM-pass1-console.txt',run/'SRAM-pass2-console.txt',run/'backup-verified')
                assert independent['sha256']==p.r.sha(backups[0])
                state.update(SRAM_two_full_backups_verified=True,SRAM_bytes_each=131072,SRAM_sha256=p.r.sha(backups[0]),SRAM_mode=f'{modes[0]:02X}',SRAM_comparison='byte-for-byte identical')
                final_via=via(command(b'V\r',EDU,'EDU-VIA-after.txt'));expected_via=bytearray(before_via);expected_via[3]&=~0x18
                assert final_via==expected_via,'VIA controls or unrelated flags changed';state['VIA_after']=final_via.hex()
                checkpoint('SRAM-backups-identical');note('PROGRESS 4/6: both complete SRAM exports match byte for byte; mode and unrelated VIA state retained')
                command(b'Q\r',io.REC,'EDU-Q-REC.txt')
                # Verify the actually executed immutable RAM image independently.
                command(b'C1\r',io.REC,'RAM-check-C1.txt');command(b'A\r',common.MON,'RAM-check-MON-A.txt')
                dump=command(f'D 0200 {0x200+len(image)-1:04X}\r'.encode(),common.MON,'EDU-device-RAM-dump.txt',show=False)
                loaded=common.parse_dump(dump,0x200,0x200+len(image)-1);io.atomic(run/'EDU-device-RAM.bin',loaded)
                assert loaded==image,'Executed RAM image differs from the exact qualified BIN';state['loaded_RAM_independently_verified']=True
                command(b'J3\r',common.CHOICES,'RAM-check-J3.txt');command(b'S',io.REC,'RAM-check-REC.txt')
                note('PROGRESS 5/6: executed preflight RAM matched; double-read every flash bank again')
                full_read('after');state.update(all_banks_double_read_verified=True,B0_backup_preserved=True,wear_counts_preserved=True,journal_sequence_unchanged=True,default_S_and_banks_disabled=True)
                final=command(b'J',io.REC,'final-REC.txt');assert b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
                state.update(passed=True,final_REC_verified=True,post_final_REC_commands=0,stop_before_flashing_honored=True)
                checkpoint('REC-verified-stopped');note('PROGRESS 6/6: REC> verified; STOP before flashing; no further board commands')
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc())
                if active_prompt==EDU:
                    try:
                        command(b'Q\r',io.REC,'failure-safe-Q-REC.txt');state['failure_returned_REC']=True
                    except BaseException:state['failure_return_exception']=traceback.format_exc()
                checkpoint('inspection-required');raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=io.now());checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle' and wearpath.read_bytes()==wearraw
    for name,raw in others.items():assert (markerpath.parent/(name+'.json')).read_bytes()==raw
    state.update(other_board_markers_unchanged=True,host_wear_history_unchanged=True);io.save(run/'report.json',state)
    session.update(step16='EDU SRAM RAM preflight and two full 128KiB backups completed; identical; returned REC; no flashing',last_completed_step=16,
        step16_report=str(run/'report.json'),step16_console_log=str(run/'console-log.txt'),step16_receipt=str(run/'receipt.md'),
        step16_SRAM_sha256=state['SRAM_sha256'],configuration_changed=False,EDU_SRAM_ROM_installed=False,
        current_stage='F+C/D+MON A/B+VX1 E; EDU SRAM RAM preflight/backup complete; default S, banks disabled; stopped REC',
        next_step='Await next owner-directed step; stopped before EDU ROM installer or any flashing',updated_utc=io.now())
    io.save(sessionpath,session);print('PASS 2609 SRAM preflight and two full identical backups; REC; no flashing',flush=True)


if __name__=='__main__':main()
