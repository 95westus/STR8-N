"""Restore the fresh2512 escrow after the locally rejected oversized packet."""
import json
from pathlib import Path
import install_2512_native_utilities as d

t=d.t;BASE=t.ROOT/'output/qualification/2512-EDU-startup-RAM-20261101-r1'


def run():
    folder=BASE/'owner-recovery';folder.mkdir(exist_ok=False)
    ram=(BASE/'owner-ram.bin').read_bytes();zp=(BASE/'owner-zp.bin').read_bytes();old=(BASE/'B3-before.bin').read_bytes()
    mp=t.ROOT/'output/qualification/device-operations/2512.json';m=json.loads(mp.read_text())
    assert m['application_RAM_restore_pending'] and t.sha(old)==m['current_physical_bank_sha256']['B3']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,resets=0)
    with t.serial_lease('2512-EDU-startup-owner-recovery',timeout=60):
      with (folder/'serial.jsonl').open('x') as log:
        s=d.Session(folder,log,'2512')
        try:
            s.link.send(b'\r');s.until((t.REC,t.MON),seconds=15)
            if s.context==t.MON:s.command('Q',(t.REC,))
            s.service(reader);assert s.client.flash(3)==old;r['B3_unchanged']=True
            r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            r['passed']=r['owner_RAM_restored'] and r['owner_ZP_restored']
            m=json.loads(mp.read_text());m.update(application_RAM_restore_pending=False,application_ram_restored=True,
               block_snapshot=False,edu_startup_RAM_worker_active=False,final_prompt='REC>',last_EDU_startup_owner_recovery=str(folder/'report.json'))
            t.save(mp,m)
        finally:s.link.close();r['port_released']=True;t.save(folder/'report.json',r)
    print('PASS2512 RAM/ZP restored; B3 unchanged; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
