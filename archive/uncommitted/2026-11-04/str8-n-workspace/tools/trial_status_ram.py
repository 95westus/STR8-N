"""Preserving, RAM-only startup STATUS trial; never opens an excluded board."""
import argparse,json,re,binascii
from pathlib import Path
import install_2512_native_utilities as d

t=d.t
SERVICE=d.SERVICE
PROMPTS=(t.MON,t.REC,d.FT,t.CLOCK,t.WB,b'B0> ',b'B1> ',b'B2> ')

def run(board,folder,candidate):
    folder=Path(folder).resolve();candidate=Path(candidate).resolve()
    assert folder.is_relative_to(t.ROOT/'output/qualification')
    manifest=json.loads((candidate/'RAM-trial-manifest.json').read_text())
    image=(candidate/manifest['payload']['file']).read_bytes()
    assert t.sha(image)==manifest['payload']['sha256'] and len(image)==14250
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    markpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    report=dict(board=board,passed=False,phase='prepared',started_utc=t.utc(),
        F_writes=0,flash_writes=0,journal_writes=0,SRAM_data_writes=0,RTC_SET=0,
        PF_ACK=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,
        candidate_sha256=t.sha(image),checks=[])
    folder.mkdir(parents=True,exist_ok=False);(folder/'.gitignore').write_text('*\n')
    def save():t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(markpath.read_text());m.update(fields);t.save(markpath,m)
    def check(name):report['checks'].append(name);save();print('PASS '+name,flush=True)
    s=None;borrowed=False;marker=None;ram=zp=None;original=None
    save()
    try:
        with t.serial_lease(board+'-STATUS-RAM-readonly',timeout=30):
            marker=json.loads(markpath.read_text())
            assert not marker.get('application_RAM_restore_pending')
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=d.Session(folder,log,board);s.link.send(b'\r')
                    s.until(PROMPTS,seconds=15);original=s.context
                    if s.context in (d.FT,t.CLOCK,t.WB):s.command('Q',(t.MON,))
                    if s.context in (b'B0> ',b'B1> ',b'B2> '):s.command('B3',(t.MON,))
                    if s.context==t.REC:s.command('B',(t.MON,))
                    assert s.context==t.MON
                    version=s.command('V')  # g8 accepts only the legacy short name.
                    expected=b'g0000000B' if board=='2512' else b'g00000008'
                    assert expected in version
                    ram,zp=s.owner()
                    (folder/'owner-ram.bin').write_bytes(ram);(folder/'owner-zp.bin').write_bytes(zp)
                    report.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp),original_context=original.decode())
                    check('fresh-native-owner-escrow')
                    mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    borrowed=True;s.rec();t.transport.recovery_usb(s.link);s.service(reader)
                    assert s.client.read(b'M',0x6500)==reader+ram[len(reader):]
                    assert s.client.read(b'Z',0xe0)==zp
                    # One relevant-bank capture supplies actual journal/layout admission.
                    # No repeated board-wide checksum passes.
                    for bank in (2,3):
                        body=s.client.flash(bank);(folder/f'before-B{bank}.bin').write_bytes(body)
                        report[f'B{bank}_sha256']=t.sha(body)
                    b3=(folder/'before-B3.bin').read_bytes()
                    frozen=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
                    assert b3[-4096:]==frozen
                    t.save(folder/'journal.json',t.classify_journal(b3))
                    s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
                    s.load(image,t.sha(image),t.MON)
                    face=s.command('VERSION')
                    (folder/'new-VERSION.txt').write_bytes(face)
                    cpu=b'CPU: 65C02' if board=='2512' else b'CPU: 65C816 emulation'
                    assert cpu in face and b'STATUS tools unavailable' not in face
                    assert re.search(rb'MONITOR A gen 000000[0-9A-F]{2} VALID',face)
                    assert re.search(rb'MONITOR B gen 000000[0-9A-F]{2} VALID',face)
                    assert b'RAM $0200-$66FF' in face and b'EDU ON' in face
                    assert b'FLASH: B2:8 tracked max ' in face and b'Battery: ' in face
                    if board=='2512':assert b'Board: 2512' in face and b'within age policy*' in face
                    check('RAM-MON-admits-relocated-provider-and-renders-rich-status')
                    concise=s.command('TIME');(folder/'new-TIME.txt').write_bytes(concise)
                    assert re.search(rb'RTCC: 20\d\d-\d\d-\d\d \d\d:\d\d:\d\d flags \$[0-9A-F]{2}',concise)
                    assert b'/ MON ' not in concise and b'MONITOR A' not in concise
                    check('concise-UTC-TIME-retained')
                    # Only the private MON session byte; no old dispatcher/tool load.
                    assert b'REFUSED' not in s.command('!M 6A20 00')
                    off=s.command('VERSION');assert b'EDU OFF' in off and b'RTCC: --*' in off
                    assert b'REFUSED' not in s.command('!M 6A20 01')
                    on=s.command('VERSION');assert b'EDU ON' in on
                    check('EDU-session-OFF-skips-device-reads-and-ON-resumes')
                    s.command('Q',(t.REC,));s.service(reader)
                    assert s.client.flash(3)==b3
                    check('journal-metadata-and-golden-F-unchanged')
                    report['phase']='RAM-trial-passed'
                finally:
                    try:
                        if borrowed:
                            if s.context!=SERVICE:
                                if s.context!=t.REC:s.command('Q',(t.REC,))
                                s.service(reader)
                            report.update(s.client.restore_owner(ram,zp));s.context=t.REC
                            if original!=t.REC:s.command('B',(t.MON,))
                            report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close();report.update(port_released=True,final_prompt=s.context.decode() if s.context else None)
                        if borrowed:
                            restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                            mark(status_worker_active=False,application_RAM_restore_pending=not restored,
                                application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                                last_STATUS_RAM_trial=str(folder/'report.json'))
                        save()
        report.update(passed=report['phase']=='RAM-trial-passed',finished_utc=t.utc());save()
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--folder',required=True);p.add_argument('--candidate',required=True)
    a=p.parse_args();run(a.board,a.folder,a.candidate)
