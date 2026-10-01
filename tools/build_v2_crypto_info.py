"""Build fixed informational ATECC608 commands and RAM probe."""
import hashlib, json, shutil
from pathlib import Path
import build_v2_a24 as base
OUT=base.ROOT/'BUILD/v2-crypto-info'
SOURCE=base.ROOT/'tools/v2-crypto-info'
NAME='crypto-info-2000'
def crc(data):
    value=0
    for byte in data:
        for bit in range(8):
            mix=((byte>>bit)&1)^((value>>15)&1)
            value=(value<<1)&65535
            if mix: value^=0x8005
    return value.to_bytes(2,'little')
def commands():
    rows=[('revision',0x30,0,0),('state',0x30,2,0),('persistent_latch',0x30,4,0)]
    rows += [(f'key_valid_{i}',0x30,1,i) for i in range(16)]
    rows += [(f'config_{i*4:03d}',2,0,i) for i in range(32)]
    rows += [(f'counter_{i}',0x24,0,i) for i in range(2)]
    rows += [(f'otp_{i*4:02d}',2,1,i) for i in range(16)]
    result=[]
    for name,op,mode,param in rows:
        data=bytes([7,op,mode,param,0])
        result.append({'name':name,'packet':(data+crc(data)).hex()})
    return result
def main():
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'asm').mkdir(exist_ok=True)
    rows=commands()
    (OUT/'asm/commands.inc').write_text(f'COMMAND_COUNT EQU {len(rows)}\nCOMMANDS\n'+''.join('        DB '+','.join('$'+p['packet'][i:i+2] for i in range(0,14,2))+'\n' for p in rows))
    base.OUT=OUT
    memory,symbols=base.assemble(NAME,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=SOURCE)
    data=base.dense_image(memory,0x2000,symbols['PROBE_END'])
    assert symbols['PROBE_END']<0x6900
    (OUT/(NAME+'.bin')).write_bytes(data)
    (OUT/(NAME+'.s19')).write_text((OUT/'asm'/(NAME+'.s19')).read_text().replace('S9030000FC','S9032000DC'))
    (OUT/'build.json').write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'symbols':symbols,'commands':rows},indent=2)+'\n')
    print(f'{len(data)} bytes, {len(rows)} informational commands')
if __name__=='__main__': main()
