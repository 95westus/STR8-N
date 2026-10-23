"""Name every demo literal at the top, without changing emitted bytes."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def name_constants(lines,edu):
    # Idempotent: retain existing definitions and name only remaining literals.
    defs=[];body=[]
    for line in lines:
        if line=='; Named constants: edit these definitions; ASM accepts name = expression.':continue
        if re.fullmatch(r'\w+\s*=\s*.+',line):defs.append(line)
        else:body.append(line)
    known={line.split('=')[0].strip() for line in defs}
    def define(name,value):
        if name not in known:defs.append(f'{name} = {value}');known.add(name)
        return name
    addresses={0x0200:'APP_ORG',0x7E60:'ABI_DESC',0x7E67:'ABI_HOLD',
        0x7E6D:'ABI_PUTC',0x7E76:'ABI_CANCEL',0x7E7C:'ABI_HEX',0x7E7F:'ABI_NEWLINE',
        0x7D04:'EDU_SIG0',0x7D05:'EDU_SIG1',0x7D06:'EDU_FORMAT',0x7D0C:'EDU_PRESENT',
        0x7FA0:'LED_DATA',0x7FA1:'LED_CRA',0x7F00:'CS0',0x7F20:'CS1',0x7F40:'CS2',0x7F60:'CS3'}
    result=[]
    for line in body:
        code,sep,comment=line.partition(';')
        if code.strip():
            def replace(m):
                value=int(m[0][1:],16)
                if value in addresses:return define(addresses[value],m[0])
                name=None
                for needle,label in [('LDX #$03','ABI_LAST'),('AND #$07','FRAME_MASK'),
                    ('AND #$04','CRA_DATA_BIT'),('BRK $01','STOP_READY'),('BRK $02','STOP_DONE'),
                    ('delay: LDX #$FF','DWELL_OUTER'),('dwell: LDX #$FF','DWELL_OUTER'),
                    ('LDY #$00','LOOP_WRAP'),('burst: LDX #$40','BURST_BATCHES')]:
                    if needle in code:name=label;break
                if 'CMP #' in code and value==(0xF8 if edu else 0x40):name='FRAME_COUNT'
                if 'CMP #$01' in code:name='DISC_VERSION'
                if not name:name=f'B{value:02X}'
                return define(name,m[0])
            code=re.sub(r'\$[0-9A-Fa-f]+\b',replace,code)
            for char,name in [('S','DISC_S'),('V','DISC_V'),('E','NO_EDU_CHAR')]:
                if "'"+char+"'" in code:code=code.replace("'"+char+"'",define(name,"'"+char+"'"))
        result.append(code+(sep+comment if sep else ''))
    return ['; Named constants: edit these definitions; ASM accepts name = expression.']+defs+result

def main():
    folder=ROOT/'examples/source-cycle'
    for stem in ('sxb-cs-patterns','edu-led31','sxb-cs-patterns-loop','edu-led31-loop'):
        p=folder/(stem+'.asm');lines=name_constants(p.read_text().splitlines(),'edu' in stem)
        p.write_text('\n'.join(lines)+'\n')
        p.with_suffix('.numbered.txt').write_text(''.join(f'{10*(i+1)} {s}\n' for i,s in enumerate(lines)))
        p.with_suffix('.paste.txt').write_text('PASTE\n'+'\n'.join(lines)+'\n.\n')
        print(stem,len(lines),'lines',sum(len(s)+4 for s in lines),'packed bytes')
    (folder/'edu-led31-loop-onboard.asm').write_bytes((folder/'edu-led31-loop.asm').read_bytes())

if __name__=='__main__':main()
