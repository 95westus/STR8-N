"""Bounded MAINT/read soak; RAM program loads only, no persistent writes."""
import argparse, concurrent.futures, hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS

ROOT = Path(__file__).resolve().parents[1]

def run(board, port, root, until=None):
    out=root/board; out.mkdir()
    report=dict(board=board, passed=False, rounds=0, persistent_writes=False,
                reset=False, clock_set=False, trim_changed=False)
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'serial.jsonl').open('w') as log:
        link=Link(port,log)
        try:
            stop=time.monotonic()+.5
            while time.monotonic()<stop: link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ')
            assert not any(p in initial for p in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')), 'Board in another program'
            link.command('B3')
            def state(label):
                assert link.dump(0x7D27,0x7D27)==b'\x01'
                descriptor=link.dump(0x7D04,0x7D0B)
                assert descriptor[:3]==b'SV\x01' and descriptor[3]&1
                link.command('R CLOCK',b'CLOCK> ')
                status=link.command('STATUS',b'CLOCK> ')
                trim=link.command('TRIM',b'CLOCK> ')
                eui=link.command('EUI',b'CLOCK> ')
                assert b'Running: yes' in status and b'Backup enabled: yes' in status
                assert b'0 steps; coarse OFF; OSCTRIM $00' in trim
                (out/(label+'-clock.txt')).write_bytes(status+trim+eui)
                link.command('Q')
                return trim,eui,descriptor
            def flash(label):
                hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    image=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    (out/f'{label}-b{bank}.bin').write_bytes(image)
                    hashes.append(hashlib.sha256(image).hexdigest())
                link.command('B3');return hashes
            before=state('before'); flash_before=flash('before')
            deadline=(time.monotonic()+max(0,until-time.time()-30) if until else time.monotonic()+180)
            while time.monotonic()<deadline:
                n=report['rounds']
                for command in ('APPS','TIME','R MAINT L'):
                    (out/f'{n:03d}-{command.replace(" ","-")}.txt').write_bytes(link.command(command))
                loaded=link.dump(0x2000,0x203F)
                assert any(v not in (0,255) for v in loaded)
                (out/f'{n:03d}-maint-start.txt').write_bytes(link.command('R MAINT',b'BM> '))
                for command in ('?','M 1','M 2','M 3','T'):
                    (out/f'{n:03d}-maint-{command.replace("?","help").replace(" ","-")}.txt').write_bytes(link.command(command,b'BM> '))
                link.command('Q')
                assert link.dump(0x2000,0x203F)==loaded, 'MAINT code changed'
                link.dump(0x0200,0x023F);link.dump(0x6400,0x643F)
                assert state(f'{n:03d}')==before
                report['rounds']+=1;save()
                time.sleep(min(5,max(0,deadline-time.monotonic())))
            assert flash('after')==flash_before, 'Persistent flash changed'
            assert state('after')==before
            report.update(passed=True,flash_hashes=flash_before,monitor_ready=True,
                          user_ram_program_loaded=True,full_release_soak=False)
        except Exception as exc:
            report['error']=repr(exc)
        finally:
            link.serial.close(); report['ended_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps(report),flush=True)
    return report['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--until-utc')
    args=parser.parse_args()
    until=datetime.fromisoformat(args.until_utc.replace('Z','+00:00')).timestamp() if args.until_utc else None
    if until: assert 30<until-time.time()<7200, 'Deadline must be 30 seconds to two hours ahead'
    root=ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('short-soak-%Y-%m-%d-%H%M%SZ')
    root.mkdir();ports={p.serial_number:p.device for p in comports()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda b:run(b,ports[SERIALS[b]],root,until),('2604','2609')))
    print('Evidence:',root,flush=True)
    raise SystemExit(0 if all(results) else 1)
