"""Finite owner-authorized register-edit qualification; no firmware/persistent writes.

Capture is read-only. Execute requires sealed CPU/peripheral admission and fresh
repeated archives. One local serial lease owns the whole board operation.
"""
import argparse, contextlib, hashlib, importlib.util, json, os, re, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
KIT=ROOT/'BUILD/rc1-debugger-v1g-boardtest-r1'
KIT_SHA='42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf'
FIRMWARE_SHA='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
BOARDS={'2604':('COM5','A10MQGVHA','B',2),'2609':('COM8','A10MPQXCA','A',0x16)}
DBG=b'\r\nDBG> ';MON=b'\r\nB3> '
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
NOW=lambda:datetime.now(timezone.utc).isoformat()

def groups(cells):
    result=[]
    for address,value in sorted(cells.items()):
        if not result or address!=result[-1][0]+len(result[-1][1]):result.append((address,bytearray()))
        result[-1][1].append(value)
    return [(address,bytes(body)) for address,body in result]

def admit(run,execute):
    run=Path(run).resolve();assert run.is_relative_to(Q)
    auth=READ(run/'owner-authorization.json')
    assert auth['owner_authorized'] and auth['boards']==list(BOARDS) and auth['monitor_slots']==['A','B']
    assert auth['promotion_held'] and not auth['native_debugging'] and not auth['native_applications'] and auth['RTC_issue_deferred']
    assert not auth['RTC_endurance_or_drift_collection_authorized'] and not auth['reset_firmware_install_or_persistent_setting_changes_authorized']
    assert auth['firmware_sha256']==FIRMWARE_SHA and auth['package_manifest_sha256']==KIT_SHA and SHA(KIT/'board-test-manifest.json')==KIT_SHA
    assert READ(Q/'rc1-dbg1-promotion-hold.json')['held']
    assert set(READ(Q/'active-rtc-campaign.json')['powered_off_boards'])=={'2205','2512'}
    if execute:
        ad=READ(run/'admission.json');assert ad['passed'] and ad['owner_authorization_sha256']==SHA(run/'owner-authorization.json')
        assert not ad['native_debugging'] and ad['RTC_issue_deferred']
        for path,digest in ad['source_sha256'].items():assert SHA(path)==digest,path
        for path,digest in ad['evidence_sha256'].items():assert SHA(path)==digest,path
        assert SHA(__file__)==ad['runner_sha256']
    return auth

class Qualification:
    def __init__(self,run,board,execute=False):
        self.run=Path(run).resolve();self.board=board;self.auth=admit(self.run,execute)
        self.port,self.usb,self.preferred,self.cpu=BOARDS[board]
        sys.path[:0]=[str(KIT),str(ROOT/'tools')]
        import board_link as transport
        import serial_test_coordination as coordination
        from atomic_json import publish
        from rtc_prompt_sync import establish_b3,drain
        self.t,self.coordination,self.publish,self.establish,self.drain=transport,coordination,publish,establish_b3,drain
        coordination.ROOT=Q/'serial-coordination';transport.plans.package(KIT)
        self.before=self.run/f'{board}-before'
        self.out=self.run/board
        self.borrowed=False;self.original=None;self.banks=None;self.baseline=None
        self.result=dict(passed=False,board=board,started_utc=NOW(),pid=os.getpid(),promotion_held=True,
            native_debugging=False,native_applications=False,RTC_issue_deferred=True,RTC_qualification_performed=False,
            firmware_written=False,settings_written=False,reset=False,slots={},RAM_restored_host_verified=False)

    def marker(self,state,**extra):
        path=Q/'device-operations'/f'{self.board}.json';value=READ(path)
        prior=self.run/f'{self.board}-device-operation-before.json'
        same_run=value.get('register_edit_run')==str(self.run)
        assert value.get('soak_owner_stopped') and value.get('RTC_sampling_owner_stopped')
        assert not value.get('current_soak_worker_pid') and not value.get('one_shot_collection_authorized')
        assert same_run or (not value.get('application_RAM_restore_pending') and not value.get('register_edit_worker_active') and not value.get('block_snapshot'))
        if same_run and (value.get('register_edit_worker_active') or value.get('application_RAM_restore_pending')):
            assert value.get('register_edit_worker_pid')==os.getpid()
        if not prior.exists():self.publish(prior,value)
        assert not value.get('physical_reset_pending') and not value.get('power_off_reported')
        value.update(state=state,run=str(self.run),register_edit_run=str(self.run),register_edit_worker_pid=os.getpid(),
            block_snapshot=True,soak_owner_stopped=True,promotion_held=True,native_debugging=False)
        value.update(extra)
        self.publish(path,value)

    @contextlib.contextmanager
    def connection(self,log):
        from serial.tools.list_ports import comports
        assert sum(p.device==self.port and p.serial_number==self.usb for p in comports())==1
        assert self.board not in READ(Q/'active-rtc-campaign.json')['powered_off_boards']
        with self.coordination.serial_lease('dbg1-register-edits-'+self.board,timeout=60,priority=True):
            with log.open('x') as stream:
                link=self.t.wire.Link(self.port,stream)
                try:
                    self.establish(link);yield link
                finally:link.serial.close()

    def identity(self,link,slot=None):
        text=self.t.identity(link,self.board,50)
        assert link.dump(0x7D01,0x7D01)==bytes([self.cpu])
        assert link.dump(0x7D0A,0x7D0B)==bytes.fromhex('FF64') and link.dump(0x7D0C,0x7D0C)[0]&0x80
        assert link.dump(0x7E02,0x7E03)==bytes.fromhex('817B')
        if slot:
            assert f'Running: MONITOR {slot}, gen 00000032' in text
            assert link.dump(0x7D30,0x7D30)==bytes([0xa0 if slot=='A' else 0xb0])
        assert link.dump(0x7BFC,0x7BFF)==bytes(4)
        return text

    def controls(self,link,clock=True):
        refs={cmd:link.command(cmd) for cmd in ('C','P','W')}
        status=dict(status_sha256={k:hashlib.sha256(v).hexdigest() for k,v in refs.items()})
        if not clock:return status
        text=link.command('R CLOCK',b'CLOCK> ')+link.command('STATUS',b'CLOCK> ')+link.command('Q')
        for token in (b'Running: yes',b'Backup enabled: yes'):assert token in text
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
        assert len(raw)==9 and raw[0]&128 and raw[3]&8
        expected=bytes.fromhex('000C' if self.board=='2604' else '800E');assert raw[7:9]==expected
        return dict(**status,
            RTC_control=raw[7],RTC_trim_encoding=raw[8],RTC_oscillator_start=bool(raw[0]&128),RTC_backup_enabled=bool(raw[3]&8))

    def read_flash(self,link):
        bodies=[]
        try:
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                bodies.append(self.t.read_range(link,0x8000,0xffff,prompt))
        finally:link.command('B3')
        return bodies

    def capture(self):
        assert not self.before.exists();self.before.mkdir();(self.before/'.gitignore').write_text('*\n')
        state=dict(passed=False,operation='capture',board=self.board,repeat_verified=False,board_RAM_written=False,started_utc=NOW())
        self.marker('dbg1-register-edit-read-only-capture',application_RAM_restore_pending=False)
        try:
            with self.connection(self.before/'serial.jsonl') as link:
                state['version']=self.identity(link,self.preferred);state['controls']=self.controls(link,clock=False)
                first=self.read_flash(link);second=self.read_flash(link);assert first==second
                expected=READ(Q/'rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/hardware-preflight.json')['restoration']['boards'][self.board]['flash']['all_four_bank_sha256']
                assert [hashlib.sha256(v).hexdigest() for v in first]==expected
                ram=self.t.read_range(link,0x200,0x64ff);repeat=self.t.read_range(link,0x200,0x64ff);assert ram==repeat
                files={}
                for n,body in enumerate(first):
                    for suffix,data in (('',body),('-repeat',second[n])):
                        name=f'b{n}{suffix}.bin';(self.before/name).write_bytes(data);files[name]=dict(bytes=len(data),sha256=SHA(self.before/name))
                for name,data in [('application-ram.bin',ram),('application-ram-repeat.bin',repeat),('restore-application-ram.s19',self.t.wire.s19(dict(enumerate(ram,0x200)),0x200))]:
                    (self.before/name).write_bytes(data);files[name]=dict(bytes=len(data),sha256=SHA(self.before/name))
                self.publish(self.before/'capture.json',dict(schema=1,board=self.board,usb_serial=self.usb,repeat_verified=True,files=files))
                self.t.plans.capture(self.before)
                state.update(passed=True,repeat_verified=True,all_four_flash_sha256=expected,RAM_sha256=hashlib.sha256(ram).hexdigest(),RAM_bytes=len(ram))
        except BaseException:state['failure']=traceback.format_exc();raise
        finally:
            state['finished_utc']=NOW();self.publish(self.before/'report.json',state)
            self.marker('dbg1-register-edit-capture-passed' if state['passed'] else 'inspection-required',application_RAM_restore_pending=False,application_RAM_restore_verified=True,
                block_snapshot=not state['passed'],register_edit_worker_active=False)
        print('PASS fresh repeated capture',self.board,flush=True)

    def mode(self,link):
        if self.board=='2604':return dict(cpu='65C02',native_debugging=False)
        observer=Q/'rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer';pin=READ(observer/'report.json')
        assert pin['passed'] and not pin['enters_native_mode'] and SHA(observer/'mode.s19')==pin['s19_sha256']
        self.t.load(link,observer/'mode.s19');link.command('G 2000');raw=link.dump(0x2440,0x244d)
        assert raw[:6]==bytes.fromhex('160100000000') and raw[6]&12==4 and raw[7:12]==bytes.fromhex('0117040116')
        assert raw[12]&1 and not raw[12]&8 and raw[13]==0xa5
        return dict(cpu='65C816 E=1',E_before_probe=True,DBR=0,PBR=0,direct_page=0,probe_enters_native=False,result_hex=raw.hex())

    def switch(self,link,slot):
        assert link.dump(0x7BFC,0x7BFF)==bytes(4)
        sy=READ(ROOT/'BUILD/rc1-debugger-v1g/symbols.json')[f'core/monitor-{slot.lower()}0']
        entry=sy['V2_PROMPT_ENTRY'];assert entry==(0xa087 if slot=='A' else 0xb087)
        target=link.dump(entry,entry+2);assert target==bytes([0x4c,0x7b,0xa0 if slot=='A' else 0xb0])
        image=bytes([0x78,0xd8,0x4c,entry&255,entry>>8]);link.write_ram(0x2000,image)
        reply=link.command('G 2000');self.identity(link,slot)
        return dict(passed=True,entry=entry,shim_hex=image.hex(),shim_sha256=hashlib.sha256(image).hexdigest(),reset=False,preference_written=False,output_sha256=hashlib.sha256(reply).hexdigest())

    def recover(self,link):
        self.drain(link);reply=link.command('',b'> ')
        if reply.endswith(b'DBG> '):link.command('X')
        elif reply.endswith(b'CLOCK> '):link.command('Q')
        elif not reply.endswith(MON):raise RuntimeError('Unknown context: no reset or blind RAM restore')
        self.establish(link);assert link.dump(0x7BFC,0x7BFF)==bytes(4)

    def saved_images(self,link):
        return {name:hashlib.sha256(link.dump(first,first+255,DBG)).hexdigest() for name,first in (('ZP',0),('stack',0x100))}

    def fixture(self,link,cases):
        cells=cases.fixture_cells()
        for address,body in groups(cells):
            assert 0x200<=address and address+len(body)<=0x6500;link.write_ram(address,body)
        self.verify_fixture(link,cases,MON)

    def verify_fixture(self,link,cases,prompt):
        cells={a:v for a,v in cases.fixture_cells().items() if not cases.TRACE<=a<cases.TRACE+6}
        for address,body in groups(cells):assert link.dump(address,address+len(body)-1,prompt)==body

    def begin(self,link,cases):
        reply=link.command(f'G {cases.ENTRY:04X}',DBG);value=cases.parse_display(reply);assert value==cases.BASELINE,value
        return value

    def register_command(self,link,cases,row,before):
        command=row['command'];assert '\r' not in command and command.lstrip().upper().startswith('R')
        if row['category']=='reader-cancel':
            assert command.endswith('\x03');link.send(command.encode('ascii'));reply=link.until(DBG)
        else:reply=link.command(command,DBG)
        assert cases.error_response(reply)==(not row['accepted']),(row,reply[-300:])
        shown=reply if cases.DISPLAY.search(reply) else link.command('R',DBG)
        actual=cases.parse_display(shown);expected=cases.expected_after(before,row)
        assert actual==expected,(row,expected,actual)
        return actual,dict(name=row['name'],command=command,accepted=row['accepted'],category=row['category'],
            expected_context=expected,actual_context=actual,passed=True,response_sha256=hashlib.sha256(reply).hexdigest())

    def slot(self,link,cases,slot):
        out=self.out/slot;out.mkdir();proof=dict(passed=False,started_utc=NOW(),slot=slot,parser_checks=0,resume_checks=0,unsafe_PC_refusals=0)
        self.result['slots'][slot]=proof;self.publish(self.out/'report.json',self.result)
        proof['mode_before_switch']=self.mode(link);proof['monitor_switch']=self.switch(link,slot);proof['mode_before']=self.mode(link)
        self.fixture(link,cases);context=self.begin(link,cases);images=self.saved_images(link)
        with (out/'parser-receipts.jsonl').open('x') as receipt:
            last_category=None
            for index,row in enumerate(cases.parser_cases(True)):
                if (self.run/'STOP').exists():raise RuntimeError('Owner STOP: finite qualification incomplete')
                if last_category is not None and row['category']!=last_category:assert self.saved_images(link)==images
                context,item=self.register_command(link,cases,row,context)
                receipt.write(json.dumps(item)+'\n');receipt.flush();proof['parser_checks']+=1;last_category=row['category']
                if index%100==0:self.publish(self.out/'report.json',self.result);print('PROGRESS',self.board,slot,'R parser',index+1,flush=True)
        assert self.saved_images(link)==images;self.verify_fixture(link,cases,DBG)
        # Restore only stopped context before attempting control commands.
        for field,value in cases.BASELINE.items():
            row=cases.case('restore-'+field,f'R {field}={value:04X}' if field=='PC' else f'R {field}={value:02X}',field,value)
            context,_=self.register_command(link,cases,row,context)
        for address in cases.UNSAFE_PC_TARGETS:
            row=cases.case('unsafe-PC',f'R PC={address:04X}','PC',address);context,_=self.register_command(link,cases,row,context)
            for action in ('C','S','N'):
                reply=link.command(action,DBG);assert cases.error_response(reply),(address,action,reply)
                assert cases.parse_display(link.command('R',DBG))==context
                proof['unsafe_PC_refusals']+=1
        link.command('X');assert link.dump(0x7BFC,0x7BFF)==bytes(4)
        resume_rows=[dict(row,action='C') for row in cases.resume_cases(False,hardware=True)]
        if hasattr(cases,'step_resume_cases'):resume_rows+=cases.step_resume_cases()
        with (out/'resume-receipts.jsonl').open('x') as receipt:
            for row in resume_rows:
                if (self.run/'STOP').exists():raise RuntimeError('Owner STOP: finite qualification incomplete')
                context=self.begin(link,cases);context,_=self.register_command(link,cases,row,context)
                action=row.get('operation',row.get('action','C'));step_context=None
                if action in ('S','N'):
                    reply=link.command(action,DBG);assert not cases.error_response(reply)
                    step_context=cases.parse_display(reply)
                    expected_step=dict(context,PC=cases.CAPTURE)
                    if row['field']=='PC':expected_step['SP']=(expected_step['SP']+2)&255
                    assert step_context==expected_step,(row,step_context,expected_step)
                reply=link.command('C',DBG);assert not cases.error_response(reply)
                stop=cases.parse_display(reply);assert stop['PC']==cases.CAPTURE+25
                trace=link.dump(cases.TRACE,cases.TRACE+5,DBG);expected=cases.resume_expected(cases.BASELINE,row)
                assert trace==expected,(row,trace.hex(),expected.hex())
                self.verify_fixture(link,cases,DBG)
                item=dict(name=row['name'],command=row['command'],action=action,passed=True,step_context=step_context,
                    expected_trace=expected.hex(),actual_trace=trace.hex(),stop_context=stop,program_bytes_unchanged=True)
                receipt.write(json.dumps(item)+'\n');receipt.flush();proof['resume_checks']+=1
                link.command('X');assert link.dump(0x7BFC,0x7BFF)==bytes(4)
        proof.update(passed=True,saved_stack_and_ZP_images_unchanged_by_parser=True,program_bytes_unchanged=True,
            mode_after=self.mode(link),finished_utc=NOW())
        self.publish(out/'report.json',proof);self.publish(self.out/'report.json',self.result)
        print('PASS',self.board,'MON',slot,proof['parser_checks'],'parser',proof['resume_checks'],'resume',proof['unsafe_PC_refusals'],'PC execution refusals',flush=True)

    def execute(self):
        try:self._execute()
        except BaseException:
            if not self.borrowed:
                self.result.update(passed=False,entry_failure=traceback.format_exc(),application_RAM_not_borrowed=True,
                    RAM_restoration_not_required=True,finished_utc=NOW())
                if self.out.exists():
                    self.publish(self.out/'report.json',self.result)
                    self.publish(self.out/'restore-needed.json',dict(needed=False,application_RAM_not_borrowed=True))
                self.marker('inspection-required',application_RAM_restore_pending=False,register_edit_worker_active=False,block_snapshot=True)
            raise

    def _execute(self):
        assert not self.out.exists();self.out.mkdir();self.publish(self.out/'report.json',self.result)
        identity,self.banks=self.t.plans.capture(self.before);assert identity['board']==self.board and identity['usb_serial']==self.usb
        assert READ(self.before/'report.json')['passed'];self.original=(self.before/'application-ram.bin').read_bytes();assert len(self.original)==25344
        spec=importlib.util.spec_from_file_location('register_cases',ROOT/'tools/rc1_dbg_register_edits.py');cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
        self.marker('dbg1-register-edit-entry-checks',application_RAM_restore_pending=False,register_edit_worker_active=True)
        self.publish(self.out/'restore-needed.json',dict(needed=False,application_RAM_not_borrowed=True))
        with self.connection(self.out/'serial.jsonl') as link:
            try:
                self.identity(link,self.preferred)
                assert self.controls(link,clock=False)==READ(self.before/'report.json')['controls']
                assert self.t.read_range(link,0x200,0x64ff)==self.original
                assert self.read_flash(link)==self.banks
                self.borrowed=True
                self.marker('dbg1-register-edit-qualification',application_RAM_restore_pending=True,application_RAM_restore_verified=False,register_edit_worker_active=True)
                self.publish(self.out/'restore-needed.json',dict(needed=True,archive=str(self.before),RAM_sha256=SHA(self.before/'application-ram.bin')))
                self.baseline=self.controls(link)
                for slot in ('A','B'):self.slot(link,cases,slot)
                self.result['checks_passed']=True
            except BaseException:self.result['failure']=traceback.format_exc();print(self.result['failure'],flush=True)
            finally:
                if not self.borrowed:
                    self.result['application_RAM_not_borrowed']=True
                    self.result['RAM_restoration_not_required']=True
                else:
                    idle=False
                    try:
                        self.recover(link);self.identity(link)
                        self.result['monitor_return']=self.switch(link,self.preferred);idle=True
                    except BaseException:self.result['recovery_failure']=traceback.format_exc()
                    if idle:
                        try:
                            self.result['final_mode']=self.mode(link);self.identity(link,self.preferred)
                            final_controls=self.controls(link);assert self.baseline is None or final_controls==self.baseline
                            self.result['final_controls']=final_controls
                            assert self.read_flash(link)==self.banks;self.result['all_four_flash_banks_unchanged']=True
                        except BaseException:self.result['preservation_failure']=traceback.format_exc()
                        # A preserving-check failure still requires original RAM restoration.
                        try:
                            self.recover(link);self.identity(link,self.preferred)
                            self.t.load(link,self.before/'restore-application-ram.s19')
                            for _ in range(2):assert self.t.read_range(link,0x200,0x64ff)==self.original
                            self.result['RAM_restored_host_verified']=True;self.result['full_RAM_rereads']=2
                            self.publish(self.out/'restore-needed.json',dict(needed=False,host_verified=True,RAM_sha256=hashlib.sha256(self.original).hexdigest()))
                        except BaseException:self.result['restoration_failure']=traceback.format_exc()
                self.result.update(passed=bool(self.result.get('checks_passed')) and self.result['RAM_restored_host_verified'] and
                    not any(k in self.result for k in ('recovery_failure','restoration_failure','preservation_failure')),finished_utc=NOW())
                self.publish(self.out/'report.json',self.result)
                self.marker('dbg1-register-edits-qualified' if self.result['passed'] else 'inspection-required',
                    application_RAM_restore_pending=self.borrowed and not self.result['RAM_restored_host_verified'],application_RAM_restore_verified=self.result['RAM_restored_host_verified'],
                    register_edit_qualified=self.result['passed'],block_snapshot=not self.result['passed'],register_edit_worker_active=False)
        if not self.result['passed']:raise RuntimeError('Register qualification failed; inspect report and restoration evidence')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=BOARDS,required=True)
    ap.add_argument('--capture',action='store_true');ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    worker=Qualification(a.run,a.board,execute=not a.capture)
    if a.check_only:print('PASS authorization/source/admission; no ports opened');return
    if a.capture:worker.capture()
    else:worker.execute()

if __name__=='__main__':main()
