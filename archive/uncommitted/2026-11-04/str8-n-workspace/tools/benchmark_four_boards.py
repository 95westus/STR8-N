"""Same 65C02 instruction workload on four physical boards; preserve owner RAM."""
import json,statistics,time,sys
from pathlib import Path
import standardize_ss2_64k as ss

def program(rounds=64):
 # Code/data stay on fixed pages; inner branches never cross a page.
 code=bytearray.fromhex('08 78 D8 A9');code.append(rounds)
 code+=bytes.fromhex('8D FF 33 A0 00 A2 00')
 loop=len(code)
 code+=bytes.fromhex('BD 00 30 49 5A 18 7D 00 31 2A 9D 00 32 E8')
 def branch(op):
  code.extend((op,(loop-(len(code)+2))&255))
 branch(0xd0);code.append(0x88);branch(0xd0)
 code+=bytes.fromhex('CE FF 33');branch(0xd0)
 code+=bytes.fromhex('28 A9 2F 85 E0 AD 30 7D 85 E1 6C E0 00')
 assert len(code)<256
 return bytes(code)

def inputs():
 a=bytes((i*73+19)&255 for i in range(256))
 b=bytes((i*29+113)&255 for i in range(256))
 expected=bytes(((((u^0x5a)+v)&255)<<1 | int((u^0x5a)+v>255))&255 for u,v in zip(a,b))
 return a,b,expected

def run(board):
 ss.inv.IDS['2205']=('COM3','A10MPUPNA',b'CPU: 65C02')
 out=ss.Q/f'CPU-benchmark-20261103-r2/{board}'
 out.parent.mkdir(exist_ok=True)
 r=dict(board=board,passed=False,benchmark='indexed arithmetic/read/write, 4194304 iterations',trials=[],
  timing='host perf_counter_ns from G command send to returned monitor prompt; launch overhead recorded separately',
  flash_writes=0,SPI_writes=0,RTC_writes=0,CPU_instruction_set='65C02-compatible; 2609 emulation')
 ss.wait_window(900)
 with ss.escrow(board,out,r) as x:
  (out/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  code=program();a,b,expected=inputs()
  (out/'benchmark.bin').write_bytes(code);(out/'expected-result.bin').write_bytes(expected)
  x.mon();x.s.modify(0x2000,code);x.s.modify(0x3000,a+b)
  assert x.s.dump(0x2000,0x2000+len(code)-1)==code
  assert x.s.dump(0x3000,0x31ff)==a+b
  # Identical return path, no workload; captures USB/monitor timing floor.
  return_only=bytes.fromhex('A9 2F 85 E0 AD 30 7D 85 E1 6C E0 00')
  x.s.modify(0x2100,return_only)
  def timed(address):
   start=time.perf_counter_ns();x.cmd(f'G {address:04X}',(ss.t.MON,));return (time.perf_counter_ns()-start)/1e9
  r['launch_overhead_seconds']=[timed(0x2100) for _ in range(5)]
  for trial in range(5):
   assert not ss.drift_pending(),'RTC priority before benchmark trial'
   elapsed=timed(0x2000)
   assert x.s.dump(0x3200,0x32ff)==expected,'Arithmetic result mismatch'
   assert x.s.dump(0x33ff,0x33ff)==b'\x00'
   r['trials'].append(elapsed);x.save()
   print(f'{board} trial {trial+1}/5: {elapsed:.6f}s; result correct',flush=True)
  r.update(median_seconds=statistics.median(r['trials']),minimum_seconds=min(r['trials']),maximum_seconds=max(r['trials']),
   program_sha256=ss.t.sha(code),result_sha256=ss.t.sha(expected),all_results_correct=True)
 r['passed']=all(r.get(k) for k in ('all_results_correct','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','port_released'))
 ss.t.save(out/'report.json',r);assert r['passed']
 print(f'PASS {board}: median {r["median_seconds"]:.6f}s; owner restored',flush=True)

if __name__=='__main__':
 from py65.devices.mpu65c02 import MPU
 memory=[0]*65536;test=program(1);a,b,expected=inputs()
 memory[0x2000:0x2000+len(test)]=test;memory[0x3000:0x3200]=a+b;memory[0x7d30]=0x7e
 cpu=MPU(memory=memory,pc=0x2000)
 for step in range(600000):
  if cpu.pc==0x7e2f:break
  cpu.step()
 else:raise AssertionError('Offline benchmark did not return')
 assert bytes(memory[0x3200:0x3300])==expected and memory[0x33ff]==0
 print(f'Offline workload/result/return verified: {step} instructions',flush=True)
 original_window=ss.ds.ins.window
 ss.ds.ins.window=lambda seconds=240:original_window(min(seconds,360))
 original_lease=ss.t.serial_lease
 ss.t.serial_lease=lambda kind,timeout=30:original_lease(kind,timeout=600)
 for board in sys.argv[1:] or ['2205','2512','2604','2609']:run(board)
