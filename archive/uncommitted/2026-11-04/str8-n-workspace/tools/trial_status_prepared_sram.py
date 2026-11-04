"""Complete2512's positive STATUS capacity check after explicit guarded PREP.

Same continuously preserved owner escrow as the initial trial; no host/board
owner activity between receipts. PREP acknowledges only disabled VIA CB flags,
not RTC flags. SRAM/RTC data and flash are read only.
"""
import json,re
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
CASE=t.ROOT/'output/qualification/2512-STATUS-prepared-SRAM-20261031-r1'
AUTH=t.ROOT/'output/qualification/2512-STATUS-g1-RAM-20261031-r1'
CANDIDATE=t.ROOT/'BUILD/status-g1-RAM-r1'

def run():
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    authority=json.loads((AUTH/'report.json').read_text());assert authority['passed'] and authority['owner_RAM_restored']
    ram=(AUTH/'owner-ram.bin').read_bytes();zp=(AUTH/'owner-zp.bin').read_bytes()
    assert t.sha(ram)==authority['owner_RAM_sha256'] and t.sha(zp)==authority['owner_ZP_sha256']
    image=(CANDIDATE/'STR8N-STATUS-RAM-TRIAL.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,flash_writes=0,SRAM_data_writes=0,RTC_SET=0,PF_ACK=0,
           explicit_disabled_VIA_CB_flag_ack=False,owner_RAM_restored=False,owner_ZP_restored=False,
           escrow_authority=str(AUTH/'report.json'),escrow_chain='Initial restore,64-byte guard probe/restore; no other owner activity')
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False;save()
    with t.serial_lease('2512-STATUS-explicit-SRAM-PREP-positive',timeout=30):
      marker=json.loads(t.MARK.read_text());assert not marker['application_RAM_restore_pending']
      with (CASE/'serial.jsonl').open('x') as log:
       try:
        s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
        assert s.dump(0x200,0x23F)==ram[:64] and s.dump(0,0xDF)==zp
        mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
        out=s.command('MAINT LOAD',(t.WB,));assert b'WORKBENCH WB2 g0000000B' in out
        s.command('EDU ON')
        out=s.command('SRAM PREP');assert b'Disabled CB flags acknowledged; no SPI clocks' in out
        r['explicit_disabled_VIA_CB_flag_ack']=True;save()
        mounted=s.command('SRAM');assert b'SSRAM PROGRAM:' in mounted
        (CASE/'WORKBENCH-SRAM.txt').write_bytes(mounted)
        page=re.search(rb'0800 to page ([0-9A-F]{2})',mounted)
        assert page
        boundary=(int(page[1],16) or 256)*256
        s.command('Q',(t.MON,));s.rec();t.transport.recovery_usb(s.link)
        s.load(image,t.sha(image),t.MON)
        out=s.command('VERSION');(CASE/'new-VERSION.txt').write_bytes(out)
        assert f'SSRAM: PROGRAM payload {boundary-2048} bytes'.encode() in out
        assert f'SSRAM: WORKSPACE {131072-boundary-32} bytes'.encode() in out
        assert b'Board: 2512' in out and b'within age policy*' in out
        r['capacity_display_passed']=True
       finally:
        try:
         if borrowed:
            if s.context==t.WB:s.command('Q',(t.MON,))
            if s.context!=t.REC:s.command('Q',(t.REC,))
            s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            s.command('B',(t.MON,));r.update(owner_RAM_restored=True,owner_ZP_restored=True)
        finally:
         if s is not None:s.link.close();r['port_released']=True
         if borrowed:mark(status_worker_active=False,application_RAM_restore_pending=not r['owner_RAM_restored'],
            application_ram_restored=r['owner_RAM_restored'],block_snapshot=marker['block_snapshot'] if r['owner_RAM_restored'] else True)
         save()
    r['passed']=r.get('capacity_display_passed',False) and r['owner_RAM_restored'];save()
    print(json.dumps(r,indent=2),flush=True)
if __name__=='__main__':run()
