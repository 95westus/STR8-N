"""Owner-authorized six-hour corrected rc1/ASM/DBG1 soak; preserves RAM, no flash writes."""
import argparse,contextlib,ctypes,hashlib,json,os,re,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path

BOARDS={'2604':('COM5','A10MQGVHA','B',2),'2609':('COM8','A10MPQXCA','A',0x16)}
KIT_SHA='87f5b610ed309f0be7ab8bd63e7f630bbc9c2e9885ecd048022227502934bb7d'
AUTHORIZED_HOURS=6
ASM_LINES=['10 ORG $0200','20 SEI','30 CLD','40 LDX #$FF','50 TXS','60 BRK $80','70 BRK #$03','80 JMP $7E67','90 END']
SHA=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
READ=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
NOW=lambda:datetime.now(timezone.utc).isoformat()

def due(deadline,stop,now=None):
    return Path(stop).exists() or (time.monotonic() if now is None else now)>=deadline

def duration_seconds(auth):
    assert auth['owner_authorized'] and auth['hours']==AUTHORIZED_HOURS
    assert auth['boards']==list(BOARDS) and auth['final_drift_snapshot_authorized']
    assert auth['promotion_held'] and not auth['native_debugging'] and not auth['native_applications']
    assert auth['package_manifest_sha256']==KIT_SHA
    return AUTHORIZED_HOURS*3600

def restore_all(boards,restore):
    results={}
    for board in boards:
        try:results[board]=restore(board)
        except BaseException:
            results[board]=dict(passed=False,RAM_restored_host_verified=False,errors=[traceback.format_exc()])
    return results

def asm_unit(link,transport,kit):
    """Real onboard assembly must match the already-tested query image before G."""
    text=link.command('ASM',b'ASM> ');assert b'ASM 0.5' in text
    text+=link.command('NEW',b'ASM> ')
    for line in ASM_LINES:text+=link.command(line,b'ASM> ')
    result=link.command('ASM',b'ASM> ');text+=result;assert b'OK 12 bytes' in result,result
    text+=link.command('DUMP',b'ASM> ')+link.command('S19',b'ASM> ')+link.command('QUIT')
    cells={}
    # The package's S-record entry is 0200; the legacy install reader accepts
    # only 2000+, so decode with the same checksum rules as the RAM smoke loader.
    for row in (kit/'smoke/query.s19').read_text().splitlines():
        raw=bytes.fromhex(row[2:]);assert sum(raw)&255==255
        if row.startswith('S1'):
            address=int.from_bytes(raw[1:3],'big');cells.update(dict(enumerate(raw[3:-1],address)))
    expected=bytes(cells[a] for a in sorted(cells));assert expected==bytes.fromhex('78D8A2FF9A008000034C677E')
    assert transport.read_range(link,0x200,0x200+len(expected)-1)==expected,'ASM output differs; execution refused'
    query=READ(kit/'smoke/scenarios.json')['tests'][-1]
    for step in query['steps']:
        prompt=b'DBG> ' if step['prompt']=='DBG' else b'\r\nB3> '
        answer=link.command(step['command'],prompt);transport.check(step,answer);text+=answer
    assert link.dump(0x7BFC,0x7BFD)==b'\0\0'
    assert transport.read_range(link,0x200,0x200+len(expected)-1)==expected
    return dict(passed=True,bytes=len(expected),output_sha256=hashlib.sha256(expected).hexdigest(),BRK_80_query_and_explicit_signature=True),text

def debugger_unit(link,transport,kit):
    suite=READ(kit/'smoke/scenarios.json');completed=[]
    for test in suite['tests']:
        cells=transport.load(link,kit/test['image'])
        for step in test['steps']:
            prompt=b'DBG> ' if step['prompt']=='DBG' else b'\r\nB3> '
            transport.check(step,link.command(step['command'],prompt))
        assert link.dump(0x7BFC,0x7BFD)==b'\0\0'
        assert transport.read_range(link,min(cells),max(cells))==bytes(cells[a] for a in sorted(cells)),'Breakpoint patch remains'
        completed.append(test['name'])
    return dict(passed=True,tests=completed,breakpoint_hits=16,all_eight_hit_twice=True,program_bytes_restored=True)

class Runner:
    def __init__(self,workspace,run):
        self.root=workspace.resolve();self.run=run.resolve();self.q=self.root/'output/qualification';self.kit=self.root/'BUILD/rc1-debugger-boardtest-r2'
        sys.path.insert(0,str(self.root/'tools'));sys.path.insert(0,str(self.kit))
        import board_link as transport
        from atomic_json import publish
        from rtc_prompt_sync import establish_b3,drain
        import serial_test_coordination as coordination
        self.transport=transport;self.publish=publish;self.establish=establish_b3;self.drain=drain;self.coordination=coordination
        self.coordination.ROOT=self.q/'serial-coordination';self.original={};self.flash_hashes={};self.last_flash={};self.last_clock={}
        auth=READ(self.run/'owner-authorization.json');self.duration_seconds=duration_seconds(auth)
        self.auth=auth;assert SHA(self.kit/'board-test-manifest.json')==KIT_SHA;transport.plans.package(self.kit)
        assert READ(self.q/'rc1-dbg1-promotion-hold.json')['held']
        assert SHA(auth['baseline_index'])==auth['baseline_index_sha256']
        active=READ(self.q/'active-rtc-campaign.json');assert set(active['powered_off_boards'])=={'2205','2512'}
        self.campaign_path=Path(active['campaign_state']);self.baselines={x['board']:x for x in READ(auth['baseline_index'])['boards']}
        self.observer=self.root/'output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer'
        pin=READ(self.observer/'report.json');assert pin['passed'] and not pin['enters_native_mode'] and SHA(self.observer/'mode.s19')==pin['s19_sha256']
        self.observer_sha256=pin['s19_sha256']
        self.source_pins={str(path):SHA(path) for path in [self.root/'tools'/name for name in
            ('snapshot_rtc_campaign.py','rtc_utc_baseline.py','rtc_campaign_segments.py','beta4_migration.py','rtc_prompt_sync.py','serial_test_coordination.py')]+[self.root/'BUILD/v2-rtc-kernel/utc-client/rtc-sample-client.s19']}
        self.state=dict(state='initializing',pid=os.getpid(),candidate='rc1-debugger-v1f-MAINT-corrected',generation=50,authorized_hours=AUTHORIZED_HOURS,promotion_held=True,boards={b:dict(passed_cycles=0,breakpoint_hits=0,slot=info[2]) for b,info in BOARDS.items()},
            clock_set=False,trim_changed=False,settings_changed=False,flash_written=False,native_debugging=False,native_applications_tested=False,
            runner_sha256=SHA(__file__),package_manifest_sha256=KIT_SHA,owner_authorization_sha256=SHA(self.run/'owner-authorization.json'),baseline_index_sha256=auth['baseline_index_sha256'],final_snapshot_source_sha256=self.source_pins)
    def status(self,phase,**extra):
        self.state.update(state=phase,updated_unix=time.time(),**extra);self.publish(self.run/'status.json',self.state)
    def marker(self,board,phase,blocked=True,**extra):
        path=self.q/'device-operations'/f'{board}.json';value=READ(path);value.update(state=phase,run=str(self.run),block_snapshot=blocked,soak_owner_stopped=False,**extra);self.publish(path,value)
    def campaign(self,active):
        value=READ(self.campaign_path);value.update(soak_active=active,soak_state=self.state['state'],debugger_soak_current=dict(run=str(self.run),state=self.state['state'],pid=os.getpid(),boards=list(BOARDS),hours=AUTHORIZED_HOURS,deadline_unix=self.state.get('deadline_unix')),automatic_workload_restart_permitted=False)
        self.publish(self.campaign_path,value)
    @contextlib.contextmanager
    def connection(self,board,log_path):
        from serial.tools.list_ports import comports
        port,usb,_,_=BOARDS[board];assert sum(p.device==port and p.serial_number==usb for p in comports())==1,'COM/USB identity mismatch'
        active=READ(self.q/'active-rtc-campaign.json');assert board not in active['powered_off_boards']
        marker=READ(self.q/'device-operations'/f'{board}.json');assert marker['run']==str(self.run) and not marker.get('power_off_reported')
        with self.coordination.serial_lease('rc1-asm-dbg1-soak-'+board,timeout=60):
            with log_path.open('a') as log:
                link=self.transport.wire.Link(port,log)
                try:yield link
                finally:link.serial.close()
    def guard(self,link,board):
        text=self.transport.identity(link,board,50);slot=BOARDS[board][2]
        assert f'Running: MONITOR {slot}, gen 00000032' in text
        assert ('65C816' if board=='2609' else '65C02') in text
        assert link.dump(0x7D30,0x7D30)==bytes([0xA0 if slot=='A' else 0xB0])
        assert link.dump(0x7D01,0x7D01)==bytes([BOARDS[board][3]]) and link.dump(0x7E02,0x7E03)==b'\x81\x7B'
        assert link.dump(0x7BFC,0x7BFD)==b'\0\0';return text
    def mode(self,link,board):
        if board!='2609':return dict(cpu='65C02',native_debugging=False)
        assert SHA(self.observer/'mode.s19')==self.observer_sha256
        self.transport.load(link,self.observer/'mode.s19');link.command('G 2000');raw=link.dump(0x2440,0x244D)
        assert raw[:6]==bytes.fromhex('160100000000') and raw[6]&12==4
        assert raw[7:12]==bytes.fromhex('0117040116') and raw[12]&1 and not raw[12]&8 and raw[13]==0xA5
        return dict(cpu='65C816 E=1',E_before_probe=True,DBR=0,PBR=0,direct_page=0,IRQ_disabled=True,decimal_clear=True,probe_enters_native=False,result_hex=raw.hex())
    def clock(self,link,board):
        text=link.command('R CLOCK',b'CLOCK> ')+link.command('STATUS',b'CLOCK> ')+link.command('Q')
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode());baseline=self.baselines[board]
        trim=(raw[8]&127)*(1 if raw[8]&128 else -1)
        assert trim==baseline['trim_steps'] and raw[7]==baseline['control_register']
        assert raw[0]&128 and raw[3]&8 and b'Running: yes' in text and b'Backup enabled: yes' in text
        return dict(passed=True,control=raw[7],trim_steps=trim,raw=raw.hex(),clock_set=False),text
    def flash(self,link,board):
        actual=[]
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
            data=self.transport.read_range(link,0x8000,0xFFFF,prompt);actual.append(hashlib.sha256(data).hexdigest())
        link.command('B3');assert actual==self.flash_hashes[board],'Flash/settings changed during soak';self.last_flash[board]=time.monotonic()
        return dict(passed=True,all_four_bank_sha256=actual)
    def cycle(self,board):
        self.transport.plans.package(self.kit)
        n=self.state['boards'][board]['passed_cycles'];out=self.run/board/f'{n:06d}';out.mkdir(parents=True)
        self.status('running',current_board=board,current_unit='rc1/ASM/DBG1')
        self.marker(board,'rc1-asm-dbg1-soak-running',application_RAM_restore_pending=True)
        self.publish(self.run/f'{board}-restore-needed.json',dict(needed=True,archive=str(self.run/f'{board}-before'),RAM_sha256=hashlib.sha256(self.original[board]).hexdigest()))
        proof=dict(passed=False,board=board,slot=BOARDS[board][2],started_utc=NOW(),native_debugging=False)
        self.publish(out/'report.json',proof)
        with self.connection(board,out/'serial.jsonl') as link:
            self.establish(link);proof['version']=self.guard(link,board);proof['mode_before']=self.mode(link,board)
            for text,name in (('APPS','apps'),('T 1','table'),('C','configuration'),('P','preference'),('W','wear'),('TIME','time'),('?','help')):
                (out/(name+'.txt')).write_bytes(link.command(text))
            batch=link.command('BATCH APPS;VERSION',b'BATCH done')+link.until(b'\r\nB3> ');assert b'BATCH stopped' not in batch;(out/'batch.txt').write_bytes(batch)
            proof['ASM'],text=asm_unit(link,self.transport,self.kit);(out/'asm.txt').write_bytes(text)
            proof['debugger']=debugger_unit(link,self.transport,self.kit)
            proof['mode_after']=self.mode(link,board);self.guard(link,board)
            if n%10==0:proof['RTC'],text=self.clock(link,board);(out/'clock.txt').write_bytes(text)
            if time.monotonic()-self.last_flash[board]>=3600:proof['flash']=self.flash(link,board)
        proof.update(passed=True,finished_utc=NOW());self.publish(out/'report.json',proof)
        entry=self.state['boards'][board];entry.update(passed_cycles=n+1,breakpoint_hits=16*(n+1),latest_receipt=str(out/'report.json'),latest_pass_unix=time.time())
        self.status('running',current_board=None,current_unit=None)
        print('PASS',board,n+1,'rc1/ASM/DBG1; 16 breakpoint hits',flush=True)
    def recover_idle(self,link):
        self.drain(link);text=link.command('',b'> ')
        if text.endswith(b'DBG> '):link.command('X')
        elif text.endswith(b'ASM> '):link.command('QUIT')
        elif text.endswith(b'CLOCK> '):link.command('Q')
        elif not re.search(rb'B[0-3]> $',text):raise RuntimeError('Unknown context; no reset or blind restoration')
        self.establish(link)
    def restore(self,board):
        errors=[];result=dict(passed=False,RAM_restored_host_verified=False)
        try:
            with self.connection(board,self.run/f'{board}-restore.jsonl') as link:
                self.recover_idle(link)
                try:
                    self.guard(link,board);result['mode']=self.mode(link,board)
                    result['RTC'],text=self.clock(link,board);(self.run/f'{board}-final-clock.txt').write_bytes(text)
                    result['flash']=self.flash(link,board)
                except BaseException:errors.append(traceback.format_exc());self.recover_idle(link)
                self.transport.load(link,self.run/f'{board}-before/restore-application-ram.s19')
                body=self.transport.read_range(link,0x200,0x200+len(self.original[board])-1);assert body==self.original[board]
                result['RAM_restored_host_verified']=True
            self.publish(self.run/f'{board}-restore-needed.json',dict(needed=False,host_verified=True,RAM_sha256=hashlib.sha256(body).hexdigest()))
        except BaseException:errors.append(traceback.format_exc())
        result.update(passed=not errors,errors=errors,finished_utc=NOW());self.publish(self.run/f'{board}-final.json',result)
        self.marker(board,'rc1-asm-dbg1-soak-idle' if result['passed'] else 'inspection-required',blocked=not result['passed'],application_RAM_restore_pending=not result['RAM_restored_host_verified'],application_RAM_restore_verified=result['RAM_restored_host_verified'])
        return result
    def snapshot(self):
        self.status('final-drift-snapshot')
        for name,digest in self.source_pins.items():assert SHA(name)==digest,'Snapshot source changed: '+name
        result=subprocess.run([sys.executable,str(self.root/'tools/snapshot_rtc_campaign.py'),'--board','2604','--board','2609'],cwd=self.root,capture_output=True,text=True)
        (self.run/'final-drift-snapshot.log').write_text(result.stdout+result.stderr)
        match=re.search(r'^SNAPSHOT (.+)$',result.stdout,re.M);path=Path(match[1].strip())/'summary.json' if match else None
        proof=dict(passed=False,returncode=result.returncode,summary=str(path) if path else None)
        if path and path.exists():
            summary=READ(path);proof.update(passed=result.returncode==0 and summary['passed'] and {b['board'] for b in summary['boards']}==set(BOARDS),summary_sha256=SHA(path),boards=summary['boards'])
        self.publish(self.run/'final-drift-snapshot.json',proof);return proof
    def execute(self):
        self.status('validating-fresh-backups');work_error=None;final={};snapshot=dict(passed=False);started=None
        assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            for board in BOARDS:
                cap=self.run/f'{board}-before';identity,banks=self.transport.plans.capture(cap);assert identity['board']==board and identity['usb_serial']==BOARDS[board][1]
                assert READ(cap/'report.json')['passed'];self.original[board]=(cap/'application-ram.bin').read_bytes()
                self.flash_hashes[board]=[hashlib.sha256(b).hexdigest() for b in banks];self.last_flash[board]=time.monotonic()
                for sector in READ(self.kit/'board-test-manifest.json')['sectors']:
                    offset=sector['address']-0x8000;assert banks[sector['bank']][offset:offset+4096]==(self.kit/sector['target']).read_bytes()
            started=time.monotonic();deadline=started+self.duration_seconds;started_unix=time.time()
            self.status('running',started_utc=NOW(),started_unix=started_unix,deadline_unix=started_unix+self.duration_seconds,monitored_seconds=0)
            self.campaign(True)
            while not due(deadline,self.run/'STOP'):
                for board in BOARDS:
                    if due(deadline,self.run/'STOP'):break
                    assert SHA(self.auth['baseline_index'])==self.auth['baseline_index_sha256']
                    assert SHA(self.kit/'board-test-manifest.json')==KIT_SHA
                    self.cycle(board);self.state['monitored_seconds']=time.monotonic()-started
                for _ in range(5):
                    if due(deadline,self.run/'STOP'):break
                    time.sleep(1)
            self.state['completed_authorized_duration']=time.monotonic()>=deadline
        except BaseException:
            work_error=traceback.format_exc();self.state['workload_failure']=work_error;print(work_error,flush=True)
        finally:
            self.state['monitored_seconds']=0 if started is None else time.monotonic()-started
            self.status('restoring')
            final=restore_all(self.original,self.restore)
            try:
                if set(final)==set(BOARDS) and all(x['passed'] for x in final.values()):
                    snapshot=self.snapshot()
                    for board in BOARDS:
                        try:
                            with self.connection(board,self.run/f'{board}-post-snapshot.jsonl') as link:
                                self.establish(link);self.guard(link,board)
                                assert self.transport.read_range(link,0x200,0x200+len(self.original[board])-1)==self.original[board]
                            final[board]['RAM_verified_after_snapshot']=True
                        except BaseException:
                            final[board].update(passed=False,RAM_verified_after_snapshot=False)
                            final[board]['errors'].append(traceback.format_exc())
                            self.marker(board,'inspection-required',blocked=True,application_RAM_restore_pending=True)
                            self.publish(self.run/f'{board}-restore-needed.json',dict(needed=True,reason='post-snapshot full RAM verification failed',archive=str(self.run/f'{board}-before')))
                        self.publish(self.run/f'{board}-final.json',final[board])
            except BaseException:self.state['final_snapshot_failure']=traceback.format_exc()
            passed=not work_error and self.state.get('completed_authorized_duration',False) and snapshot['passed'] and set(final)==set(BOARDS) and all(x.get('RAM_verified_after_snapshot') for x in final.values())
            self.status('completed' if passed else 'stopped-needs-review',passed=passed,final=final,final_drift_snapshot=snapshot,finished_utc=NOW())
            self.publish(self.run/'report.json',self.state);self.campaign(False)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print('END',self.state['state'],self.run/'report.json',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    runner=Runner(a.workspace,a.run)
    if a.check_only:print('PASS owner authorization, exact candidate, baseline and E=1 observer; no ports');return
    assert not (a.run/'status.json').exists(),'Worker may not be restarted over an existing run'
    runner.execute()

if __name__=='__main__':main()
