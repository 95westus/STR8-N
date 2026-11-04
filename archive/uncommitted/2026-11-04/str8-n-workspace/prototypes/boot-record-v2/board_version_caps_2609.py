"""Owner-authorized exact VERSION/CAPS install on 2609; stop at F REC.

Reuse the hardware-tested USB RAM readback service. Offline plan verification
runs in its own process and retains its no-device guard. No configuration writer.
"""
import argparse,json,re,subprocess,sys,time,traceback,hashlib
from pathlib import Path
import board_journal_init_2609 as io
p=io.p
ROOT,HERE=p.ROOT,p.HERE
MENU=b'RAM MINSTALL ? V W I Q> '
CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
MON=b'B3> '
IDLE_REPLIES=(b'\r\nREC> ',b'\r\nREFUSED: command\r\nREC> ')


def admit(plan,qualification,readback,image_path):
    result=subprocess.run([sys.executable,str(HERE/'prepare_version_caps_2609.py'),'verify','--out',str(plan)],capture_output=True,text=True)
    assert result.returncode==0,'Offline plan verification failed: '+result.stderr
    info=p.r.read(plan/'plan.json');q=p.r.read(qualification);rb=p.r.read(readback/'qualification.json')
    assert info['F_unchanged'] and info['erase_order']==['B3:E000','B3:A000','B3:B000']
    assert q['passed'] and q['checks']==52 and q['plan_sha256']==p.digest(plan/'plan.json')
    for name,value in q['sources'].items():assert p.digest(HERE/name)==value
    assert p.digest(image_path)==q['payloads'][info['BIN']]['sha256']
    assert image_path.read_bytes()==(plan/'payload'/info['BIN']).read_bytes()
    assert rb['passed'] and len(rb['cases'])==4 and all(c['passed'] for c in rb['cases'])
    assert rb['F_sha256']==p.digest(p.TARGET/'payload/f-offline-component.bin') and rb['loader_sha256']==p.digest(readback/'payload/readback-RAM.bin')
    assert rb['service_source_sha256']==p.digest(HERE/'mon-absent-service.inc') and rb['builder_sha256']==p.digest(HERE/'prepare_journal_readback_2609.py')
    assert info['counts_after']==[n+(i in (26,27,30)) for i,n in enumerate(info['counts_before'])]
    return info,q


def parse_dump(reply,first,last):
    cells={}
    for line in reply.decode('ascii').splitlines():
        match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
        if match:cells.update((int(match[1],16)+n,v) for n,v in enumerate(bytes.fromhex(match[2])))
    assert set(cells)==set(range(first,last+1)),'Incomplete read-only MON dump'
    return bytes(cells[a] for a in range(first,last+1))


def verify_postimages(before,after,info,plan):
    assert p.r.hashes(before)==info['source_sha256'] and p.r.hashes(after)==info['expected_sha256']
    assert before[:3]==after[:3] and p.r.sha(after[0])==p.WDC_SHA
    assert before[3][:0x2000]==after[3][:0x2000] and before[3][0x7000:]==after[3][0x7000:]
    assert before[3][0x4000:0x4300]==after[3][0x4000:0x4300] and before[3][0x4600:0x6000]==after[3][0x4600:0x6000]
    records=p.snbt_records(after);assert len(records)==7
    by_offset={off:(seq,row) for seq,off,row in records}
    assert {off:seq for off,(seq,row) in by_offset.items()}=={0x4000:1015,0x4100:1016,0x4200:1017,0x4300:1018,0x4400:1019,0x4500:1020,0x5000:1014}
    for off,(seq,row) in by_offset.items():
        assert row[32:48].hex()==info['config'] and row[7]==ord('S') and row[13]==0
        assert row[160:164]==b'\xff'*4 and int.from_bytes(row[18:22],'little')==p.GENERATION
        if off in (0x4300,0x4400,0x4500):
            desired=info['counts_before'].copy();desired[30]+=1
            if off>=0x4400:desired[26]+=1
            if off==0x4500:desired[27]+=1
            assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==desired
        else:assert row==before[3][off:off+256]
    slots=[]
    for page in (0xa0,0xb0):
        data=after[3][(page-0x80)*256:(page-0x70)*256]
        assert p.wire.slot_valid(data,page) and data[20:24]==b'PR04' and int.from_bytes(data[8:12],'little')==p.GENERATION
        assert data==(plan/f'payload/monitor-{page:02x}-version-caps.bin').read_bytes()
        normalized=bytearray(data);normalized[18:20]=b'\0\0';normalized[31]=0;normalized[0xfdc:0xffc]=bytes(32)
        assert hashlib.sha256(normalized).digest()==data[0xfdc:0xffc]
        slots.append(dict(slot='A' if page==0xa0 else 'B',sha256=p.r.sha(data),CRC_valid=True,commit_byte=data[31],generation='8000000F'))
    extension=after[3][0x6000:0x7000]
    assert extension==(plan/'payload/version-caps-e000.bin').read_bytes() and p.wire.crc(extension)==0 and extension[:4]==b'VX\x01\x40' and extension[31]==0
    normalized=bytearray(extension);normalized[-2:]=b'\0\0';normalized[31]=0;normalized[0xfdc:0xffc]=bytes(32)
    assert hashlib.sha256(normalized).digest()==extension[0xfdc:0xffc]
    return slots


def verify_info(data,page,info,plan):
    assert len(data)==224 and data[:4]==b'VI\x01\xe0' and data[4:8]==b'\x17\x01\x16\x01'
    assert data[8]==page and data[9:12]==b'\x03\x03\x03'
    assert data[12:24]==p.GENERATION.to_bytes(4,'little')*3
    assert data[24:56]==bytes.fromhex(info['F_sha256'])
    for offset,name in ((56,'monitor-a0-version-caps.bin'),(88,'monitor-b0-version-caps.bin'),(168,'version-caps-e000.bin')):
        assert data[offset:offset+32]==(plan/'payload'/name).read_bytes()[0xfdc:0xffc]
    assert data[216:219]==b'\x01\x04\x01' and data[219]&1 and data[220:]==b'\xff'*4


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','qualification','readback','image','run'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();plan=args.plan.resolve();run=args.run.resolve();readback=args.readback.resolve();image_path=args.image.resolve()
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists(),'Fresh private run required'
    info,q=admit(plan,args.qualification,readback,image_path)
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=p.r.read(markerpath)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='b15-F-CD-MON-AB' and marker['journals_initialized']
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','application_RAM_restore_pending','owner_application_running','power_off_reported'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),info['source_sha256']))
    sessionpath=plan.parent/'session.json';session=p.r.read(sessionpath)
    assert session['journals_initialized'] and session['MON_installed'] and not session['configuration_changed']
    oldwear_path=Path(session['wear_history']);oldwear_raw=oldwear_path.read_bytes();oldwear=json.loads(oldwear_raw)
    assert oldwear['counts']==info['counts_before'] and oldwear['sequence']==info['sequence_before']
    run.mkdir(parents=True);(run/'.gitignore').write_text('*\n')
    io.save(run/'marker-before.json',marker);io.save(run/'session-before.json',session);io.atomic(run/'host-wear-before.json',oldwear_raw)
    other_markers={name:(markerpath.parent/(name+'.json')).read_bytes() for name in ('2205','2512','2604') if (markerpath.parent/(name+'.json')).exists()}
    for name,raw in other_markers.items():io.atomic(run/(name+'-marker-before.json'),raw)
    io.save(run/'authorization.json',dict(board='2609',USB=io.USB,owner_authorized=True,
        user_text='run the VERSION/CAPS RAM installer on 2609. preserve my wear counts and b0 backup, show the console log and file names, verify VERSION and CAPS from both MONs, return to REC>, then stop before configuration changes.',
        erases=['B3:E','B3:A','B3:B'],journal_appends=['C300','C400','C500'],C_D_erase_authorized=False,
        configuration_change_authorized=False,MON_read_only_launch_verification=True,other_boards_authorized=False,
        plan_sha256=p.digest(plan/'plan.json'),BIN_sha256=p.digest(image_path)))
    state=dict(board='2609',passed=False,started_utc=io.now(),phase='admitted-before-port',confirmation_sent=False,
        MON_device_verified=False,all_banks_double_read_verified=False,MON_A_boot_verified=False,MON_B_boot_verified=False,
        final_REC_verified=False,configuration_changed=False,ACIA_board_tested=False,
        plan=str(plan/'plan.json'),plan_sha256=p.digest(plan/'plan.json'),RAM_BIN=str(image_path),RAM_BIN_sha256=p.digest(image_path),
        counts_before=info['counts_before'],counts_planned=info['counts_after'],source_sha256=info['source_sha256'],expected_sha256=info['expected_sha256'])
    def checkpoint(phase):
        state.update(phase=phase,updated_utc=io.now());io.save(run/'report.json',state)
        current=dict(marker,state='VERSION-CAPS-install-'+phase,VERSION_CAPS_worker_active=not state.get('closed',False),
            VERSION_CAPS_run=str(run),block_snapshot=True,physical_reset_pending=False)
        if state['MON_device_verified']:current.update(MON_A_present=True,MON_B_present=True,firmware='2.0proto b15 VX1 F + C/D + MON A/B + E',
            current_firmware_profile='b15-VX1-F-CD-MON-AB-E',monitor_generation=p.GENERATION,VERSION_CAPS_installed=True)
        if state['all_banks_double_read_verified']:current['current_physical_bank_sha256']=dict(zip(('B0','B1','B2','B3'),info['expected_sha256']))
        if state['final_REC_verified']:current.update(last_VERSION_CAPS_report=str(run/'report.json'),last_VERSION_CAPS_REC=str(run/'final-REC.txt'))
        io.save(markerpath,current)
    source=[(plan/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    reader_path=readback/'payload/readback-RAM.bin';reader=reader_path.read_bytes();image=image_path.read_bytes()
    sys.path.insert(0,str(ROOT/'tmp/migration-python'))
    from serial.tools.list_ports import comports
    with io.serial_lease('2609-b15-VERSION-CAPS-install',timeout=30,priority=True):
        assert p.r.read(markerpath)==marker
        ports=[port for port in comports() if port.serial_number==io.USB];assert len(ports)==1,'Unique 2609 USB required'
        with (run/'serial.jsonl').open('x') as log,(run/'console-log.txt').open('x',encoding='utf-8',newline='') as console:
            def note(text):
                line='[HOST] '+text+'\n';console.write(line);console.flush();print(line.rstrip(),flush=True)
            def capture(token,name,seconds=45):
                raw=io.wait_text(link,token,seconds);io.atomic(run/name,raw)
                console.write(raw.decode('ascii'));console.flush()
                print('CONSOLE PROMPT',token.decode('ascii').strip(),flush=True)
                return raw
            def command(body,token,name):
                note('TX '+repr(body));link.send(body);return capture(token,name)
            def load(path,body,prompt,name):
                note(f'FILE {path.name}: {len(body)} bytes; SHA-256 {p.r.sha(body)}; raw L to $0200')
                reply=command(b'L\r',b'SEND BIN\r\n',name+'-L.txt');assert reply==b'L\r\nSEND BIN\r\n'
                for offset in range(0,len(body),64):link.send(body[offset:offset+64]);time.sleep(.01)
                return capture(prompt,name+'-startup.txt')
            def full_read(phase,wanted):
                assert command(b'C1\r',io.REC,phase+'-C1.txt')==b'C1\r\nREC> '
                assert load(reader_path,reader,io.SVC,phase+'-readback')==io.SVC
                captured=[]
                for repeat in (1,2):
                    pass_banks=[]
                    for bank in range(4):
                        data=io.service_read(link,b'F'+bytes([bank]),32768)
                        io.atomic(run/f'{phase}-r{repeat}-b{bank}.bin',data);assert data==wanted[bank],f'{phase} B{bank} mismatch; no retry'
                        pass_banks.append(data);note(f'{phase}-r{repeat}-b{bank}.bin: 32768 bytes + serial CRC verified; SHA-256 {p.r.sha(data)}')
                    captured.append(pass_banks)
                memory=io.service_read(link,b'M',0x6300);io.atomic(run/(phase+'-service-RAM.bin'),memory)
                assert memory[:len(reader)]==reader
                note('readback-RAM.bin loaded prefix independently read back and matched')
                return captured[0]
            link=p.wire.Link(ports[0].device,log)
            try:
                checkpoint('USB-sync-read-only');note('USB '+ports[0].device+' serial '+io.USB+'; full console capture: console-log.txt')
                initial=bytearray();last=started=time.monotonic()
                while time.monotonic()-last<1:
                    assert time.monotonic()-started<20
                    raw=link.read(4096)
                    if raw:initial.extend(raw);last=time.monotonic()
                assert all(c in (8,9,10,13,127) or 32<=c<=126 for c in initial)
                if initial:console.write(initial.decode('ascii'))
                assert command(b'\r',io.REC,'initial-REC.txt') in IDLE_REPLIES
                note('PROGRESS 1/7: source verification; all reads precede VERSION/CAPS confirmation')
                before=full_read('before',source)
                command(b'J',io.REC,'before-software-REC.txt')
                state['fresh_all_bank_double_read_verified']=True;checkpoint('source-double-read-verified')
                note('PROGRESS 2/7: exact F+C/D+MON source and B0 WDC backup confirmed twice')
                assert command(b'C1\r',io.REC,'installer-C1.txt')==b'C1\r\nREC> '
                launch=load(image_path,image,MENU,'installer')
                assert b'2609 RAM VERSION/CAPS INSTALL / b15 F / USB only\r\n' in launch
                assert all(f'B{n} OK\r\n'.encode() in launch for n in range(4))
                wear=command(b'W\r',MENU,'installer-W.txt')
                for bank in range(4):
                    for label,counts in (('before',info['counts_before']),('planned',info['counts_after'])):
                        text=f'B{bank} {label}: '+' '.join(map(str,counts[8*bank:8*bank+8]));assert text.encode() in wear
                io.save(run/'wear-reservation.json',dict(board='2609',created_utc=io.now(),durable_before_confirmation=True,
                    counts_before=info['counts_before'],reserved_counts=info['counts_after'],erase_order=['B3:E','B3:A','B3:B'],
                    source_history=str(oldwear_path),plan_sha256=state['plan_sha256'],C_D_erases=0,F_erases=0,
                    unknown_history_mask='ffffffff',semantics='Reservations become verified actual counts after readback'))
                note('PROGRESS 3/7: wear-reservation.json durable; E 42->43, A 50->51, B 53->54; C=78 D=47 F=30 unchanged')
                confirmation=command(b'I\r',b'then Enter> ','installer-confirmation.txt')
                assert confirmation==b'I\r\nType INSTALL VERSION then Enter> '
                state['confirmation_sent']=True;checkpoint('MON-write-confirmation-ready')
                note('Embedded FILES: version-caps-e000.bin; monitor-a0-version-caps.bin; monitor-b0-version-caps.bin')
                result=command(b'INSTALL VERSION\r',MENU,'installer-result.txt')
                addresses=[b'C300\r\n',b'E000\r\n',b'C400\r\n',b'A000\r\n',b'C500\r\n',b'B000\r\n']
                locations=[result.find(text) for text in addresses];assert min(locations)>=0 and locations==sorted(locations)
                assert result.count(b'erase sector; verify blank\r\n')==3 and result.count(b'committed; entire action readback VERIFIED\r\n')==6
                assert b'ALL COMPONENTS VERIFIED; default S recovery; B0 and F preserved\r\n' in result
                verified=command(b'V\r',MENU,'installer-V.txt');assert all(f'B{n} OK\r\n'.encode() in verified for n in range(4))
                state['MON_device_verified']=True;checkpoint('MON-device-verified')
                note('PROGRESS 4/7: E/A/B committed last; six action readbacks and all-bank V passed')
                command(b'Q\r',io.REC,'installer-Q-REC.txt')
                for target,page in (('A',0xa0),('B',0xb0)):
                    command(b'C1\r',io.REC,'MON-'+target+'-C1.txt')
                    banner=command(target.encode()+b'\r',MON,'MON-'+target+'-banner.txt')
                    assert b'STR8-N 2.0proto' in banner
                    active_reply=command(b'D 7D30 7D30\r',MON,'MON-'+target+'-active.txt')
                    assert parse_dump(active_reply,0x7d30,0x7d30)==bytes([page]),'Wrong MON active page'
                    identity_reply=command(b'D 7D00 7D02\r',MON,'MON-'+target+'-identity.txt')
                    identity=parse_dump(identity_reply,0x7d00,0x7d02);assert identity[:2]==b'\x03\x16' and identity[2]&1
                    version=command(b'VERSION\r',MON,'MON-'+target+'-VERSION.txt')
                    golden=(args.qualification.parent/'simulated-VERSION.txt').read_bytes()
                    if target=='B':golden=golden.replace(b'Running MON: A',b'Running MON: B')
                    assert version==golden,'VERSION differs from the qualified record/renderer fixture'
                    caps=command(b'CAPS\r',MON,'MON-'+target+'-CAPS.txt')
                    assert caps==(args.qualification.parent/'simulated-CAPS.txt').read_bytes(),'CAPS differs from qualified fixture'
                    structured=command(b'D 6700 67DF\r',MON,'MON-'+target+'-INFO-dump.txt')
                    data=parse_dump(structured,0x6700,0x67df);verify_info(data,page,info,plan)
                    io.atomic(run/('MON-'+target+'-INFO.bin'),data)
                    state['MON_'+target+'_VERSION_CAPS_verified']=True
                    state['MON_'+target+'_boot_verified']=True;checkpoint('MON-'+target+'-USB-boot-verified')
                    command(b'J3\r',CHOICES,'MON-'+target+'-J3.txt')
                    command(b'S',io.REC,'MON-'+target+'-return-REC.txt')
                    note('MON '+target+' VERSION/CAPS and 224-byte INFO record verified; J3/S returned to REC')
                note('PROGRESS 5/7: VERSION/CAPS verified from both MONs; no saved-configuration commands sent')
                after=full_read('after',expected);state['monitors']=verify_postimages(before,after,info,plan)
                for entry in state['monitors']:
                    target=entry['slot'];offset=0x2000 if target=='A' else 0x3000
                    io.atomic(run/('MON-'+target+'-device.bin'),after[3][offset:offset+4096])
                    note('MON-'+target+'-device.bin matches monitor-'+('a0' if target=='A' else 'b0')+'-version-caps.bin; CRC/commit/build identity valid')
                io.atomic(run/'version-caps-e000-device.bin',after[3][0x6000:0x7000])
                note('version-caps-e000-device.bin matches version-caps-e000.bin; CRC/commit/build identity valid')
                state.update(all_banks_double_read_verified=True,B0_backup_preserved=True,saved_configuration_unchanged=True)
                checkpoint('independent-after-boot-readback-verified')
                note('PROGRESS 6/7: post-boot double read passed for every bank, all 32 counts and preserved configuration')
                final=command(b'J',io.REC,'final-REC.txt');assert b'WAIT...' in final and b'Recovery L A/B 0-3 C1/2/3 ?' in final
                state.update(passed=True,final_REC_verified=True,post_final_REC_commands=0,counts_after=info['counts_after'],
                    actual_erase_order=['B3:E','B3:A','B3:B'],C_D_erases=0,stop_before_configuration_honored=True)
                checkpoint('REC-verified-stopped')
                note('PROGRESS 7/7: REC> verified; STOP before configuration changes; no further board commands')
            except BaseException:
                state.update(passed=False,failure=traceback.format_exc());checkpoint('inspection-required');raise
            finally:
                link.serial.close();state.update(closed=True,port_released=True,finished_utc=io.now())
                checkpoint('REC-verified-stopped' if state['passed'] else 'inspection-required')
    assert p.r.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    assert oldwear_path.read_bytes()==oldwear_raw
    for name,raw in other_markers.items():assert (markerpath.parent/(name+'.json')).read_bytes()==raw
    state['other_board_markers_unchanged']=True;io.save(run/'report.json',state)
    wear=dict(schema=1,board='2609',counts=info['counts_after'],sequence=info['sequence_after'],config=info['config'],history_unknown_mask='ffffffff',
        semantics='Verified tracked lower bounds; prior lifetime wear remains unknown',source_history=str(oldwear_path),
        added_erase_attempts=[dict(bank=3,sector='E',count=1),dict(bank=3,sector='A',count=1),dict(bank=3,sector='B',count=1)],
        device_erase_program_verify_passed=True,independent_all_bank_double_read_passed=True,onboard_journal_initialized=True,
        execution_report=str(run/'report.json'),execution_report_sha256=p.digest(run/'report.json'))
    io.save(run/'host-wear-after.json',wear)
    current=p.r.read(markerpath);current.update(last_tracked_wear_host_record=str(run/'host-wear-after.json'),
        snapshot_block_reason='Onboarding stopped at F REC; no RTC sampling authorized',MON_A_boot_verified=True,MON_B_boot_verified=True)
    io.save(markerpath,current)
    session.update(step09='VERSION/CAPS install and both MON queries verified; returned to REC; stopped before configuration',
        last_completed_step=9,MON_installed=True,VERSION_CAPS_installed=True,configuration_changed=False,step09_report=str(run/'report.json'),step09_receipt=str(run/'receipt.md'),
        wear_history=str(run/'host-wear-after.json'),current_stage='F+C/D+MON A/B+VX1 E; stopped at REC; configuration unchanged',
        next_step='Await next owner-directed step; no configuration changes performed',updated_utc=io.now())
    io.save(sessionpath,session)
    print('PASS VERSION/CAPS hardware installation; console log',run/'console-log.txt',flush=True)


if __name__=='__main__':main()
