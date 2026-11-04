"""Create a separate BASE1 RAM assembler port; preserve all legacy sources."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
OUT=REPO/'monitors/devtools/base1/assembler';REF=REPO/'monitors/devtools/legacy-reference'
sys.path.insert(0,str(REPO/'tools'));from build_mona import sha

def run():
 OUT.mkdir(parents=True,exist_ok=False)
 asm=(REF/'assembler/asm-app.asm').read_text();layout=(REF/'assembler/layout.inc').read_text()
 for name,a,b in [('OUTPUT_END',0x3300,0x2000),('SOURCE_START',0x3300,0x2000),('SOURCE_END',0x4f00,0x3800),('SYMBOL_START',0x4f00,0x3800),('SYMBOL_END',0x6300,0x4000),('STATE_END',0x6500,0x6700)]:
  layout,n=re.subn(rf'^{name} EQU \$[0-9A-F]+',f'{name} EQU ${b:04X}',layout,flags=re.M);assert n==1,name
 def move_state(s):return re.sub(r'\$(6[34][0-9A-Fa-f]{2})\b',lambda m:f'${int(m[1],16)+0x200:04X}',s)
 layout=move_state(layout);asm=move_state(asm)
 # SYMBOL_END is4000 and must not be relocated by the state transform.
 asm=asm.replace('STR8-N ASM 0.5 / 65C02','STR8-N ASM 0.6-dev g1 / BASE1 PR05 RAM')
 asm,n=re.subn(r'(PRINT_LOOP:.*?\n JSR PUTC\n INY\n)\s+JMP PRINT_LOOP',r'\1 BNE PRINT_LOOP\n INC TEMP+1\n JMP PRINT_LOOP',asm,count=1,flags=re.S);assert n==1
 asm=asm.replace('NEW PASTE LIST ASM LST SYMS S19 ? ','NEW PASTE LIST ASM LST SYMS DUMP S19 QUIT ? ')
 asm=asm.replace('HELP: DB "number text:', 'HELP: DB "SAVE/LOAD SRAM name; FLASH not linked in RAM1",$0D,$0A\n DB "number text:')
 (OUT/'asm-app.asm').write_text(asm,encoding='utf-8');(OUT/'layout.inc').write_text(layout,encoding='utf-8')
 (OUT/'source-equ.inc').write_text('NS_INIT EQU $5D08\nNS_EDIT EQU $5D12\nNS_DISPATCH EQU $5D1B\n')
 source=(REF/'source-store/source.asm').read_text()
 source=source.replace(' INCLUDE "storage-equ.inc"\n','').replace(' INCLUDE "worker-equ.inc"\n','')
 start=source.index('NS_CALL_STORAGE:');end=source.index('NS_HEADER:',start)
 adapter='''; The PROGRAM provider remains in6B00-77FF while ASM is active.
; Explicit source operations only. The RAM1 flash adapter refuses, no writes.
NS_CALL_STORAGE:
 LDA NS_PROVIDER
 BEQ NS_P_PROGRAM
 LDA #$81
 CLC
 RTS
NS_P_PROGRAM:
 LDX #7
NS_P_HEADER:
 LDA $6B00,X
 CMP NS_P_ID,X
 BNE NS_P_ABSENT
 DEX
 BPL NS_P_HEADER
 LDA NS_OPERATION
 CMP #2
 BNE NS_P_CALL
 ; Lookup before restore. Reject executable or out-of-capsule records before
 ; the provider can copy them over source, symbols or resident code.
 LDA #4
 STA NS_REQUEST
 JSR NS_P_API
 BCC NS_P_RETURN
 LDY #4
 LDA ($E6),Y
 BNE NS_P_BAD
 INY
 LDA ($E6),Y
 CMP #2
 BNE NS_P_BAD
 INY
 LDA ($E6),Y
 STA NS_STORED_LENGTH
 INY
 LDA ($E6),Y
 STA NS_STORED_LENGTH+1
 CMP #>(SOURCE_END-SOURCE_START+9)
 BCC NS_P_MIN
 BNE NS_P_BAD
 LDA NS_STORED_LENGTH
 CMP #<(SOURCE_END-SOURCE_START+9)
 BCS NS_P_BAD
NS_P_MIN:
 LDA NS_STORED_LENGTH+1
 BNE NS_P_ENTRY
 LDA NS_STORED_LENGTH
 CMP #8
 BCC NS_P_BAD
NS_P_ENTRY:
 LDY #8
 LDA ($E6),Y
 INY
 ORA ($E6),Y
 BNE NS_P_BAD
 LDA #2
 STA NS_REQUEST
NS_P_CALL:
 JSR NS_P_API
NS_P_RETURN:
 RTS
NS_P_API:
 LDA #<NS_REQUEST
 LDX #>NS_REQUEST
 JSR $6B15
 RTS
NS_P_BAD:
 LDA #$44
 CLC
 RTS
NS_P_ABSENT:
 LDA #$80
 CLC
 RTS
NS_P_ID: DB "SP",1,13,"PR05"
'''
 source=source[:start]+adapter+source[end:];source=source.replace(' INCLUDE "flash.inc"\n','')
 source=source.replace('NS_SHELL:\n PLA\n PLA\n JMP SHELL','NS_SHELL:\n PLA\n PLA\n PLA\n PLA\n JMP SHELL',1)
 (OUT/'source.asm').write_text(source,encoding='utf-8');(OUT/'state.inc').write_text(move_state((REF/'source-store/state.inc').read_text()))
 (OUT/'provenance.json').write_text(json.dumps(dict(reference={str(p.relative_to(REF)):sha(p.read_bytes()) for p in (REF/'assembler').glob('*')},source_reference=sha((REF/'source-store/source.asm').read_bytes()),foundation_changed=False,status='PORT_SOURCE_NOT_LIVE'),indent=2))
 print('Created separate BASE1 ASM RAM1 sources; legacy untouched')

if __name__=='__main__':run()
