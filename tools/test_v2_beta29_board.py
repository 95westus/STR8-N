"""Offline smoke test of the exact 2512 installation images and retained data."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta29-candidate'
import argparse,json,re
from pathlib import Path
from test_v2_status import fresh,boot,snapshot
from test_v2_beta29 import cmd,k,META
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-beta29-candidate'
def main(root):
 plan=json.loads((root/'upgrade/plan.json').read_text());array=(root/'retained/sram-prior/array-0.bin').read_bytes();checks=[]
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 def fixture(key=None):
  cpu,m=fresh();m.banks=[bytearray((root/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
  m.spi.devices[0].data[:]=array;m.fast=True
  raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(root/'retained/devices-before/status.txt').read_bytes())[1].decode());m.bus.rtc_regs[:9]=raw
  m.bus.ee[0xF2:0xF8]=bytes.fromhex('5410ECB6743C')
  k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
  if key:m.rx.extend(key)
  boot(cpu);return cpu,m
 cpu,m=fixture();assert b'2.0b29' in m.tx and m.ram[0x7D30]==0xB0
 original=snapshot(m)
 text=cmd(cpu,m,b'BATCH VERSION;TIME\r');assert b'MONITOR A gen 00000028 VALID' in text and b'MONITOR B gen 00000029 VALID default' in text and b'BATCH done' in text,text
 passed('exact live-preimage plan boots beta29 B with beta28 A retained; BATCH VERSION/TIME')
 text=cmd(cpu,m,b'APPS\r');assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
 text=cmd(cpu,m,b'T\r');assert b'CLOCK' in text and b'MAINT' not in text and b'B2:' not in text,text
 for name,title,query in [('MAINT',b'BANK MAINT 2.4',b'?\r'),('SRAM',b'SRAM 1.4',b'T\r'),('WORK',b'WORK 1.4',b'?\r'),('EDU',b'EDU 1.4',b'?\r')]:
  text=cmd(cpu,m,('R '+name+'\r').encode());assert title in text,text
  text=cmd(cpu,m,query);text=cmd(cpu,m,b'Q\r');assert text.endswith(b'B3> ')
  assert snapshot(m)==original and not m.events
  passed(name+' launch/query/Q preserves all storage')
 text=cmd(cpu,m,b'R MAINT\rNAME Z29CHECK\r');assert text.endswith(b'Type YES: '),text
 text=cmd(cpu,m,b'NO\r');assert text.endswith(b'BM> '),text
 cmd(cpu,m,b'Q\r');assert snapshot(m)==original and not m.events
 passed('NAME regression stays in MAINT, waits for confirmation and refuses NO without writes')
 text=cmd(cpu,m,b'BATCH R SRAM;BOGUS;Q\r');assert b'BATCH stopped: command failed' in text and text.endswith(b'SRAM> '),text
 cmd(cpu,m,b'Q\r');passed('SRAM batch error cancels queued Q and leaves SRAM prompt')
 text=cmd(cpu,m,b'R CLOCK\rSTATUS\rBATTERY\rQ\r');assert b'CLOCK 1.9' in text and b'Running: yes' in text and b'Backup enabled: yes' in text and text.endswith(b'B3> '),text
 assert snapshot(m)==original and not m.events
 passed('CLOCK 1.9 STATUS/BATTERY/Q and complete retained state unchanged')
 cpu,m=fixture(b'A');assert b'2.0b28' in m.tx and m.ram[0x7D30]==0xA0
 original=snapshot(m)
 assert b'EDU 1.4' in cmd(cpu,m,b'R EDU\r');cmd(cpu,m,b'Q\r')
 assert b'CLOCK 1.9' in cmd(cpu,m,b'R CLOCK\r');cmd(cpu,m,b'Q\r')
 assert snapshot(m)==original and not m.events
 passed('retained beta28 A boots and launches native EDU and CLOCK normally')
 prior=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)];final=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
 assert final[0]==prior[0] and final[1][:0x3000]==prior[1][:0x3000] and final[1][0x6000:]==prior[1][0x6000:]
 assert final[3][:0x3000]==prior[3][:0x3000] and final[3][0x5000:]==prior[3][0x5000:]
 passed('B0, unaffected B1, RTC/identity/name tail, beta28 A and fixed recovery preserved byte for byte')
 result=dict(passed=True,checks=checks,build_sha256=sha((BUILD/'build.json').read_bytes()),expected_hashes=plan['expected_hashes'],retained_sram_sha256=sha(array),board_access=False)
 (root/'upgrade/beta29-board-test-results.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);main(p.parse_args().root)
