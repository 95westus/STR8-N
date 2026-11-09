"""Execute current DEV ASM and both examples in CPU models; no board access."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


class Machine:
    def __init__(self, cpu, body, origin, entry):
        self.memory=bytearray(65536)
        self.memory[origin:origin+len(body)]=body
        self.memory[0x7e60:0x7e64]=b'RA\x01\x0d'
        self.cpu=cpu(memory=self.memory,pc=entry)
        self.cpu.pc=entry
        self.cpu.sp=0xff
        self.cpu.p |= self.cpu.INTERRUPT
        self.input=deque();self.output=bytearray();self.exited=None
    def ret(self): self.cpu.pc=(self.cpu.stPopWord()+1)&65535
    def run(self, data=b'', limit=30000000):
        self.input.extend(data);begin=len(self.output);cpu=self.cpu
        for count in range(limit):
            pc=cpu.pc
            if pc==0x7e70:
                if not self.input:return bytes(self.output[begin:])
                cpu.a=self.input.popleft();self.ret()
            elif pc==0x7e6d:
                self.output.append(cpu.a);self.ret()
            elif pc==0x7e7f:
                self.output.extend(b'\r\n');self.ret()
            elif pc==0x7e7c:
                self.output.extend(f'{cpu.a:02X}'.encode());self.ret()
            elif pc==0x7e76:
                cpu.p &= ~cpu.CARRY;self.ret()
            elif pc==0x7e73:
                cpu.p &= ~cpu.CARRY
                if self.input:cpu.a=self.input.popleft();cpu.p |= cpu.CARRY
                self.ret()
            elif pc in (0x7e64,0x7e67):
                self.exited=pc;return bytes(self.output[begin:])
            else:cpu.step()
        raise AssertionError(f'CPU limit at {cpu.pc:04X}: {bytes(self.output[-200:])!r}')


def check_asm(build,kit,cpu,report):
    packet=next((kit/name).read_bytes() for name,info in json.loads((kit/'COMPONENTS.json').read_text())['artifacts'].items()
                if info['component']=='ASM' and info.get('load')=='0200')
    machine=Machine(cpu,packet,0x200,0x200)
    assert b'ASM> ' in machine.run()
    joined=bytearray();proof=[]
    for part in report['Microchess']['parts']:
        assert b'ASM> ' in machine.run(b'NEW\r')
        assert b'Paste' in machine.run(b'PASTE\r')
        source=(build/part['file']).read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r')
        text=machine.run(source+b'.\r')
        assert b'Error' not in text,text[-300:]
        packed=int.from_bytes(machine.memory[0x6500:0x6502],'little')-0x2000
        assert packed==part['packed_bytes'],(packed,part)
        text=machine.run(b'ASM\r')
        assert b'OK ' in text,text
        length=int.from_bytes(machine.memory[0x6502:0x6504],'little')
        origin=int.from_bytes(machine.memory[0x6504:0x6506],'little')
        assert origin==int(part['origin'],16) and length==int(part['end_exclusive'],16)-origin
        actual=bytes(machine.memory[0x200:0x200+length]);joined.extend(actual)
        # Actual ASM S19 output carries the logical origin of each part.
        text=machine.run(b'S19\r')
        records=[line for line in text.splitlines() if re.fullmatch(rb'S[019](?:[0-9A-F]{2}){4,}',line)]
        assert records and records[-1].startswith(b'S9')
        (build/(part['file']+'.s19')).write_bytes(b'\r\n'.join(records)+b'\r\n')
        proof.append({'part':part['file'],'origin':part['origin'],'bytes':length,'source_bytes':packed})
        print('PASS actual DEV ASM:',part['file'],length,'bytes',flush=True)
    expected=(build/'microchess-ram.bin').read_bytes()
    assert bytes(joined)==expected,'Actual DEV ASM output differs from readable WDC reference'
    from example_images import records, ap02
    restored={}
    for part in report['Microchess']['parts']:
        values,_=records((build/(part['file']+'.s19')).read_bytes())
        assert not (restored.keys() & values.keys())
        restored.update(values)
    assert bytes(restored[i] for i in range(0x200,0x200+len(expected)))==expected
    assert ap02(bytes(joined))==(build/'microchess-ap02-b1-8000.bin').read_bytes()
    (build/'microchess-assembled-in-dev-asm.bin').write_bytes(joined)
    return proof


def check_chess(build,cpu):
    body=(build/'microchess-ram.bin').read_bytes()
    m=Machine(cpu,body,0x200,0x200)
    text=m.run();assert b'(c) 1976-2005 Peter Jennings' in text and b'|WK|' in text
    assert b'Copyright (c) 2026 95west.us/wlp1963; MIT' in text
    assert m.memory[0x10+15]==0x13 and m.memory[0x10+31]==0x63
    m.run(b'P');assert m.memory[0x10+15]==0x33
    m.run(b'6343\r');assert m.memory[0x10+31]==0x43
    m.run(b'E');assert m.memory[0xb7]==1
    m.run(b'C');assert m.memory[0x10+15]==0x13 and m.memory[0x10+31]==0x63
    m.run(b'Q');assert m.exited==0x7e67
    assert bytes(m.memory[0x200:0x200+len(body)])==body
    image=(build/'microchess-ap02-b1-8000.bin').read_bytes()
    import binascii
    assert image[:8]==b'AP\x02 PR05' and image[15]==0
    assert int.from_bytes(image[28:30],'little')==binascii.crc_hqx(image[:28],65535)
    end=int.from_bytes(image[8:10],'little')
    assert int.from_bytes(image[30:32],'little')==binascii.crc_hqx(image[32:end],65535)
    ap=Machine(cpu,image,0x8000,0x8020)
    assert b'(c) 1976-2005 Peter Jennings' in ap.run()
    assert bytes(ap.memory[0x200:0x200+len(body)])==body
    ap.run(b'Q');assert ap.exited==0x7e67
    return {'game_commands':['P','6343','E','C','Q'],'AP02_CRCs_and_entry':True,'RAM_bytes':len(body)}


def check_basic(build,cpu):
    body=(build/'osi-basic-opaque-b0-8000.bin').read_bytes()
    m=Machine(cpu,body,0x8000,0x8000)
    reserved=bytes(m.memory[0x6700:0x8000]);system_zp=bytes(m.memory[0xe0:0x100])
    startup=m.run();assert b'OSI 6502 BASIC VERSION' in startup and b'1977 Microsoft' in startup,startup
    assert int.from_bytes(m.memory[0x85:0x87],'little')==0x6700
    text=m.run(b'PRINT 2+3\r');assert re.search(rb'\r\n\s*5\s*\r\n',text),text
    for line in [b'10 FOR I=1 TO 3\r',b'20 PRINT I*I\r',b'30 NEXT I\r']:m.run(line)
    text=m.run(b'RUN\r')
    for value in [b'1',b'4',b'9']:assert re.search(rb'\r\n\s*'+value+rb'\s*\r\n',text),text
    text=m.run(b'LIST\r');assert b'FOR I' in text and b'NEXT I' in text
    text=m.run(b'PRINT "FOUNDATION"\r');assert b'FOUNDATION\r\n' in text
    m.run(b'NEW\r');m.run(b'10 GOTO 10\r')
    text=m.run(b'RUN\r\x03');assert b'\r\nOK\r\n' in text,text
    assert bytes(m.memory[0x6700:0x8000])==reserved
    assert bytes(m.memory[0xe0:0x100])==system_zp
    assert bytes(m.memory[0x8000:0xa000])==body
    m.run(b'\x1b');assert m.exited==0x7e64
    return {'cold_boot':True,'arithmetic':True,'FOR_NEXT':True,'LIST':True,'strings':True,
            'Ctrl_C':True,'ESC_public_reset':True,'reserved_RAM_and_system_ZP_preserved':True,'ROM_unchanged':True}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--cpu',choices=['65c02','65c816-e'],default='65c02');p.add_argument('--skip-asm',action='store_true')
    args=p.parse_args();sys.path.insert(0,str(ROOT/'tests/vendor'))
    if args.cpu=='65c02':from py65.devices.mpu65c02 import MPU
    else:from py65816.devices.mpu65c816 import MPU
    report=json.loads((args.build/'EXAMPLES.json').read_text());result={}
    if not args.skip_asm:result['actual_DEV_ASM']=check_asm(args.build,args.kit,MPU,report)
    result['Microchess']=check_chess(args.build,MPU);print('PASS Microchess RAM/AP02',flush=True)
    result['OSI_BASIC']=check_basic(args.build,MPU);print('PASS OSI BASIC B0',flush=True)
    result.update(passed=True,cpu=args.cpu,F_rebuilt=False,physical_board_access=False,
                  public_RAM_ABI='modeled console/return endpoints; no private F calls',
                  test_harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  DEV_ASM_sha256=next(info['sha256'] for info in json.loads((args.kit/'COMPONENTS.json').read_text())['artifacts'].values()
                      if info['component']=='ASM' and info.get('load')=='0200'),
                  example_payload_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.build.glob('*.bin')})
    (args.build/f'tests-examples-{args.cpu}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
