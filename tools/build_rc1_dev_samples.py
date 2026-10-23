"""Generate small, pasteable ASM 0.5 source documents, no hardware access."""
import json
from pathlib import Path
from name_rc1_demo_constants import name_constants

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'examples/source-cycle'

CS = [
    ('forward chase', [1, 2, 4, 8, 1, 2, 4, 8]),
    ('reverse chase', [8, 4, 2, 1, 8, 4, 2, 1]),
    ('bounce', [1, 2, 4, 8, 4, 2, 1, 0]),
    ('alternating pairs', [5, 10, 5, 10, 5, 10, 5, 10]),
    ('fill and drain', [1, 3, 7, 15, 7, 3, 1, 0]),
    ('outside and inside', [9, 6, 9, 6, 9, 6, 9, 6]),
    ('all blink', [15, 0, 15, 0, 15, 0, 15, 0]),
    ('adjacent pairs', [3, 6, 12, 9, 3, 6, 12, 9]),
]
EDU = [
    ('walking one', [1,2,4,8,16,32,64,128]),
    ('walking zero', [254,253,251,247,239,223,191,127]),
    ('reverse one', [128,64,32,16,8,4,2,1]),
    ('reverse zero', [127,191,223,239,247,251,253,254]),
    ('wigwag', [240,15]*4),
    ('checkerboard', [170,85]*4),
    ('all blink', [255,0]*4),
    ('fill left', [1,3,7,15,31,63,127,255]),
    ('drain left', [255,127,63,31,15,7,3,1]),
    ('fill right', [128,192,224,240,248,252,254,255]),
    ('drain right', [255,254,252,248,240,224,192,128]),
    ('expand pairs', [24,60,126,255,126,60,24,0]),
    ('contract pairs', [129,195,231,255,231,195,129,0]),
    ('two dot chase', [3,6,12,24,48,96,192,129]),
    ('three dot chase', [7,14,28,56,112,224,193,131]),
    ('four dot chase', [15,30,60,120,240,225,195,135]),
    ('split chase', [17,34,68,136,17,34,68,136]),
    ('outer bounce', [129,66,36,24,36,66,129,0]),
    ('gray ramp', [0,1,3,2,6,7,5,4]),
    ('binary ramp', [0,1,2,3,4,5,6,7]),
    ('mirrored binary', [0,129,66,195,36,165,102,231]),
    ('alternating fill', [1,5,21,85,87,95,127,255]),
    ('alternating drain', [255,127,95,87,85,21,5,1]),
    ('paired blink', [51,204]*4),
    ('nibble count', [0,17,34,51,68,85,102,119]),
    ('center pulse', [24,24,0,24,0,0,24,0]),
    ('edge pulse', [129,129,0,129,0,0,129,0]),
    ('comet', [1,3,7,14,28,56,112,224]),
    ('reverse comet', [128,192,224,112,56,28,14,7]),
    ('sparkle', [18,9,188,94,47,175,239,207]),
    ('crossfade halves', [240,225,195,135,15,30,60,120]),
]


def source(edu):
    patterns = EDU if edu else CS
    lines = ['; ASM 0.5 source document; paste unnumbered lines with PASTE.',
             '; IRQ masked, decimal clear; 816 E=1, D/DBR/PBR=0.',
             '; BRK 01 ready; BRK 02 complete; C continues; Ctrl-C cleans up.',
             'ORG $0200', 'SEI', 'CLD',
             '; Validate initialized RAM ABI before calling any entry.',
             'LDX #$03', 'abi: LDA $7E60,X', 'CMP signature,X',
             'BNE bad', 'DEX', 'BPL abi', 'JMP start',
             'bad: JMP bad', 'signature: BYTE $52,$41,$01,$0D',
             'start: STZ frame']
    if edu:
        lines += ['; Current rc1 discovery descriptor, not a public LED ABI.',
                  'LDA $7D04', "CMP #'S'", 'BNE absent',
                  'LDA $7D05', "CMP #'V'", 'BNE absent',
                  'LDA $7D06', 'CMP #$01', 'BNE absent',
                  'LDA $7D0C', 'BEQ absent',
                  '; Do not select DDR or rewrite CRA/DDRA.',
                  'LDA $7FA1', 'AND #$04', 'BEQ absent',
                  'LDA $7FA0', 'STA entry', 'BRA ready',
                  "absent: LDA #'E'", 'JSR $7E6D', 'JSR $7E7F', 'JMP $7E67']
    lines += ['ready: BRK $01', 'NOP', 'next: JSR $7E76', 'BCS finish',
              'LDA frame', 'AND #$07', 'BNE show',
              '; Print one-based pattern number in hexadecimal.',
              'LDA frame', 'LSR A', 'LSR A', 'LSR A', 'INC A',
              'JSR $7E7C', 'JSR $7E7F',
              'show: LDX frame', 'LDA patterns,X']
    if edu:
        lines += ['STA $7FA0', 'JSR delay']
    else:
        lines += ['STA mask', 'JSR burst']
    lines += ['INC frame', 'LDA frame', f'CMP #${len(patterns)*8:02X}',
              'BNE next', 'finish: NOP']
    if edu: lines += ['LDA entry', 'STA $7FA0']
    lines += ['done: BRK $02', 'JMP $7E67']
    if edu:
        lines += ['; Edit this immediate to change the frame dwell.',
                  'delay: LDX #$FF', 'outer: LDY #$00',
                  'inner: DEY', 'BNE inner', 'DEX', 'BNE outer', 'RTS']
    else:
        lines += ['; Reads assert CS. No writes to these four windows.',
                  '; Owner confirms no hardware attached to CS0-CS3 windows.',
                  'burst: LDX #$40', 'batch: LDY #$00',
                  'pulse: LDA mask', 'AND #$01', 'BEQ skip0', 'LDA $7F00',
                  'skip0: LDA mask', 'AND #$02', 'BEQ skip1', 'LDA $7F20',
                  'skip1: LDA mask', 'AND #$04', 'BEQ skip2', 'LDA $7F40',
                  'skip2: LDA mask', 'AND #$08', 'BEQ skip3', 'LDA $7F60',
                  'skip3: DEY', 'BNE pulse', 'DEX', 'BNE batch', 'RTS']
    lines += ['patterns:']
    for i, (name, frames) in enumerate(patterns, 1):
        lines += [f'; {i:02d}: {name}', 'BYTE '+','.join(f'${v:02X}' for v in frames)]
    lines += ['frame: BYTE $00', 'entry: BYTE $00' if edu else 'mask: BYTE $00', 'END']
    return name_constants(lines,edu)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, edu in (('sxb-cs-patterns', False), ('edu-led31', True)):
        lines = source(edu)
        assert max(map(len, lines)) <= 120
        packed_bytes = sum(len(line)+4 for line in lines)
        assert packed_bytes <= 7168
        (DEST/(name+'.asm')).write_text('\n'.join(lines)+'\n')
        (DEST/(name+'.numbered.txt')).write_text(''.join(f'{(i+1)*10} {line}\n' for i,line in enumerate(lines)))
        (DEST/(name+'.paste.txt')).write_text('PASTE\n'+'\n'.join(lines)+'\n.\n')
        manifest[name] = dict(patterns=[dict(name=n, frames=v) for n,v in (EDU if edu else CS)],
            pattern_count=31 if edu else 8, frame_count=248 if edu else 64,
            source_lines=len(lines), packed_source_bytes=packed_bytes)
    (DEST/'patterns.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in m.items() if k != 'patterns'} for n,m in manifest.items()}, indent=2))


if __name__ == '__main__': main()
