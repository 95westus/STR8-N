"""One-board-at-a-time, source-aware fleet inventory and retained references."""
import argparse,json,sys,re,time
from pathlib import Path
import migrate_v2 as u
import backup_str8n_board as backup
import archive_v2_edu_sram as array
import capture_v2_display_devices as devices
from beta4_migration import Link
from rtc_prompt_sync import establish_b3
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease

def call(module,args):
    saved=sys.argv
    try:sys.argv=[module.__name__]+args;module.main()
    finally:sys.argv=saved

def port(board):return next(p.device for p in comports() if p.serial_number==SERIALS[board])

def inventory(base,boards):
    for board in boards:
        root=base/board;root.mkdir(parents=True,exist_ok=False)
        with serial_lease('unified-fleet-inventory'),(root/'inventory-serial.jsonl').open('x') as log:
            l=Link(port(board),log)
            try:
                establish_b3(l);active=l.dump(0x7D30,0x7D30)[0]
                state=dict(board=board,port=port(board),active_page=active,inactive_page=active^0x10,
                    monitor_config=l.command('C').decode(errors='replace'),service_descriptor=l.dump(0x7D04,0x7D0B).hex())
                (root/'initial-state.json').write_text(json.dumps(state,indent=2)+'\n')
            finally:l.serial.close()
            call(backup,['--board',board,'--port',port(board),'--out',str(root/'prior-verified')])
        source=u.identify([(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)],active)
        (root/'source.json').write_text(json.dumps(source,indent=2)+'\n')
        print('INVENTORY',board,json.dumps(source),flush=True)

def reference(base,boards):
    campaign=u.read(u.ROOT/'output/qualification/active-rtc-campaign.json')
    for board in boards:
        root=base/board;retained=root/'retained';retained.mkdir(exist_ok=False)
        with serial_lease('unified-fleet-reference'):
            on=bytes.fromhex(u.read(root/'initial-state.json')['service_descriptor'])[3]!=0
            if on:call(array,['--root',str(retained),'--board',board,'--port',port(board),'--stage','prior'])
            call(devices,['--root',str(retained),'--board',board,'--port',port(board),'--stage','before','--baseline-index',campaign['baseline_index']])
        print('PASS',board,'retained references; EDU', 'ON' if on else 'OFF',flush=True)

def verify_current(base,boards):
    for board in boards:
        root=base/board;source=u.read(root/'source.json');assert source['version']=='2.0b25' and source['generation']==37
        banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)];build=u.ROOT/source['source_build'];meta=u.read(build/'build.json')
        for n,h in meta['artifacts'].items():assert u.sha((build/n).read_bytes())==h
        for bank,i,name in ((3,0x6000,'str8n-v2-recovery-e000-efff.bin'),(2,0x4800,'boot-status/asset.bin'),(2,0x6000,'local-display/asset.bin'),(1,0,meta['maintenance_storage_file'])):
            data=(build/name).read_bytes();assert banks[bank][i:i+len(data)]==data,name
        fallback=u.identify(banks,source['inactive_page']);assert fallback['generation']<37
        j=u.m.journal(banks[3]);assert j and j[15:21]==b'P'+bytes((source['active_page'],))+(37).to_bytes(4,'little')
        prior=u.ROOT/('output/qualification/beta25-unified-2026-10-14/2205/retest/report.json' if board=='2205' else 'output/qualification/beta25-2026-10-14/2609/retest/report.json')
        qualified=u.read(prior);assert qualified['passed'] and qualified['final_flash_hashes']==[u.sha(b) for b in banks]
        with serial_lease('unified-already-current'),(root/'already-current-serial.jsonl').open('x') as log:
            l=Link(port(board),log)
            try:
                establish_b3(l);assert l.dump(0x7D30,0x7D30)==bytes((source['active_page'],))
                text=l.command('TIME');assert b'UTC ' not in text and len([v for v in text.split(b'\r\n') if v and v not in (b'TIME',b'B3> ')])==1
                (root/'time.txt').write_bytes(text);detail=l.command('R CLOCK',b'CLOCK> ');assert b'UTC ' in detail
                for command in ('STATUS','TRIM','EUI','HISTORY'):detail+=l.command(command,b'CLOCK> ')
                l.command('Q');(root/'clock.txt').write_bytes(detail)
            finally:l.serial.close()
        report=dict(passed=True,board=board,version='2.0b25',generation=37,action='already-current-no-write',active_slot='B',fallback_version=fallback['version'],fallback_generation=fallback['generation'],
            complete_flash_matches_existing_hardware_qualification=True,flash_hashes=[u.sha(b) for b in banks],time_and_clock_queries_passed=True,flash_written=False)
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',board,'already beta25; unchanged flash and retained fallback; TIME/CLOCK queries passed',flush=True)

def capture(base,boards):
    import serial
    state={}
    with serial_lease('unified-fleet-reset-capture'):
        try:
            for board in boards:
                root=base/board;plan=u.read(root/'upgrade/plan.json');pending=u.read(root/'upgrade/install/reset-pending.json')
                assert pending['device_sectors_verified'] and pending['physical_reset_pending']
                out=root/'physical-reset';out.mkdir(exist_ok=False);log=(out/'serial.jsonl').open('x')
                state[board]=dict(link=Link(port(board),log),log=log,data=bytearray(),done=False,disconnects=0,plan=plan,out=out)
            print('ARMED: receive-only RESET capture on '+', '.join(boards)+' for 15 minutes; TX=0',flush=True)
            deadline=time.monotonic()+900
            while time.monotonic()<deadline and not all(s['done'] for s in state.values()):
                for board,s in state.items():
                    if s['done']:continue
                    try:
                        if s['link'] is None:
                            found=next((p.device for p in comports() if p.serial_number==SERIALS[board]),None)
                            if found is None:continue
                            s['link']=Link(found,s['log'])
                        l=s['link'];s['data'].extend(l.read(max(1,l.serial.in_waiting)))
                    except (serial.SerialException,OSError):
                        if s['link']:s['link'].serial.close()
                        s['link']=None;s['disconnects']+=1;continue
                    data=bytes(s['data'])
                    if data.endswith(b'\r\nB3> '):
                        complete=b'STR8-N 2.0b25' in data and f"gen {s['plan']['source_generation']:08X} VALID".encode() in data and b'gen 00000025 VALID' in data
                        power_boot=b'PF logged, ACK' in data
                        assert complete or power_boot,'Incomplete physical boot without power-fail evidence'
                        (s['out']/'boot.txt').write_bytes(data)
                        p=base/board/'upgrade/install/reset-pending.json';r=u.read(p)
                        r.update(physical_reset_pending=False,physical_reset_verified=True,physical_power_cycle_tested=power_boot,
                            physical_power_cycle_boot_captured_without_initial_header=not complete)
                        p.write_text(json.dumps(r,indent=2)+'\n')
                        s['done']=True;l.serial.close();s['link']=None;print('PASS',board,'physical boot capture; beta25 default; full banner',complete,flush=True)
                time.sleep(.05)
            assert all(s['done'] for s in state.values()),'Physical reset capture timed out'
        finally:
            for s in state.values():
                if s['link']:s['link'].serial.close()
                s['log'].close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('inventory','reference','verify-current','capture'));p.add_argument('--root',required=True,type=Path);p.add_argument('--boards',nargs='+',choices=tuple(SERIALS),required=True);a=p.parse_args()
    {'inventory':inventory,'reference':reference,'verify-current':verify_current,'capture':capture}[a.stage](a.root,a.boards)
