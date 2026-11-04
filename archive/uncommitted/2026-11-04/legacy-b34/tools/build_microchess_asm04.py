"""Prepare attributed Microchess sources for the existing ASM 0.4, offline."""
from pathlib import Path
import collections
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'examples/beta33/microchess'
OUT=ROOT/'BUILD/microchess-asm04'


def outside(text,fn):
    return ''.join(s if i%2 else fn(s) for i,s in enumerate(re.split(r'''("[^"]*"|'[^']*')''',text)))


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'qualification.json').unlink(missing_ok=True)
    raw=(SRC/'Microchess6502-upstream.txt').read_text()
    notice=raw[:raw.index('; modified by Daryl')].rstrip('; \n\r')+'\n'
    (SRC/'LICENSE.txt').write_text(notice,encoding='ascii')
    lines=[]
    for original in raw.splitlines():
        line=original.split(';')[0].rstrip()
        if not line.strip():continue
        if re.match(r'\s*(cpu|page)\b',line,re.I):continue
        if line.lstrip().startswith('*='):
            if '$1000' in line:lines.append('ORG $0200')
            continue
        if '=' in line:
            name,value=map(str.strip,line.split('=',1))
            if name.upper().startswith('ACIA'):continue
            n=int(value[1:],16)
            if name=='BOARD':n=0x10
            elif name=='BK':n=0x20
            elif n>=0xDC:n-=0x7C
            lines.append(f'{name.upper()} = ${n:02X}')
            continue
        label=''
        if not line[0].isspace():
            match=re.match(r'(\w+)\s*(.*)',line);label=match[1].upper();line=match[2]
        line=line.strip()
        if line:
            op,*tail=line.split(None,1);op=op.upper()
            op={'DB':'BYTE','ASC':'TEXT'}.get(op,op)
            operand=outside(tail[0],str.upper) if tail else ''
            operand=re.sub(r'#"(.)"',lambda m:"#'"+m[1]+"'",operand)
            if op in ('LSR','ASL','ROL','ROR') and not operand:operand='A'
            line=op+(' '+operand if operand else '')
        lines.append((label+': ' if label else '')+line)
    text='\n'.join(lines)+'\n'
    text=text.replace('LDA #$00\nSTA REV\nJSR INIT_6551',
        'SEI\nCLD\nLDA #$00\nSTA REV\nLDX #$1F\nINITIAL: LDA SETW,X\nSTA BOARD,X\nDEX\nBPL INITIAL\nLDX #$1B\nSTX OMOVE\nLDA #$CC\nSTA DIS1\nSTA DIS2\nSTA DIS3')
    text=text.replace('JMP $FF00','JMP $7E67')
    # Absolute references to the original ZP display fields must move too.
    text=text.replace('LDA $FB','LDA DIS1').replace('LDA $FA','LDA DIS2').replace('LDA $F9','LDA DIS3')
    start=text.index('INIT_6551:');end=text.index('SYSHEXOUT:')
    text=text[:start]+'''SYSKIN: PHX
PHY
JSR $7E70
PLY
PLX
CMP #3
BEQ DONE
CMP #27
BEQ DONE
CMP #$61
BCC KEYRETURN
CMP #$7B
BCS KEYRETURN
AND #$DF
KEYRETURN: RTS
SYSCHOUT: PHA
PHP
PHX
PHY
JSR $7E6D
PLY
PLX
PLP
PLA
RTS
'''+text[end:]
    text=text.replace('"MicroChess (c) 1996-2005 Peter Jennings, www.benlo.com"',
        '"Microchess Copyright 1976 Peter Jennings benlo.com"')
    # Distant exit branches need explicit long forms on the 6502.
    text=text.replace('BEQ DONE','BNE *+5\nJMP DONE')
    header='; Microchess Copyright 1976 Peter Jennings benlo.com\n; License and port credits: LICENSE.txt / README.md\n'
    (SRC/'microchess-readable.asm').write_text(header+text,encoding='ascii')
    # Inline infrequent constants: their declaration otherwise costs more
    # source-buffer space than the extra literal characters at each use.
    constants=dict(re.findall(r'^([A-Z_][A-Z_0-9]*) = (\$[0-9A-F]+)$',text,re.M))
    for name,value in constants.items():
        uses=len(re.findall(r'(?<![$\w])'+name+r'\b',text))-1
        if uses<=3:
            text=re.sub(r'^'+name+r' = '+re.escape(value)+r'\n','',text,flags=re.M)
            text=outside(text,lambda s:re.sub(r'(?<![$\w])'+name+r'\b',value,s))
    names=re.findall(r'^([A-Z_][A-Z_0-9]*)\s*(?:=|:)',text,re.M)
    assert len(names)==len(set(names))
    frequency=collections.Counter(re.findall(r'\b[A-Z_][A-Z_0-9]*\b',outside(text,lambda s:s)))
    ranked=sorted(names,key=lambda n:(-frequency[n],n))
    available=list('BCDEFGHIJKLMNOPQRSTUVWZ')+[a+b for a in 'BCDEFGHIJKLMNOPQRSTUVWZ' for b in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    mapping=dict(zip(ranked,available))
    def compact(line):
        line=outside(line,lambda s:re.sub(r'(?<![$\w])[A-Z_][A-Z_0-9]*\b',lambda m:mapping.get(m[0],m[0]),s))
        if '=' in line:return line.replace(' ','')
        label=''
        if ':' in line:label,line=line.split(':',1);label+=':'
        op,*tail=line.strip().split(None,1)
        return label+op+(' '+outside(tail[0],lambda s:s.replace(' ','').replace('\t','')) if tail else '')
    compact_lines=[outside(compact(l),lambda s:re.sub(r'\$0([0-9A-F])\b',r'$\1',s)) for l in text.splitlines()]
    packed=sum(len(l)+4 for l in compact_lines)
    # Keep a short attribution in the board's source, full notices alongside.
    compact_lines.insert(0,'; Copyright 1976 Peter Jennings benlo.com; see LICENSE.txt')
    packed=sum(len(l)+4 for l in compact_lines)
    (SRC/'microchess.asm').write_text('\n'.join(compact_lines)+'\n',encoding='ascii')
    (SRC/'symbols.json').write_text(json.dumps(mapping,indent=2)+'\n')
    OUT.mkdir(parents=True,exist_ok=True)
    info=dict(upstream_url='https://benlo.com/files/Microchess6502.txt',
        upstream_sha256=hashlib.sha256((SRC/'Microchess6502-upstream.txt').read_bytes()).hexdigest(),
        source_lines=len(compact_lines),packed_source_bytes=packed,source_capacity=7168,symbols=len(names),
        origin=0x200,physical_output=0x200,board=0x10,board_sentinel=0x0F,
        zero_page_ranges=[[0x0F,0x2F],[0x60,0x80],[0xB0,0xB7]],
        public_calls=dict(putc=0x7E6D,getc=0x7E70,hold=0x7E67),physical_hardware_tested=False)
    (OUT/'preparation.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info,indent=2))
    assert packed<=7168,'Compact source does not fit the unmodified ASM 0.4'
    return info


if __name__=='__main__':prepare()
