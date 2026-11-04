"""Owner-requested2609 CLK cleanup: archive4 payloads, retire4 SRAM slots."""
import binascii,json,re
from pathlib import Path
import install_2609_candidate3 as ins
import nf_opaque as opaque
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q
INV=Q/'2609-CLK-inventory-20261102-r1';OUT=Q/'2609-CLK-cleanup-20261102-r1'
BUILD=t.ROOT/'BUILD/2609-CLK-retirement-r1';PB=t.PB
SLOTS=(4,5,6,7);COMMIT_ADDRESSES=(0x17f,0x1bf,0x1ff,0x23f)

def run():
 ins.ins.window(420);assert json.loads((INV/'report.json').read_text())['passed']
 plan=json.loads((BUILD/'manifest.json').read_text());body=(BUILD/'CLK-RETIRE-RAM.bin').read_bytes();assert t.sha(body)==plan['sha256']
 assert plan['allowed_write_addresses']==[f'{a:05X}' for a in COMMIT_ADDRESSES] and plan['allowed_write_value']==0
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());t.save(OUT/'RAM-helper-manifest.json',plan)
 reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2609.json'
 r=dict(board='2609',owner_direction='2609 has multiple clk, remove them',passed=False,retired_slots=[],SPI_bytes_written=0,flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
 s=None;ram=zp=None;borrowed=False
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):
  face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
 def mon():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context==PB:s.link.send(b'Q');s.until((t.MON,),seconds=15)
  if s.context in (t.WB,t.CLOCK):cmd('Q',(t.MON,))
  if s.context==t.REC:cmd('B',(t.MON,))
  assert s.context==t.MON
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
 def raw(address,data=None):
  assert s.context==PB and address%64==0 and 0<=address<=0x1ffc0
  fields=address.to_bytes(3,'big')
  if data is not None:
   assert address+63 in COMMIT_ADDRESSES and len(data)==64 and data[:63]==meta[address:address+63] and data[63]==0
   assert r.get('all_four_payloads_archived_and_CRC_verified')
   crc=binascii.crc_hqx(fields+data,65535);r['pending_commit_address']=f'{address+63:05X}';save()
   s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode());face=s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face,face
   r['SPI_bytes_written']+=1;r['retired_slots'].append(address//64-1);r.pop('pending_commit_address');save()
  s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=s.until((PB,));frames=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(frames)==1,face
  frame=bytes.fromhex(frames[0].decode());assert frame[:3]==fields and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
  return frame[3:-2]
 save()
 with t.serial_lease('2609-owner-requested-CLK-cleanup',timeout=30):
  ins.ins.window(420);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  t.save(OUT/'marker-before.json',m)
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);mon()
    prefix=s.dump(0x200,0x1ff+len(reader));zp=s.dump(0,0xdf);opaque.durable_file(OUT/'owner-zp.bin',zp)
    mark(CLK_cleanup_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
    mon();cmd('MAINT LOAD',(t.WB,));mounted=cmd('SRAM');assert b'SSRAM PROGRAM:' in mounted;cmd('TABLE P')
    # READ mounts the current provider and selects the saved EDU profile.
    assert b'RAW64' in cmd('SRAM READ 0 0000');cmd('Q',(t.MON,));assert t.sha(s.dump(0x6b00,0x77ff))==plan['provider_sha256']
    rec();s.load(body,plan['sha256'],PB)
    meta=b''.join(raw(a) for a in range(0,0x240,64));assert meta==(INV/'PROGRAM-directory.bin').read_bytes(),'Directory changed; no retirement issued'
    opaque.durable_file(OUT/'PROGRAM-directory-before.bin',meta)
    records=json.loads((INV/'report.json').read_text())['records'];assert [x['slot'] for x in records]==list(SLOTS) and all(x['name']=='CLK' and x['kind']==1 for x in records)
    archived=[]
    for record in records:
     if drift_pending():raise InterruptedError('RTC priority before any retirement')
     ins.ins.window(60);start=int(record['address'],16);length=record['length'];payload=bytearray()
     for a in range(start,start+length,64):
      if drift_pending():raise InterruptedError('RTC priority before any retirement')
      payload.extend(raw(a))
     payload=bytes(payload[:length]);assert binascii.crc_hqx(payload,65535)==int(record['CRC'],16)
     name=f'CLK-slot{record["slot"]}-seq{record["sequence"]}-{start:05X}.bin';opaque.durable_file(OUT/name,payload)
     archived.append(dict(**record,file=name,sha256=t.sha(payload)));t.save(OUT/'archived-records.json',archived)
     print(f'Archived CLK slot{record["slot"]}, seq{record["sequence"]}, {length} bytes',flush=True)
    r['all_four_payloads_archived_and_CRC_verified']=True;save();ins.ins.window(60)
    expected=bytearray(meta)
    for address in COMMIT_ADDRESSES:
     before=raw(address-63);assert before==meta[address-63:address+1] and before[63]==0xa5
     expected[address]=0;assert raw(address-63,bytes(expected[address-63:address+1]))==expected[address-63:address+1]
    after=b''.join(raw(a) for a in range(0,0x240,64));assert after==expected
    opaque.durable_file(OUT/'PROGRAM-directory-after.bin',after);r['only_directory_commit_bytes_changed']=True
    mon();cmd('MAINT LOAD',(t.WB,));cmd('SRAM');face=cmd('TABLE P');assert b' CLK' not in face and b'error' not in face.lower();r['no_CLK_directory_entries']=True
    cmd('Q',(t.MON,));face=cmd('R CLOCK',(t.CLOCK,));assert b'CLOCK' in face and b'Board:' in face;r['native_R_CLOCK_available']=True
    cmd('Q',(t.MON,));rec();s.service(reader);assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3'];r['B3_F_images_settings_history_unchanged']=True
   except BaseException as e:r['error']=repr(e);save();raise
   finally:
    try:
     if borrowed:rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    finally:
     if s:s.link.close();r['port_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(CLK_cleanup_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=m['block_snapshot'] if restored else True,final_prompt='REC>',last_CLK_cleanup=str(OUT/'report.json'))
     save()
 r['passed']=bool(r.get('only_directory_commit_bytes_changed') and r.get('native_R_CLOCK_available') and r.get('no_CLK_directory_entries') and r.get('B3_F_images_settings_history_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2609 all4 CLK entries retired; archived; R CLOCK available; four SPI bytes; F/history exact; owner restored; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
