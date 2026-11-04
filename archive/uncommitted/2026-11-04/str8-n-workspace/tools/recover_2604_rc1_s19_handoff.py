"""Recover the sixteen-byte 2604 trial via load-only S19; no persistent writes."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from installer.engine.legacy_transport import Link,s_record
from installer.common import save
from installer.engine.runtime import sha
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease
import install_named_edu_2512 as guard

PRIOR=ROOT/'output/qualification/2604-rc1-S19-handoff-RAM-20261102-r1'
OUT=ROOT/'output/qualification/2604-rc1-S19-owner-recovery-20261102-r1'
MP=ROOT/'output/qualification/device-operations/2604.json'
MON=b'\r\nB3> '


def run():
    before=json.loads((PRIOR/'report.json').read_text())
    assert before['load_only_S19_passed'] and before['explicit_G_handoff_passed'] and before['port_released']
    ram=(PRIOR/'owner-ram.bin').read_bytes();zp=(PRIOR/'owner-zp.bin').read_bytes()
    cache=(PRIOR/'provider-cache-before.bin').read_bytes();hooks=(PRIOR/'vectors-before.bin').read_bytes()
    assert len(ram)==0x6500 and len(zp)==0xe0 and len(cache)==0xd00 and len(hooks)==0x90
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
    report=dict(board='2604',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,power_cuts=0,physical_resets=0,phase='initial-cancel-probe')
    def mark(**fields):m=json.loads(MP.read_text());m.update(fields);save(MP,m)
    def checkpoint(**fields):report.update(fields);save(OUT/'report.json',report)
    def load(link,first,body,label):
        text='\n'.join([s_record('0',0,b'2604 owner recovery')]+[s_record('1',a,body[a-first:a-first+32]) for a in range(first,first+len(body),32)]+[s_record('9',first)])+'\n'
        durable(OUT/(label+'.s19'),text.encode())
        link.command('L',b'S19')
        for row in text.splitlines():link.send(row.encode()+b'\r\n');time.sleep(.04)
        face=link.until(MON,seconds=30);durable(OUT/(label+'-console.txt'),face)
        assert f'Entry {first:04X}'.encode() in face and not any(v in face for v in (b'Bad',b'Protected',b'Wrap',b'Error'))
    checkpoint()
    link=None
    with (OUT/'serial.jsonl').open('x') as log:
      try:
        with serial_lease('2604-rc1-S19-owner-recovery-cancel-probe',timeout=30):
          mark(rc1_s19_probe_worker_active=False,rc1_s19_recovery_worker_active=True)
          link=Link('COM5',log);link.send(b'\x03\r')
          try:face=link.until(MON,seconds=5);recovered=True;durable(OUT/'cancel-console.txt',face)
          except TimeoutError:recovered=False
        if not recovered:
          mark(physical_reset_pending=True,rc1_s19_recovery_worker_active=False,rc1_s19_reset_waiting=True)
          checkpoint(phase='waiting-for-2604-physical-reset')
          print('ARMED2604 physical RESET receiver on COM5; no flash writes; fleet lease released',flush=True)
          deadline=time.monotonic()+12*3600;tail=b''
          while time.monotonic()<deadline:
            tail=(tail+link.read(max(1,link.serial.in_waiting)))[-4096:]
            if b'A/B/S,Enter default' in tail:
              link.send(b'B');face=link.until(MON,seconds=30)
              durable(OUT/'reset-console.txt',tail+face);break
          else:raise TimeoutError('No2604 RESET seen; owner escrow retained')
          checkpoint(physical_resets=1,phase='legacy-monitor-recovered')
        with serial_lease('2604-rc1-S19-owner-restoration',timeout=90):
          mark(physical_reset_pending=False,rc1_s19_reset_waiting=False,rc1_s19_recovery_worker_active=True)
          def dump(first,last):return b''.join(link.dump(a,min(a+511,last)) for a in range(first,last+1,512))
          source=ROOT/'local-archives/STR8-N-rc1-g0034-2604-20261102/live-board'
          b3=dump(0x8000,0xffff);assert b3==(source/'b3.bin').read_bytes()
          if report['physical_resets']:
            active=dump(0x7d30,0x7d30)[0];assert active==0xb0 and dump(0x7df9,0x7df9)==b'\0'
            payload=ram[-512:]+cache+hooks+zp
            code=bytearray(bytes.fromhex('78 D8 A2 00'))
            loop=0x2004
            destinations=[0x6500,0x6600]+list(range(0x6b00,0x7800,256))
            for n,destination in enumerate(destinations):
                code+=bytes((0xbd,0,(0x3000+256*n)>>8,0x9d,0,destination>>8))
            code+=bytes((0xe8,0xd0,(loop-(0x2000+len(code)+3))&255))
            assert 0<len(code)<128
            for start,destination,size in ((0x3f00,0x7e00,0x90),(0x3f90,0,0xe0)):
                code+=bytes((0xa2,0));again=0x2000+len(code)
                code+=bytes((0xbd,start&255,start>>8,0x9d,destination&255,destination>>8,0xe8,0xe0,size,0xd0,(again-(0x2000+len(code)+11))&255))
            code+=bytes.fromhex('4C 68 B1')
            body=bytes(code)+bytes(0x1000-len(code))+payload
            assert len(payload)==0x1070 and len(body)==0x2070
            load(link,0x2000,body,'upper-cache-hook-ZP-restorer')
            assert dump(0x2000,0x406f)==body
            link.command('G 2000')
            assert dump(0x6500,0x66ff)==ram[-512:] and dump(0x6b00,0x77ff)==cache
            assert dump(0x7e00,0x7e8f)==hooks and dump(0,0xdf)==zp
            load(link,0x200,ram[:-512],'original-owner-lower-RAM')
          else:
            load(link,0x2000,ram[0x1e00:0x1e10],'original-sixteen-bytes')
          assert dump(0x200,0x66ff)==ram and dump(0,0xdf)==zp
          assert dump(0x6b00,0x77ff)==cache and dump(0x7e00,0x7e8f)==hooks
          assert dump(0x8000,0xffff)==b3
          checkpoint(passed=True,phase='restored',owner_RAM_restored=True,owner_ZP_restored=True,full_cache_restored=True,hooks_restored=True,B3_exact=True,final_prompt='B3>')
          mark(rc1_s19_probe_worker_active=False,rc1_s19_recovery_worker_active=False,rc1_s19_reset_waiting=False,
            physical_reset_pending=False,application_RAM_restore_pending=False,block_snapshot=False,
            application_ram_restored=True,last_rc1_S19_owner_recovery=str(OUT/'report.json'))
      except BaseException as error:checkpoint(error=repr(error));raise
      finally:
        if link:link.serial.close();checkpoint(port_released=True)
    print(json.dumps(report,indent=2))


if __name__=='__main__':run()
