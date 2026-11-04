"""Execute only owner-approved320-byte AS/1 PROGRAM fixture; restore exactly."""
import binascii,json,re
from pathlib import Path
import devtools_2512_session as ds
t=ds.t;Q=ds.Q;SCOPE=Q/'2512-AS1-PROGRAM-scope-20261102-r1';OUT=Q/'2512-AS1-PROGRAM-trial-20261102-r1'
ASM=t.ROOT/'BUILD/asm-base1-g1-r6';REST=t.ROOT/'BUILD/2512-AS1-restorer-r1';PB=t.PB

def run():
 a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
 assert a['approved'] and a['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes()) and a['review_sha256']==t.sha((SCOPE/'review-document.md').read_bytes())
 rm=json.loads((REST/'manifest.json').read_text());rb=(REST/'AS1-SPI-RESTORER.bin').read_bytes();ab=(ASM/'ASM-BASE1-RAM.bin').read_bytes();assert t.sha(rb)==rm['sha256'] and t.sha(ab)==p['ASM_sha256'] and rm['plan_sha256']==a['plan_sha256']
 originals={int(v,16):(SCOPE/f'SPI-{v}-original.bin').read_bytes() for v in p['write_blocks']};assert all(t.sha(originals[int(v,16)])==h for v,h in p['preimages'].items())
 r=dict(board='2512',passed=False,checks=[],temporary_PROGRAM_bytes=320,flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,SPI_restored=False,SPI_mutation_pending=False)
 dirty=False;fault=None
 with ds.escrow(OUT,r,'2512-approved-AS1-PROGRAM-trial',window=300) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
  def save():x.save()
  def check(n):r['checks'].append(n);save();print('PASS2512 AS1 '+n,flush=True)
  def mount_helper():
   helper_mon();x.mon();x.wb();assert b'RAW64' in x.cmd('SRAM READ 0 0000');x.mon();assert t.sha(x.s.dump(0x6b00,0x77ff))==rm['provider_sha256'];x.rec();x.s.load(rb,rm['sha256'],PB)
  def helper_mon():
   if x.s.context==PB:x.s.link.send(b'Q');x.s.until((t.MON,),seconds=15)
  def raw(address,data=None):
   assert x.s.context==PB and address%64==0;fields=address.to_bytes(3,'big')
   if data is not None:
    assert address in originals and len(data)==64
    assert data==originals[address] or (address==0x800 and data==fault),'Only original restoration or one admitted payload fault/repair block'
    crc=binascii.crc_hqx(fields+data,65535);x.s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode());face=x.s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face,face
   x.s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=x.s.until((PB,));rows=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(rows)==1,face
   row=bytes.fromhex(rows[0].decode());assert row[:3]==fields and binascii.crc_hqx(row[:-2],65535)==int.from_bytes(row[-2:],'big');return row[3:-2]
  def enter_asm():
   helper_mon();x.wb();assert b'RAW64' in x.cmd('SRAM READ 0 0000');x.mon();x.rec();x.s.load(ab,p['ASM_sha256'],ds.AP)
  def source_lines():
   for n,line in enumerate(p['lines'],1):x.cmd(f'{10*n} {line}')
  def load_source(dirty_source=False):
   if dirty_source:x.cmd('LOAD SRAM AS1TRY',(ds.CONF,));return x.cmd('YES',(ds.AP,))
   return x.cmd('LOAD SRAM AS1TRY')
  try:
   x.wb();meta=b''.join(x.raw(v) for v in range(0,0x240,64));assert t.sha(meta)==p['directory_sha256']
   for address,body in originals.items():assert x.raw(address)==body,'Fixture changed; no SAVE issued'
   enter_asm();source_lines();assert b'OK 8 bytes' in x.cmd('ASM')
   dirty=True;r['SPI_mutation_pending']=True;x.mark(ASM_source_SPI_restore_pending=True);save()
   assert b'Source saved' in x.cmd('SAVE SRAM AS1TRY')
   mount_helper();slot=raw(0x140);payload=b''.join(raw(v) for v in (0x800,0x840,0x880,0x8c0));cap=(SCOPE/'expected-AS1-capsule.bin').read_bytes()
   assert slot[:4]==b'SP\x01\0' and slot[63]==0xa5 and binascii.crc_hqx(slot[:62],65535)==0
   assert int.from_bytes(slot[10:12],'little')==p['allocation']['next_sequence']
   assert int.from_bytes(slot[4:6],'little')==0x200 and int.from_bytes(slot[6:8],'little')==len(cap) and slot[8:10]==b'\0\0' and slot[14:16]==bytes((8,1)) and slot[16:32]==b'AS1TRY'.ljust(16,b'\0')
   assert payload[:len(cap)]==cap and payload[len(cap):]==b''.join(originals[v] for v in (0x800,0x840,0x880,0x8c0))[len(cap):]
   assert binascii.crc_hqx(cap,65535)==int.from_bytes(slot[12:14],'little');(OUT/'AS1-saved-directory.bin').write_bytes(slot);(OUT/'AS1-saved-payload-page.bin').write_bytes(payload)
   check('real-SAVE-exact-AS1-capsule-directory-and-payload-CRC')
   enter_asm();assert b'Source loaded' in load_source();listing=x.cmd('LIST');assert all(line.encode() in listing for line in p['lines']);assert b'OK 8 bytes' in x.cmd('ASM');check('new-ASM-session-LOAD-LIST-and-reassembly')
   x.cmd('20 LDA #$55');x.cmd('LOAD SRAM AS1TRY',(ds.CONF,));assert b'Load cancelled' in x.cmd('NO',(ds.AP,));assert b'LDA #$55' in x.cmd('LIST');check('dirty-source-LOAD-cancellation-preserves-edits')
   mount_helper();normal=raw(0x800);corrupt=bytearray(normal);corrupt[8]^=1;fault=bytes(corrupt);assert raw(0x800,fault)==fault
   enter_asm();x.cmd('10 BYTE $99');face=load_source(True);assert b'Source storage:' in face and b'Source loaded' not in face;assert b'BYTE $99' in x.cmd('LIST');check('payload-CRC-fault-refused-before-source-copy')
   mount_helper();fault=normal;assert raw(0x800,normal)==normal
   enter_asm();assert b'Source loaded' in load_source();assert b'OK 8 bytes' in x.cmd('ASM');x.cmd('QUIT',(t.MON,));assert x.s.dump(0x200,0x207)==bytes.fromhex('A9428D00184C677E');check('payload-repair-reload-and-independent-assembled-output')
  finally:
   if dirty:
    mount_helper()
    for address,body in originals.items():
     if raw(address)!=body:assert raw(address,body)==body
    assert all(raw(address)==body for address,body in originals.items());helper_mon();x.wb();after=b''.join(x.raw(v) for v in range(0,0x240,64));assert after==meta
    r['SPI_restored']=True;r['SPI_mutation_pending']=False;x.mark(ASM_source_SPI_restore_pending=False);save();check('all320-SPI-bytes-and-entire-directory-restored')
 r['passed']=bool(len(r['checks'])==6 and r['SPI_restored'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['provider_cache_restored'] and r['B3_F_images_settings_history_unchanged']);t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 AS1 PROGRAM source persistence;320 bytes restored; F/settings/history/owner preserved;REC>;COM4 free',flush=True)

if __name__=='__main__':run()
