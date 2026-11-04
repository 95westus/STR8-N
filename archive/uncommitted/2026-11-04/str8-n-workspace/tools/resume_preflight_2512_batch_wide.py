"""Fresh owner escrow and C/D/metadata/PROGRAM-directory admission; no NVM writes."""
import json,re
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
CASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1/preflight-resume'
SERVICE=d.SERVICE

def run():
 CASE.mkdir(parents=True,exist_ok=False)
 report=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,full_board_backup_passes=0,owner_RAM_restored=False)
 def save():t.save(CASE/'report.json',report)
 s=None;borrowed=False;ram=zp=None
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 mark=json.loads(t.MARK.read_text());assert not mark['block_snapshot'] and not mark['application_RAM_restore_pending']
 save()
 with t.serial_lease('2512-batch-wide-readonly-preflight',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.until((t.MON,),seconds=180)
    assert b'g0000000A / MON B' in s.command('VERSION')
    original=CASE.parent/'preflight'
    ram=(original/'owner-ram.bin').read_bytes();zp=(original/'owner-zp.bin').read_bytes()
    (CASE/'owner-ram.bin').write_bytes(ram);(CASE/'owner-zp.bin').write_bytes(zp)
    report.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp),escrow_source='Fresh pre-helper save from preceding read-only admission; no intervening application/helper')
    b3=bytearray((t.ROOT/'output/qualification/2512-native-utilities-20261030-r1/HOST-install-r8/final-B3.bin').read_bytes())
    b3[0x4000:0x6000]=(original/'journal-CD.bin').read_bytes()
    b3[0x1C00:0x2000]=(original/'RTC-metadata.bin').read_bytes()
    (CASE/'B3-planning-reference.bin').write_bytes(b3)
    report['B3_evidence']='Accepted system bytes plus fresh C/D and metadata; installation must independently admit each target preimage'
    borrowed=True;m=json.loads(t.MARK.read_text());m.update(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);t.save(t.MARK,m)
    s.command('MAINT',(t.WB,));s.mount()
    directory=bytearray()
    for a in range(0,0x240,64):
     out=s.command(f'SRAM READ 0 {a:04X}')
     f=re.findall(rb'RAW64 ((?:[0-9A-F]{2} ){64})',out);assert len(f)==1
     directory.extend(bytes.fromhex(f[0].decode()))
    (CASE/'PROGRAM-directory.bin').write_bytes(directory)
    (CASE/'PROGRAM-table.txt').write_bytes(s.command('TABLE P'))
    report['PROGRAM_header_hex']=bytes(directory[:64]).hex()
    report['passed']=True
   finally:
    try:
     if borrowed:
      if s.context in (t.WB,t.MON):s.rec()
      assert s.context==t.REC
      t.transport.recovery_usb(s.link);s.service(reader);report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
      s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:
      m=json.loads(t.MARK.read_text());m.update(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored']);t.save(t.MARK,m)
     save()
 print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
