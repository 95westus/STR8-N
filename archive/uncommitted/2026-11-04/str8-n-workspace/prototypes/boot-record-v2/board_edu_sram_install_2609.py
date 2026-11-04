"""Owner-authorized exact ES1 install; preserve SRAM and boot policy; stop REC.

Only the previously qualified RAM installer can write flash. Verification uses
the read-only RAM preflight, installed-provider client and full-bank reader.
Offline builders run in subprocesses, never in this live process.
"""
import argparse,json,sys,time,traceback
from pathlib import Path
import board_edu_sram_preflight_2609 as pre
import edu_sram_backup as backup

io,p,common=pre.io,pre.p,pre.common
ROOT,HERE,SESSION=pre.ROOT,pre.HERE,pre.SESSION
INSTALLER='2609-EDU-SRAM-INSTALL-RAM.bin'
CLIENT='2609-EDU-SRAM-RAM.bin'
PROVIDER='2609-EDU-SRAM-B3-8.bin'
MENU=b'RAM MINSTALL ? V W I Q> '


def admit(ready,readback,prior):
    q,base,ram_preflight,prebuild=pre.admit(ready,readback)
    build=Path(q['build']);plan=p.r.read(build/'plan.json')
    assert plan['BIN']==INSTALLER and plan['confirmation']=='INSTALL EDU' and plan['erase_order']==['B3:8000']
    assert plan['counts_after']==[n+(i==24) for i,n in enumerate(plan['counts_before'])]
    assert plan['counts_before']==base['counts'] and plan['counts_after'][24]==27
    assert plan['sequence_before']==1020 and plan['sequence_after']==1021 and plan['default']=='S' and plan['enabled_banks']==0
    for name,key in ((INSTALLER,'BIN_sha256'),(CLIENT,'client_sha256'),(PROVIDER,'provider_sha256')):
        assert (ready/name).read_bytes()==(build/'payload'/name).read_bytes() and p.digest(ready/name)==plan[key]
    report=p.r.read(prior/'report.json');audit=p.r.read(prior/'audit.json');close=p.r.read(prior/'closeout.json')
    assert report['passed'] and audit['passed'] and close['passed'] and report['final_REC_verified'] and report['port_released']
    assert audit['report_sha256']==close['report_sha256']==p.digest(prior/'report.json') and close['audit_sha256']==p.digest(prior/'audit.json')
    arrays=[]
    for repeat in (1,2):
        path=prior/f'SRAM-pass{repeat}-131072.bin';raw=path.read_bytes();assert len(raw)==131072
        parsed,mode=backup.parse((prior/f'SRAM-pass{repeat}-console.txt').read_bytes());assert raw==parsed and mode==0x40
        assert p.r.sha(raw)==report['SRAM_sha256']==audit['SRAM_sha256'];arrays.append(raw)
    assert arrays[0]==arrays[1]
    return q,plan,base,build,ram_preflight,arrays


def verify_post(banks,plan,source,expected):
    assert p.r.hashes(banks)==plan['expected_sha256'] and banks==expected
    assert banks[:3]==source[:3] and p.r.sha(banks[0])==p.WDC_SHA
    assert banks[3][0x1000:0x4600]==source[3][0x1000:0x4600] and banks[3][0x4700:]==source[3][0x4700:]
    records=p.snbt_records(banks);seq,offset,row=max(records)
    assert len(records)==8 and seq==1021 and offset==0x4600 and row[7]==ord('S') and row[13]==0
    assert row[32:48].hex()==plan['config'] and row[160:164]==b'\xff'*4
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==plan['counts_after']
    assert banks[3][:4096]==expected[3][:4096] and p.wire.crc(banks[3][:4096])==0 and banks[3][31]==0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ready','readback','prior'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--run',type=Path);parser.add_argument('--admit-only',action='store_true');args=parser.parse_args()
    ready,readback,prior=(getattr(args,n).resolve() for n in ('ready','readback','prior'))
    q,plan,base,build,preflight_path,originals=admit(ready,readback,prior)
    if args.admit_only:
        print('PASS admission: exact 6760-byte installer; ES1/client; 48-check kit; both 131072-byte hardware backups; one B3:8 erase reserved 26->27',flush=True);return
    run=args.run.resolve();assert run.is_relative_to(ROOT/'output/qualification') and not run.exists()
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E'
    assert marker['EDU_SRAM_preflight_verified'] and not marker['EDU_SRAM_ROM_installed']
    assert not any(value for key,value in marker.items() if key.endswith('_worker_active'))
    assert not any(marker.get(key) for key in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running','power_off_reported'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),plan['source_sha256']))
    sessionpath=SESSION/'session.json';session=p.r.read(sessionpath);oldwear_path=Path(session['wear_history']);oldwear=oldwear_path.read_bytes()
    history=json.loads(oldwear);assert history['sequence']==1020 and history['counts']==plan['counts_before'] and not session['configuration_changed']
    assert p.digest(oldwear_path)==p.r.read(prior/'audit.json')['host_wear_sha256']
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)];expected=[(build/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    pre.cfg.verify_banks(source,base);verify_post(expected,plan,source,expected)
    others={name:(markerpath.parent/(name+'.json')).read_bytes() for name in ('2205','2512','2604') if (markerpath.parent/(name+'.json')).exists()}
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n');io.save(run/'marker-before.json',marker);io.save(run/'session-before.json',session);io.atomic(run/'host-wear-before.json',oldwear)
    for name,raw in others.items():io.atomic(run/(name+'-marker-before.json'),raw)
    io.save(run/'authorization.json',dict(board='2609',USB=io.USB,user_text='run 2609-EDU-SRAM-INSTALL-RAM.bin on 2609. preserve my wear counts, b0 and SRAM. show progress and console log with file names, verify the provider and SRAM against both backups, return to REC>, then stop before config changes.',
        installer=str(ready/INSTALLER),installer_sha256=plan['BIN_sha256'],plan_sha256=p.digest(build/'plan.json'),
        flash_erases=['B3:8'],journal_appends=['C600'],C_D_erases=False,F_write=False,B0_write=False,
        configuration_changes_authorized=False,SRAM_writes_authorized=False,SRAM_mode_writes_authorized=False,other_boards_authorized=False,
        original_SRAM_backups=[str(prior/f'SRAM-pass{n}-131072.bin') for n in (1,2)],SRAM_sha256=p.r.sha(originals[0])))
    state=dict(board='2609',hardware=True,passed=False,started_utc=io.now(),phase='admitted-before-port',ready=str(ready),build=str(build),readback=str(readback),prior=str(prior),
        plan_sha256=p.digest(build/'plan.json'),installer_sha256=plan['BIN_sha256'],provider_sha256=plan['provider_sha256'],client_sha256=plan['client_sha256'],
        source_sha256=plan['source_sha256'],expected_sha256=plan['expected_sha256'],counts_before=plan['counts_before'],counts_planned=plan['counts_after'],
        sequence_before=1020,sequence_planned=1021,confirmation_sent=False,flash_device_verified=False,all_banks_double_read_verified=False,
        configuration_changed=False,saved_setting_writes=0,SRAM_writes=0,SRAM_mode_writes=0,ACIA_board_tested=False,original_SRAM_sha256=p.r.sha(originals[0]))
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='EDU-install-'+phase,EDU_install_worker_active=not state.get('closed',False),EDU_install_run=str(run),block_snapshot=True)
        if state['flash_device_verified']:current.update(EDU_SRAM_ROM_installed=True,current_firmware_profile='b15-VX1-ES1-F-CD-MON-AB-E-8',firmware='2.0proto b15 VX1 ES1 F + C/D + MON A/B + E + B3:8')
        if state['all_banks_double_read_verified']:current['current_physical_bank_sha256']=dict(zip(('B0','B1','B2','B3'),plan['expected_sha256']))
        if state.get('final_REC_verified'):current.update(last_EDU_install_report=str(run/'report.json'),last_EDU_install_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    reader_path=readback/'payload/readback-RAM.bin';reader=reader_path.read_bytes();installer=(ready/INSTALLER).read_bytes();client=(ready/CLIENT).read_bytes()
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-b15-EDU-SRAM-install',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==io.USB];assert len(ports)==1,'Unique 2609 USB required'
        with (run/'serial.jsonl').open('x') as log,(run/'console-log.txt').open('x',encoding='ascii',newline='') as console:
            active_prompt=None
            def note(text):
                line='[HOST] '+text+'\n';console.write(line);console.flush();print(line.rstrip(),flush=True)
            def capture(token,name=None,show=True,stream=False):
                nonlocal active_prompt
                raw=io.wait_text(link,token,90) if stream else link.until(token,90)
                raw.decode('ascii');active_prompt=token
                if name:io.atomic(run/name,raw)
                console.write(raw.decode('ascii'));console.flush()
                if show and not stream:print(raw.decode('ascii').rstrip(),flush=True)
                return raw
            def command(body,token,name=None,show=True,stream=False):
                nonlocal active_prompt
                if show:note('TX '+repr(body))
                active_prompt=None;link.send(body);return capture(token,name,show,stream)
            def load(path,body,prompt,name,stream=False):
                note(f'FILE {path.name}: {len(body)} bytes; SHA-256 {p.r.sha(body)}; raw L at $0200')
                assert command(b'L\r',b'SEND BIN\r\n',name+'-L.txt')==b'L\r\nSEND BIN\r\n'
                for off in range(0,len(body),64):link.send(body[off:off+64]);time.sleep(.01)
                return capture(prompt,name+'-startup.txt',stream=stream)
            def full_read(phase,want):
                assert command(b'C1\r',io.REC,phase+'-C1.txt')==b'C1\r\nREC> '
                assert load(reader_path,reader,io.SVC,phase+'-readback')==io.SVC
                for repeat in (1,2):
                    banks=[]
                    for bank in range(4):
                        raw=io.service_read(link,b'F'+bytes([bank]),32768);io.atomic(run/f'{phase}-r{repeat}-b{bank}.bin',raw)
                        assert raw==want[bank],f'{phase} B{bank} differs; stop without retry';banks.append(raw)
                        note(f'{phase}-r{repeat}-b{bank}.bin: 32768 bytes, serial CRC verified, SHA-256 {p.r.sha(raw)}')
                    pre.cfg.verify_banks(banks,base) if phase=='before' else verify_post(banks,plan,source,expected)
                memory=io.service_read(link,b'M',0x6300);io.atomic(run/(phase+'-service-RAM.bin'),memory);assert memory[:len(reader)]==reader
            def sram_setup(prefix):
                help_reply=command(b'?\r',pre.EDU,prefix+'-help.txt');assert b'No SRAM write, mode change, probe, format or saved EDU switch.' in help_reply
                query=command(b'S\r',pre.EDU,prefix+'-info.txt');assert b'STATUS COMPLETED MODE: 00 00 FF\r\n' in query and b'physical presence UNPROVEN' in query
                v=pre.via(command(b'V\r',pre.EDU,prefix+'-VIA-before.txt'));ddr,pcr,acr,ifr,ier=v
                assert not (ddr&0x2f or pcr&0xf0 or acr&0x1e or ier&0x18),'SPI/VIA owner busy'
                if ifr&0x18:
                    ack=command(b'A\r',pre.EDU,prefix+'-disabled-CB-ack.txt');assert b'STATUS COMPLETED MODE: 00 ' in ack
                    after=pre.via(command(b'V\r',pre.EDU,prefix+'-VIA-prepared.txt'));assert after[:3]==v[:3] and after[4]==ier and after[3]==ifr&~0x18
                    state[prefix+'_disabled_CB_ack']=True
                else:state[prefix+'_disabled_CB_ack']=False
                state[prefix+'_VIA_before']=v.hex();return v
            def sram_pass(prefix):
                note(f'FILE {prefix}-131072.bin; full console {prefix}-console.txt; comparing each chunk against BOTH original backups')
                data=bytearray();began=time.monotonic()
                with (run/(prefix+'-console.txt')).open('xb') as transcript,(run/(prefix+'.partial')).open('xb') as partial:
                    transcript.write(pre.EDU)
                    for address in range(0,131072,64):
                        reply=command(f'R {address:05X} 40\r'.encode(),pre.EDU,show=False);transcript.write(reply);transcript.flush()
                        body,mode=pre.chunk(reply,address);assert mode==0x40
                        assert all(body==old[address:address+64] for old in originals),'SRAM differs from an original backup at '+f'{address:05X}'
                        data.extend(body);partial.write(body);partial.flush()
                        if len(data)%8192==0:
                            state.update(SRAM_pass=prefix,SRAM_pass_bytes=len(data));checkpoint(prefix)
                            note(f'PROGRESS {prefix}: {len(data)}/131072 bytes ({len(data)*100//131072}%), mode 40; BOTH backups match; elapsed {time.monotonic()-began:.1f}s')
                parsed,mode=backup.parse((run/(prefix+'-console.txt')).read_bytes());assert parsed==data==originals[0]==originals[1] and mode==0x40
                io.atomic(run/(prefix+'-131072.bin'),data);note(f'COMPLETE FILE {prefix}-131072.bin: 131072 bytes; SHA-256 {p.r.sha(data)}; identical to BOTH original backups')
                return bytes(data)
            def via_finish(prefix,before):
                after=pre.via(command(b'V\r',pre.EDU,prefix+'-VIA-after.txt'));want=bytearray(before);want[3]&=~0x18
                assert after==want;state[prefix+'_VIA_after']=after.hex()
            link=p.wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync');note('USB '+ports[0].device+' serial '+io.USB+'; complete console-log.txt')
                initial=bytearray();last=started=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-started<20
                    raw=link.read(4096)
                    if raw:initial.extend(raw);last=time.monotonic()
                assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in initial)
                if initial:io.atomic(run/'initial-unsolicited.txt',initial);console.write(initial.decode('ascii'))
                assert command(b'\r',io.REC,'initial-REC.txt') in common.IDLE_REPLIES
                note('PROGRESS 1/8: double-read source flash; exact B0, F, journals and all counts required before install')
                full_read('before',source);command(b'J',io.REC,'before-return-REC.txt');state['fresh_source_double_read_verified']=True
                command(b'C1\r',io.REC,'preflight-C1.txt');assert b'RAM PREFLIGHT' in load(preflight_path,preflight_path.read_bytes(),pre.EDU,'preflight')
                v=sram_setup('preflight');note('PROGRESS 2/8: fresh full SRAM read before erase; compare with both saved backups')
                sram_pass('SRAM-before-install');via_finish('preflight',v);command(b'Q\r',io.REC,'preflight-Q-REC.txt');state['fresh_SRAM_matches_both_backups']=True
                command(b'C1\r',io.REC,'installer-C1.txt');launch=load(ready/INSTALLER,installer,MENU,'installer',stream=True)
                assert b'2609 RAM EDU/SRAM READ-ONLY INSTALL / b15 F / USB only\r\n' in launch
                assert all(f'B{n} OK\r\n'.encode() in launch for n in range(4))
                wear=command(b'W\r',MENU,'installer-W.txt')
                for bank in range(4):
                    for label,counts in (('before',plan['counts_before']),('planned',plan['counts_after'])):
                        assert (f'B{bank} {label}: '+' '.join(map(str,counts[8*bank:8*bank+8]))).encode() in wear
                io.save(run/'wear-reservation.json',dict(board='2609',created_utc=io.now(),durable_before_confirmation=True,counts_before=plan['counts_before'],
                    reserved_counts=plan['counts_after'],erase_order=['B3:8'],journal_append='C600',sequence_reserved=1021,source_history=str(oldwear_path),
                    plan_sha256=state['plan_sha256'],unknown_history_mask='ffffffff',C_D_erases=0,F_erases=0,
                    semantics='Reserve one B3:8 erase attempt; never roll counts back on interruption'))
                note('PROGRESS 3/8: durable wear-reservation.json; B3:8 26->27 only; embedded FILE 2609-EDU-SRAM-B3-8.bin; C600 reservation first')
                assert command(b'I\r',b'then Enter> ','installer-confirm.txt')==b'I\r\nType INSTALL EDU then Enter> '
                state['confirmation_sent']=True;checkpoint('flash-confirmation-ready')
                result=command(b'INSTALL EDU\r',MENU,'installer-result.txt',stream=True)
                assert result.find(b'C600\r\n')>=0 and result.find(b'8000\r\n')>result.find(b'C600\r\n')
                assert result.count(b'erase sector; verify blank\r\n')==1 and result.count(b'committed; entire action readback VERIFIED\r\n')==2
                assert b'ALL COMPONENTS VERIFIED; default S recovery; B0 and F preserved\r\n' in result
                verified=command(b'V\r',MENU,'installer-V.txt',stream=True);assert all(f'B{n} OK\r\n'.encode() in verified for n in range(4))
                state['flash_device_verified']=True;checkpoint('provider-device-verified');command(b'Q\r',io.REC,'installer-Q-REC.txt')
                note('PROGRESS 4/8: installer verified reservation/provider; double-read all banks against exact expected images')
                full_read('after-install',expected);command(b'J',io.REC,'after-install-return-REC.txt');state['all_banks_double_read_verified']=True
                io.atomic(run/'2609-EDU-SRAM-B3-8-device.bin',expected[3][:4096]);state['provider_independent_readback_verified']=True;checkpoint('provider-independently-verified')
                command(b'C1\r',io.REC,'client-C1.txt');assert b'ES1 EDU/SRAM READ ONLY / 2609 b15\r\n' in load(ready/CLIENT,client,pre.EDU,'client')
                v=sram_setup('client');note('PROGRESS 5/8: installed-provider client active; two full SRAM passes against both original backups')
                after1=sram_pass('SRAM-after-pass1');after2=sram_pass('SRAM-after-pass2');assert after1==after2==originals[0]==originals[1]
                backup.assemble(run/'SRAM-after-pass1-console.txt',run/'SRAM-after-pass2-console.txt',run/'SRAM-after-verified')
                via_finish('client',v);state.update(SRAM_two_post_install_full_reads_verified=True,SRAM_matches_both_original_backups=True,SRAM_sha256=p.r.sha(after1),SRAM_mode='40')
                checkpoint('SRAM-preservation-verified');command(b'Q\r',io.REC,'client-Q-REC.txt')
                note('PROGRESS 6/8: full retained SRAM/mode preserved; independently read back executed client')
                command(b'C1\r',io.REC,'RAM-check-C1.txt');command(b'A\r',common.MON,'RAM-check-MON-A.txt')
                dump=command(f'D 0200 {0x200+len(client)-1:04X}\r'.encode(),common.MON,'client-device-RAM-dump.txt',show=False)
                loaded=common.parse_dump(dump,0x200,0x200+len(client)-1);io.atomic(run/'client-device-RAM.bin',loaded)
                sy=p.r.read(build/'symbols.json')['core/edu-client'];immutable=sy['EC_IMM_END']-0x200
                assert loaded[:immutable]==client[:immutable] and loaded[sy['EC_ERROR']-0x200]==0
                state.update(client_immutable_RAM_verified=True,client_immutable_bytes=immutable,client_mutable_tail_bytes=len(client)-immutable)
                command(b'J3\r',common.CHOICES,'RAM-check-J3.txt');command(b'S',io.REC,'RAM-check-REC.txt')
                note('PROGRESS 7/8: final double-read flash after provider/SRAM exercise; verify only B3:8 and C600 changed')
                full_read('final',expected)
                final=command(b'J',io.REC,'final-REC.txt');assert b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
                state.update(passed=True,final_REC_verified=True,post_final_REC_commands=0,B0_backup_preserved=True,prior_counts_retained=True,
                    counts_after=plan['counts_after'],sequence_after=1021,actual_erase_order=['B3:8'],C_D_erases=0,saved_configuration_unchanged=True,
                    default_S_and_banks_disabled=True,stop_before_configuration_honored=True)
                checkpoint('REC-verified-stopped');note('PROGRESS 8/8: REC> verified; STOP before configuration changes; no further board commands')
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc())
                if active_prompt==pre.EDU:
                    try:command(b'Q\r',io.REC,'failure-safe-Q-REC.txt');state['failure_returned_REC']=True
                    except BaseException:state['failure_return_exception']=traceback.format_exc()
                checkpoint('inspection-required');raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=io.now());checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert oldwear_path.read_bytes()==oldwear and p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    for name,raw in others.items():assert (markerpath.parent/(name+'.json')).read_bytes()==raw
    for n in (1,2):assert (prior/f'SRAM-pass{n}-131072.bin').read_bytes()==originals[n-1]
    state.update(other_board_markers_unchanged=True,original_SRAM_backups_unchanged=True,prior_host_wear_record_unchanged=True);io.save(run/'report.json',state)
    wear=dict(schema=1,board='2609',counts=plan['counts_after'],sequence=1021,config=plan['config'],history_unknown_mask='ffffffff',
        semantics='Verified tracked lower bounds; prior lifetime wear remains unknown',source_history=str(oldwear_path),
        added_erase_attempts=[dict(bank=3,sector='8',count=1)],device_erase_program_verify_passed=True,independent_all_bank_double_read_passed=True,
        onboard_journal_initialized=True,execution_report=str(run/'report.json'),execution_report_sha256=p.digest(run/'report.json'))
    io.save(run/'host-wear-after.json',wear)
    current=p.r.read(markerpath);current.update(last_tracked_wear_host_record=str(run/'host-wear-after.json'),EDU_SRAM_ROM_installed=True,EDU_SRAM_preservation_verified=True)
    io.save(markerpath,current)
    session.update(step17='ES1 B3:8 installed; provider and full SRAM verified against both backups; returned REC; no config change',last_completed_step=17,
        step17_report=str(run/'report.json'),step17_console_log=str(run/'console-log.txt'),step17_receipt=str(run/'receipt.md'),step17_SRAM_sha256=state['SRAM_sha256'],
        wear_history=str(run/'host-wear-after.json'),configuration_changed=False,EDU_SRAM_ROM_installed=True,
        current_stage='F+C/D+MON A/B+VX1 E+ES1 B3:8; default S; banks disabled; seq1021; stopped REC',
        next_step='Await next owner-directed step; stopped before configuration changes',updated_utc=io.now())
    io.save(sessionpath,session);print('PASS ES1 install; SRAM matches both originals; REC; no configuration changes',flush=True)


if __name__=='__main__':main()
