"""2604-only bounded native S19/G proof; sixteen borrowed RAM bytes, no flash."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from inspect_2604_rc1g34_capture import CAPTURE,F_HASH,inspect
from installer.engine.legacy_transport import Link,s_record
from installer.engine.runtime import sha
from installer.common import save
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease,drift_pending
import install_named_edu_2512 as guard

OUT=ROOT/'output/qualification/2604-rc1-S19-handoff-RAM-20261102-r1'
MON=b'\r\nB3> '


def run():
    source=inspect(CAPTURE);guard.window(150)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
    durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
    report=dict(board='2604',passed=False,flash_writes=0,SPI_accesses=0,RTC_accesses=0,
        journal_writes=0,resets=0,power_cuts=0,borrowed_RAM_bytes=16,started_utc=guard.t.utc())
    mp=ROOT/'output/qualification/device-operations/2604.json'
    link=None;borrowed=False;original=None
    def checkpoint(**fields):
        marker=json.loads(mp.read_text());marker.update(fields);save(mp,marker)
    with serial_lease('2604-rc1g34-bounded-native-S19-G-RAM-proof',timeout=30):
      guard.window(150)
      marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['block_snapshot'] and not marker['application_RAM_restore_pending']
      assert not marker['physical_reset_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      from serial.tools.list_ports import comports
      matches=[p for p in comports() if p.serial_number=='A10MQGVHA']
      assert len(matches)==1 and matches[0].device=='COM5'
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          link=Link('COM5',log);link.send(b'\r');link.until(MON,seconds=10)
          def dump(first,last):return b''.join(link.dump(a,min(a+511,last)) for a in range(first,last+1,512))
          b3=dump(0x8000,0xffff);assert sha(b3)==source['bank_sha256']['B3'] and sha(b3[-4096:])==F_HASH
          # Admit the exact private prompt against the source/build symbols and
          # both complete slot payloads, instead of treating it as a public ABI.
          build=ROOT/'BUILD/rc1-r10p2-g0034'
          distribution=(build/'firmware.bin').read_bytes()
          assert sha(distribution)=='0df4a802d618c0df5e658dcf2cd05037f0a892a209abaeac6bca0d595c468945'
          assert b3[0x2000:0x4000]==distribution[0x12000:0x14000]
          active=dump(0x7d30,0x7d30)[0];assert active in (0xa0,0xb0)
          symbols=json.loads((build/'symbols.json').read_text())
          prompt=symbols['core/monitor-a0' if active==0xa0 else 'core/monitor-b0']['V2_PROMPT']
          assert prompt==(0xa168 if active==0xa0 else 0xb168)
          assert dump(0x7df9,0x7df9)==b'\0','Legacy storage return hook active'
          ram=dump(0x200,0x66ff);zp=dump(0,0xdf);cache=dump(0x6b00,0x77ff);hooks=dump(0x7e00,0x7e8f)
          for name,body in [('owner-ram.bin',ram),('owner-zp.bin',zp),('provider-cache-before.bin',cache),('vectors-before.bin',hooks)]:durable(OUT/name,body)
          original=ram[0x1e00:0x1e10]
          # LDA #A5; STA $2008; JMP admitted MON prompt. No I/O or ROM calls.
          probe=bytes.fromhex('A9 A5 8D 08 20 4C')+prompt.to_bytes(2,'little')+bytes(8)
          assert len(probe)==16
          text='\n'.join((s_record('0',0,b'RC1 g0034 bounded RAM proof'),s_record('1',0x2000,probe),s_record('9',0x2000)))+'\n'
          durable(OUT/'probe.s19',text.encode())
          if drift_pending():raise InterruptedError('RTC priority before RAM upload')
          checkpoint(rc1_s19_probe_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
          borrowed=True
          link.command('L',b'S19')
          for line in text.splitlines():link.send(line.encode()+b'\r\n');time.sleep(.04)
          face=link.until(MON);durable(OUT/'loaded-console.txt',face)
          assert b'Entry 2000' in face and not any(x in face for x in (b'Bad',b'Protected',b'Wrap',b'Error'))
          assert dump(0x2000,0x200f)==probe,'S19 did not load exact bytes / autoran unexpectedly'
          link.command('G 2000');assert dump(0x2008,0x2008)==b'\xa5'
          report.update(load_only_S19_passed=True,explicit_G_handoff_passed=True,
              active_monitor='A' if active==0xa0 else 'B',private_prompt=f'{prompt:04X}')
        except BaseException as error:report['error']=repr(error);raise
        finally:
          try:
            if link and borrowed:
              # rc1 M dispatch depends on the extension's private slot router.
              # Restore through the independently proved load-only path.
              restore='\n'.join((s_record('0',0,b'2604 RAM probe restore'),s_record('1',0x2000,original),s_record('9',0x2000)))+'\n'
              link.command('L',b'S19')
              for row in restore.splitlines():link.send(row.encode()+b'\r\n');time.sleep(.04)
              face=link.until(MON)
              assert b'Entry 2000' in face
              assert dump(0x200,0x66ff)==ram and dump(0,0xdf)==zp
              assert dump(0x6b00,0x77ff)==cache and dump(0x7e00,0x7e8f)==hooks
              assert dump(0x8000,0xffff)==b3
              report.update(owner_RAM_restored=True,owner_ZP_restored=True,full_cache_restored=True,hooks_restored=True,B3_exact=True)
              checkpoint(rc1_s19_probe_worker_active=False,application_RAM_restore_pending=False,block_snapshot=False,
                  application_ram_restored=True,last_rc1_S19_RAM_handoff=str(OUT/'report.json'))
          except BaseException as error:
            report['restoration_error']=repr(error)
            raise
          finally:
            if link:link.serial.close();report['port_released']=True
            report['passed']=bool(report.get('explicit_G_handoff_passed') and report.get('B3_exact') and not report.get('error'))
            report['finished_utc']=guard.t.utc();save(OUT/'report.json',report)
    assert report['passed'];print(json.dumps(report,indent=2))


if __name__=='__main__':run()
