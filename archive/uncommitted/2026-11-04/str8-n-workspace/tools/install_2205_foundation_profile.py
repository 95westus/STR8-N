"""Approved compact2205 profile:29 image erases, D/C rotations, B binding."""
import json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import install_named_edu_2512 as ins
import nf_opaque as opaque
from journal_rotation_plan import reserve
from installer.common import save
from installer.engine.runtime import sha
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease,drift_pending
t=ins.t
SCOPE=ROOT/'output/qualification/2205-foundation-rollout-scope-20261102-r1'
CONVERSION=ROOT/'output/qualification/2205-foundation-conversion-installed-20261102-r1'
OUT=ROOT/'output/qualification/2205-foundation-profile-installed-20261102-r1'
MP=ROOT/'output/qualification/device-operations/2205.json'
CONFIG=b'RAM CONFIG ? B C I W Q> '
START=b'DBG RAM start 0200-3FFF; Q MON> '


class Session(t.Session):
    def __init__(self,out,log):
        self.folder=out;self.context=None;self.counter=0;self.client=None
        self.link=t.transport.RecoveryLink('COM3',log,usb_serial='A10MPUPNA')


def run():
    p=json.loads((SCOPE/'compact/plan.json').read_text());a=json.loads((SCOPE/'approval.json').read_text())
    assert a['approved'] and a['variant']=='compact' and a['total_erases']==34
    assert a['plan_sha256']==sha((SCOPE/'compact/plan.json').read_bytes())
    assert p['total_erases']==34 and len(p['targets'])==29 and p['native_journal_rotations']==['B3:D','B3:C']
    conversion=json.loads((CONVERSION/'report.json').read_text())
    assert conversion['passed'] and conversion['all_four_banks_verified'] and conversion['owner_RAM_restored'] and conversion['owner_ZP_restored'] and conversion['port_released']
    ram=(CONVERSION/'owner-ram.bin').read_bytes();zp=(CONVERSION/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    config=(t.REPO/'firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes()
    expected=[(SCOPE/'conversion-engine-review'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    print('2205 approved29-image install waiting for RTC window480s',flush=True)
    while True:
        try:ins.window(480);break
        except AssertionError:time.sleep(1)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
    durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes());durable(OUT/'approval.json',(SCOPE/'approval.json').read_bytes())
    durable(OUT/'owner-ram.bin',ram);durable(OUT/'owner-zp.bin',zp)
    r=dict(board='2205',passed=False,phase='preflight',checks=[],completed=[],image_erase_requests=0,
        journal_erase_requests=0,journal_appends=0,F_writes=0,SPI_writes=0,RTC_setting_writes=0,
        resets=0,power_cuts=0,automatic_retries=0,owner_RAM_restored=False,owner_ZP_restored=False,
        escrow_authority='Fresh native escrow carried through the verified conversion/restoration; no app run between stages')
    def checkpoint(**kw):r.update(kw);save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(MP.read_text());m.update(kw);save(MP,m)
    def check(label):r['checks'].append(label);checkpoint();print('PASS2205 '+label,flush=True)
    checkpoint();s=None;borrowed=False
    with serial_lease('2205-approved-native-profile23-plus-C-rotation',timeout=600):
      ins.window(480);m=json.loads(MP.read_text())
      assert m['foundation_conversion_complete'] and m['foundation_rollout_qualification_pending']
      assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
      assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
      durable(OUT/'marker-before.json',MP.read_bytes())
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          s=Session(OUT,log);s.link.send(b'\r');s.until((t.REC,),seconds=15)
          def cmd(line,tokens=None):
            face=s.command(line,tokens);durable(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:38]}.txt',face);return face
          def rec():
            if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
            elif s.context==b'RAM SERVICE BASE1> ':s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
            elif s.context!=t.REC:
                if s.context==b'ASM> ':cmd('QUIT',(t.MON,))
                if s.context==b'DBG> ':cmd('X',(t.MON,))
                if s.context==START:cmd('Q',(t.MON,))
                if s.context in (t.CLOCK,t.WB):cmd('Q',(t.MON,))
                if s.context in (b'BM> ',b'FLASH/MAINT> ',CONFIG):cmd('Q',(t.MON,t.REC))
                if s.context==t.MON:cmd('Q',(t.REC,))
            assert s.context==t.REC,'Unknown state; do not blindly reload'
          borrowed=True;mark(foundation_rollout_worker_active=True,application_ram_restored=False,application_RAM_restore_pending=True,block_snapshot=True)
          s.service(reader)
          memory=s.client.read(b'M',0x6500);assert memory==reader+ram[len(reader):] and s.client.read(b'Z',0xe0)==zp
          for bank in range(4):assert s.client.flash(bank)==expected[bank]
          check('converted-preimages-SNBT-F-and-carried-owner-escrow-admitted')
          rec();s.load(writer,sha(writer),opaque.PROMPT)
          with (OUT/'opaque-wire.jsonl').open('x') as wirelog:
            wire=opaque.Wire(s.link.serial,timeout=90,trace=wirelog,progress=lambda line:print('2205 '+line,flush=True))
            for target,wanted in zip(p['targets'],p['native_operations']):
              if drift_pending():raise InterruptedError('RTC priority at completed-sector boundary; no next erase')
              ins.window(60)
              bank=target['bank'];address=int(target['address'],16);offset=address-0x8000
              assert not(bank==3 and address in (0xc000,0xd000,0xf000))
              before=wire.read_sector(bank,address>>8);assert before==expected[bank][offset:offset+4096] and sha(before)==target['before_sha256']
              body=(SCOPE/'compact'/target['file']).read_bytes();assert sha(body)==target['sha256']
              future,op=reserve(expected[3],bank*8+(address-0x8000)//4096);assert op==wanted
              r['image_erase_requests']+=1;r['journal_erase_requests']+=len(op['journal_sector_erases'])
              assert r['image_erase_requests']<=29 and r['journal_erase_requests']<=2
              checkpoint(phase='writing-'+f'B{bank}:{address:04X}',pending_target=f'B{bank}:{address:04X}')
              s.context=None;assert not wire.replace_sector(bank,address>>8,before,body);s.context=opaque.PROMPT
              assert wire.read_sector(bank,address>>8)==body
              temp=bytearray(expected[bank]);temp[offset:offset+4096]=body;expected[bank]=bytes(temp)
              if bank==3:temp=bytearray(future);temp[offset:offset+4096]=body;future=bytes(temp)
              expected[3]=future
              r['journal_appends']+=len(op['journal_appends']);r['completed'].append(r.pop('pending_target'))
              (OUT/'B3-current-predicted.bin').write_bytes(expected[3]);check('installed-'+r['completed'][-1])
          assert r['image_erase_requests']==29 and r['journal_erase_requests']==1 and r['journal_appends']==30
          rec();s.service(reader)
          for bank in range(4):assert s.client.flash(bank)==expected[bank]
          check('all29-images-and-reservations-independent-readback')
          rec();s.load(config,sha(config),CONFIG)
          assert b'DEFAULT=S' in cmd('B')
          checkpoint(binding_append_requested=True)
          face=cmd('C B');assert b'OK' in face and b'REFUSED' not in face
          r['journal_appends']+=len(p['native_operations'][-1]['journal_appends'])
          r['journal_erase_requests']+=len(p['native_operations'][-1]['journal_sector_erases'])
          assert r['journal_appends']==32 and r['journal_erase_requests']==2
          face=cmd('Q',(t.MON,));assert b'STR8-N MON B  gen 00000010' in face
          expected[3]=(SCOPE/'compact/B3-expected.bin').read_bytes()
          rec();s.service(reader)
          for bank in range(4):
            body=s.client.flash(bank);assert body==(SCOPE/'compact'/f'B{bank}-expected.bin').read_bytes()
            durable(OUT/f'B{bank}-installed.bin',body)
          checkpoint(NVM_verified=True);check('saved-B-g10-final-root-counts-metadata-and-golden-F-exact')
          rec();face=cmd('A',(t.MON,));assert b'STR8-N MON A  gen 00000010' in face
          face=cmd('VERSION');assert b'CPU: 65C02' in face and b'Board: 2205' in face
          sample=cmd('TIME');assert re.search(rb'RTCC: 20.*trim \$[0-9A-F]{2} ctrl \$[0-9A-F]{2}',sample)
          rec();cmd('B',(t.MON,));assert b'STR8-N MON B  gen 00000010' in cmd('VERSION')
          check('MON-A-B-Traditional-VERSION-CPU02-board-metadata-and-TIME-trim')
          cmd('MAINT LOAD',(t.WB,));face=cmd('SRAM');assert b'SSRAM PROGRAM:' in face
          cmd('WORK');assert b'REFUSED' not in cmd('TABLE P');cmd('Q',(t.MON,))
          cmd('R CLOCK',(t.CLOCK,));assert b'raw' in cmd('STATUS').lower();cmd('HISTORY');cmd('Q',(t.MON,))
          # Compact profile has no resident MAINT/FLASH copies. Exercise the
          # same exact host-loaded REC BINs that shipped in Candidate4.
          kit=ROOT/'BUILD/unified-g10-candidate4-2512-acceptance-20261102-r1/STR8N-UNIFIED-MON-g00000010-ASMDBG-g2-candidate4'
          catalog=json.loads((kit/'NATIVE-COMPONENTS.json').read_text())
          for name,prompt in [('MAINT',b'BM> '),('FLASH',b'FLASH/MAINT> ')]:
              rec();item=catalog['REC_utilities'][name];body=(kit/item['file']).read_bytes();assert sha(body)==item['sha256'];s.load(body,sha(body),prompt)
              face=cmd('VERSION');assert b'REFUSED' not in face
              if name=='MAINT':assert b'EDITOR BUFFER' in cmd('?')
              cmd('Q',(t.MON,t.REC))
              if s.context==t.REC:cmd('B',(t.MON,))
          face=cmd('APPS');assert b'ASM B0:A000' in face and b'DBG B0:C000' in face
          check('installed-CLOCK-and-REC-MAINT-FLASH-EDU-SRAM-WORK-TABLE-and-APPS')
          # Returning RAM-only batch and assembler execution; no stored fixture.
          assert b'BATCH done' in cmd('BATCH VERSION;TIME')
          cmd('R ASM',(b'ASM> ',))
          for line in ('10 ORG $0200','20 LDA #$23','30 JSR $7E6D','40 JMP $7E67','50 END'):cmd(line)
          assert b'OK 8 bytes' in cmd('ASM');assert b'S1' in cmd('S19')
          cmd('QUIT',(t.MON,));assert s.dump(0x200,0x207)==bytes.fromhex('A923206D7E4C677E')
          assert b'#' in cmd('G 0200',(t.MON,))
          check('installed-returning-BATCH-and-ASM-list-export-RAM-run-HOLD')
          # Minimal real BRK step/continue gate; broader parity follows reusable tests.
          for line in ('M 1800 A9 35 EA 4C 67 7E',):cmd(line)
          cmd('R DBG',(START,));cmd('1800',(b'DBG> ',))
          face=cmd('S');assert b'PC=1802' in face and b'A=35' in face
          cmd('C',(t.MON,));assert s.dump(0x7e02,0x7e03)+s.dump(0x7e67,0x7e69)==bytes.fromhex('577E4C937E')
          check('installed-DBG-real-BRK-step-continue-and-new-runtime-default-hooks')
          checkpoint(functional_checks_passed=True)
        except BaseException as error:checkpoint(error=repr(error));raise
        finally:
          try:
            if borrowed and s:
              rec();s.service(reader)
              actual=s.client.flash(3);assert actual==expected[3]
              r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            restored=r.get('owner_RAM_restored') and r.get('owner_ZP_restored')
            mark(foundation_rollout_worker_active=False,application_RAM_restore_pending=not restored,
                application_ram_restored=bool(restored),block_snapshot=True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',
                foundation_profile_installation_pending=not r.get('NVM_verified'),foundation_profile_acceptance_pending=True,
                last_foundation_profile_install=str(OUT/'report.json'))
            if r.get('NVM_verified'):
                j=p['journal_after'];mark(current_physical_bank_sha256=p['expected_bank_sha256'],current_wear_counts=j['counts'],
                    current_journal_sequence=j['sequence'],current_valid_journal_records=j['valid_records'],
                    current_journal_valid_records=j['valid_records'],monitor_generation='00000010',saved_default='B',saved_default_generation='00000010',
                    status_installation_complete=True,Foundation_runtime_initialized=True,ASM_DBG_flash_installed=True,
                    state='Foundation-MONg10-installed',preferred_monitor='B',
                    current_firmware_profile='Foundation-BASE1-PR05-MONg10-native-DEVTOOLSg2')
            checkpoint()
    checkpoint(passed=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('port_released')),
        phase='installed-owner-restored-awaiting-default-reset',total_rollout_erases=3+r['image_erase_requests']+r['journal_erase_requests'])
    assert r['passed'] and r['total_rollout_erases']==34 and r['journal_appends']==32
    print(json.dumps(r,indent=2),flush=True)


if __name__=='__main__':run()
