"""Offline smoke test of the exact 2512 installation images and retained data."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-candidate'
import argparse,json,re
from pathlib import Path
from test_v2_status import fresh,boot,snapshot
from test_v2_spi_resident import k
from test_v2_sram_store import console
cmd=lambda cpu,m,line:console(cpu,m,line,limit=100000000)
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-beta32-candidate';META=json.loads((BUILD/'build.json').read_text())
def main(root):
 plan=json.loads((root/'upgrade/plan.json').read_text());array=(root/'retained/sram-prior/array-0.bin').read_bytes();checks=[]
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 def fixture(key=None,success_return=False):
  cpu,m=fresh();m.banks=[bytearray((root/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
  m.spi.devices[0].data[:]=array;m.fast=True
  raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(root/'retained/devices-before/status.txt').read_bytes())[1].decode());m.bus.rtc_regs[:9]=raw
  ee=(root/'retained/devices-before/eeprom-0.bin').read_bytes();m.bus.ee[:128]=ee[:128];m.bus.ee[0xF0:0xF9]=ee[128:137]
  if success_return:
   m.banks=[bytearray((root/f'prior-verified/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
   k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000);boot(cpu)
   assert b'2.0b31' in m.tx
   m.banks=[bytearray((root/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
   from beta4_migration import read_s19
   cells,_=read_s19(root/'upgrade/installer.s19');mf=json.loads((BUILD/'migrator/manifest.json').read_text());sy=mf['symbols']
   for a,v in cells.items():m.ram[a]=v
   n=sy['V2W_END']-0x7800;m.ram[0x7800:0x7800+n]=bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
   cpu.x=sy['MIG_DONE']&255;cpu.y=sy['MIG_DONE']>>8;cpu.pc=plan['success_checkpoint']-3;m.tx.clear()
  k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
  if key:m.rx.extend(key)
  boot(cpu);return cpu,m
 cpu,m=fixture(success_return=True);assert b'MIGRATION VERIFIED; READY FOR J3' in m.tx
 passed('successful installer return stub prints verification and bootstraps beta32 with original installer RAM worker; no physical reset')
 text=cmd(cpu,m,b'J3\r');assert b'STR8-N 2.0b32' in text and b'MONITOR B gen 0000002C VALID default' in text,text
 assert text.count(b'FLASH: wear check ')==1 and ('FLASH: wear check '+plan['expected_wear_status']).encode() in text,text
 assert plan['expected_wear_peak'].encode() in text,text
 (root/'upgrade/model-boot.txt').write_bytes(text)
 passed('J3 software restart boots verified beta32 B; expected FLASH wear check appears exactly once')
 assert b'2.0b32' in m.tx and m.ram[0x7D30]==0xB0
 original=snapshot(m)
 text=cmd(cpu,m,b'BATCH VERSION;TIME\r');assert b'FLASH: wear check' not in text
 assert b'MONITOR A gen 00000028 VALID' in text and b'MONITOR B gen 0000002C VALID default' in text and b'BATCH done' in text,text
 passed('exact live-preimage plan boots beta32 B with beta28 A retained; BATCH VERSION/TIME')
 text=cmd(cpu,m,b'APPS\r');assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
 text=cmd(cpu,m,b'T\r');assert b'CLOCK' not in text and b'MAINT' not in text and b'B2:' not in text,text
 for name,title,query in [('MAINT',b'BANK MAINT 2.4',b'?\r')]:
  text=cmd(cpu,m,(name+'\r').encode());assert title in text,text
  text=cmd(cpu,m,query);text=cmd(cpu,m,b'Q\r');assert text.endswith(b'B3> ')
  assert snapshot(m)==original and not m.events
  passed(name+' launch/query/Q preserves all storage')
 text=cmd(cpu,m,b'BATCH SRAM;G CLK;STATUS;Q\r');assert b'BATCH done' in text and b'CLOCK 1.9' in text and b'Running: yes' in text and b'Backup enabled: yes' in text and text.endswith(b'B3> '),text
 assert snapshot(m)==original and not m.events
 passed('saved SRAM CLOCK 1.9 batch STATUS/Q and complete retained state unchanged')
 cpu,m=fixture(b'A');assert b'2.0b28' in m.tx and m.ram[0x7D30]==0xA0
 original=snapshot(m)
 assert b'EDU 1.4' in cmd(cpu,m,b'R EDU\r');cmd(cpu,m,b'Q\r')
 assert snapshot(m)==original and not m.events
 passed('retained beta28 A boots with the new wear helper and launches EDU normally')
 prior=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)];final=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
 assert final[0]==prior[0] and final[1]==prior[1]
 assert final[3][:0x3000]==prior[3][:0x3000] and final[3][0x5000:]==prior[3][0x5000:]
 passed('B0, unaffected B1, RTC/identity/name tail, beta28 A and fixed recovery preserved byte for byte')
 result=dict(passed=True,installer_return_verified=True,j3_reset_verified=True,wear_boot_verified=True,wear_peak_verified=True,checks=checks,build_sha256=sha((BUILD/'build.json').read_bytes()),expected_hashes=plan['expected_hashes'],retained_sram_sha256=sha(array),board_access=False)
 (root/'upgrade/beta32-board-test-results.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);main(p.parse_args().root)
