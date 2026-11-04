"""Owner-authorized CONFIG A then S; exact two appends, no erase or SRAM write."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
import board_edu_sram_preflight_2609 as pre
import edu_sram_backup as backup
io,p,common=pre.io,pre.p,pre.common
ROOT,HERE,SESSION=pre.ROOT,pre.HERE,pre.SESSION
PLAN=SESSION/'step18-CONFIG-exercise-seq1021-plan-r4'
READY=SESSION/'step18-CONFIG-exercise-seq1021-ready'
BUILD=SESSION/'step10-CONFIG-build-r1'
READBACK=SESSION/'step05-readback-tools-r1'
EDU_READY=SESSION/'step15-EDU-SRAM-ready'
CFG=b'RAM CONFIG ? B C I W Q> '


def admit():
    result=subprocess.run([sys.executable,str(HERE/'prepare_config_save_restore_seq1021_2609.py'),'verify','--out',str(PLAN)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    plan=p.r.read(PLAN/'plan.json');q=p.r.read(READY/'qualification.json')
    assert q['passed'] and q['checks']==25 and q['mutation_prefixes']==602 and q['retained_SRAM_checks']==730 and q['no_SPI_access']
    assert q['plan_sha256']==p.digest(PLAN/'plan.json') and q['checker_sha256']==p.digest(HERE/'test_config_save_restore_seq1021_2609.py')
    image=READY/'2609-CONFIG-RAM.bin';assert image.read_bytes()==(BUILD/'payload'/image.name).read_bytes()
    assert len(image.read_bytes())==2728 and p.digest(image)==q['BIN_sha256']==plan['BIN_sha256']
    rb=p.r.read(READBACK/'qualification.json');assert rb['passed'] and len(rb['cases'])==4 and rb['loader_sha256']==p.digest(READBACK/'payload/readback-RAM.bin')
    eq=p.r.read(EDU_READY/'qualification.json');assert eq['passed'] and eq['checks']==48
    for name,info in eq['artifacts'].items():assert p.digest(EDU_READY/name)==info['sha256']
    arrays=[(SESSION/f'step16-EDU-SRAM-preflight-live/SRAM-pass{n}-131072.bin').read_bytes() for n in (1,2)]
    assert arrays[0]==arrays[1] and len(arrays[0])==131072 and p.r.sha(arrays[0])==plan['baseline']['SRAM_sha256']
    assert plan['counts_before']==plan['counts_after'] and plan['erase_count']==0 and plan['journal_appends']==['C700','C800']
    return plan,image,arrays


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--admit-only',action='store_true');parser.add_argument('--run',type=Path)
    args=parser.parse_args();plan,image_path,originals=admit()
    if args.admit_only:print('PASS exact CONFIG BIN, 25 groups/602 prefixes/730 SRAM checks, both backups and two append-only rows; no port opened',flush=True);return
    run=args.run.resolve();assert run.is_relative_to(ROOT/'output/qualification') and not run.exists()
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['current_firmware_profile']=='b15-VX1-ES1-F-CD-MON-AB-E-8' and marker['EDU_SRAM_provider_verified']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active')) and not any(marker.get(k) for k in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),plan['source_sha256']))
    sessionpath=SESSION/'session.json';session=p.r.read(sessionpath);wearpath=Path(session['wear_history']);oldwear=wearpath.read_bytes();wear=json.loads(oldwear)
    assert session['last_completed_step']==17 and wear['sequence']==1021 and wear['counts']==plan['counts_before'] and not session['configuration_changed']
    run.mkdir();(run/'.gitignore').write_text('*\n');io.save(run/'marker-before.json',marker);io.save(run/'session-before.json',session);io.atomic(run/'host-wear-before.json',oldwear)
    others={b:(markerpath.parent/(b+'.json')).read_bytes() for b in ('2205','2512','2604')}
    io.save(run/'authorization.json',dict(owner_authorized=True,board='2609',USB=io.USB,
        user_text='next, run the CONFIG save/restore exercise on 2609: temporary MON A, then restore S. preserve wear counts, b0 and SRAM, keep banks disabled, and show the console log.',
        saved_commands=['C A','C S'],journal_targets=['C700','C800'],erase_authorized=False,SRAM_writes_authorized=False,other_boards_authorized=False,
        plan_sha256=p.digest(PLAN/'plan.json'),RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path)))
    stages={name:[(PLAN/f'{name}-b{n}.bin').read_bytes() for n in range(4)] for name in ('source','MON-A','restored-S')}
    expected=stages['source'];image=image_path.read_bytes();reader_path=READBACK/'payload/readback-RAM.bin';reader=reader_path.read_bytes()
    client_path=EDU_READY/'2609-EDU-SRAM-RAM.bin';client=client_path.read_bytes()
    sy=p.r.read(BUILD/'symbols.json')['core/ram-config'];literal=lambda name:image[sy[name]-0x200:].split(b'\0',1)[0]
    wear_reply=b'W\r\n'+b''.join(f'B{n//8}:{n%8+8:X} {v:06X}\r\n'.encode() for n,v in enumerate(plan['counts_before']))+b'UNKNOWN HISTORY\r\nOK\r\n'+CFG
    state=dict(board='2609',passed=False,hardware=True,started_utc=io.now(),plan=str(PLAN/'plan.json'),plan_sha256=p.digest(PLAN/'plan.json'),
        RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),saved_setting_writes=0,erase_count=0,SRAM_writes=0,SRAM_mode_writes=0,
        counts_before=plan['counts_before'],counts_after=plan['counts_after'],source_sha256=plan['source_sha256'],expected_sha256=plan['operations'][-1]['bank_sha256'])
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='CONFIG-exercise-'+phase,CONFIG_exercise_worker_active=not state.get('closed',False),CONFIG_exercise_run=str(run),block_snapshot=True)
        if state.get('final_REC_verified'):current.update(last_CONFIG_exercise_report=str(run/'report.json'),last_CONFIG_exercise_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-CONFIG-save-restore',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[v for v in comports() if v.serial_number==io.USB];assert len(ports)==1
        with (run/'serial.jsonl').open('x') as log,(run/'console-log.txt').open('x',encoding='ascii',newline='') as console:
            active_prompt=None
            def note(text):
                line='[HOST] '+text+'\n';console.write(line);console.flush();print(line.rstrip(),flush=True)
            def capture(token,name=None,show=True):
                nonlocal active_prompt
                raw=link.until(token,90);raw.decode('ascii');active_prompt=token
                if name:io.atomic(run/name,raw)
                console.write(raw.decode('ascii'));console.flush()
                if show:print(raw.decode('ascii').rstrip(),flush=True)
                return raw
            def command(body,token,name=None,show=True):
                nonlocal active_prompt
                if show:note('TX '+repr(body))
                active_prompt=None;link.send(body);return capture(token,name,show)
            def load(path,body,prompt,name):
                note(f'FILE {path.name}: {len(body)} bytes; SHA-256 {p.r.sha(body)}; raw L at $0200')
                assert command(b'L\r',b'SEND BIN\r\n',name+'-L.txt')==b'L\r\nSEND BIN\r\n'
                for off in range(0,len(body),64):link.send(body[off:off+64]);time.sleep(.01)
                return capture(prompt,name+'-startup.txt')
            def policy(banks,target,seq):
                actual,offset,row=max(p.snbt_records(banks));assert actual==seq and row[7]==ord(target) and row[13]==0 and row[14:18]==b'\x08'*4
                assert row[160:164]==b'\xff'*4 and [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==plan['counts_before']
                return row
            def flash_reads(prefix,want,target,seq):
                command(b'C1\r',io.REC,prefix+'-C1.txt');assert load(reader_path,reader,io.SVC,prefix+'-reader')==io.SVC
                for repeat in (1,2):
                    banks=[]
                    for bank in range(4):
                        raw=io.service_read(link,b'F'+bytes([bank]),32768);io.atomic(run/f'{prefix}-r{repeat}-b{bank}.bin',raw)
                        assert raw==want[bank],f'{prefix} B{bank} differs; inspect without retry';banks.append(raw)
                        note(f'FILE {prefix}-r{repeat}-b{bank}.bin: 32768 bytes; CRC OK; SHA-256 {p.r.sha(raw)}')
                    policy(banks,target,seq)
                assert p.r.sha(banks[0])==p.WDC_SHA
            def settings(target,key):return key+b'\r\n'+f'DEFAULT={target}\r\n'.encode()+b''.join(f'B{n} OFF ENTRY=8000\r\n'.encode() for n in range(4))+CFG
            def inspect(target,prefix):
                for key in (b'B',b'C'):assert command(key+b'\r',CFG,prefix+'-'+key.decode()+'.txt')==settings(target,key)
                assert command(b'W\r',CFG,prefix+'-W.txt')==wear_reply
            def checked_config(target,prefix):
                command(b'C1\r',io.REC,prefix+'-C1.txt')
                assert load(image_path,image,CFG,prefix)==literal('CONFIG_BANNER')+CFG
                inspect(target,prefix)
                command(b'Q\r',io.REC if target=='S' else common.MON,prefix+'-Q.txt')
                if target=='S':command(b'A\r',common.MON,prefix+'-manual-MON-A.txt')
                raw=command(b'D 0200 0CA7\r',common.MON,prefix+'-RAM-dump.txt',show=False)
                observed=common.parse_dump(raw,0x200,0xca7);want=bytearray(image);want[sy['CONFIG_ROW']-0x200]=4
                assert observed==want;io.atomic(run/(prefix+'-device-RAM.bin'),observed)
                note('CONFIG RAM independently verified; only the expected display-row byte differs')
                assert command(b'G 0200\r',CFG,prefix+'-RAM-reentry.txt')==b'G 0200\r\n'+literal('CONFIG_BANNER')+CFG
            def sram(prefix):
                command(b'C1\r',io.REC,prefix+'-C1.txt');assert b'ES1 EDU/SRAM READ ONLY / 2609 b15\r\n' in load(client_path,client,pre.EDU,prefix+'-client')
                before=pre.via(command(b'V\r',pre.EDU,prefix+'-VIA-before.txt'));ddr,pcr,acr,ifr,ier=before
                assert not (ddr&0x2f or pcr&0xf0 or acr&0x1e or ier&0x18),'SPI owner busy'
                if ifr&0x18:
                    note('Guarded A acknowledges only idle, disabled CB flags; no SRAM or mode write')
                    assert b'STATUS COMPLETED MODE: 00 ' in command(b'A\r',pre.EDU,prefix+'-CB-ack.txt')
                note(f'FILE {prefix}-131072.bin: full read compared with BOTH original backups')
                data=bytearray();began=time.monotonic()
                with (run/(prefix+'-console.txt')).open('xb') as transcript:
                    transcript.write(pre.EDU)
                    for address in range(0,131072,64):
                        reply=command(f'R {address:05X} 40\r'.encode(),pre.EDU,show=False);transcript.write(reply);transcript.flush()
                        body,mode=pre.chunk(reply,address);assert mode==0x40 and all(body==old[address:address+64] for old in originals)
                        data.extend(body)
                        if len(data)%16384==0:note(f'PROGRESS {prefix}: {len(data)}/131072 bytes; mode40; both backups match; elapsed {time.monotonic()-began:.1f}s')
                parsed,mode=backup.parse((run/(prefix+'-console.txt')).read_bytes());assert parsed==data==originals[0]==originals[1] and mode==0x40
                io.atomic(run/(prefix+'-131072.bin'),data)
                after=pre.via(command(b'V\r',pre.EDU,prefix+'-VIA-after.txt'));want=bytearray(before);want[3]&=~0x18;assert after==want
                command(b'Q\r',io.REC,prefix+'-Q-REC.txt')
                note(f'VERIFIED {prefix}-131072.bin: SHA-256 {p.r.sha(data)}; full contents and mode preserved')
                return bytes(data)
            link=p.wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync');note('USB '+ports[0].device+' serial '+io.USB+'; full console-log.txt')
                initial=bytearray();last=started=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-started<20
                    raw=link.read(4096)
                    if raw:initial.extend(raw);last=time.monotonic()
                if initial:console.write(initial.decode('ascii'))
                assert command(b'\r',io.REC,'initial-REC.txt') in common.IDLE_REPLIES
                note('PROGRESS 1/7: double-read exact seq1021 source; B0 and every count verified before a save')
                flash_reads('before',stages['source'],'S',1021);command(b'J',io.REC,'before-return-REC.txt')
                checkpoint('source-double-read-verified')
                before_sram=sram('SRAM-before');state['fresh_SRAM_before_matches_both_backups']=True;checkpoint('SRAM-before-verified')
                note('PROGRESS 2/7: load and independently verify 2609-CONFIG-RAM.bin; all banks remain OFF')
                checked_config('S','CONFIG-before-A')
                io.save(run/'saved-setting-intent.json',dict(owner_authorized=True,commands=['C A','C S'],targets=['C700','C800'],counts_unchanged=plan['counts_before'],erase_count=0,recorded_utc=io.now()))
                checkpoint('save-A-ready');state['C_A_sent']=True
                assert command(b'C A\r',CFG,'CONFIG-save-A.txt')==b'C A\r\nOK\r\n'+CFG
                state['saved_setting_writes']=1;inspect('A','CONFIG-saved-A')
                boot=command(b'Q\r',common.MON,'saved-A-autoboot.txt');assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b15 B3 65C816' in boot
                assert common.parse_dump(command(b'D 7D30 7D30\r',common.MON,'saved-A-active-slot.txt'),0x7d30,0x7d30)==b'\xa0'
                row=common.parse_dump(command(b'D C700 C7FF\r',common.MON,'saved-A-journal-dump.txt',show=False),0xc700,0xc7ff)
                assert row==(PLAN/'MON-A-journal-row.bin').read_bytes();io.atomic(run/'saved-A-device-journal.bin',row)
                note('PROGRESS 3/7: VERIFIED C700 seq1022; saved A booted without an A key; MON A0; banks00; counts unchanged')
                state.update(saved_A_verified=True,temporary_sequence=1022);checkpoint('saved-A-verified')
                command(b'J3\r',common.CHOICES,'saved-A-manual-J3.txt');command(b'S',io.REC,'saved-A-manual-S.txt')
                checked_config('A','CONFIG-before-S');state['C_S_sent']=True;checkpoint('restore-S-ready')
                assert command(b'C S\r',CFG,'CONFIG-restore-S.txt')==b'C S\r\nOK\r\n'+CFG
                state['saved_setting_writes']=2;inspect('S','CONFIG-restored-S')
                boot=command(b'Q\r',io.REC,'restored-S-autoboot.txt');assert b'Boot : 6 5 4 3 2 1 0' in boot
                note('PROGRESS 4/7: saved S reached REC without an S override; banks00; all 32 counts unchanged')
                state['restored_S_autoboot_verified']=True;checkpoint('S-restored')
                note('PROGRESS 5/7: two full post-exercise SRAM reads against both original backups')
                after1=sram('SRAM-after-pass1');after2=sram('SRAM-after-pass2');assert before_sram==after1==after2
                state.update(SRAM_preserved=True,SRAM_sha256=p.r.sha(after1),SRAM_mode='40',SRAM_full_reads=3)
                note('PROGRESS 6/7: final all-bank double-read; only C700 and C800 may differ')
                flash_reads('final',stages['restored-S'],'S',1023)
                final=command(b'J',io.REC,'final-REC.txt');assert b'Boot : 6 5 4 3 2 1 0' in final
                state.update(passed=True,final_REC_verified=True,post_final_REC_commands=0,sequence_after=1023,default_after='S',enabled_banks=0,
                    B0_preserved=True,wear_counts_preserved=True,all_flash_exact_expected=True,configuration_policy_restored=True)
                checkpoint('REC-verified-stopped');note('PROGRESS 7/7: REC> verified; STOP; zero erases, B0 and SRAM preserved')
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc());checkpoint('inspection-required')
                if active_prompt==pre.EDU:
                    try:command(b'Q\r',io.REC,'failure-safe-REC.txt');state['failure_returned_REC']=True
                    except BaseException:state['failure_return_exception']=traceback.format_exc()
                raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=io.now());checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert wearpath.read_bytes()==oldwear and p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    for board,body in others.items():assert (markerpath.parent/(board+'.json')).read_bytes()==body
    state.update(other_boards_unchanged=True,prior_wear_record_unchanged=True);io.save(run/'report.json',state)
    newwear=dict(wear,sequence=1023,source_history=str(wearpath),added_erase_attempts=[],execution_report=str(run/'report.json'),execution_report_sha256=p.digest(run/'report.json'),
        semantics='Same tracked counts; CONFIG appended A then S without erase; prior lifetime wear remains unknown')
    io.save(run/'host-wear-after.json',newwear)
    current=p.r.read(markerpath);current.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),state['expected_sha256'])),
        last_tracked_wear_host_record=str(run/'host-wear-after.json'),CONFIG_save_restore_verified=True,configuration_changed=False,journal_sequence=1023,
        default_boot='S',enabled_banks=0,CONFIG_exercise_worker_active=False)
    io.save(markerpath,current)
    session.update(step19='CONFIG saved A at C700 seq1022, restored S at C800 seq1023; banks00; zero erases; B0/SRAM verified; REC',last_completed_step=19,
        step19_report=str(run/'report.json'),step19_console_log=str(run/'console-log.txt'),wear_history=str(run/'host-wear-after.json'),configuration_changed=False,
        configuration_exercise_completed=True,current_stage='F+C/D+MON A/B+VX1+ES1; default S; banks00; seq1023; stopped REC',updated_utc=io.now())
    io.save(sessionpath,session)
    print('PASS CONFIG A then S; console log',run/'console-log.txt',flush=True)


if __name__=='__main__':main()
