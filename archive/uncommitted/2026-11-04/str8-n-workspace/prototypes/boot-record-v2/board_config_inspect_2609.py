"""Owner-authorized USB CONFIG inspection; no saved-setting command path."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
import board_version_caps_2609 as common
io=common.io
p=io.p
ROOT,HERE=p.ROOT,p.HERE
CFG=b'RAM CONFIG ? B C I W Q> '
KEYS=(b'?\r',b'B\r',b'C\r',b'W\r')
NAMES=('help','B','C','W')


def admit(build,ready,readback):
    result=subprocess.run([sys.executable,str(HERE/'prepare_ram_config_2609.py'),'verify','--out',str(build)],capture_output=True,text=True)
    assert result.returncode==0,'Offline CONFIG verification failed: '+result.stderr
    info=p.r.read(build/'ram-config-build.json');q=p.r.read(ready/'qualification.json');base=p.r.read(build/'baseline.json')
    assert q['passed'] and q['checks']==31 and q['build_sha256']==p.digest(build/'ram-config-build.json')
    for name,digest in q['sources'].items():assert p.digest(HERE/name)==digest
    for name,digest in q['receipts'].items():assert p.digest(name)==digest
    image=ready/q['BIN'];assert image.name=='2609-CONFIG-RAM.bin' and image.read_bytes()==(build/'payload'/image.name).read_bytes()
    assert p.digest(image)==q['sha256']==info['app_sha256'] and len(image.read_bytes())==q['bytes']==2728
    assert base==q.get('baseline',base) and base['default']=='S' and base['enabled_banks']==0 and base['sequence']==1020
    rb=p.r.read(readback/'qualification.json')
    assert rb['passed'] and len(rb['cases'])==4 and all(c['passed'] for c in rb['cases'])
    assert rb['F_sha256']==base['F_sha256']==p.digest(p.TARGET/'payload/f-offline-component.bin')
    assert rb['loader_sha256']==p.digest(readback/'payload/readback-RAM.bin')
    assert rb['service_source_sha256']==p.digest(HERE/'mon-absent-service.inc')
    assert rb['builder_sha256']==p.digest(HERE/'prepare_journal_readback_2609.py')
    return info,q,base,image


def verify_banks(banks,base):
    assert p.r.hashes(banks)==base['bank_sha256'] and p.r.sha(banks[0])==p.WDC_SHA
    records=p.snbt_records(banks);seq,off,row=max(records,key=lambda r:r[0])
    assert len(records)==7 and seq==base['sequence']==1020
    assert row[7]==ord('S') and row[13]==0 and row[14:18]==b'\x08'*4
    assert row[32:48].hex()==base['config'] and row[160:164]==b'\xff'*4
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==base['counts']
    return dict(sequence=seq,record_count=len(records),default='S',enabled_banks=0,counts=base['counts'],B0_sha256=p.WDC_SHA)


def golden_replies(build,ready):
    image=(ready/'2609-CONFIG-RAM.bin').read_bytes();sy=p.r.read(build/'symbols.json')['core/ram-config']
    def literal(name):return image[sy[name]-0x200:].split(b'\0',1)[0]
    settings=b'DEFAULT=S\r\n'+b''.join(f'B{n} OFF ENTRY=8000\r\n'.encode() for n in range(4))
    base=p.r.read(build/'baseline.json')
    wear=b''.join(f'B{n//8}:{n%8+8:X} {v:06X}\r\n'.encode() for n,v in enumerate(base['counts']))+b'UNKNOWN HISTORY\r\nOK\r\n'
    return dict(startup=literal('CONFIG_BANNER')+CFG,help=b'?\r\n'+literal('CONFIG_HELP_TEXT')+CFG,
                B=b'B\r\n'+settings+CFG,C=b'C\r\n'+settings+CFG,W=b'W\r\n'+wear+CFG)


def verify_loaded(raw,build,ready):
    image=(ready/'2609-CONFIG-RAM.bin').read_bytes();sy=p.r.read(build/'symbols.json')['core/ram-config']
    expected=bytearray(image);expected[sy['CONFIG_ROW']-0x200]=4
    assert raw==expected,'CONFIG RAM differs outside the expected display-row byte'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','ready','readback','run'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build,ready,readback,run=(getattr(args,n).resolve() for n in ('build','ready','readback','run'))
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists(),'Fresh run required'
    info,q,base,image_path=admit(build,ready,readback);gold=golden_replies(build,ready)
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
        user_text='run 2609-CONFIG-RAM.bin on 2609 for inspection only. show the console log for ?, bare B, bare C and W. preserve wear counts and b0, keep default S and banks disabled, return to REC>, then stop before saved-setting writes.',
        CONFIG_commands=['?','B','C','W','Q'],saved_setting_writes_authorized=False,flash_writes_authorized=False,other_boards_authorized=False,
        RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path)))
    state=dict(board='2609',passed=False,started_utc=io.now(),phase='admitted-before-port',hardware=True,
        build=str(build),ready=str(ready),readback=str(readback),RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),
        baseline=base,configuration_changed=False,flash_written=False,saved_setting_writes=0,ACIA_board_tested=False)
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='CONFIG-inspection-'+phase,CONFIG_inspection_worker_active=not state.get('closed',False),
            CONFIG_inspection_run=str(run),block_snapshot=True)
        if state.get('final_REC_verified'):current.update(last_CONFIG_inspection_report=str(run/'report.json'),last_CONFIG_inspection_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)];verify_banks(source,base)
    reader_path=readback/'payload/readback-RAM.bin';reader=reader_path.read_bytes();image=image_path.read_bytes()
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-b15-CONFIG-inspection',timeout=30,priority=True):
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
                note('PROGRESS 2/5: B0 and exact b15/VX1 baseline confirmed; load 2609-CONFIG-RAM.bin')
                assert command(b'C1\r',io.REC,'CONFIG-C1.txt')==b'C1\r\nREC> '
                assert load(image_path,image,CFG,'CONFIG')==gold['startup']
                for key,name in zip(KEYS,NAMES):
                    assert key in KEYS,'CONFIG inspection-only allowlist'
                    reply=command(key,CFG,'CONFIG-'+name+'.txt');assert reply==gold[name],'CONFIG '+name+' differs from qualified display'
                    state['CONFIG_'+name+'_verified']=True
                checkpoint('CONFIG-displays-verified')
                note('PROGRESS 3/5: ?, bare B, bare C, W matched; DEFAULT=S; B0-B3 OFF; all counts preserved')
                command(b'Q\r',io.REC,'CONFIG-Q-REC.txt')
                # The unchanged MON supplies an independent read of executed RAM.
                # Only CONFIG_ROW changes, from 0 to 4 after the B/C display loops.
                command(b'C1\r',io.REC,'RAM-check-C1.txt')
                command(b'A\r',common.MON,'RAM-check-MON-A.txt')
                dump=command(f'D 0200 {0x200+len(image)-1:04X}\r'.encode(),common.MON,'CONFIG-RAM-dump.txt')
                loaded=common.parse_dump(dump,0x200,0x200+len(image)-1);verify_loaded(loaded,build,ready)
                io.atomic(run/'CONFIG-device-RAM.bin',loaded);state['loaded_RAM_independently_verified']=True
                command(b'J3\r',common.CHOICES,'RAM-check-J3.txt');command(b'S',io.REC,'RAM-check-return-REC.txt')
                after=full_read('after');assert before==after
                state.update(all_banks_double_read_verified=True,B0_backup_preserved=True,wear_counts_preserved=True,
                    journal_sequence_unchanged=True,default_S_and_banks_disabled=True)
                checkpoint('independent-post-inspection-readback-verified')
                note('PROGRESS 4/5: loaded CONFIG code verified; all four banks twice reread unchanged, including every journal byte')
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
    session.update(step11='CONFIG inspection only completed; ?, B, C, W verified; returned to REC; no saved-setting writes',
        last_completed_step=11,configuration_changed=False,step11_report=str(run/'report.json'),step11_receipt=str(run/'receipt.md'),
        step11_console_log=str(run/'console-log.txt'),current_stage='F+C/D+MON A/B+VX1 E; CONFIG inspected; default S, banks disabled; stopped at REC',
        next_step='Await next owner-directed step; saved-setting writes not performed',updated_utc=io.now())
    io.save(sessionpath,session)
    print('PASS CONFIG hardware inspection; console log',run/'console-log.txt',flush=True)


if __name__=='__main__':main()
