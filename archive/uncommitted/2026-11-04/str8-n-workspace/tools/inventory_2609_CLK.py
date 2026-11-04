"""Read2609 stored-clock directory only, preserving owner RAM and RTC priority."""
import binascii,json,re
from pathlib import Path
import install_2609_candidate3 as ins
t=ins.t;d=ins.d;Q=ins.Q
OUT=Q/'2609-CLK-inventory-20261102-r1'

def run():
 ins.ins.window(180);OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 mp=Q/'device-operations/2609.json';reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 r=dict(board='2609',passed=False,flash_writes=0,SPI_writes=0,RTC_writes=0,owner_RAM_restored=False,owner_ZP_restored=False);s=None;borrowed=False;ram=zp=None
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):
  out=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(out);return out
 def mon():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context==t.WB:cmd('Q',(t.MON,))
  if s.context==t.REC:cmd('B',(t.MON,))
  assert s.context==t.MON
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
 save()
 with t.serial_lease('2609-CLK-readonly-inventory',timeout=30):
  ins.ins.window(180);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);mon()
    cmd('VERSION');prefix=s.dump(0x200,0x1ff+len(reader));zp=s.dump(0,0xdf);(OUT/'owner-zp.bin').write_bytes(zp)
    mark(CLK_inventory_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
    ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
    mon();cmd('T 0-3');cmd('MAINT LOAD',(t.WB,));cmd('SRAM');cmd('TABLE P')
    data=bytearray()
    for address in range(0,0x240,64):
     out=cmd(f'SRAM READ 0 {address:04X}');match=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){63}[0-9A-F]{2})',out);assert match,out
     data.extend(bytes.fromhex(match[1].decode()))
    (OUT/'PROGRAM-directory.bin').write_bytes(data);h=data[:64]
    assert h[:2]==b'SS' and h[2] in (1,2) and h[63]==0xa5 and binascii.crc_hqx(h[:62],65535)==0
    records=[]
    for slot in range(8):
     row=data[(slot+1)*64:(slot+2)*64]
     if row[63]!=0xa5:continue
     assert row[:4]==b'SP\x01\0' and binascii.crc_hqx(row[:62],65535)==0
     records.append(dict(slot=slot,name=row[16:32].split(b'\0')[0].decode(),sequence=int.from_bytes(row[10:12],'little'),kind=row[15],load=f'{int.from_bytes(row[4:6],"little"):04X}',entry=f'{int.from_bytes(row[8:10],"little"):04X}',length=int.from_bytes(row[6:8],'little'),address=f'{row[14]*256:05X}',CRC=f'{int.from_bytes(row[12:14],"little"):04X}'))
    r['records']=records;r['directory_sha256']=t.sha(data);save();print(json.dumps(records,indent=2),flush=True)
   except BaseException as e:r['error']=repr(e);save();raise
   finally:
    try:
     if borrowed:rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    finally:
     if s:s.link.close();r['port_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(CLK_inventory_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=m['block_snapshot'] if restored else True,final_prompt='REC>',last_CLK_inventory=str(OUT/'report.json'))
     save()
 r['passed']=bool(r.get('records') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2609 CLK inventory; owner RAM/ZP restored; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
