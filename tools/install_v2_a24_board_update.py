"""Install a guarded S19 updater via STR8-N L/G on COM3."""
import argparse
import json
import serial
import time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('s19',type=Path)
p.add_argument('--phase',choices=('f','e'),required=True)
p.add_argument('--log',type=Path,required=True)
a=p.parse_args()
lines=a.s19.read_bytes().splitlines(keepends=True)
if not lines[-1].startswith(b'S9'):
 raise SystemExit('Missing S9')
a.log.parent.mkdir(parents=True,exist_ok=True)
s=serial.Serial('COM3',115200,timeout=.1,write_timeout=5)
s.dtr=False;s.rts=False
log=a.log.open('w',encoding='utf8')
def record(direction,data):
 log.write(json.dumps({'time':time.time(),'direction':direction,'text':data.decode('latin1'),'hex':data.hex()})+'\n');log.flush()
def send(data):
 s.write(data);record('TX',data)
def until(token,seconds=8):
 end=time.monotonic()+seconds;b=bytearray()
 while time.monotonic()<end:
  x=s.read(256)
  if x:
   b.extend(x);record('RX',x)
   if token in b:return bytes(b)
 raise RuntimeError(f'timed out waiting for {token!r}; got {bytes(b)[-200:]!r}')
try:
 s.reset_input_buffer()
 send(b'\r');until(b'B3> ')
 send(b'L\r');until(b'S19')
 for i,line in enumerate(lines):
  send(line)
  time.sleep(.055)
  if i%32==31:
   x=s.read(s.in_waiting or 0)
   if x:record('RX',x)
 got=until(b'B3> ',10)
 if b'entry 2000' not in got and b'Entry 2000' not in got:
  raise RuntimeError(f'No 2000 entry: {got[-250:]!r}')
 send(b'G 2000\r')
 if a.phase=='f':
  until(b'TYPE BACKUP B2F> ',10)
  send(b'BACKUP B2F\r')
  until(b'TYPE STR8-N 2.0a24> ',45)
  send(b'STR8-N 2.0A24\r')
  until(b'STR8-N 2.0a24 VERIFIED; RESET',45)
  until(b'B3> ',15)
 else:
  until(b'TYPE Y to repair> ',10)
  send(b'Y')
  until(b'B3:E VERIFIED; RESET',25)
  until(b'B3> ',15)
 print(a.phase,'INSTALL PASS')
finally:
 s.close();log.close()
