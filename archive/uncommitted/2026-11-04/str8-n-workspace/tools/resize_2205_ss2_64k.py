"""Owner-requested2205 SS2 P64 resize, preserving records and all payload bytes."""
import binascii,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import standardize_ss2_64k as base
import devtools_2512_session as ds
from install_2205_foundation_profile import Session,t,MP
from prepare_ss2_64k_scope import seal,ranges
from inventory_boards_readonly import durable
from installer.common import save
from serial_test_coordination import serial_lease,drift_pending
from program_format import inspect

Q=ROOT/'output/qualification'
SCOPE=Q/'2205-SS2-64K-scope-20261102-r2'
OUT=Q/'2205-SS2-64K-standardized-20261102-r1'
REFERENCE=Q/'2205-foundation-SPI-preservation-20261102-r1/SPI-after.bin'
ALLOW=set(range(64))|set(range(0x240,0x280))|set(range(0x2c0,0x300))

class Escrow(ds.Session):
    def __init__(self,out,r):
        self.out=out;self.r=r;self.mp=MP;self.s=None;self.ram=self.zp=self.high=None;self.cache_first=0x6b00

def prepare():
    before=REFERENCE.read_bytes();old=inspect(before)
    assert old['format']=='SS2' and old['boundary']=='08000' and old['generation']==2
    assert len(old['records'])==2 and all(v['payload_CRC_valid'] for v in old['records'])
    assert all(before[0x31f+32*i]!=0xa5 for i in range(4)),'Managed WORK claims require a separate preservation review'
    assert before[:64]==before[0x240:0x280]
    session=bytearray(before[0x280:0x2c0]);assert session[:4]==b'WS\x01\x00' and session[63]==0xa5 and binascii.crc_hqx(session[:62],65535)==0
    assert before[0x2ff]!=0xa5 and int.from_bytes(session[4:8],'little')==1 and int.from_bytes(session[8:12],'little')==1
    new=bytearray(before);header=bytearray(before[:64]);header[5:7]=(256).to_bytes(2,'little');header[8:12]=(3).to_bytes(4,'little')
    new[:64]=new[0x240:0x280]=seal(header)
    session[4:8]=(2).to_bytes(4,'little');session[8:12]=(2).to_bytes(4,'little');session[12:14]=bytes(2)
    new[0x2c0:0x300]=seal(session)
    changes={i for i,(a,b) in enumerate(zip(before,new)) if a!=b};assert changes<=ALLOW
    after=inspect(bytes(new));assert after['boundary']=='10000' and after['records']==old['records']
    SCOPE.mkdir();(SCOPE/'.gitignore').write_text('*\n')
    durable(SCOPE/'SPI-metadata-original.bin',before[:2048]);durable(SCOPE/'SPI-metadata-expected.bin',new[:2048])
    p=dict(board='2205',owner_instruction='change 64/64 on 2205.',authorized=True,port='COM3',usb_serial='A10MPUPNA',
        format='SS2',from_PROGRAM_boundary='08000',to_PROGRAM_boundary='10000',PROGRAM_records=old['records'],
        old_full_SPI_sha256=t.sha(before),old_metadata_sha256=t.sha(before[:2048]),expected_metadata_sha256=t.sha(new[:2048]),
        allowed_SPI_write_ranges=ranges(ALLOW),distinct_management_addresses_permitted=192,expected_changed_bytes=len(changes),
        native_operation='WORK P 64; Y confirmation; one new WS epoch',generation=3,session_revision=2,session_epoch=2,
        reclassified_range='08000-0FFFF:32KiB WORKSPACE becomes PROGRAM; all bytes preserved; later STORE may allocate here',
        PROGRAM_payload_bytes=63488,WORKSPACE_payload_bytes=65504,flash_writes=0,F_writes=0,journal_writes=0,RTC_setting_writes=0,
        physical_resets=0,power_cuts=0,automatic_retries=0,verified_full_SPI_reference=str(REFERENCE),reference_receipt=str(Q/'2205-foundation-SPI-preservation-20261102-r1/report.json'),fresh_metadata_and_RAM_escrow_required=True,reference_basis='Full SPI independently verified after rollout; subsequent qualified RTC/LED/battery operations do not write SPI; require fresh identical2048-byte metadata and full post-resize payload comparison',
        unchanged_all_four_flash_banks_required=True,preserve_directory='00040-0023F',preserve_payload='00800-1FFFF',
        storage_image_sha256=t.sha((ROOT/'BUILD/storage-installed-auto-r2/SRAM-WORK-g4-flash.bin').read_bytes()))
    save(SCOPE/'plan.json',p)
    (SCOPE/'review-document.txt').write_text(
        '2205 ONLY: owner requested64K PROGRAM/64K WORKSPACE. Native WORK P64.\n'
        'No flash/journal/RTC-setting writes, reset, power cut, format, record deletion or payload relocation.\n'
        '192 management addresses maximum:00000-0003F,00240-0027F,002C0-002FF.\n'
        'Both CLK records retained. Full SPI before/after with exact predicted metadata delta.\n'
        '08000-0FFFF becomes PROGRAM allocation space; existing raw bytes retained. No managed claims allowed.\n'
        'Reuse verified full SPI rollout preimage; subsequent qualified RTC work has no SPI writes.\n'
        'Require fresh exact2048-byte metadata; archive fresh four-bank/RAM/ZP/cache/hooks.\n'
        'Require original metadata exact, both stored CRCs valid and no claim markers.\n'
        'Preserve every payload byte, settings/history and RTC calibration; F stays golden.\n'
        'Yield to RTC; use shared lease and sufficient window. Restore RAM/ZP/cache/hooks; finish REC>, COM3 free.\n'
        'No automatic retry or repair after unexpected response; preserve evidence and report.\n',encoding='utf-8')
    print('Prepared2205 native P64 scope:192 management addresses; two CLK records/payload preserved; zero flash writes.',flush=True)

def run():
    p=json.loads((SCOPE/'plan.json').read_text(encoding='utf-8'));assert p['authorized'] and p['owner_instruction']=='change 64/64 on 2205.'
    before_meta=(SCOPE/'SPI-metadata-original.bin').read_bytes();after_meta=(SCOPE/'SPI-metadata-expected.bin').read_bytes()
    assert t.sha(before_meta)==p['old_metadata_sha256'] and t.sha(after_meta)==p['expected_metadata_sha256']
    base.wait_window(480)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes());durable(OUT/'plan.json',(SCOPE/'plan.json').read_bytes())
    r=dict(board='2205',passed=False,flash_writes=0,journal_writes=0,RTC_setting_writes=0,resets=0,power_cuts=0,automatic_retries=0,metadata_operation_started=False,SPI_change_pending=False)
    x=Escrow(OUT,r);x.save();borrowed=False
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();banks={}
    with serial_lease('2205-owner-requested-SS2-64K-resize',timeout=600):
      ds.ins.window(480);m=json.loads(MP.read_text(encoding='utf-8'))
      assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending'] and not m['block_snapshot']
      assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
      durable(OUT/'marker-before.json',MP.read_bytes())
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          s=x.s=Session(OUT,log);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);x.mon()
          face=x.cmd('VERSION');assert b'Board: 2205' in face and b'STR8-N MON B  gen 00000010' in face
          prefix=s.dump(0x200,0x1ff+len(reader));x.zp=s.dump(0,0xdf);x.high=s.dump(0x6b00,0x77ff);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
          for name,v in [('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)]:durable(OUT/name,v)
          borrowed=True;x.mark(SS2_standardization_worker_active=True,application_ram_restored=False,application_RAM_restore_pending=True,block_snapshot=True)
          x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;x.ram=prefix+memory[len(reader):];durable(OUT/'owner-ram.bin',x.ram)
          for b in range(4):
            banks[b]=s.client.flash(b);assert t.sha(banks[b])==m['current_physical_bank_sha256'][f'B{b}'];durable(OUT/f'B{b}-before.bin',banks[b])
          assert banks[1][0x3000:0x6000]==(ROOT/'BUILD/storage-installed-auto-r2/SRAM-WORK-g4-flash.bin').read_bytes()
          assert t.sha(banks[3][-4096:])==m['current_F_sha256']=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
          assert base.metadata(x)==before_meta
          reference_report=json.loads((Q/'2205-foundation-SPI-preservation-20261102-r1/report.json').read_text(encoding='utf-8'));assert reference_report['passed'] and reference_report['whole_SPI_exact']
          before=REFERENCE.read_bytes();assert t.sha(before)==p['old_full_SPI_sha256'] and before[:2048]==before_meta
          durable(OUT/'SPI-before.bin',before);r['SPI_preimage_basis']=p['reference_basis'];r['full_SPI_reference_receipt']=p['reference_receipt'];r['fresh_metadata_matches_reference']=True
          layout=inspect(before);assert layout['records']==p['PROGRAM_records'] and all(v['payload_CRC_valid'] for v in layout['records'])
          assert all(before[0x31f+32*i]!=0xa5 for i in range(4))
          archive=ROOT/'local-archives/2205-SS2-64K-20261102';archive.mkdir();(archive/'.gitignore').write_text('*\n')
          for f in list(OUT.glob('*before.bin'))+[OUT/'owner-ram.bin',OUT/'owner-zp.bin',OUT/'plan.json',OUT/'marker-before.json']:durable(archive/f.name,f.read_bytes())
          r['verified_reference_SPI_and_fresh_four_banks_archived']=True;x.save()
          ds.ins.window(360);assert not drift_pending(),'RTC priority before mutation'
          x.cmd('R WORK',(base.WORK,));x.cmd('!',(base.MENU,));x.cmd('UNLOCK',(base.UNLOCK,));x.cmd('YES',(base.MENU,));x.cmd('W',(base.WORK,))
          x.cmd('P 64',(base.APPLY,))
          if drift_pending():x.cmd('NO',(base.WORK,));raise InterruptedError('RTC requested; resize cancelled before mutation')
          r.update(metadata_operation_started=True,SPI_change_pending=True);x.save();x.mark(SS2_SPI_restore_pending=True)
          face=x.cmd('Y',(base.WORK,));assert b'Resized.' in face,face
          x.cmd('?',(base.WORK,));x.mon()
          after=base.capture(x,'after',base.reader_packet(),priority=False)
          assert after==after_meta+before[2048:],'Unexpected SRAM delta: no automatic retry'
          post=inspect(after);assert post['format']=='SS2' and post['boundary']=='10000' and post['generation']==3 and post['records']==layout['records']
          save(OUT/'layout-after.json',post)
          assert base.metadata(x)==after_meta
          r.update(SPI_change_pending=False,whole_SPI_matches_exact_plan=True,PROGRAM_records_exact=True,all_payload_bytes_exact=True,PROGRAM_boundary='10000',SPI_sha256=t.sha(after));x.save()
          x.rec();s.service(reader)
          for b in range(4):assert s.client.flash(b)==banks[b]
          r['all_four_banks_exact']=True
        except BaseException as e:r['error']=repr(e);x.save();raise
        finally:
          try:
            if borrowed:
              if x.s.context in (base.CONFIRM,base.APPLY):x.cmd('NO',(base.WORK,))
              if x.s.context==base.UNLOCK:x.cmd('NO',(base.MENU,))
              if x.s.context==base.MENU:x.cmd('Q',(t.MON,))
              x.mon();assert x.hooks()==x.oldhooks;x.restore_high();x.rec();s.service(reader)
              try:assert s.client.flash(3)==banks[3];r['F_images_settings_history_exact']=True
              finally:r.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
          finally:
            if x.s:x.s.link.close();r['port_released']=True
            restored=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored'));pending=bool(r.get('SPI_change_pending'))
            if borrowed:x.mark(SS2_standardization_worker_active=False,application_ram_restored=restored,application_RAM_restore_pending=not restored,block_snapshot=not restored or pending,SS2_SPI_restore_pending=pending,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_SS2_standardization=str(OUT/'report.json'))
            x.save()
    r['passed']=all(r.get(k) for k in ('whole_SPI_matches_exact_plan','PROGRAM_records_exact','all_payload_bytes_exact','all_four_banks_exact','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
    x.save();assert r['passed']
    m=json.loads(MP.read_text(encoding='utf-8'));m.update(SPI_format='SS2',PROGRAM_boundary='10000',WORKSPACE_start='10000');save(MP,m)
    print('PASS2205 SS2/64K PROGRAM/64K WORKSPACE; both CLK records and all payload exact; flash/settings/history and owner RAM preserved; REC>, COM3 released.',flush=True)

if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    else:run()
