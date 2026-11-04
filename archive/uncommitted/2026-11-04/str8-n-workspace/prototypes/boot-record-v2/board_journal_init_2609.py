"""Owner-authorized first C/D journal initialization; USB 2609 only.

Exact qualified RAM BIN, durable host wear reservation, independent before/after
full-bank reads, commit/readback checks, final F REC. No MON installation path.
Serial access is confined to main. Do not replay after a partial failure.
"""
import argparse,json,os,sys,time,traceback,subprocess
from datetime import datetime,timezone
from pathlib import Path
import wdc_b15_2609 as p
from installer.engine import legacy_transport as wire
from serial_test_coordination import serial_lease

ROOT,HERE=p.ROOT,p.HERE
USB='A10MPQXCA'
REC=b'REC> '
MENU=b'RAM JINIT ? V W I Q> '
SVC=b'RAM SERVICE> '
CONFIRM=b'type INIT C/D then Enter> '
now=lambda:datetime.now(timezone.utc).isoformat()


def atomic(path,body):
    path=Path(path);pending=path.with_suffix(path.suffix+'.pending')
    with pending.open('wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    pending.replace(path)
    assert path.read_bytes()==body


def save(path,value):atomic(path,(json.dumps(value,indent=2)+'\n').encode())


def exact(link,count):
    data=bytes(link.pending[:count]);del link.pending[:len(data)]
    return data+link.exact(count-len(data)) if len(data)<count else data


def service_read(link,command,count):
    assert command in [b'F'+bytes([n]) for n in range(4)]+[b'M'],'Service command outside read-only allowlist'
    assert count==(0x6300 if command==b'M' else 32768) and not link.pending
    link.send(command);frame=exact(link,count+2)
    assert wire.crc(frame[:count])==int.from_bytes(frame[count:],'little'),'RAM service CRC mismatch'
    assert link.until(SVC,15)==SVC,'RAM service framing differs'
    return frame[:count]


def wait_text(link,token,seconds=45):
    """Stream progress while retaining the exact buffered serial transcript."""
    deadline=time.monotonic()+seconds;shown=0
    while True:
        raw=bytes(link.pending)
        assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in raw),'Unexpected nontext state'
        while b'\n' in raw[shown:]:
            end=raw.index(b'\n',shown)+1
            line=raw[shown:end].decode('ascii').strip()
            if line:print('DEVICE',line,flush=True)
            shown=end
        if b'REFUSED/FAILED' in raw:raise RuntimeError('Initializer refused/failed; no retry; inspect capture')
        end=raw.find(token)
        if end>=0:
            end+=len(token);result=raw[:end];del link.pending[:end]
            return result
        if time.monotonic()>deadline:raise TimeoutError('Waiting for '+repr(token)+': '+repr(raw[-180:]))
        link.pending.extend(link.read(max(1,link.serial.in_waiting)))


def raw_load(link,body,prompt):
    assert 0<len(body)<=0x6300 and not link.pending
    assert link.command('L',b'SEND BIN\r\n')==b'L\r\nSEND BIN\r\n','Exact F raw-loader boundary required'
    for off in range(0,len(body),64):link.send(body[off:off+64]);time.sleep(.01)
    return wait_text(link,prompt)


def restart_service(link):
    assert not link.pending
    link.send(b'J')
    reply=wait_text(link,REC,45)
    assert b'Recovery L A/B 0-3 C1/2/3 ?' in reply and b'WAIT...' in reply
    return reply


def verify_records(banks,info):
    records=p.snbt_records(banks)
    assert len(records)==2 and {off for _,off,_ in records}=={0x4000,0x5000}
    result=[]
    for seq,off,row in records:
        counts=[int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]
        assert counts==info['counts_reserved'] and row[160:164]==b'\xff'*4
        assert row[32:48].hex()==info['config_before'] and row[7]==ord('S') and row[13]==0
        assert int.from_bytes(row[18:22],'little')==p.GENERATION and row[255]==0
        assert seq==info['sequences'][0 if off==0x5000 else 1]
        assert banks[3][off+256:off+4096]==b'\xff'*3840
        result.append(dict(sector='C' if off==0x4000 else 'D',sequence=seq,header_CRC_valid=True,
                           body_CRC_valid=True,commit_byte=0,counts=counts,unknown_mask='ffffffff',default='S'))
    return result


def verify_plan(plan):
    # The offline planner intentionally refuses all device/network imports.
    # Keep that boundary intact in its own process; this live wrapper only
    # consumes a successfully verified manifest and the fixed payload bytes.
    result=subprocess.run([sys.executable,str(HERE/'prepare_journal_init_2609.py'),
                           'verify','--out',str(plan)],capture_output=True,text=True)
    assert result.returncode==0,'Offline plan verification failed: '+result.stderr
    return p.r.read(plan/'plan.json')


def admit(plan,qualification,readback):
    info=verify_plan(plan);q=p.r.read(qualification);rb=p.r.read(readback/'qualification.json')
    assert q['passed'] and q['checks']==32 and q['source_plan_sha256']==p.digest(plan/'plan.json')
    assert q['image_sha256']==info['image_sha256'] and q['image_bytes']==2738
    for name,value in q['source_sha256'].items():assert p.digest(HERE/name)==value
    assert rb['passed'] and len(rb['cases'])==4 and all(c['passed'] for c in rb['cases'])
    assert rb['F_sha256']==info['F_sha256'] and rb['plan_sha256']==p.digest(plan/'plan.json')
    assert rb['loader_sha256']==p.digest(readback/'payload/readback-RAM.bin')
    assert rb['service_source_sha256']==p.digest(HERE/'mon-absent-service.inc')
    assert rb['builder_sha256']==p.digest(HERE/'prepare_journal_readback_2609.py')
    assert info['counts_before'][28:]==[77,46,42,30] and info['counts_reserved'][28:]==[78,47,42,30]
    return info,q,rb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','qualification','readback','run'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();plan=args.plan.resolve();run=args.run.resolve();readback=args.readback.resolve()
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists(),'Fresh private run required'
    info,q,rb=admit(plan,args.qualification,readback)
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='b15-F-only' and marker['F_only_REC_verified']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running','power_off_reported'))
    assert marker['current_physical_bank_sha256']=={f'B{n}':v for n,v in enumerate(info['source_sha256'])}
    sessionpath=plan.parent/'session.json';session=p.r.read(sessionpath)
    assert not session['journals_initialized'] and not session['MON_installed']
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n')
    save(run/'marker-before.json',marker);save(run/'session-before.json',session)
    others={name:(markerpath.parent/(name+'.json')).read_bytes() for name in ('2205','2512','2604') if (markerpath.parent/(name+'.json')).exists()}
    for name,raw in others.items():atomic(run/(name+'-marker-before.json'),raw)
    save(run/'authorization.json',dict(owner_authorized=True,board='2609',USB=USB,
        user_text='run the RAM journal initializer on 2609 using C/D. preserve my wear counts and b0 backup, show progress, verify the journals and return to REC>, then stop before installing MON A/B.',
        flash_targets=['B3:D','B3:C'],MON_install_authorized=False,other_board_access_authorized=False,
        RTC_EEPROM_write_authorized=False,RAM_readback_tools=True,plan_sha256=p.digest(plan/'plan.json')))
    state=dict(board='2609',passed=False,phase='admitted-before-port',started_utc=now(),flash_written=False,
        confirmation_sent=False,device_journals_verified=False,independent_readback_verified=False,
        final_REC_verified=False,MON_installed=False,ACIA_board_tested=False,
        plan=str(plan/'plan.json'),plan_sha256=p.digest(plan/'plan.json'),image_sha256=info['image_sha256'],
        counts_before=info['counts_before'],counts_reserved=info['counts_reserved'],
        source_sha256=info['source_sha256'],expected_sha256=info['expected_sha256'])
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=now());save(run/'report.json',state)
        current=dict(marker,state='journal-init-'+phase,journal_init_worker_active=not state.get('closed',False),
            journal_init_run=str(run),block_snapshot=True,physical_reset_pending=False,MON_A_present=False,MON_B_present=False)
        if state['device_journals_verified']:current.update(journals_initialized=True,current_firmware_profile='b15-F-and-CD',firmware='2.0proto b15 F + C/D; no MON')
        if state['independent_readback_verified']:current['current_physical_bank_sha256']={f'B{n}':v for n,v in enumerate(info['expected_sha256'])}
        if state['final_REC_verified']:current.update(last_journal_init_REC=str(run/'final-REC.txt'),last_journal_init_report=str(run/'report.json'))
        if state.get('wear_history'):current['last_tracked_wear_host_record']=state['wear_history']
        save(markerpath,current)
    reader=(readback/'payload/readback-RAM.bin').read_bytes();image=(plan/'payload/2609-journal-init-RAM.bin').read_bytes()
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    source=[(plan/f'source-b{n}.bin').read_bytes() for n in range(4)]
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with serial_lease('2609-b15-first-CD-journal',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==USB];assert len(ports)==1,'Unique 2609 USB identity required'
        with (run/'serial.jsonl').open('x') as log:
            link=wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync-read-only')
                print('PROGRESS 1/6: USB',ports[0].device,USB,'; synchronizing F recovery',flush=True)
                initial=bytearray();last=start_time=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-start_time<20,'No quiet text boundary'
                    data=link.read(4096)
                    if data:initial.extend(data);last=time.monotonic()
                assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in initial),'Unexpected nontext initial state'
                link.send(b'\r');reply=wait_text(link,REC,20)
                assert reply==b'\r\nREFUSED: command\r\nREC> ','Expected b15 idle REC boundary'
                atomic(run/'initial-REC.txt',bytes(initial)+reply)

                def full_read(phase,wanted):
                    assert link.command('C1',REC)==b'C1\r\nREC> '
                    launch=raw_load(link,reader,SVC);assert launch==SVC
                    for repeat in (1,2):
                        for bank in range(4):
                            data=service_read(link,b'F'+bytes([bank]),32768)
                            atomic(run/f'{phase}-r{repeat}-b{bank}.bin',data)
                            assert data==wanted[bank],f'{phase} bank {bank} differs; no retry'
                            print(f'PROGRESS READ {phase} {repeat}/2 B{bank}: exact 32768 bytes + CRC',flush=True)
                    loaded=service_read(link,b'M',0x6300);atomic(run/f'{phase}-service-RAM.bin',loaded)
                    assert loaded[:len(reader)]==reader,'Raw loader RAM readback differs'

                full_read('before',source)
                atomic(run/'before-software-REC.txt',restart_service(link))
                state['fresh_all_bank_double_read_verified']=True;checkpoint('fresh-source-verified')
                print('PROGRESS 2/6: all four source banks double-read; exact B0 WDC backup confirmed',flush=True)
                assert link.command('C1',REC)==b'C1\r\nREC> '
                launch=raw_load(link,image,MENU);atomic(run/'initializer-startup.txt',launch)
                assert launch.startswith(b'2609 RAM JOURNAL INIT / b15 F / USB only\r\n')
                assert all(f'B{n} OK\r\n'.encode() in launch for n in range(4))
                checkpoint('RAM-initializer-preflight-passed')
                link.send(b'W\r');wear=wait_text(link,MENU);atomic(run/'wear-before-init.txt',wear)
                for bank in range(4):
                    line=f'B{bank} 8-F before: '+ ' '.join(map(str,info['counts_before'][8*bank:8*bank+8]))
                    assert line.encode() in wear
                assert b'Planned C 77->78, D 46->47; F stays 30.' in wear
                save(run/'wear-reservation.json',dict(board='2609',created_utc=now(),durable_before_confirmation=True,
                    counts_before=info['counts_before'],reserved_counts=info['counts_reserved'],history_unknown_mask='ffffffff',
                    planned_erase_order=['B3:D','B3:C'],source_history=session['wear_history'],plan_sha256=state['plan_sha256'],
                    semantics='Conservative reservations until both device/full-bank verifications pass; no reset of imported counts'))
                print('PROGRESS 3/6: durable reservation saved; retained counts, C=78/D=47 reserved, F=30',flush=True)
                link.send(b'I\r');confirmation=wait_text(link,CONFIRM);atomic(run/'confirmation-prompt.txt',confirmation)
                assert confirmation==b'I\r\nErase B3:D then C only; type INIT C/D then Enter> '
                checkpoint('confirmation-ready')
                state.update(confirmation_sent=True,flash_written=True);checkpoint('CD-erase-attempts-authorized')
                link.send(b'INIT C/D\r');result=wait_text(link,MENU,60);atomic(run/'initializer-result.txt',result)
                required=[b'B0 OK\r\n',b'B1 OK\r\n',b'B2 OK\r\n',b'B3 OK\r\n',
                    b'D0: erase and verify blank\r\n',b'C0: erase and verify blank\r\n',
                    b'C/D VERIFIED; recovery default; MON A/B absent; no other sector written\r\n']
                offsets=[result.find(x) for x in required];assert min(offsets)>=0 and offsets==sorted(offsets)
                assert result.count(b'committed; all 4096 bytes verified\r\n')==2
                link.send(b'V\r');verified=wait_text(link,MENU);atomic(run/'initializer-V.txt',verified)
                assert verified==b'V\r\nC/D postimages VERIFIED\r\n'+MENU
                state['device_journals_verified']=True;checkpoint('CD-device-verified')
                print('PROGRESS 4/6: D then C committed; all 8192 bytes verified again by V',flush=True)
                link.send(b'Q\r');atomic(run/'initializer-Q-REC.txt',wait_text(link,REC))
                full_read('after',expected)
                state['records']=verify_records(expected,info)
                state.update(independent_readback_verified=True,B0_backup_double_read_preserved=True,
                    all_nonCD_flash_double_read_unchanged=True,config_body_preserved=True)
                checkpoint('independent-postimages-verified')
                print('PROGRESS 5/6: independent double read of every bank passed; C/D CRCs, commits and all 32 counts verified',flush=True)
                final=restart_service(link);atomic(run/'final-REC.txt',final)
                state.update(final_REC_verified=True,passed=True,post_final_REC_commands=0,
                    stop_before_MON_honored=True,actual_erase_order=['B3:D','B3:C'],counts_after=info['counts_reserved'])
                checkpoint('REC-verified-stopped')
                print('PROGRESS 6/6: F software restart reached REC>; STOP; no MON installation',flush=True)
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc());checkpoint('inspection-required');raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=now())
                checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    for name,raw in others.items():assert (markerpath.parent/(name+'.json')).read_bytes()==raw,'Other board state changed'
    state['other_board_markers_unchanged']=True
    save(run/'report.json',state)
    # The immutable step-3 history remains intact. Publish a new actual-count
    # record only after all device, repeated host readback, and REC checks pass.
    wear=dict(schema=1,board='2609',counts=info['counts_reserved'],sequence=info['sequences'][1],
        config=info['config_before'],history_unknown_mask='ffffffff',
        semantics='Verified tracked lower bounds; prior lifetime wear remains unknown',
        source_history=session['wear_history'],added_erase_attempts=[dict(bank=3,sector='D',count=1),dict(bank=3,sector='C',count=1)],
        device_erase_program_verify_passed=True,independent_all_bank_double_read_passed=True,
        onboard_journal_initialized=True,execution_report=str(run/'report.json'),execution_report_sha256=p.digest(run/'report.json'))
    save(run/'host-wear-after.json',wear)
    current=p.r.read(markerpath);current.update(last_tracked_wear_host_record=str(run/'host-wear-after.json'),
        snapshot_block_reason='F and C/D installed; no compatible MON-based RTC sampler',journals_initialized=True)
    save(markerpath,current)
    session.update(step05='C/D initialized, independently verified and returned to REC; stopped before MON',
        last_completed_step=5,journals_initialized=True,MON_installed=False,step05_report=str(run/'report.json'),
        step05_receipt=str(run/'receipt.md'),wear_history=str(run/'host-wear-after.json'),
        current_stage='F + C/D; stopped at REC>; MON A/B not installed',
        next_step='Await next owner-directed step; do not install MON A/B yet',updated_utc=now())
    save(sessionpath,session)
    print('PASS hardware journal initializer; report',run/'report.json',flush=True)


if __name__=='__main__':main()
