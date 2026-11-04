"""Observe one physical RESET, select golden recovery, restore owner RAM only."""
import json
import argparse
from pathlib import Path
import preflight_program_apps_20261030 as p

t=p.t
BASE=t.ROOT/'output/qualification/2512-native-utilities-20261030-r1'
CASE=BASE/'loader-recovery'

def run(label='loader-recovery',diagnose=False):
    case=BASE/label
    case.mkdir(exist_ok=False)
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',passed=False,flash_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    with t.serial_lease('2512-native-loader-golden-recovery',timeout=180,priority=True):
        with (case/'serial.jsonl').open('x') as log:
            s=p.Session(case,log,'2512')
            try:
                print('ARMED: waiting for 2512 physical RESET; no commands sent',flush=True)
                (case/'armed.json').write_text(json.dumps({'board':'2512','port':'COM4','armed':True})+'\n')
                face=s.link.until(t.transport.CHOICES,seconds=600)
                assert t.transport.IDENTITY in face
                s.link.send(b'S');s.link.until(t.REC,seconds=20);s.context=t.REC
                if diagnose:
                    s.command('B',(t.MON,))
                    for start,end,name in [(0x2000,0x207F,'app-head'),(0x7000,0x73FF,'loader-RAM'),(0x5C00,0x5FFF,'overlay-context')]:
                        (case/(name+'.bin')).write_bytes(s.dump(start,end))
                    s.command('Q',(t.REC,))
                t.transport.recovery_usb(s.link);s.service(reader)
                report.update(s.client.restore_owner(ram,zp));s.context=t.REC
                face=s.command('B',(t.MON,));assert b'g0000000A / MON B' in face
                report.update(passed=True,owner_RAM_restored=True,owner_ZP_restored=True,final_prompt='B3>')
                marker=json.loads(t.MARK.read_text());marker.update(native_utility_worker_active=False,
                    application_RAM_restore_pending=False,application_ram_restored=True,
                    block_snapshot=True,firmware_verification_pending=True,final_prompt='B3>',
                    native_loader_recovery=str(case/'report.json'))
                t.save(t.MARK,marker)
            finally:
                s.link.close();report['COM4_released']=True;t.save(case/'report.json',report)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='loader-recovery');parser.add_argument('--diagnose',action='store_true');args=parser.parse_args();run(args.label,args.diagnose)
