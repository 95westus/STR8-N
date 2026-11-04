"""Owner-authorized logical retirement of CLK/CLOCK/NFCOPY; no flash writes."""
import binascii,json
from pathlib import Path
import devtools_2512_session as ds
from serial_test_coordination import drift_pending
t=ds.t; Q=ds.Q
OUT=Q/'2512-obsolete-PROGRAM-cleanup-20261102-r2'
INV=Q/'unified-cleanup-inventory-20261102-r1/2512'
SM=b'SRAM> '; CT=b'STORAGE> '; YES=b'Enable SRAM writes for this RAM session? Type YES: '

def run():
 r=dict(board='2512',passed=False,authorization='remove 2512 clk/clock/nfcopy cleanup as recommended',flash_writes=0,journal_writes=0,RTC_writes=0,WORKSPACE_writes=0)
 with ds.escrow(OUT,r,'2512-approved-obsolete-PROGRAM-cleanup',window=480,cache_first=0x6b00,cache_end=0x77ff) as x:
  x.wb(); meta=b''.join(x.raw(a) for a in range(0,0x800,64))
  assert meta==(INV/'SPI-metadata-00000-007FF.bin').read_bytes(),'Fresh directory differs; no deletion sent'
  (OUT/'SPI-metadata-before.bin').write_bytes(meta)
  records=json.loads((INV/'PROGRAM-metadata-layout.json').read_text())['records']
  assert [(z['slot'],z['name']) for z in records]==[(5,'CLK'),(6,'CLOCK'),(7,'NFCOPY')]
  archived=[]
  for z in records:
   assert not drift_pending(),'Yield to RTC before deleting'
   a=int(z['payload_address'],16); n=z['length']; data=b''.join(x.raw(p) for p in range(a,a+n,64))[:n]
   entry=meta[int(z['directory_address'],16):int(z['directory_address'],16)+64]
   assert binascii.crc_hqx(data,65535)==int.from_bytes(entry[12:14],'little')
   name=f"{z['name']}-slot{z['slot']}-seq{z['sequence']}.bin";(OUT/name).write_bytes(data)
   archived.append(dict(**z,file=name,sha256=t.sha(data)))
   print('Archived '+name,flush=True)
  t.save(OUT/'archived-records.json',archived);r['all_payloads_archived_CRC_verified']=True;x.save()
  ds.ins.window(180);assert not drift_pending()
  x.mon();x.cmd('R SRAM',(SM,));x.cmd('!',(CT,));x.cmd('UNLOCK',(YES,));x.cmd('YES',(CT,));x.cmd('S',(SM,))
  for name in ('CLK','CLOCK','NFCOPY'):
   face=x.cmd('D '+name,(SM,));assert b'error' not in face.lower() and b'REFUSED' not in face,face
  face=x.cmd('C',(SM,));assert b'error' not in face.lower() and b'REFUSED' not in face,face
  table=x.cmd('T',(SM,));assert all(name.encode() not in table for name in ('CLK','CLOCK','NFCOPY')),table
  x.mon();x.wb();after=b''.join(x.raw(a) for a in range(0,0x800,64));(OUT/'SPI-metadata-after.bin').write_bytes(after)
  changed=[i for i,(a,b) in enumerate(zip(meta,after)) if a!=b]
  assert changed and all(0x40<=i<0x240 for i in changed)
  assert all(after[0x40+64*k+63]!=0xa5 for k in range(8))
  for z in archived:
   a=int(z['payload_address'],16); n=z['length']; data=b''.join(x.raw(p) for p in range(a,a+n,64))[:n]
   assert t.sha(data)==z['sha256']
  r.update(all_eight_directory_slots_free=True,payload_bytes_unchanged=True,changed_metadata_addresses=[f'{i:05X}' for i in changed],removed_names=['CLK','CLOCK','NFCOPY'])
  x.mon();x.cmd('R CLOCK',(t.CLOCK,));x.mon();r['native_R_CLOCK_available']=True
 r['passed']=bool(r.get('all_eight_directory_slots_free') and r.get('B3_F_images_settings_history_unchanged') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored'))
 t.save(OUT/'report.json',r);assert r['passed'];print('PASS cleanup; owner RAM restored; REC>; COM4 released',flush=True)
if __name__=='__main__':run()
