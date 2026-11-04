"""Restore the fresh owner escrow after a RAM-only SRAM helper refusal."""
import argparse,json
from pathlib import Path
import install_2512_native_utilities as d
t=d.t

def run(board,base):
    base=Path(base).resolve();assert base.is_relative_to(t.ROOT/'output/qualification')
    case=base/'owner-recovery';case.mkdir(exist_ok=False)
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    prior=json.loads((base/'report.json').read_text());assert prior['board']==board
    assert prior['SRAM_data_writes']==prior['WORKSPACE_writes']==0
    ram=(base/'owner-ram.bin').read_bytes();zp=(base/'owner-zp.bin').read_bytes();old=(base/'B3-before.bin').read_bytes()
    assert t.sha(ram)==prior['owner_RAM_sha256'] and t.sha(zp)==prior['owner_ZP_sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(passed=False,board=board,flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,resets=0)
    with t.serial_lease(board+'-SRAM-WORK-owner-recovery',timeout=60):
      m=json.loads(mp.read_text());assert m['application_RAM_restore_pending']
      with (case/'serial.jsonl').open('x') as log:
        s=d.Session(case,log,board)
        try:
            s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15)
            if s.context==t.MON:s.command('Q',(t.REC,))
            t.transport.recovery_usb(s.link);s.service(reader)
            assert s.client.flash(3)==old
            r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            s.command('B',(t.MON,))
            r.update(passed=True,owner_RAM_restored=True,owner_ZP_restored=True,B3_unchanged=True)
            m=json.loads(mp.read_text());m.update(application_RAM_restore_pending=False,
                application_ram_restored=True,block_snapshot=False,sram_work_positive_worker_active=False,
                last_SRAM_WORK_owner_recovery=str(case/'report.json'))
            t.save(mp,m)
        finally:
            s.link.close();r['port_released']=True;t.save(case/'report.json',r)
    print('PASS '+board+' owner RAM/ZP restored and read back; B3 unchanged; port released',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--base',required=True)
    a=p.parse_args();run(a.board,a.base)
