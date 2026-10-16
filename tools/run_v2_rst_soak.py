"""Four parallel board workers; R/S/T with two pinned scratch sectors each."""
import argparse,concurrent.futures,ctypes,datetime,hashlib,json,os,re,threading,time,traceback
from pathlib import Path
import beta4_migration as migration
import upgrade_v2_fleet as fleet
import run_beta23_soak as smoke
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease,drift_pending
from remove_v2_sdemo import records
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1]
BOARDS=('2205','2512','2604','2609')
NAMES=('MAINT','CLOCK','SRAM','WORK','EDU')
PROMPT=b'\r\nB3> '
END_LOCAL='2026-10-15T08:59:00-05:00'
END=datetime.datetime.fromisoformat(END_LOCAL).timestamp()
LOCK=threading.Lock()

def sha(b):return hashlib.sha256(b).hexdigest()
def active_boards(root):
    path=root/'excluded-boards.json'
    excluded=json.loads(path.read_text()) if path.exists() else []
    assert all(b in BOARDS for b in excluded)
    return tuple(b for b in BOARDS if b not in excluded)
def save(p,v):
    with LOCK:
        publish(p,v)

def bank(l,b):
    prompt=f'\r\nB{b}> '.encode();l.command(f'B{b}',prompt)
    try:return b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
    finally:l.command('B3')

def scratch(l):
    l.command('B2',b'\r\nB2> ')
    try:return l.dump(0x8000,0x9FFF,b'\r\nB2> ')
    finally:l.command('B3')

def clock(l):
    l.command('R CLOCK',b'CLOCK> ')
    result={c:l.command(c,b'CLOCK> ').hex() for c in ('HISTORY','TRIM','EUI')}
    status=l.command('STATUS',b'CLOCK> ');raw=re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)
    assert raw and b'Running: yes' in status
    result['control_trim']=bytes.fromhex(raw[1].decode())[7:9].hex()
    l.command('Q');return result

def prepare(root):
    plans={}
    for board in BOARDS:
        folder=root/board;manifest=json.loads((folder/'prior-verified/manifest.json').read_text());assert manifest['repeat_verified']
        images=[(folder/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
        for i,b in enumerate(images):assert b==(folder/f'prior-verified/b{i}-repeat.bin').read_bytes() and sha(b)==manifest['banks'][i]['sha256']
        assert images[2][:8192]==b'\xff'*8192,'B2:8/9 must be completely erased before authorization is pinned'
        programs={}
        for b,image in enumerate(images):
            for offset,n,label in records(image):
                name=label.decode('ascii')
                assert not name.startswith('RSOAK'),'Prior scratch record conflicts with this run'
                if name in NAMES:
                    assert name not in programs,'Duplicate program label'
                    h=image[offset:offset+24];body=image[offset+24:offset+24+n]
                    programs[name]=dict(bank=b,address=offset+0x8000,entry=int.from_bytes(h[4:6],'little'),size=n,sha256=sha(body))
                    (folder/(name.lower()+'-original.bin')).write_bytes(body)
        assert set(programs)==set(NAMES),programs
        plans[board]=dict(board=board,serial=fleet.u.deploy.SERIALS[board],scratch_bank=2,scratch_sectors=[8,9],
            scratch_original_sha256=sha(images[2][:8192]),programs=programs,source=json.loads((folder/'source.json').read_text()),
            config_hex=migration.journal(images[3])[8:24].hex(),initial_flash_hashes=[sha(b) for b in images])
        save(folder/'soak-plan.json',plans[board])
    config=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),end_local=END_LOCAL,
        end_utc=datetime.datetime.fromtimestamp(END,datetime.timezone.utc).isoformat(),boards=list(BOARDS),parallel_workers=4,
        scratch_policy='Only B2 sectors 8/9 per board; normal existing B3 C/D wear journal updates allowed',
        programs=list(NAMES),max_saved_payload=8168,write_cutoff_seconds_before_end=300,
        large_programs='Complete source bodies exercised as successive <=8168-byte SAVE/RESTORE chunks',
        excluded='No firmware replacement, reset, RTC setters/ACK/CLEAR/TRIM setters, EEPROM writes, SRAM format/allocation or arbitrary application execution')
    save(root/'config.json',config);print('PREPARED four-board parallel soak; B2:8/9 pinned; deadline',END_LOCAL,flush=True)

def guard_plan(p):
    assert p['board'] in BOARDS and p['scratch_bank']==2 and p['scratch_sectors']==[8,9]
    assert p['serial']==fleet.u.deploy.SERIALS[p['board']]

def erase(l,out,p):
    guard_plan(p);old=scratch(l)
    if old==b'\xff'*8192:return [0,0]
    assert time.time()<END-30,'No late erase: inspect scratch recovery record'
    used=[int(old[i*4096:(i+1)*4096]!=b'\xff'*4096) for i in range(2)]
    l.command('R MAINT',b'BM> ')
    text=l.command('E 2 8-9',b'WRITE? TYPE Y> ')
    assert b'DEST B2:8000-9FFF' in text,text
    text=l.command('Y',b'BM> ');assert b'VERIFIED' in text and b'FAILED' not in text,text
    l.command('Q');assert scratch(l)==b'\xff'*8192,'Scratch cleanup failed'
    return used

def filler(first,last,pattern):
    assert 0x2000<=first<=last<=0x64FF
    stop=last+1
    # Executes only from 0200; fills an application range, then returns via HOLD.
    head=bytes((0x78,0xD8,0xA9,first&255,0x85,0xE0,0xA9,first>>8,0x85,0xE1,0xA0,0))
    loop=bytes((0xA9,pattern,0x91,0xE0,0xE6,0xE0,0xD0,2,0xE6,0xE1,
        0xA5,0xE1,0xC9,stop>>8,0xD0,0xF0,0xA5,0xE0,0xC9,stop&255,0xD0,0xEA,0x4C,0x67,0x7E))
    return head+loop

def unit(l,root,p,name,iteration,out,model=False):
    started=time.time();guard_plan(p);board=p['board'];source=root/board;row=p['programs'][name]
    expected=(source/(name.lower()+'-original.bin')).read_bytes();assert sha(expected)==row['sha256']
    before_clock=clock(l);assert before_clock==json.loads((source/'clock-original.json').read_text())
    assert l.dump(0x7D30,0x7D30)==bytes((json.loads((source/'initial-state.json').read_text())['active_page'],))
    assert scratch(l)==b'\xff'*8192,'Scratch must start blank'
    table=l.command('T');assert all(n.encode() in table for n in NAMES);(out/'table.txt').write_bytes(table)
    load=f"R {row['bank']} {row['address']:04X} L" if name=='SRAM' else f'R {name} L'
    text=l.command(load);assert b'Done' in text,text
    assert l.dump(row['entry'],row['entry']+row['size']-1)==expected,'Installed RESTORE differs from source'
    # Restore/run every installed foreground utility, using read-only commands.
    if model:
        prompt=b'BM> ' if name=='MAINT' else (name+'> ').encode()
        l.command(f'R {name}',prompt);l.command('?',prompt);l.command('Q')
    else:smoke.commands(l,name.lower() if name!='CLOCK' else 'clock')
    erases=[0,0];chunks=[]
    for index,offset in enumerate(range(0,len(expected),8168)):
        if not model and (time.time()>=END-300 or (root/'STOP').exists()):break
        piece=expected[offset:offset+8168];first=row['entry']+offset;last=first+len(piece)-1
        label=f'RSOAK{NAMES.index(name)}{index}'
        l.command(load);assert l.dump(first,last)==piece
        save(out/'restore-state.json',dict(board=board,needs_restore=True,scratch_bank=2,scratch_sectors=[8,9],original='all FF',phase='before SAVE'))
        try:
            text=l.command(f'S 2 8000 {first:04X} {last:04X} {label}');assert b'Done' in text,text
            want=b'SR\1\x3f'+first.to_bytes(2,'little')+len(piece).to_bytes(2,'little')+label.encode().ljust(16,b'\0')+piece
            assert scratch(l)==want+b'\xff'*(8192-len(want)),'SAVE changed bytes outside exact scratch record'
            assert label.encode() in l.command('T 2')
            assert b'SR error 02' in l.command(f'S 2 8000 {first:04X} {last:04X} {label}'),'Occupied SAVE must refuse'
            code=filler(first,last,(iteration+index+0xA5)&255);old=l.dump(0x0200,0x0200+len(code)-1)
            try:
                l.write_ram(0x0200,code);l.command('G 0200')
                assert l.dump(first,min(first+15,last))==bytes(((iteration+index+0xA5)&255,))*min(16,len(piece))
                modes=(f'R 2 {label} L',f'R {label} L','R 2 8000 L')
                text=l.command(modes[(iteration+index)%3]);assert b'Done' in text,text
                assert l.dump(first,last)==piece,'Scratch RESTORE differs after RAM overwrite'
            finally:l.write_ram(0x0200,old)
            chunks.append(dict(offset=offset,bytes=len(piece),sha256=sha(piece),restore_mode=modes[(iteration+index)%3]))
        finally:
            counts=erase(l,out,p);erases=[a+b for a,b in zip(erases,counts)]
            save(out/'restore-state.json',dict(board=board,needs_restore=False,scratch_verified_blank=True,erases=erases))
        assert b'SR error 05' in l.command(f'R 2 {label} L'),'Deleted scratch record must be missing'
    images=[bank(l,b) for b in range(4)]
    for b,data in enumerate(images):
        original=(source/f'prior-verified/b{b}.bin').read_bytes()
        if b!=3:assert data==original,('Unrelated flash changed',b)
        else:assert data[:0x4000]==original[:0x4000] and data[0x6000:]==original[0x6000:],'Firmware/identity/slots changed'
    journal=migration.journal(images[3]);assert journal and journal[8:24].hex()==p['config_hex']
    prior=json.loads((source/'wear-state.json').read_text());current=[int.from_bytes(journal[24+3*i:27+3*i],'little') for i in range(32)]
    for idx,(a,b) in enumerate(zip(prior['counts'],current)):
        assert b>=a
        if idx in (16,17):assert b-a==erases[idx-16],('Scratch wear mismatch',idx,a,b,erases)
        elif idx in (28,29):assert b-a<=2,'Unexpected journal rotations'
        else:assert b==a,('Erase outside authorized sectors',idx)
    save(source/'wear-state.json',dict(counts=current,sequence=int.from_bytes(journal[4:8],'little')))
    assert clock(l)==before_clock,'Clock state changed'
    assert not any(label.decode().startswith('RSOAK') for b in images for _,_,label in records(b))
    for b in range(4):save(source/f'latest-b{b}-hash.json',dict(sha256=sha(images[b])))
    report=dict(passed=True,board=board,program=name,iteration=iteration,chunks=chunks,erases=erases,started=started,
        complete_payload_coverage=sum(c['bytes'] for c in chunks)==len(expected),
        scratch_blank=True,original_programs_and_firmware_preserved=True,clock_preserved=True,finished=time.time())
    save(out/'report.json',report);print('PASS',board,name,'round',iteration,'chunks',len(chunks),'erases',erases,flush=True)
    return report

def baseline(root):
    for board in BOARDS:
        folder=root/board;p=json.loads((folder/'soak-plan.json').read_text());guard_plan(p)
        with serial_lease('soak-baseline'),(folder/'baseline-serial.jsonl').open('a') as log:
            l=migration.Link(fleet.port(board),log)
            try:
                establish_b3(l);smoke.guards(l);assert scratch(l)==b'\xff'*8192
                save(folder/'clock-original.json',clock(l));smoke.eeprom_readback(l,folder,root,board)
            finally:l.serial.close()
        j=migration.journal((folder/'prior-verified/b3.bin').read_bytes())
        save(folder/'wear-state.json',dict(counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)],sequence=int.from_bytes(j[4:8],'little')))
    print('PASS four-board RTC/EEPROM references and blank scratch boundaries',flush=True)

def worker(root,board,name,iteration):
    folder=root/board;p=json.loads((folder/'soak-plan.json').read_text());out=folder/f'{iteration:05d}-{name}';out.mkdir(exist_ok=False)
    with (out/'serial.jsonl').open('x') as log:
        l=migration.Link(fleet.port(board),log)
        try:establish_b3(l);smoke.guards(l);return unit(l,root,p,name,iteration,out)
        finally:l.serial.close()

def run(root,smoke_only=False):
    assert time.time()<END-600,'Too late to begin overnight soak'
    assert json.loads((root/'drift/baseline/index.json').read_text())['passed'],'Fresh drift baseline required'
    for board in ('2205','2604','2609'):
        proof=json.loads((root/f'model-{board}-r3'/board/'00000-MAINT/report.json').read_text())
        assert proof['passed'] and len(proof['chunks'])==2,'Largest transaction model qualification required'
    config=json.loads((root/'config.json').read_text());assert config['end_local']==END_LOCAL and config['parallel_workers']==4
    prior=[json.loads(p.read_text()) for b in BOARDS for p in (root/b).glob('[0-9]*-*/report.json')]
    assert all(p['passed'] for p in prior)
    assert all(not json.loads(p.read_text()).get('needs_restore') for p in root.glob('*/*/restore-state.json'))
    iteration=max((p['iteration'] for p in prior),default=-1)+1
    status=dict(state='running',pid=os.getpid(),parallel_workers=4,end_local=END_LOCAL,rounds=iteration,passed_units=len(prior),boards={b:dict(passed_units=sum(p['board']==b for p in prior)) for b in BOARDS})
    status.update(active_boards=list(active_boards(root)),excluded_boards=[b for b in BOARDS if b not in active_boards(root)],parallel_workers=len(active_boards(root)))
    save(root/'status.json',status);save(ROOT/'output/qualification/active-beta25-rst-soak.json',dict(root=str(root),pid=os.getpid(),end_local=END_LOCAL))
    assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4,thread_name_prefix='RST-board') as pool:
            while time.time()<END-300:
                for name in NAMES:
                    if time.time()>=END-300 or (root/'STOP').exists():break
                    while drift_pending():
                        status.update(state='yielding-to-RTC',updated=time.time());save(root/'status.json',status)
                        if time.time()>=END-300 or (root/'STOP').exists():break
                        time.sleep(5)
                    if time.time()>=END-300 or (root/'STOP').exists():break
                    status.update(state='running',program=name,rounds=iteration,updated=time.time());save(root/'status.json',status)
                    with serial_lease('parallel-RST-soak',timeout=600):
                        futures={pool.submit(worker,root,b,name,iteration):b for b in active_boards(root)}
                        failures=[]
                        for f in concurrent.futures.as_completed(futures):
                            b=futures[f]
                            try:
                                result=f.result();status['passed_units']+=1;status['boards'][b].update(passed_units=status['boards'][b]['passed_units']+1,last_program=name,last_finished=result['finished'])
                            except Exception:failures.append(dict(board=b,error=traceback.format_exc()))
                            status['updated']=time.time();save(root/'status.json',status)
                        if failures:raise RuntimeError(json.dumps(failures))
                iteration+=1;status['rounds']=iteration;save(root/'status.json',status)
                if smoke_only:break
                # Repeat at a bounded pace while varying payload phase by round.
                for _ in range(12):
                    if time.time()>=END-300 or (root/'STOP').exists():break
                    time.sleep(5)
                if (root/'STOP').exists():break
        assert all(not json.loads(p.read_text()).get('needs_restore') for p in root.glob('*/*/restore-state.json'))
        status.update(state='smoke-passed' if smoke_only else 'finalizing',updated=time.time());save(root/'status.json',status)
        if not smoke_only:
            final_verify(root)
            while time.time()<END and not (root/'STOP').exists():time.sleep(min(5,END-time.time()))
            status.update(state='completed',ports_released=True,restoration_verified=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            save(root/'status.json',status)
    except Exception:
        status.update(state='stopped-on-failure',error=traceback.format_exc(),updated=time.time());save(root/'status.json',status);raise
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

def final_verify(root):
    def one(board):
        folder=root/board
        with (folder/'final-serial.jsonl').open('a') as log:
            l=migration.Link(fleet.port(board),log)
            try:
                establish_b3(l);assert scratch(l)==b'\xff'*8192
                for b in range(4):
                    data=bank(l,b);assert sha(data)==json.loads((folder/f'latest-b{b}-hash.json').read_text())['sha256']
                    (folder/f'final-b{b}.bin').write_bytes(data)
                assert clock(l)==json.loads((folder/'clock-original.json').read_text())
                smoke.eeprom_readback(l,folder,root,board)
                save(folder/'final-report.json',dict(passed=True,scratch_blank=True,full_flash_verified=True,EEPROM_and_clock_preserved=True,finished=time.time()))
            finally:l.serial.close()
    with serial_lease('parallel-RST-final',timeout=120),concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for f in concurrent.futures.as_completed([pool.submit(one,b) for b in active_boards(root)]):f.result()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','baseline','smoke','run'));p.add_argument('--root',required=True,type=Path);a=p.parse_args();root=a.root.resolve()
    if a.stage=='prepare':prepare(root)
    elif a.stage=='baseline':baseline(root)
    else:run(root,a.stage=='smoke')
