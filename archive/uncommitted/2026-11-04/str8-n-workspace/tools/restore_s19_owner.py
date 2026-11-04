"""Restore the fresh owner escrow after a S19 trial's host prompt mismatch."""
import argparse,json
from pathlib import Path
import install_2512_native_utilities as d

t=d.t

def run(source):
    source=Path(source).resolve();assert source.is_relative_to(t.ROOT/'output/qualification')
    old=json.loads((source/'report.json').read_text());board=old['board']
    ram=(source/'owner-ram.bin').read_bytes();zp=(source/'owner-zp.bin').read_bytes()
    b3=(source/'B3-before.bin').read_bytes();assert len(ram)==0x6500 and len(zp)==0xE0
    folder=source/'owner-recovery';folder.mkdir(exist_ok=False)
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    marker=json.loads(mp.read_text());assert marker['application_RAM_restore_pending']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board=board,passed=False,flash_writes=0,SRAM_writes=0,resets=0)
    with t.serial_lease(board+'-S19-owner-restoration',timeout=600):
      with (folder/'serial.jsonl').open('x') as log:
        s=d.Session(folder,log,board)
        try:
            s.link.send(b'\r');s.until((t.MON,t.REC,t.CLOCK),seconds=12)
            if s.context==t.CLOCK:s.command('Q',(t.MON,))
            if s.context==t.MON:s.command('Q',(t.REC,))
            s.service(reader);assert s.client.flash(3)==b3;r['B3_unchanged']=True
            r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            s.command('B',(t.MON,));assert b'g0000000D / MON B' in s.command('VERSION')
            r['passed']=r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['B3_unchanged']
            if r['passed']:
                marker=json.loads(mp.read_text());marker.update(s19_RAM_worker_active=False,
                    store_front_RAM_worker_active=False,
                    application_RAM_restore_pending=False,application_ram_restored=True,block_snapshot=False,
                    last_S19_owner_recovery=str(folder/'report.json'))
                t.save(mp,marker)
        finally:
            s.link.close();r['port_released']=True;t.save(folder/'report.json',r)
    print(json.dumps(r,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);a=p.parse_args();run(a.source)
