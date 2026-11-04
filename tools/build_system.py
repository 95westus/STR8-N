"""Shared assembly branch expansion; the old full-system builder is retired.

BASE1's canonical builder reuses the frozen F and independent migration code.
"""
import re

def long_branches(text, prefix='P_LONG_'):
    inverse = dict(BEQ='BNE', BNE='BEQ', BCC='BCS', BCS='BCC',
                   BMI='BPL', BPL='BMI', BVC='BVS', BVS='BVC')
    rows, number = [], 0
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS|BRA)\s+(\w+)\s*', line)
        if not match:
            rows.append(line)
        elif match[1] == 'BRA':
            rows.append('        JMP ' + match[2])
        else:
            number += 1
            skip = prefix + str(number)
            rows.extend(('        ' + inverse[match[1]] + ' ' + skip,
                         '        JMP ' + match[2], skip + ':'))
    return '\n'.join(rows) + '\n'



def build(*args, **kwargs):
    raise ValueError('Use tools/build_base1.py; full-system/reference images are outside BASE1')


if __name__=='__main__':
    raise SystemExit('Use tools/build_base1.py; no alternate F rebuild path is supplied')
