"""Owner-requested empty PROGRAM directory, with full SPI escrow and verification."""
import json
from pathlib import Path
import standardize_ss2_64k as ss
from serial_test_coordination import drift_pending

def run():
 ss.inv.IDS['2205']=('COM3','A10MPUPNA',b'CPU: 65C02')
 t=ss.t
 out=ss.Q/'2205-PROGRAM-empty-20261103-r1'
 r=dict(board='2205',passed=False,authorization='2205 make free 63488, not 39936',flash_writes=0,journal_writes=0,RTC_writes=0)
 ss.wait_window(900)
 with ss.escrow('2205',out,r) as x:
  (out/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  packet=ss.reader_packet()
  before=ss.capture(x,'before',packet)
  from program_format import inspect
  layout=inspect(before)
  assert layout['format']=='SS2' and layout['boundary']=='10000'
  assert [(z['slot'],z['name'],z['length']) for z in layout['records']]==[(6,'CLK',12231),(7,'CLK',11224)]
  assert all(z['payload_CRC_valid'] for z in layout['records'])
  archive=t.ROOT/'local-archives/2205-PROGRAM-retired-20261103'
  archive.mkdir();(archive/'.gitignore').write_text('*\n')
  ss.nf_opaque.durable_file(archive/'SPI-before.bin',before)
  t.save(archive/'layout-before.json',layout)
  for z in layout['records']:
   a=int(z['payload_address'],16);data=before[a:a+z['length']]
   assert t.sha(data)==z['payload_sha256']
   ss.nf_opaque.durable_file(archive/f"CLK-slot{z['slot']}-seq{z['sequence']}.bin",data)
  r['archive']=str(archive);x.save()
  ss.ds.ins.window(420);assert not drift_pending()
  SM=b'SRAM> ';CT=b'STORAGE> '
  x.mon();x.cmd('R SRAM',(SM,));x.cmd('!',(CT,));x.cmd('UNLOCK',(ss.UNLOCK,));x.cmd('YES',(CT,));x.cmd('S',(SM,))
  r['SPI_change_pending']=True;x.save();x.mark(SS2_SPI_restore_pending=True)
  for command in ('D CLK','C'):
   face=x.cmd(command,(SM,));assert b'error' not in face.lower() and b'REFUSED' not in face,face
  x.cmd('T',(SM,));x.mon()
  after=ss.capture(x,'after',packet,priority=False)
  post=inspect(after);t.save(out/'layout-after.json',post)
  assert not post['records'] and len(post['free_slots'])==8
  changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
  assert changed and all(0x40<=i<0x240 for i in changed)
  assert after[0x800:]==before[0x800:]
  r.update(SPI_change_pending=False,PROGRAM_free_bytes=63488,directory_free_slots=8,payload_and_WORK_bytes_unchanged=True,changed_addresses=changed)
  x.mark(PROGRAM_free_bytes=63488,PROGRAM_directory_free_slots=8,last_PROGRAM_cleanup=str(out/'report.json'))
  x.save()
 r['passed']=all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','payload_and_WORK_bytes_unchanged','port_released'))
 t.save(out/'report.json',r);assert r['passed'];print('PASS: 2205 PROGRAM free 63488; RAM restored; port released',flush=True)

if __name__=='__main__':run()
