"""USB user demonstration of F; no flash or saved-setting command path."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
import board_version_caps_2609 as common
import board_config_inspect_2609 as cfgcommon
io=common.io
p=io.p
ROOT,HERE=p.ROOT,p.HERE
WAIT=b'Press one key to test input> '
HELP=b'L=0200 ^C=cancel idle3s\r\nA/B 0-3 C1USB/2ACIA/3both\r\n'


def admit(build,ready,readback):
    result=subprocess.run([sys.executable,str(HERE/'prepare_f_user_demo_2609.py'),'verify','--out',str(build)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    q=p.r.read(ready/'qualification.json');assert q['passed'] and q['checks']==8 and q['byte_reproducible']
    oldbuild=build.parent/'step10-CONFIG-build-r1';oldready=build.parent/'step10-CONFIG-ready'
    _,_,base,_=cfgcommon.admit(oldbuild,oldready,readback)
    assert q['baseline']==base and q['F_sha256']==base['F_sha256']
    image=ready/'b15-F-DEMO-RAM.bin'
    assert image.read_bytes()==(build/'payload'/image.name).read_bytes() and p.digest(image)==q['sha256']
    assert image.stat().st_size==q['bytes']==485
    for name in ('golden-startup-65c816-e.txt','golden-result-65c816-e.txt','executed-RAM-65c816-e.bin'):
        assert (ready/name).is_file()
    return q,q,base,image


def verify_banks(banks,base):
    assert p.r.hashes(banks)==base['bank_sha256'] and p.r.sha(banks[0])==p.WDC_SHA
    records=p.snbt_records(banks);seq,off,row=max(records,key=lambda r:r[0])
    assert len(records)==7 and seq==base['sequence']==1020
    assert row[7]==ord('S') and row[13]==0 and row[14:18]==b'\x08'*4
    assert row[32:48].hex()==base['config'] and row[160:164]==b'\xff'*4
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==base['counts']
    return dict(sequence=seq,record_count=len(records),default='S',enabled_banks=0,counts=base['counts'],B0_sha256=p.WDC_SHA)


def verify_loaded(raw,build,ready,cpu='65c816-e'):
    assert raw==(build/f'executed-RAM-{cpu}.bin').read_bytes()==(ready/f'executed-RAM-{cpu}.bin').read_bytes()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','ready','readback','run'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build,ready,readback,run=(getattr(args,n).resolve() for n in ('build','ready','readback','run'))
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists(),'Fresh run required'
    info,q,base,image_path=admit(build,ready,readback)
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E'
    assert marker['MON_A_present'] and marker['MON_B_present'] and marker['journals_initialized'] and marker['VERSION_CAPS_installed']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running','power_off_reported'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),base['bank_sha256']))
    sessionpath=build.parent/'session.json';session=p.r.read(sessionpath)
    assert session['VERSION_CAPS_installed'] and not session['configuration_changed']
    wearpath=Path(session['wear_history']);wearraw=wearpath.read_bytes();wear=json.loads(wearraw)
    assert wear['counts']==base['counts'] and wear['sequence']==base['sequence']
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n')
    io.save(run/'marker-before.json',marker);io.save(run/'session-before.json',session);io.atomic(run/'host-wear-before.json',wearraw)
    others={name:(markerpath.parent/(name+'.json')).read_bytes() for name in ('2205','2512','2604') if (markerpath.parent/(name+'.json')).exists()}
    for name,raw in others.items():io.atomic(run/(name+'-marker-before.json'),raw)
    io.save(run/'authorization.json',dict(board='2609',USB=io.USB,owner_authorized=True,
        user_text='i want a demo of things F can do for users, then what else can be done. Perhaps a full load BIN, journal, A B etc. Demonstrate F without saved-setting or flash writes; preserve the existing board.',
        F_commands=['?','C1','0','L','Ctrl-C before payload'],saved_setting_writes_authorized=False,flash_writes_authorized=False,other_boards_authorized=False,
        RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path)))
    state=dict(board='2609',passed=False,started_utc=io.now(),phase='admitted-before-port',hardware=True,
        build=str(build),ready=str(ready),readback=str(readback),RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),
        baseline=base,configuration_changed=False,flash_written=False,saved_setting_writes=0,ACIA_board_tested=False)
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='F-user-demo-'+phase,F_user_demo_worker_active=not state.get('closed',False),
            F_user_demo_run=str(run),block_snapshot=True)
        if state.get('final_REC_verified'):current.update(last_F_user_demo_report=str(run/'report.json'),last_F_user_demo_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)];verify_banks(source,base)
    reader_path=readback/'payload/readback-RAM.bin';reader=reader_path.read_bytes();image=image_path.read_bytes()
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-b15-F-user-demo',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==io.USB];assert len(ports)==1,'Unique 2609 USB required'
        with (run/'serial.jsonl').open('x') as log,(run/'console-log.txt').open('x',encoding='utf-8',newline='') as console:
            def note(text):
                line='[HOST] '+text+'\n';console.write(line);console.flush();print(line.rstrip(),flush=True)
            def capture(token,name):
                raw=io.wait_text(link,token);io.atomic(run/name,raw);console.write(raw.decode('ascii'));console.flush();return raw
            def command(body,token,name):
                note('TX '+repr(body));link.send(body);return capture(token,name)
            def load(path,body,prompt,name):
                note(f'FILE {path.name}: {len(body)} bytes; SHA-256 {p.r.sha(body)}; raw L at $0200')
                assert command(b'L\r',b'SEND BIN\r\n',name+'-L.txt')==b'L\r\nSEND BIN\r\n'
                for offset in range(0,len(body),64):link.send(body[offset:offset+64]);time.sleep(.01)
                return capture(prompt,name+'-startup.txt')
            def full_read(phase):
                assert command(b'C1\r',io.REC,phase+'-C1.txt')==b'C1\r\nREC> '
                assert load(reader_path,reader,io.SVC,phase+'-readback')==io.SVC
                banks=[]
                for repeat in (1,2):
                    observed=[]
                    for bank in range(4):
                        raw=io.service_read(link,b'F'+bytes([bank]),32768)
                        io.atomic(run/f'{phase}-r{repeat}-b{bank}.bin',raw)
                        assert raw==source[bank],f'{phase} B{bank} changed; stop without retry'
                        observed.append(raw);note(f'{phase}-r{repeat}-b{bank}.bin: serial CRC verified; SHA-256 {p.r.sha(raw)}')
                    banks=observed
                memory=io.service_read(link,b'M',0x6300);io.atomic(run/(phase+'-service-RAM.bin'),memory)
                assert memory[:len(reader)]==reader
                verify_banks(banks,base);return banks
            link=p.wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync-read-only');note('USB '+ports[0].device+' serial '+io.USB+'; console-log.txt')
                initial=bytearray();last=started=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-started<20
                    raw=link.read(4096)
                    if raw:initial.extend(raw);last=time.monotonic()
                assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in initial)
                if initial:console.write(initial.decode('ascii'))
                assert command(b'\r',io.REC,'initial-REC.txt') in common.IDLE_REPLIES
                note('PROGRESS 1/5: before inspection, double-read all banks; no flash write commands')
                before=full_read('before');command(b'J',io.REC,'before-software-REC.txt')
                state['before_double_read_verified']=True;checkpoint('source-double-read-verified')
                note('PROGRESS 2/5: F-only user commands: help, USB selection, disabled bank, cancellable raw load')
                help_reply=command(b'?\r',io.REC,'F-help.txt');assert HELP in help_reply
                assert command(b'C1\r',io.REC,'F-C1.txt')==b'C1\r\nREC> '
                disabled=command(b'0\r',io.REC,'F-disabled-bank.txt')
                assert disabled==b'0\r\n\r\nRecovery L A/B 0-3 C1/2/3 ?\r\nREC> '
                assert command(b'L\r',b'SEND BIN\r\n','F-cancel-L.txt')==b'L\r\nSEND BIN\r\n'
                canceled=command(b'\x03',io.REC,'F-cancel-result.txt');assert b'Recovery L A/B' in canceled
                launch=load(image_path,image,WAIT,'F-demo')
                assert launch==(ready/'golden-startup-65c816-e.txt').read_bytes()
                result=command(b'!',io.REC,'F-demo-result.txt')
                assert result==(ready/'golden-result-65c816-e.txt').read_bytes()
                state.update(F_help_verified=True,F_cancel_verified=True,F_disabled_bank_verified=True,F_RAM_program_verified=True)
                checkpoint('F-user-demo-verified')
                note('PROGRESS 3/5: b15-F-DEMO-RAM.bin ran: CPU16, RAM calculation1235, key21, returned to REC; no flash commands')
                # The unchanged MON supplies an independent read of executed RAM.
                # Compare all app bytes against the model's executed RAM image.
                command(b'C1\r',io.REC,'RAM-check-C1.txt')
                command(b'A\r',common.MON,'RAM-check-MON-A.txt')
                dump=command(f'D 0200 {0x200+len(image)-1:04X}\r'.encode(),common.MON,'F-demo-RAM-dump.txt')
                loaded=common.parse_dump(dump,0x200,0x200+len(image)-1);verify_loaded(loaded,build,ready)
                io.atomic(run/'F-demo-device-RAM.bin',loaded);state['loaded_RAM_independently_verified']=True
                command(b'J3\r',common.CHOICES,'RAM-check-J3.txt');command(b'S',io.REC,'RAM-check-return-REC.txt')
                after=full_read('after');assert before==after
                state.update(all_banks_double_read_verified=True,B0_backup_preserved=True,wear_counts_preserved=True,
                    journal_sequence_unchanged=True,default_S_and_banks_disabled=True)
                checkpoint('independent-post-inspection-readback-verified')
                note('PROGRESS 4/5: loaded F-demo code verified; all four banks twice reread unchanged, including every journal byte')
                final=command(b'J',io.REC,'final-REC.txt')
                assert b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
                state.update(passed=True,final_REC_verified=True,post_final_REC_commands=0,stop_before_saved_setting_writes_honored=True)
                checkpoint('REC-verified-stopped');note('PROGRESS 5/5: REC> verified; STOP; no saved-setting writes and no further board commands')
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc());checkpoint('inspection-required');raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=io.now())
                checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    assert wearpath.read_bytes()==wearraw
    for name,raw in others.items():assert (markerpath.parent/(name+'.json')).read_bytes()==raw
    state['other_board_markers_unchanged']=True;state['host_wear_history_unchanged']=True;io.save(run/'report.json',state)
    session.update(step13='F user demo completed over USB; returned to REC; no flash/settings writes',
        last_completed_step=13,configuration_changed=False,step13_report=str(run/'report.json'),step13_receipt=str(run/'receipt.md'),
        step13_console_log=str(run/'console-log.txt'),current_stage='F+C/D+MON A/B+VX1 E; F-only-services demo complete; S/mask00; stopped at REC',
        next_step='Await next owner-directed step; CONFIG save/restore remains prepared only',updated_utc=io.now())
    io.save(sessionpath,session)
    print('PASS F user hardware demo; console log',run/'console-log.txt',flush=True)


if __name__=='__main__':main()
