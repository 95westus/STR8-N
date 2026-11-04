; All banking and writes run in common RAM. The old XIP call addresses are
; deliberately absent. These fixed worker entries are pinned to F_FREEZE.
X28_BANK EQU $62F0
MM_V2W_SELECT:
        STA X28_BANK
        JMP V2W_SELECT
X28_R1:
        PHX
        LDA X28_BANK
        JSR V2W_SELECT
        LDA (MM_SRC)
        BRA MB_READ_RETURN
X28_R2:
        PHX
        LDA X28_BANK
        JSR V2W_SELECT
        LDA (MM_DST)
        BRA MB_READ_RETURN
X28_R5:
        PHX
        LDA X28_BANK
        JSR V2W_SELECT
        LDA (MM_TZ_PTR),Y
MB_READ_RETURN:
        PHA
        LDA #3
        JSR V2W_SELECT
        PLA
        PLX
        ORA #0
        RTS
X28_R19:
        LDA $9000,X
        RTS
X28_C6:
        JMP V2W_SNAPSHOT
X28_C7:
        JMP V2W_ANALYZE
X28_C5:
        ; Caller is SEI. Skip only the fixed13-byte guard/BRK preamble;
        ; raw destinations may not contain BRK vectors. All target admission
        ; precedes this call, and the worker still checks readiness/accounts.
        JMP V2W_MUTATE+13
X28_C9:
        JMP V2W_BYTE+2

B29_LINE_1:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE MB_LINE_LIVE
        LDA #4
        LDX #<MM_BM_LINE
        LDY #>MM_BM_LINE
        JSR BQ_NEXT
        BCC MB_LINE_LIVE
        STY MM_LINELEN
        SEC
        RTS
MB_LINE_LIVE:
        JMP MM_READLINE
B29_ERROR_HOOK:
        PHP
        PHA
        LDA #2
        BRA MB_BATCH_ERROR
B29_CANCEL_HOOK:
        PHP
        PHA
        LDA #3
MB_BATCH_ERROR:
        STA BQ_ERROR
        PLA
        PLP
        RTS

; Word aliases are recognized before the reference's one-letter parser.
MB_ALIASES:
        LDX #<MB_VERSION_WORD
        LDY #>MB_VERSION_WORD
        JSR MB_MATCH
        BCS MB_VERSION
        LDX #<MB_TABLE_WORD
        LDY #>MB_TABLE_WORD
        JSR MB_MATCH
        BCS MB_TABLE_ALIAS
        LDX #<MB_BOOT_WORD
        LDY #>MB_BOOT_WORD
        JSR MB_MATCH
        BCS MB_BOOT_TOOL
        RTS
MB_MATCH:
        STX MM_TXT
        STY MM_TXT+1
        LDY #0
MB_MATCH_NEXT:
        LDA (MM_TXT),Y
        BEQ MB_MATCH_END
        CMP MM_BM_LINE,Y
        BNE MB_MATCH_NO
        INY
        BRA MB_MATCH_NEXT
MB_MATCH_END:
        LDA MM_BM_LINE,Y
        BEQ MB_MATCH_OK
        CMP #' '
        BNE MB_MATCH_NO
MB_MATCH_OK:
        STY MM_INDEX
        SEC
        RTS
MB_MATCH_NO:
        CLC
        RTS
MB_TABLE_ALIAS:
        PLA
        PLA
        JMP MM_BM_TABLE
MB_VERSION:
        PLA
        PLA
        JSR MM_ENDLINE
        BCC MM_BM_BAD
        LDA #3
        JSR MM_V2W_SELECT
        JSR MB_VERSION_CALL
        LDX #<MM_TITLE
        LDY #>MM_TITLE
        JMP MM_MESSAGE
MB_VERSION_CALL:
        JMP ($66F2)
MB_BOOT_TOOL:
        PLA
        PLA
        JSR MM_SPACES
        BNE MB_CONFIG_COPY
        JMP CONFIG_SHOW
MB_CONFIG_COPY:
        LDX MM_INDEX
        LDY #0
MB_CONFIG_BYTE:
        LDA MM_BM_LINE,X
        STA V2_LINE,Y
        BEQ MB_CONFIG_DONE
        INX
        INY
        CPY #40
        BCC MB_CONFIG_BYTE
        JMP MM_BM_BAD
MB_CONFIG_DONE:
        JMP CONFIG_DISPATCH
MB_VERSION_WORD: DB "VERSION",0
MB_TABLE_WORD: DB "TABLE",0
MB_BOOT_WORD: DB "BOOT",0

MM_BM_QUIT:
        JSR MM_ENDLINE
        BCC MM_BM_BAD
        JMP $6600
MM_BM_MAP:
        JSR MM_SPACES
        BEQ MB_MAP_DEFAULT
        JSR MM_NUMBER
        BCC MM_BM_BAD
        LDA MM_NUM+1
        BNE MM_BM_BAD
        LDA MM_NUM
        BEQ MM_BM_BAD
        CMP #4
        BCS MM_BM_BAD
        BRA MB_MAP_HAVE
MB_MAP_DEFAULT:
        LDA #2
MB_MAP_HAVE:
        PHA
        JSR MM_ENDLINE
        BCC MB_MAP_BAD
        PLA
        CMP #3
        BNE MB_MAP_NORMAL
        LDA #'W'
        STA MB_SERVICE_LINE
        STZ MB_SERVICE_LINE+1
        BRA MB_SERVICE
MB_MAP_NORMAL:
        ORA #'0'
        STA MB_SERVICE_LINE+1
        LDA #'M'
        STA MB_SERVICE_LINE
        STZ MB_SERVICE_LINE+2
MB_SERVICE:
        LDA #3
        JSR MM_V2W_SELECT
        LDX #<MB_SERVICE_LINE
        LDY #>MB_SERVICE_LINE
        LDA #3
        JSR $E008
        JMP MM_BM_MENU
MB_MAP_BAD:
        PLA
        JMP MM_BM_BAD
MB_SERVICE_LINE EQU $63E0

MM_BM_BOOT:
        JSR MM_BANK
        BCC MM_BM_BAD
        CMP #4
        BCS MM_BM_BAD
        STA MB_BOOT_BANK
        JSR MM_ENDLINE
        BCC MM_BM_BAD
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ MM_BM_BAD
        LDA MB_BOOT_BANK
        CMP #3
        BEQ MB_FOUNDATION
        LDA #0
        JSR JE_ENTER
        BCC MM_BM_BAD
        LDX MB_BOOT_BANK
        LDA MB_MASKS,X
        AND JE_FRAME+13
        BEQ MM_BM_BAD
        STZ V2_VECTOR
        LDA JE_FRAME+14,X
        STA V2_VECTOR+1
        LDA MB_BOOT_BANK
        STA V2_SELECTED
        JMP V2W_EXECUTE
MB_FOUNDATION:
        JMP $F004
MB_MASKS: DB 1,2,4,8
MB_BOOT_BANK EQU $63E8
