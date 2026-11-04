import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'owner-direct-peek-r2';CASE.mkdir(exist_ok=False)
code=bytearray.fromhex('78 D8 20 79 7E 9C F9 7D A9 01 8D 2B 7C')
for a,n in ((0x200,64),(0x66C0,64),(0,224)):
 code+=bytes.fromhex('A2 00');start=len(code)
 code+=bytes([0xBD,a&255,a>>8,0x20,0x6D,0x7E,0x90,0xFB,0xE8,0xE0,n,0xD0,0xF3])
code+=bytes.fromhex('9C 2B 7C 4C 67 7E')
with t.serial_lease('2512-independent-owner-peek-no-NVM',timeout=30):
 with (CASE/'serial.jsonl').open('x') as log:
  s=d.Session(CASE,log,'2512')
  try:
   s.link.send(b'\r');s.until((t.MON,),seconds=12)
   for off in range(0,len(code),8):s.command('!M '+f'{0x6B00+off:04X} '+code[off:off+8].hex(' '))
   s.modify(0x3000,bytes.fromhex('4C 00 6B'))
   s.link.send(b'G 3000\r');s.until((b'G 3000\r\n',),seconds=10)
   raw=bytearray()
   while len(raw)<352:
    n=352-len(raw)
    if s.link.pending:raw+=s.link.pending[:n];del s.link.pending[:n]
    else:raw+=s.link.read(n)
   (CASE/'direct-owner-samples.bin').write_bytes(raw);s.until((t.MON,),seconds=15)
   ram=(BASE/'RAM-trial/owner-ram.bin').read_bytes();zp=(BASE/'RAM-trial/owner-zp.bin').read_bytes();expected=ram[:64]+ram[-64:]+zp
   print('direct first matches',raw[:64]==expected[:64],'last',raw[64:128]==expected[64:128],'ZP',raw[128:]==expected[128:],flush=True)
   print('actual first',raw[:32].hex(' '),flush=True)
  finally:
   if s.context==t.MON:s.modify(0x3000,(BASE/'RAM-trial/owner-ram.bin').read_bytes()[0x2e00:0x2e03])
   s.link.close()
