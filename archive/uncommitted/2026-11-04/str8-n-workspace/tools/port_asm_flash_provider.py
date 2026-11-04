"""Reuse the preserved SF/1 parser; replace legacy sector mutation with append.

The provider is private to paired ASM, in RAM7000-77FF. It never erases or
touches B3 and asks for the exact allocation before programming blank bytes.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'

def source():
 s=(REPO/'monitors/devtools/legacy-reference/source-store/flash.inc').read_text()
 s=s.replace('CMP #$1C','CMP #>(SOURCE_END-SOURCE_START+8)')
 a=s.index('NF_EXIT:');b=s.index('NF_READ_HEADER:',a);s=s[:a]+'NF_EXIT:\n RTS\n'+s[b:]
 a=s.index(' STZ PTR\n LDA #2\n STA PTR+1\n JSR NF_SNAPSHOT',s.index('NF_SAVE:'));b=s.index('NF_LOAD:',a)
 s=s[:a]+''' ; Allocation approval is required even when a sector reads all FF.
 LDX #<NF_CONFIRM_TEXT
 LDY #>NF_CONFIRM_TEXT
 JSR PRINT
 LDA NF_START
 JSR $7E7C
 LDA #0
 JSR $7E7C
 LDX #<NF_SPAN_TEXT
 LDY #>NF_SPAN_TEXT
 JSR PRINT
 LDA NF_NEEDED
 JSR $7E7C
 LDX #<NF_YES_TEXT
 LDY #>NF_YES_TEXT
 JSR PRINT
 JSR READ_LINE
 LDA ERROR
 BNE NF_CANCELLED
 LDY #0
NF_CONFIRM:
 LDA LINE,Y
 CMP NS_YES_WORD,Y
 BNE NF_CANCELLED
 INY
 CPY #4
 BCC NF_CONFIRM
 ; Recheck the selected extent after confirmation, before its first write.
 JSR NF_IS_ERASED
 BNE NF_PROGRAM_ERROR
 LDA NF_NEEDED
 CMP #2
 BNE NF_WRITE_BEGIN
 LDA NF_CURRENT
 PHA
 CLC
 ADC #$10
 STA NF_CURRENT
 JSR NF_IS_ERASED
 TAX
 PLA
 STA NF_CURRENT
 TXA
 BNE NF_PROGRAM_ERROR
NF_WRITE_BEGIN:
 STZ V2_FLASH_PTR
 LDA NF_START
 STA V2_FLASH_PTR+1
 LDA #<NF_HEADER
 STA PTR
 LDA #>NF_HEADER
 STA PTR+1
 LDA #32
 STA NF_LEFT
 STZ NF_LEFT+1
 JSR NF_WRITE_BLOCK
 BCC NF_PROGRAM_ERROR
 STZ PTR
 LDA #2
 STA PTR+1
 LDA NF_HEADER+4
 STA NF_LEFT
 LDA NF_HEADER+5
 STA NF_LEFT+1
 JSR NF_WRITE_BLOCK
 BCC NF_PROGRAM_ERROR
 ; Publish only after every header/payload byte has been read back.
 LDA #3
 STA V2_FLASH_PTR
 LDA NF_START
 STA V2_FLASH_PTR+1
 LDA #$3F
 STA V2_FLASH_DATA
 JSR NF_WRITE_BYTE
 BCC NF_PROGRAM_ERROR
 JMP NF_SUCCESS
NF_CANCELLED:
 LDA #$54
 JMP NF_FAILURE
NF_WRITE_BLOCK:
 LDA NF_LEFT
 ORA NF_LEFT+1
 BEQ NF_WRITE_DONE
 LDA (PTR)
 STA V2_FLASH_DATA
 JSR NF_WRITE_BYTE
 BCC NF_WRITE_FAILED
 INC PTR
 BNE NF_WRITE_ADDRESS
 INC PTR+1
NF_WRITE_ADDRESS:
 INC V2_FLASH_PTR
 BNE NF_WRITE_COUNT
 INC V2_FLASH_PTR+1
NF_WRITE_COUNT:
 LDA NF_LEFT
 BNE NF_WRITE_DEC
 DEC NF_LEFT+1
NF_WRITE_DEC:
 DEC NF_LEFT
 BRA NF_WRITE_BLOCK
NF_WRITE_DONE:
 SEC
 RTS
NF_WRITE_FAILED:
 CLC
 RTS
NF_WRITE_BYTE:
 ; RAM-only SST byte worker; raw entry skips the public BRK function prefix.
 ; Strict B0:8000-DFFF bounds, FF preimage and independent readback.
 LDA V2_FLASH_PTR+1
 CMP #$80
 BCC NF_WRITE_FAILED
 CMP #$E0
 BCS NF_WRITE_FAILED
 LDA #0
 JSR $7848
 LDA (V2_FLASH_PTR)
 CMP #$FF
 BNE NF_WRITE_LOCKED
 LDA V2_FLASH_DATA
 CMP #$FF
 BEQ NF_WRITE_VERIFY
 STZ $F6
 JSR $7B64
 BCC NF_WRITE_LOCKED
NF_WRITE_VERIFY:
 LDA (V2_FLASH_PTR)
 CMP V2_FLASH_DATA
 BNE NF_WRITE_LOCKED
 LDA #3
 JSR $7848
 SEC
 RTS
NF_WRITE_LOCKED:
 LDA #3
 JSR $7848
 CLC
 RTS
NF_CONFIRM_TEXT: DB "Append source B0:",0
NF_SPAN_TEXT: DB " sectors ",0
NF_YES_TEXT: DB "; type YES> ",0
'''+s[b:]
 a=s.index('NF_SNAPSHOT:');s=s[:a]+'''NF_READ16:
 LDA #16
 STA V2_COUNT
NF_READ:
 STZ V2_SELECTED
 JSR $7830
 RTS
'''
 return ''' MODULE FLASH_SOURCE_PROVIDER
 INCLUDE "asm-equ.inc"
 INCLUDE "ns-equ.inc"
 INCLUDE "state.inc"
 INCLUDE "flash-bindings.inc"
 CODE
 DB "FS",1,8,"PR05"
 JMP NF_ENTRY
 DW NS_CRC_BYTE,NS_YES_WORD
'''+s+'NF_END:\n ENDMOD\n END\n'

if __name__=='__main__':
 target=REPO/'monitors/devtools/base1/assembler/flash-provider.asm'
 assert not target.exists();target.write_text(source(),encoding='utf-8');print('Created RAM SF/1 append-only source provider; no device access')
