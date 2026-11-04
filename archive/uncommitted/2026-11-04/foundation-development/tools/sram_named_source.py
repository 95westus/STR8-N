"""Named-copy extension using the SRAM manager's existing trusted hooks."""
from named_transfer_source import short_branches


def extension(reference):
    text=reference[reference.index('MM_X_REQ EQU'):reference.index('MM_X_FAIL_MESSAGE DB')]
    text+='MM_X_FAIL_MESSAGE DB "Copy failed; source retained; dest pending.",13,10,0\n'
    text=short_branches(text)
    a,b=text.index('MM_X_DISCOVER:'),text.index('        JSR SM_INIT',text.index('MM_X_DISCOVER:'))
    text=text[:a]+'MM_X_DISCOVER:\n'+text[b:]
    text=text.replace('MM_X_FROM_SRAM:\n        LDA MM_X_BANK\n        BNE MS_COPY_ALLOWED\n        JMP MM_X_BAD',
        'MM_X_FROM_SRAM:\n        LDA MM_X_BANK\n        CMP #2\n        BCC MS_COPY_ALLOWED\n        JMP MM_X_BAD')
    text=text.replace('JSR X28_C1','JSR MB_X_ALLOC').replace('CMP #$65','CMP #$67')
    text=text.replace("CMP #'S'", "CMP #'P'\n        BEQ MM_X_SRAM_SPACE\n        CMP #'S'")
    text=text.replace('        LDA #$FF\n','MM_X_SRAM_SPACE:\n        LDA #$FF\n',1)
    text=text.replace('MM_X_COPY:\n','MM_X_COPY:\n        LDA $7FA0\n        STA MX_OLD_LED\n        LDA SW_UNLOCKED\n        STA MX_OLD_UNLOCK\n        LDA #3\n        STA MM_RESIDENT\n')
    text=text.replace('MM_X_UNHOOK:\n','MM_X_UNHOOK:\n        LDA MX_OLD_LED\n        STA $7FA0\n        LDA MX_OLD_UNLOCK\n        STA SW_UNLOCKED\n')
    text=text.replace('MM_X_EXEC_MAGIC DB "ED",1,3\n','')
    text=text.replace('MM_X_API:\n        LDA #<MM_X_REQ\n        LDX #>MM_X_REQ\n        JMP SM_C_API',
        '''MM_X_API:
        LDA #$A5
        STA MX_API_ACTIVE
        LDA #<MM_X_REQ
        LDX #>MM_X_REQ
        JSR SM_C_API
        PHP
        PHA
        STZ MX_API_ACTIVE
        PLA
        PLP
        RTS''')
    # One live Y authorizes only this copy, never general SRAM administration.
    text=text.replace('MM_X_CONFIRM:\n','MM_X_CONFIRM:\n')
    marker="        LDA MM_BM_LINE+1\n"
    # The confirm tail is patched separately below, not other name comparisons.
    a,b=text.index('MM_X_CONFIRM:'),text.index('MM_X_SPACE:')
    confirm=text[a:b].replace('        SEC\n        RTS','        LDA #1\n        STA SW_UNLOCKED\n        SEC\n        RTS',1)
    text=text[:a]+confirm+text[b:]
    return text


SUPPORT='''
MM_BM_LINE EQU SW_LINE
MM_INDEX EQU $6398
MM_RESIDENT EQU $6399
MX_OLD_UNLOCK EQU $639A
MX_RETURN EQU $639B
MX_API_ACTIVE EQU $639C
MX_OLD_LED EQU $639D
MM_TXT EQU $C6
MM_PUTC EQU $7E6D
MM_HEX EQU $7E7C
MM_NL EQU $7E7F
X28_C9 EQU $7B64
X28_C8 EQU $7830
SW_NAMED_PRESET:
        LDX #7
SW_NAMED_MAGIC_CHECK:
        LDA $6770,X
        CMP SW_NAMED_MAGIC,X
        BNE SW_NAMED_NONE
        DEX
        BPL SW_NAMED_MAGIC_CHECK
        STZ $6770
        LDX #0
SW_NAMED_PRESET_COPY:
        LDA $6740,X
        STA SW_LINE,X
        BEQ SW_NAMED_PRESET_READY
        INX
        CPX #41
        BCC SW_NAMED_PRESET_COPY
        SEC
        RTS
SW_NAMED_PRESET_READY:
        LDA #1
        STA MX_RETURN
        PLA
        PLA
        JMP SW_NAMED_COMMAND
SW_NAMED_NONE:
        STZ MX_RETURN
        CLC
        RTS
SW_NAMED_COMMAND:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ MM_BM_BAD
        LDA SW_LINE
        CMP #'X'
        BNE MM_BM_BAD
        LDA SW_LINE+1
        CMP #' '
        BNE MM_BM_BAD
        LDA #1
        STA MM_INDEX
        JMP MM_X_COPY
MM_SPACES:
        LDX MM_INDEX
SW_X_SPACE:
        LDA SW_LINE,X
        CMP #' '
        BNE SW_X_SPACE_END
        INX
        STX MM_INDEX
        BRA SW_X_SPACE
SW_X_SPACE_END:
        ORA #0
        RTS
MM_ENDLINE:
        JSR MM_SPACES
        BNE SW_X_NO
        SEC
        RTS
SW_X_NO:
        CLC
        RTS
MM_PRINT:
        JMP SW_PRINT
MM_READLINE:
        JMP SW_READLINE
MM_V2W_SELECT:
        JMP V2W_SELECT
MM_BM_BAD:
        LDX #<SW_X_USAGE
        LDY #>SW_X_USAGE
        BRA MM_MESSAGE
MM_BM_CANCEL:
        JSR B29_CANCEL_HOOK
        LDX #<SW_X_CANCEL
        LDY #>SW_X_CANCEL
MM_MESSAGE:
        JSR SW_PRINT
        LDA MX_RETURN
        BEQ SW_X_LOCAL_RETURN
        LDX #0
SW_X_RESTORE_MON:
        LDA $5D00,X
        STA $6A00,X
        INX
        BNE SW_X_RESTORE_MON
        LDX #0
SW_X_RESTORE_ZP:
        LDA $5C00,X
        STA $00,X
        INX
        CPX #$E0
        BCC SW_X_RESTORE_ZP
        LDA #2
        STA $6778
        LDX #HC_IMAGE_END-HC_IMAGE-1
SW_X_TAIL:
        LDA HC_IMAGE,X
        STA $6B00,X
        DEX
        BPL SW_X_TAIL
        JMP $6B00
SW_X_LOCAL_RETURN:
        JMP SW_PROMPT
SW_NAMED_MAGIC: DB "BX",1,1,"PR05"
SW_X_USAGE: DB "X bank NAME P NAME / X P NAME bank NAME",13,10,0
SW_X_CANCEL: DB "Canceled; source retained.",13,10,0
'''
