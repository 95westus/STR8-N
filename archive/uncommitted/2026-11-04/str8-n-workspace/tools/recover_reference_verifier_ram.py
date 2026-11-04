"""Preserving continuation of the known 2512 B1-prompt verifier stop."""
import json
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
base=t.ROOT/'output/qualification/2512-reference-workflows-20261101-r7'
case=base/'owner-recovery';case.mkdir(exist_ok=False)
mp=t.ROOT/'output/qualification/device-operations/2512.json'
ram=(base/'owner-ram.bin').read_bytes();zp=(base/'owner-zp.bin').read_bytes()
reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
old=(base/'B3-before.bin').read_bytes();report=dict(passed=False,flash_writes=0,journal_writes=0)
with t.serial_lease('2512-verifier-owner-RAM-preserving-recovery',timeout=60):
    m=json.loads(mp.read_text());assert m['application_RAM_restore_pending']
    with (case/'serial.jsonl').open('x') as log:
        s=d.Session(case,log,'2512')
        try:
            s.link.send(b'\r');s.until((b'B1> ',t.MON,t.REC),seconds=15)
            if s.context==b'B1> ':s.command('B3',(t.MON,))
            if s.context==t.MON:s.command('Q',(t.REC,))
            t.transport.recovery_usb(s.link);s.service(reader)
            assert s.client.flash(3)==old
            report.update(s.client.restore_owner(ram,zp));s.context=t.REC
            s.command('B',(t.MON,))
            report.update(passed=True,owner_RAM_restored=True,owner_ZP_restored=True,NVM_verified=True)
            m=json.loads(mp.read_text());m.update(reference_verify_worker_active=False,
                application_RAM_restore_pending=False,application_ram_restored=True,block_snapshot=False)
            m['current_physical_bank_sha256']['B3']=t.sha(old);m['display_offset_minutes']=-360
            t.save(mp,m)
            prior=json.loads((base/'report.json').read_text())
            prior.update(owner_RAM_restored=True,owner_ZP_restored=True,NVM_verified=True,
                host_error='Expected B3 after WB Q; selected bank was correctly B1',
                owner_recovery=str(case/'report.json'))
            t.save(base/'report.json',prior)
        finally:
            s.link.close();report['port_released']=True;t.save(case/'report.json',report)
print('PASS 2512 owner RAM/ZP restored/read back; B3 unchanged; COM4 released',flush=True)
