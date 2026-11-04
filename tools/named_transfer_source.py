"""Adapt preserved named-copy algorithms to a separate bounded BASE1 provider."""
import re


def short_branches(text):
    inverse={'BCC':'BCS','BCS':'BCC','BEQ':'BNE','BNE':'BEQ','BMI':'BPL','BPL':'BMI','BVC':'BVS','BVS':'BVC'}
    pattern=r'^([ \t]*)(B(?:CC|CS|EQ|NE|MI|PL|VC|VS))\s+(MM_\w*LONG_\w+)\s*\n[ \t]*JMP\s+(\w+)\s*\n\3:\s*\n'
    return re.sub(pattern,lambda m:m[1]+inverse[m[2]]+' '+m[4]+'\n',text,flags=re.M)


def bank_source(reference):
    text=reference[reference.index('MM_X_REQ EQU'):reference.index('MM_X_FAIL_MESSAGE DB')]
    text+='MM_X_FAIL_MESSAGE DB "Copy failed; source retained; destination may be pending.",13,10,0\n'
    text=short_branches(text)
    a,b=text.index('MM_X_DISCOVER:'),text.index('        LDA MM_X_DIRECTION\n',text.index('MM_X_DISCOVER:'))
    text=text[:a]+'''MM_X_DISCOVER:
        JSR SM_INIT
        BCC MM_X_FAIL
'''+text[b:]
    text=text.replace('MM_X_FROM_SRAM:\n        LDA MM_X_BANK\n        BNE MS_COPY_ALLOWED\n        JMP MM_X_BAD',
        'MM_X_FROM_SRAM:\n        LDA MM_X_BANK\n        CMP #2\n        BCC MS_COPY_ALLOWED\n        JMP MM_X_BAD')
    text=text.replace('JSR X28_C1','JSR MB_X_ALLOC')
    text=text.replace('CMP #$65','CMP #$67')
    text=text.replace('STA $6400,X','STA $5000,X').replace('LDA $6400,X','LDA $5000,X')
    text=text.replace('LDA #$64\n        STA SM_D_BP+1','LDA #$50\n        STA SM_D_BP+1')
    text=text.replace('LDA #<MM_X_RESTORE_CHUNK','LDA #$09').replace('LDA #>MM_X_RESTORE_CHUNK','LDA #$20')
    # P is the current PROGRAM spelling; retain S for the reference command.
    text=text.replace("CMP #'S'", "CMP #'P'\n        BEQ MM_X_SRAM_SPACE\n        CMP #'S'")
    # Insert the label at the reference's admitted SRAM space return.
    text=text.replace('        LDA #$FF\n', 'MM_X_SRAM_SPACE:\n        LDA #$FF\n',1)
    # Raw READ uses the exact frozen RAM worker; no old E jump addresses.
    text+='''
X28_C8:
        JMP V2W_READ
SM_INIT:
        STZ MM_BLEN
        STZ MM_BLEN+1 ; X borrows the editor buffer; no stale editor commit
        JMP MB_LOAD_XP
'''
    return text


def provider_source(source):
    text=source.replace('MODULE PROGRAM_PROVIDER','MODULE NAMED_PROGRAM').replace('DB "SP",1,13,"PR05"','DB "XP",1,13,"PR05"')
    # Only the already-proven mount/allocation/CRC/publication engine is shared.
    # This private component has no arbitrary RAM restore/run or public SP use.
    a,b=text.index('        LDA SP_TAIL\n'),text.index('SP_API_RESULT:')
    text=text[:a]+text[b:]
    text=text.replace('CMP #10','CMP #6')
    text=text.replace('        CMP #8\n        BCS SAVE\n','')
    text=text.replace('        JSR SP_CLIENT_RANGE\n        BNE SAVE_RETURN\n','')
    text=text.replace('        LDA (PTR),Y\n        JSR CRC_BYTE','        JSR $2003\n        JSR CRC_BYTE',1)
    text=text.replace('SAVE_WRITE_LOOP:\n        JSR CHUNK\n        LDA #2\n        JSR TRANSFER',
                      'SAVE_WRITE_LOOP:\n        JSR CHUNK\n        JSR $2006')
    a,b=text.index('RESTORE:\n'),text.index('CRC_INIT:\n')
    text=text[:a]+'''RESTORE:
        ; op2 inspects after the complete payload CRC. The admitted MAINT
        ; callback vector2009 opts into streaming; no RAM image is loaded.
        LDA $67F5
        CMP #$09
        BNE XP_INSPECT
        LDA $67F6
        CMP #$20
        BNE XP_INSPECT
        JSR LOAD_RECORD
        JSR RANGE_CHECK
        BNE FINISH
        LDA LOAD
        STA BP
        LDA LOAD+1
        STA BP+1
        JSR SET_LEFT
        JSR CRC_INIT
XP_RESTORE_LOOP:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS XP_CANCELED
        JSR CHUNK
        JSR $2009
        BNE FINISH
        LDY #0
XP_RESTORE_CRC:
        LDA $5000,Y
        JSR CRC_BYTE
        INY
        CPY COUNT
        BNE XP_RESTORE_CRC
        JSR ADVANCE
        BNE XP_RESTORE_LOOP
        LDY #12
        LDA (REC),Y
        CMP CRC
        BNE CRC_BAD
        INY
        LDA (REC),Y
        CMP CRC+1
        BNE CRC_BAD
        LDA #0
        RTS
XP_INSPECT:
        LDA #$46
        RTS
XP_CANCELED:
        LDA #$43
        RTS
'''+text[b:]
    # Wide monitor returns and registration are not used by this private copy API.
    a,b=text.index('SP_CLIENT_RANGE:\n'),text.index('        INCLUDE "program-layout-check.inc"')
    text=text[:a]+text[b:]
    # Request fields cannot select wide/run operation codes in this component.
    text=text.replace('        LDA REQUEST\n        CMP #4\n        BEQ SP_FOUND_ONLY\n','')
    return text
