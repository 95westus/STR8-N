"""Restore escrow after stopped LED sampler; no reset or nonvolatile writes."""
import json
from pathlib import Path
import install_2609_candidate3 as ins
t=ins.t;d=ins.d;Q=ins.Q
LED=Q/'2609-candidate3-RTC-readmission-20261102-r1/LED-seconds'
OUT=Q/'2609-candidate3-LED-owner-restoration-20261102-r1'

def run():
 ins.approved();r0=json.loads((LED/'report.json').read_text());assert r0['acquisition_passed'] and r0['port_released']
 receipt=r0['LED_exit_receipt'];assert receipt[:4]==[1,0,0,0] and receipt[4:]==[0xB4,0x34]
 assert r0['restoration_error']=="AssertionError('LED/CRA restoration failed')"
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 owner=Q/'2609-candidate3-runtime-20261102-r1';ram=(owner/'owner-ram.bin').read_bytes();zp=(owner/'owner-zp.bin').read_bytes()
 reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2609.json'
 r=dict(board='2609',passed=False,reset_sent=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,LED_exit_receipt=receipt)
 def save():t.save(OUT/'report.json',r)
 save();s=None
 with t.serial_lease('2609-candidate3-stopped-sampler-owner-restoration',timeout=30):
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.MON,),seconds=15)
    m=json.loads(mp.read_text());m.update(candidate3_LED_restore_worker_active=True);t.save(mp,m)
    s.command('Q',(t.REC,));s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
   finally:
    if s:s.link.close();r['port_released']=True
    restored=r.get('owner_RAM_restored') and r.get('owner_ZP_restored');m=json.loads(mp.read_text());before=json.loads((LED/'marker-before.json').read_text())
    m.update(candidate3_LED_restore_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=bool(restored),one_shot_collection_active=False,block_snapshot=True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_candidate3_LED_owner_restoration=str(OUT/'report.json'))
    if restored:
     if 'RTC_LED_RAM_escrow' in before:m['RTC_LED_RAM_escrow']=before['RTC_LED_RAM_escrow']
     else:m.pop('RTC_LED_RAM_escrow',None)
    t.save(mp,m);save()
 r['passed']=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r['port_released']);save();assert r['passed']
 print('PASS2609 stopped LED sampler; full owner RAM/ZP restored; REC>; COM8 free; RTC hold retained',flush=True)

if __name__=='__main__':run()
