"""Copy the named-constant EDU source into numbered/paste companions."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'examples/source-cycle/edu-led31-loop.asm'
    text=source.read_text();equ={}
    for line in text.splitlines():
        m=re.fullmatch(r'(\w+) EQU (\$[0-9A-F]+)',line)
        if m:equ[m[1]]=m[2]
    result=[]
    for line in text.splitlines():
        if re.fullmatch(r'(\w+) EQU (\$[0-9A-F]+)',line):result.append('; '+line);continue
        if not line.lstrip().startswith(';'):
            for name,value in equ.items():line=re.sub(r'\b'+name+r'\b',lambda m:value,line)
        result.append(line)
    source.with_name('edu-led31-loop-onboard.asm').write_text('\n'.join(result)+'\n')
    source.with_suffix('.numbered.txt').write_text(''.join(f'{10*(i+1)} {s}\n' for i,s in enumerate(result)))
    source.with_suffix('.paste.txt').write_text('PASTE\n'+'\n'.join(result)+'\n.\n')
    print('Expanded',len(equ),'constants;',len(result),'onboard source lines')


if __name__=='__main__':main()
