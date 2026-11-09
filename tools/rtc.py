"""STR8-N UTIL RTC. Collect UTC observations, sync, or calculate/apply trim."""
import argparse
import contextlib
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

import memory_tool as memory
from installer.engine.legacy_transport import Link
from nf_recovery import RecoveryClient, PROMPT as READBACK
from rtc_timing import (COLUMNS, Reference, calculate, decode_rtc, require,
                        samples, series_key, trim_steps)

ROOT = Path(__file__).resolve().parents[1]
F_HASH = '8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
MON, REC, CLOCK = b'\r\nB3> ', b'REC> ', b'CLOCK> '
CONFIRM = b'Type YES to confirm: '
OFFSET = b'Local UTC offset +/-HH:MM (Enter keeps +00:00): '
SAMPLE_START = 0x2000


def save(path, body):
    memory.save(path, body)


def checked_image(kit, file, sha):
    body=(kit/file).read_bytes()
    require(memory.sha(body)==sha, 'Image digest mismatch: '+file)
    return body


class Board:
    def __init__(self, link, out, report, config, kit):
        self.link, self.out, self.report, self.config, self.kit = link, out, report, config, kit
        self.context = self.original = None
        self.slot = 'B'
        self.block = self.owner = None
        self.escrow_pending = False

    def update(self, **values):
        self.report.update(values)
        save(self.out/'report.json',self.report)

    def wait(self, tokens, seconds=20):
        limit=time.monotonic()+seconds
        while time.monotonic()<limit:
            found=[(self.link.pending.find(t),t) for t in tokens if t in self.link.pending]
            if found:
                at,self.context=min(found)
                end=at+len(self.context)
                body=bytes(self.link.pending[:end])
                del self.link.pending[:end]
                return body
            self.link.pending.extend(self.link.read(max(1,self.link.serial.in_waiting)))
        self.context=None
        raise TimeoutError('Expected prompt or packet missing; see the serial transcript')

    def send(self, data, tokens, seconds=20):
        self.context=None
        self.link.send(data)
        return self.wait(tokens,seconds)

    def cmd(self, line, tokens=None, seconds=20):
        require(self.context is not None,'Unknown board prompt')
        return self.send(line.encode('ascii')+b'\r',tokens or (self.context,),seconds)

    def dump(self, first, size):
        require(self.context==MON,'MON B3 prompt required')
        data=[]
        for address in range(first,first+size,512):
            end=min(first+size-1,address+511)
            data.append(memory.parse_monitor_dump(self.cmd(f'D {address:04X} {end:04X}'),address,end))
        return b''.join(data)

    def stage(self, address, body):
        require(self.context==MON and 0x200<=address and address+len(body)<=0x6700,
                'Staging must stay in owner RAM at a known MON prompt')
        for offset in range(0,len(body),8):
            text=' '.join(f'{x:02X}' for x in body[offset:offset+8])
            face=self.cmd(f'M {address+offset:04X} {text}')
            require(not any(x in face for x in (b'Long line',b'Bad',b'Protected',b'Wrap',b'REFUSED')),
                    'MON refused RAM staging')
        require(self.dump(address,len(body))==body, 'RAM staging readback differs')

    def admit(self):
        self.send(b'\r',(MON,REC),seconds=12)
        self.original=self.context
        if self.context==REC:
            self.cmd('B',(MON,))
        banner=self.cmd('VERSION')
        memory.admit_monitor_banner(banner,self.config['cpu'])
        active=re.search(rb'STR8-N MON ([AB])  gen 00000010',banner)
        require(active is not None,'Unified RC3 MON generation required')
        self.slot=active[1].decode()
        require(memory.sha(self.dump(0xf000,4096))==F_HASH,'Frozen Foundation differs')
        components=json.loads((self.kit/'COMPONENTS.json').read_bytes())['artifacts']
        filename,info=next((n,x) for n,x in components.items()
                           if x['component']=='MON' and f"slot-{self.slot.lower()}" in n)
        require(memory.sha(self.dump(0xa000 if self.slot=='A' else 0xb000,4096))==info['sha256'],
                'Installed monitor differs from the matching RC3 kit')
        self.update(original_prompt=self.original.decode().strip(),monitor_slot=self.slot,
                    foundation_sha256=F_HASH,verified_monitor_image=filename)

    def readback(self):
        if self.context==MON:
            self.cmd('Q',(REC,))
        require(self.context==REC,'READBACK needs an observed REC prompt')
        self.send(b'L\r',(b'SEND BIN\r\n',))
        self.context=None
        for offset in range(0,len(self.reader),16):
            self.link.send(self.reader[offset:offset+16])
            time.sleep(.002)
        self.wait((READBACK,))
        client=RecoveryClient(Stream(self.link),timeout=30,progress=lambda _ : None)
        client.admitted=True
        return client

    def backup_owner(self):
        items=json.loads((self.kit/'COMPONENTS.json').read_bytes())['artifacts']
        name,info=next((name,x) for name,x in items.items() if x['component']=='READBACK')
        self.reader=checked_image(self.kit,name,info['sha256'])
        prefix=self.dump(0x200,len(self.reader))
        zp=self.dump(0,0xe0)
        memory.durable(self.out/'owner-prefix.bin',prefix)
        memory.durable(self.out/'owner-zp.bin',zp)
        self.escrow_pending=True
        self.update(ram_restore_pending=True)
        client=self.readback()
        self.context=None
        current=client.read(b'M',0x6500)
        ram=prefix+current[len(prefix):]
        memory.durable(self.out/'owner-ram.bin',ram)
        self.owner=ram,zp
        require(client.read(b'Z',0xe0)==zp,'Owner ZP differs after starting READBACK')
        self.context=READBACK
        self.send(b'Q',(REC,))
        self.cmd(self.slot,(MON,))

    def clock(self):
        require(self.context==MON,'CLOCK launch needs MON')
        face=self.cmd('R CLOCK',(CLOCK,OFFSET))
        if self.context==OFFSET:
            face+=self.cmd('',(CLOCK,))
        require(b'STR8-N UTIL CLOCK 1.10' in face and b'Services unavailable' not in face,
                'Expected installed RC3 CLOCK')

    def sample(self, image, ref, segment):
        before=self.dump(SAMPLE_START,len(image))
        path=self.out/f'sample-escrow-{len(list(self.out.glob("sample-escrow-*.bin")))}.bin'
        memory.durable(path,before)
        self.block=before
        self.update(ram_restore_pending=True)
        self.stage(SAMPLE_START,image)
        self.send(b'G 2000\r',(b'!',))
        readings=[]
        stop=time.perf_counter()+4.5
        while time.perf_counter()<stop:
            start=ref.now()
            require(self.send(b'r',(b'@',),seconds=5)==b'@','Unexpected sampler packet framing')
            self.context=None
            packet=Stream(self.link).exact(19)
            finish=ref.now()
            require(self.wait((b'!',),seconds=5)==b'!','Sampler did not return to ready')
            xor=0
            for value in packet:
                xor^=value
            require(xor==0,'Sampler checksum differs')
            if packet[0]!=4:
                require(packet[0]==0,f'Sampler I²C error {packet[0]}')
                raw=packet[1:18]
                rtc=decode_rtc(raw)
                u=ref.uncertainty()
                readings.append((rtc,start,finish,rtc-finish-u,rtc+1-start+u,raw))
            time.sleep(.022)
        self.restore_block()
        require(len({x[0] for x in readings})>=3,'Too few RTC tick boundaries')
        raw=readings[-1][-1]
        require(all(x[-1][7:]==raw[7:] for x in readings),'RTC trim, control or outage evidence changed')
        lo=max(x[3] for x in readings)
        hi=min(x[4] for x in readings)
        require(0<=hi-lo<=.5,'RTC observation bounds are inconsistent or too wide')
        return dict(segment=segment,device=self.config['usb_serial'],server=ref.server,
                    reference_unix=(readings[0][1]+readings[-1][2])/2,
                    offset_low_s=lo,offset_high_s=hi,control_hex=f'{raw[7]:02x}',
                    trim_hex=f'{raw[8]:02x}',outage_hex=raw[9:].hex()),len(readings)

    def restore_block(self):
        if self.context==b'!':
            self.send(b'q',(MON,))
        require(self.context==MON,'Sampler RAM restore requires a known MON prompt')
        self.stage(SAMPLE_START,self.block)
        self.block=None
        self.update(sample_ram_verified=True,ram_restore_pending=self.escrow_pending)

    def finish(self):
        if self.block is not None and self.context in (b'!',MON):
            self.restore_block()
        if self.context==CONFIRM:
            self.cmd('NO',(CLOCK,OFFSET))
        if self.context==OFFSET:
            self.cmd('',(CLOCK,))
        if self.context==CLOCK:
            self.cmd('Q',(MON,))
        if self.owner is not None and self.context in (MON,REC,READBACK):
            if self.context==READBACK:
                self.send(b'Q',(REC,))
            client=self.readback()
            self.context=None
            result=client.restore_owner(*self.owner)
            self.context=REC
            self.escrow_pending=False
            self.update(**result,ram_restore_pending=False)
        if self.context==REC and self.original==MON:
            self.cmd(self.slot,(MON,))
        if self.context==MON and self.original==REC:
            self.cmd('Q',(REC,))
        self.update(final_prompt=self.context.decode().strip() if self.context else None,
                    original_prompt_restored=self.original is not None and self.context==self.original)
        require(self.original is None or self.context==self.original, 'Original prompt was not restored')


class Stream:
    def __init__(self, link):
        self.link=link

    def write(self, data):
        self.link.send(bytes(data))
        return len(data)

    def read(self, count):
        if self.link.pending:
            data=bytes(self.link.pending[:count])
            del self.link.pending[:count]
            return data
        return self.link.read(count)

    def exact(self, count):
        body=bytearray()
        end=time.monotonic()+5
        while len(body)<count and time.monotonic()<end:
            body.extend(self.read(count-len(body)))
        require(len(body)==count,'Incomplete sampler packet; preserve RAM escrow')
        return bytes(body)


def status(board, expected):
    face=board.cmd('STATUS')
    regs=re.search(rb'RTC registers \(raw\):((?: [0-9A-F]{2}){9})',face)
    require(regs is not None and b'Running: yes' in face and b'Calendar valid: yes' in face
            and b'Power-fail latched: no' in face,'CLOCK STATUS did not admit the RTC')
    raw=bytes.fromhex(regs[1].decode())
    require(raw[7:9]==bytes.fromhex(expected['control_hex']+expected['trim_hex']),
            'RTC control or trim changed after measurement')
    return raw


def confirm(board, cmd, expected):
    face=board.cmd(cmd,(CONFIRM,CLOCK,OFFSET))
    require(board.context==CONFIRM and expected in face,'CLOCK refused or confirmation differed')
    return face


def segment_for(profile, device):
    path=profile.with_suffix('.rtc-segment.json')
    if not path.exists():
        return 'initial'
    state=json.loads(path.read_bytes())
    require(state['device']==device and re.fullmatch(r'[0-9a-f]{32}',state['segment']),
            'Invalid private RTC segment sidecar')
    return state['segment']


def start_segment(board, args, device, intent):
    segment=uuid.uuid4().hex
    save(args.profile.with_suffix('.rtc-segment.json'),dict(device=device,segment=segment))
    board.update(write_intent=intent,new_segment=segment)
    return segment


def apply(board, args, ref, before, fit):
    raw_control=int(before['control_hex'],16)
    require(not raw_control&0x30,'Alarms are enabled')
    if args.mode=='trim':
        require(not raw_control&0x44,'Trim requires fine mode and square wave OFF')
        require(fit['device']==before['device'] and fit['reference']==before['server']
                and fit['current_trim']==trim_steps(int(before['trim_hex'],16)),
                'Live RTC does not match the trim calculation')
        proposal=fit['proposed_trim']
        require(proposal is not None,'Drift bounds do not support a unique trim')
        require(proposal!=fit['current_trim'],'Current trim already matches the proposal')
        action=f'TRIM {proposal:+d}'
    else:
        action='Set board calendar from UTC reference'
    require(input(f'{action}. Type YES to apply on {before["device"]}: ')=='YES',
            'Operation cancelled by operator')
    ref.check()
    board.backup_owner()
    board.clock()
    status(board,before)
    if args.mode=='trim':
        face=confirm(board,action,b'Requested trim:')
        match=re.search(rb'Requested trim:\s*([+-]?\d+) steps',face)
        require(match is not None and int(match[1])==proposal,'Wrong trim confirmation')
        segment=start_segment(board,args,before['device'],action)
        result=board.cmd('YES',(CLOCK,OFFSET))
        require(board.context==CLOCK and b'Trim change not verified' not in result
                and b'Trim change refused' not in result,'Inspect trim result before another attempt')
        expected=0 if proposal==0 else abs(proposal)|(0x80 if proposal>0 else 0)
    else:
        target=math.ceil(ref.now()+8)
        utc=datetime.fromtimestamp(target,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        face=confirm(board,'SET '+utc,b'SET changes UTC')
        require(utc.encode() in face,'CLOCK confirmation UTC differs')
        board.update(target_utc=utc)
        board.send(b'YES',(b'YES',),seconds=5)
        board.context=CONFIRM
        require(ref.now()<target-.15,'Missed UTC boundary')
        segment=start_segment(board,args,before['device'],'SET '+utc)
        require(ref.now()<target-.08,'Missed UTC boundary after recording intent')
        while ref.now()<target:
            time.sleep(min(.02,max(0,target-ref.now())))
        result=board.send(b'\r',(CLOCK,OFFSET))
        if board.context==OFFSET:
            result+=board.cmd('',(CLOCK,))
        require(b'SET completed.' in result,'SET outcome uncertain. Inspect STATUS before another attempt.')
        expected=int(before['trim_hex'],16)
    expected_state=dict(before,segment=segment,trim_hex=f'{expected:02x}')
    status(board,expected_state)
    board.cmd('Q',(MON,))
    return expected_state


def append_csv(path, row):
    exists=path.exists()
    if exists:
        old=samples(path)
        require(series_key(old[0])==series_key(row),'Start a new CSV after a sync, trim, outage or reference change')
        require(float(old[-1]['reference_unix'])<float(row['reference_unix']),'Sample is out of order')
        require(len(old)<1000,'CSV reached the sample limit')
    with path.open('a' if exists else 'x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


@contextlib.contextmanager
def coordinated(args, profile):
    require(os.name=='nt','Live serial support uses the Windows FTDI transport')
    import serial_test_coordination as lease
    if args.workspace:
        lease.ROOT=args.workspace.resolve()/'output/qualification/serial-coordination'
    with lease.serial_lease('rtc-operator',timeout=15):
        marker=lease.ROOT.parent/'device-operations'/f'{profile["board"]}.json'
        original=None
        if marker.exists():
            original=json.loads(marker.read_bytes())
            require(not any(original.get(k) for k in ('block_snapshot','application_RAM_restore_pending',
                         'physical_reset_pending','owner_application_running'))
                    and not any(v for k,v in original.items() if k.endswith('_worker_active')),
                    'Board has a pending or active operation')
            save(marker,dict(original,rtc_operator_worker_active=True))
        try:
            yield
        finally:
            if original is not None:
                report=json.loads((args.out/'report.json').read_bytes())
                pending=bool(report.get('ram_restore_pending'))
                state=dict(original,rtc_operator_worker_active=False,last_rtc_operator_receipt=str(args.out))
                if pending:
                    state.update(application_RAM_restore_pending=True,application_ram_restored=False,block_snapshot=True)
                elif report.get('final_prompt'):
                    state['final_prompt']=report['final_prompt']
                save(marker,state)


def operate(args, fit):
    from serial.tools.list_ports import comports
    kit=args.kit.resolve()
    config=json.loads(args.profile.read_bytes())
    require(re.fullmatch(r'[A-Za-z0-9_-]+',config['board']) and
            config.get('layout')=='wdc-sxb-edu-revd-base1' and config['foundation_sha256']==F_HASH
            and config['cpu'] in ('65c02','65c816-e'),'Unsupported profile')
    require(any(p.device.casefold()==config['port'].casefold() and
                p.serial_number==config['usb_serial'] for p in comports()),'FTDI serial identity differs')
    helper=args.sample_dir or kit/'rtc'
    manifest=json.loads((helper/'rtc-sample.json').read_bytes())
    image=checked_image(helper,manifest['file'],manifest['sha256'])
    require(manifest['load']=='2000' and manifest['entry']=='2000' and len(image)==manifest['bytes'],
            'Unexpected sampler layout')
    ref=Reference(args.server)
    args.out.mkdir(parents=True,exist_ok=False)
    report=dict(passed=False,operation=args.mode,apply=args.apply,device=config['usb_serial'],
                ram_restore_pending=False,sampler_sha256=manifest['sha256'])
    save(args.out/'report.json',report)
    with coordinated(args,config), (args.out/'serial.jsonl').open('x',encoding='ascii') as log:
        link=Link(config['port'],log)
        board=Board(link,args.out,report,config,kit)
        try:
            board.admit()
            segment=segment_for(args.profile,config['usb_serial'])
            before,count=board.sample(image,ref,segment)
            board.update(before=before,observations=count)
            print(json.dumps(dict(offset_seconds=[before['offset_low_s'],before['offset_high_s']],
                                  reference=ref.server,trim=trim_steps(int(before['trim_hex'],16)))),flush=True)
            if args.apply:
                if fit:
                    require(series_key(before)==series_key(args.fit_rows[0]),'Live state differs from the CSV segment')
                    require(0<=ref.now()-fit['last_reference_unix']<=24*3600,'Trim CSV is older than 24 hours')
                expected=apply(board,args,ref,before,fit)
                after,count=board.sample(image,ref,expected['segment'])
                board.update(after=after,post_write_observations=count)
                require(series_key(after)==series_key(expected),'Post-write RTC state differs')
                if args.mode=='sync':
                    require(after['offset_low_s']>=-1 and after['offset_high_s']<=1,
                            'SET ran but residual UTC offset exceeds one second')
                board.update(write_verified=True)
            ref.check()
        except BaseException as error:
            board.update(error=str(error))
            raise
        finally:
            try:
                board.finish()
            finally:
                link.serial.close()
                board.update(port_released=True)
        require(not report['ram_restore_pending'],'RAM restoration incomplete')
        if args.mode=='collect':
            append_csv(args.csv,before)
        board.update(passed=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest='mode',required=True)
    calc=modes.add_parser('calc',help='Calculate drift and proposed trim offline')
    calc.add_argument('csv',type=Path)
    for mode in ('collect','sync','trim'):
        cmd=modes.add_parser(mode)
        cmd.add_argument('--profile',type=Path,required=mode!='trim')
        cmd.add_argument('--server',required=mode!='trim')
        cmd.add_argument('--out',type=Path,required=mode!='trim')
        cmd.add_argument('--kit',type=Path,default=ROOT)
        cmd.add_argument('--sample-dir',type=Path)
        cmd.add_argument('--workspace',type=Path,help='Share an existing STR8-N serial lease')
        if mode in ('collect','trim'):
            cmd.add_argument('--csv',type=Path,required=True)
        if mode!='collect':
            cmd.add_argument('--apply',action='store_true',help='Request a separate operator confirmation')
        else:
            cmd.set_defaults(apply=False)
    args=parser.parse_args(argv)
    try:
        fit=None
        if args.mode in ('calc','trim'):
            args.fit_rows=samples(args.csv)
            fit=calculate(args.fit_rows)
            print(json.dumps(fit,indent=2),flush=True)
            if args.mode=='calc' or not args.apply:
                return
            if not all((args.profile,args.server,args.out)):
                parser.error('trim --apply requires --profile, --server and --out')
        operate(args,fit)
    except (ValueError,OSError,EOFError,KeyError,StopIteration) as error:
        parser.exit(1,f'RTC: {error}\n')


if __name__=='__main__':
    main()

