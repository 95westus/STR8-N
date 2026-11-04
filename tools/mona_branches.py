"""Conservative file-local branch sizing for Mona; no target execution.

Unknown memory operands cost three bytes. INCLUDE boundaries prevent branch
relaxation across code whose size is not known within this file.
"""
import re

INVERSE = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
               BMI='BPL', BPL='BMI', BVC='BVS', BVS='BVC')
SINGLE = set('RTS RTI SEI CLI CLD SED CLC SEC CLV TAX TAY TXA TYA TXS TSX '
             'PHA PLA PHX PLX PHY PLY PHP PLP INX INY DEX DEY NOP'.split())
MEMORY = set('LDA LDX LDY STA STX STY STZ CMP CPX CPY ADC SBC AND ORA EOR '
             'BIT INC DEC ASL LSR ROL ROR TRB TSB'.split())

def code_part(line):
    quote = None
    for index, char in enumerate(line):
        if char in ('"', "'"):
            if quote == char: quote = None
            elif quote is None: quote = char
        elif char == ';' and quote is None:
            return line[:index]
    return line

def conservative_branches(source, prefix):
    rows = source.splitlines();parsed = [];block = 0
    for line in rows:
        text = code_part(line).strip();label = None
        match = re.match(r'^(\w+):\s*', text)
        if match:
            label = match[1]; text = text[match.end():]
        parts = text.split(None, 1)
        op = parts[0].upper() if parts else ''
        arg = parts[1].strip() if len(parts)>1 else ''
        target = arg if op in INVERSE or op == 'BRA' else None
        if target and not re.fullmatch(r'\w+', target):
            raise ValueError('Unsupported branch expression: '+line)
        if target:
            size = 3 if op == 'BRA' else 5
        elif not op or op in ('MODULE','ENDMOD','CODE','END','INCLUDE') or re.match(r'^\w+\s+EQU\b',text):
            size = 0
        elif op in ('DB','DW'):
            tokens = re.findall(r'"[^"]*"|\x27[^\x27]*\x27|[^,]+',arg)
            size = sum(len(t.strip()[1:-1]) if t.strip().startswith(('"',"'")) else 1 for t in tokens)
            if op == 'DW': size *= 2
        elif op == 'DS':
            size = int(arg[1:],16) if arg.startswith('$') else int(arg)
        elif op in SINGLE:
            size = 1
        elif op in ('JSR','JMP'):
            size = 3
        elif op in MEMORY:
            size = 1 if not arg or arg=='A' else 2 if arg.startswith(('#','(')) else 3
        else:
            raise ValueError('Unknown assembler row; cannot size safely: '+line)
        parsed.append(dict(label=label,op=op,target=target,size=size,block=block,short=False))
        if op == 'INCLUDE': block += 1
    while True:
        labels = {};offset = 0
        for item in parsed:
            item['offset'] = offset
            if item['label']: labels[item['label']] = (item['block'],offset)
            offset += 2 if item['short'] else item['size']
        changed = False
        for item in parsed:
            if item['target'] in labels and not item['short']:
                target_block,target_offset = labels[item['target']]
                distance = target_offset-item['offset']-2
                if target_block==item['block'] and -128<=distance<=127:
                    item['short']=True;changed=True
        if not changed: break
    result = [];expanded = 0;shortened = 0
    for line,item in zip(rows,parsed):
        if not item['target'] or item['short']:
            result.append(line);shortened += bool(item['target'])
        elif item['op']=='BRA':
            if item['label']: result.append(item['label']+':')
            result.append('        JMP '+item['target']);expanded+=1
        else:
            expanded+=1;skip=prefix+str(expanded)
            if item['label']: result.append(item['label']+':')
            result.extend(('        '+INVERSE[item['op']]+' '+skip,
                           '        JMP '+item['target'],skip+':'))
    return '\n'.join(result)+'\n',dict(short_branches=shortened,expanded_branches=expanded,
        conservative_bytes=offset)
