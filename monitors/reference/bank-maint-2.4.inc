; STR8-N bank maintenance 2.1, RAM entry $2000, no E extension dependency.
; Console uses the initialized, fixed v2 RAM ABI. All banking, flash work,
; command processing and constants execute in RAM, including after B3:F erase.
; The builder expands conditional branches to long branches before assembly.
MM_SRC                     EQU $C0
MM_DST                     EQU $C2
MM_CNT                     EQU $C4
MM_TXT                     EQU $C6
MM_BUF                     EQU $C8
MM_BM_LINE                 EQU $6000
MM_NUM                     EQU $6100
MM_FIRST                   EQU $6102
MM_LAST                    EQU $6104
MM_SB                      EQU $6106
MM_DB                      EQU $6107
MM_FROM                    EQU $6108
MM_THROUGH                 EQU $610A
MM_TO                      EQU $610C
MM_TOEND                   EQU $610E
MM_LENGTH                  EQU $6110
MM_INDEX                   EQU $6112
MM_LINELEN                 EQU $6113
MM_REVERSE                 EQU $6114
MM_MODE                    EQU $6115
MM_DANGER                  EQU $6116
MM_TOUCHED                 EQU $6117
MM_RESIDENT                EQU $6118
MM_BLEN                    EQU $611A
MM_DIRTY                   EQU $611C
MM_OFFSET                  EQU $611D
MM_VALUE                   EQU $611F
MM_SAVED_INDEX             EQU $6120
MM_MAPBANK                 EQU $6121
MM_MAPSEC                  EQU $6122
MM_CRC                     EQU $6123
MM_DIGITS                  EQU $6125
MM_OVERFLOW                EQU $6126
MM_BYTE                    EQU $6127
MM_EDITOR                  EQU $5000
MM_PUTC                    EQU $7E6D
MM_GETC                    EQU $7E70
MM_HEX                     EQU $7E7C
MM_NL                      EQU $7E7F
MM_NIBBLE                  EQU $7E82
MM_START:                  SEI
                        LDX #$FF
MM_X28_CLEAR_MAINT:        STZ $6200,X
                        DEX
                        BPL MM_X28_CLEAR_MAINT
                        CLD
                        LDX #$FF
                        TXS
                        LDX #$2F
MM_BM_INIT:                STZ $6100,X
                        DEX
                        BPL MM_BM_INIT
                        JSR X28_R6
                        CMP #'W'
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R7
                        CMP #'R'
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R8
                        CMP #$01
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R9
                        CMP #$32
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R10
                        CMP #$30
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R11
                        CMP #$31
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R12
                        CMP #$52
                        BNE MM_BM_UNSUPPORTED
                        LDA V2_RESIDENT
                        CMP #$04
                        BCS MM_BM_UNSUPPORTED
                        STA MM_RESIDENT
                        LDA $7E60
                        CMP #'R'
                        BNE MM_BM_UNSUPPORTED
                        LDA $7E61
                        CMP #'A'
                        BNE MM_BM_UNSUPPORTED
                        LDA $7E62
                        CMP #$01
                        BNE MM_BM_UNSUPPORTED
                        LDA $7E63
                        CMP #$0D
                        BCC MM_BM_UNSUPPORTED
                        STZ MM_MAP_ONCE
                        LDA $7DFC
                        CMP #$4D
                        BNE MM_BM_NORMAL_START
                        STZ $7DFC
                        LDA $7DFD
                        STA MM_MAP_VIEW
                        INC MM_MAP_ONCE
                        JMP MM_BM_MAP_START
MM_BM_NORMAL_START:        LDX #<MM_TITLE
                        LDY #>MM_TITLE
                        JSR MM_PRINT
                        STZ MM_BM_LINE
                        JMP MM_BM_HELP
; No unverified ABI calls on entry refusal. Return is unavailable after G.
MM_BM_UNSUPPORTED:         BRA MM_BM_UNSUPPORTED
MM_BM_MENU:                LDX #$FF
                        TXS
                        LDA MM_RESIDENT
                        JSR MM_V2W_SELECT
                        LDX #<MM_PROMPT
                        LDY #>MM_PROMPT
                        JSR MM_PRINT
                        JSR B29_LINE_1
                        BCS MM_LEGACY_LONG_119
                        JMP MM_BM_CANCEL
MM_LEGACY_LONG_119:
                        JSR MM_BN_TRY
                        STZ MM_INDEX
                        JSR MM_SPACES
                        BEQ MM_BM_MENU
                        STA MM_MODE
                        INC MM_INDEX
                        CMP #'X'
                        BNE MM_MX_LONG_128
                        JMP MM_X_COPY
MM_MX_LONG_128:
                        CMP #'?'
                        BEQ MM_BM_HELP
                        CMP #'M'
                        BNE MM_LEGACY_LONG_128
                        JMP MM_BM_MAP
MM_LEGACY_LONG_128:
                        CMP #'T'
                        BNE MM_LEGACY_LONG_130
                        JMP MM_BM_TABLE
MM_LEGACY_LONG_130:
                        CMP #'E'
                        BNE MM_LEGACY_LONG_132
                        JMP MM_BM_ERASE
MM_LEGACY_LONG_132:
                        CMP #'C'
                        BNE MM_LEGACY_LONG_134
                        JMP MM_BM_COPY
MM_LEGACY_LONG_134:
                        CMP #'V'
                        BNE MM_LEGACY_LONG_136
                        JMP MM_BM_COPY
MM_LEGACY_LONG_136:
                        CMP #'R'
                        BNE MM_LEGACY_LONG_138
                        JMP MM_BM_READ
MM_LEGACY_LONG_138:
                        CMP #'S'
                        BNE MM_LEGACY_LONG_140
                        JMP MM_BM_STAGE
MM_LEGACY_LONG_140:
                        CMP #'W'
                        BNE MM_LEGACY_LONG_142
                        JMP MM_BM_WRITE
MM_LEGACY_LONG_142:
                        CMP #'D'
                        BNE MM_LEGACY_LONG_144
                        JMP MM_BM_DISPLAY
MM_LEGACY_LONG_144:
                        CMP #'P'
                        BNE MM_LEGACY_LONG_146
                        JMP MM_BM_PATCH
MM_LEGACY_LONG_146:
                        CMP #'F'
                        BNE MM_LEGACY_LONG_148
                        JMP MM_BM_FILL
MM_LEGACY_LONG_148:
                        CMP #'N'
                        BNE MM_LEGACY_LONG_150
                        JMP MM_BM_NEW
MM_LEGACY_LONG_150:
                        CMP #'K'
                        BNE MM_LEGACY_LONG_152
                        JMP MM_BM_CRC
MM_LEGACY_LONG_152:
                        CMP #'J'
                        BNE MM_LEGACY_LONG_154
                        JMP MM_BM_BOOT
MM_LEGACY_LONG_154:
                        CMP #'Q'
                        BNE MM_LEGACY_LONG_156
                        JMP MM_BM_QUIT
MM_LEGACY_LONG_156:
                        JMP MM_BM_BAD
MM_BM_HELP:                JSR MM_ENDLINE
                        BCC MM_BM_BAD
                        LDX #<MM_HELP
                        LDY #>MM_HELP
                        JSR MM_PRINT
                        JMP MM_BM_MENU
MM_BM_BAD: JSR B29_ERROR_HOOK
                 LDX #<MM_BAD
                        LDY #>MM_BAD
                        JMP MM_MESSAGE
MM_BM_CANCEL: JSR B29_ERROR_HOOK
              LDX #<MM_CANCEL
                        LDY #>MM_CANCEL
                        JMP MM_MESSAGE
MM_BM_FAIL: JSR B29_ERROR_HOOK
                LDX #<MM_FAILED
                        LDY #>MM_FAILED
                        JMP MM_MESSAGE
MM_BM_DONE:                LDA MM_MODE
                        CMP #'W'
                        BNE MM_BM_DONE_TEXT
                        STZ MM_DIRTY
MM_BM_DONE_TEXT:           LDX #<MM_DONE
                        LDY #>MM_DONE
MM_MESSAGE:                JSR MM_PRINT
                        JMP MM_BM_MENU

; E bank sector[-sector]. A range is wholly validated before any mutation.
MM_BM_ERASE:               JSR MM_BANK
                        BCC MM_BM_BAD
                        CMP #$FF
                        BEQ MM_BM_BAD
                        STA MM_DB
                        STA MM_SB
                        JSR MM_RANGE
                        BCC MM_BM_BAD
                        LDA MM_FIRST+1
                        ORA MM_LAST+1
                        BNE MM_BM_BAD
                        LDA MM_FIRST
                        CMP #$08
                        BCC MM_BM_BAD
                        LDA MM_LAST
                        CMP #$10
                        BCS MM_BM_BAD
                        JSR MM_SCALE_RANGE
                        JSR MM_ENDLINE
                        BCC MM_BM_BAD
                        JSR MM_SOURCE_FIELDS
                        LDA MM_FIRST
                        STA MM_TO
                        LDA MM_FIRST+1
                        STA MM_TO+1
                        JSR MM_GET_LENGTH
                        JSR MM_DEST_END
                        BCC MM_BM_BAD
                        LDA #$FD
                        STA MM_SB
                        JSR MM_CONFIRM
                        BCC MM_BM_CANCEL
                        JMP MM_COPY_RUN

; C/V source-space range destination-space start. Flash 8-F shorthand is
; a sector/range; full addresses allow partial-sector copies with preservation.
MM_BM_COPY:                JSR MM_SOURCE_ARGS
                        BCS MM_LEGACY_LONG_220
                        JMP MM_BM_BAD
MM_LEGACY_LONG_220:
                        JSR MM_DEST_ARGS
                        BCS MM_LEGACY_LONG_222
                        JMP MM_BM_BAD
MM_LEGACY_LONG_222:
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_224
                        JMP MM_BM_BAD
MM_LEGACY_LONG_224:
                        LDA MM_MODE
                        CMP #'V'
                        BNE MM_LEGACY_LONG_227
                        JMP MM_COMPARE_RUN
MM_LEGACY_LONG_227:
                        JSR MM_CONFIRM
                        BCS MM_LEGACY_LONG_229
                        JMP MM_BM_CANCEL
MM_LEGACY_LONG_229:
                        JMP MM_COPY_RUN
MM_BM_WRITE:               JSR MM_BUFFER_PRESENT
                        BCS MM_LEGACY_LONG_232
                        JMP MM_BM_BAD
MM_LEGACY_LONG_232:
                        LDA #$FE
                        STA MM_SB
                        STZ MM_FROM
                        LDA #$50
                        STA MM_FROM+1
                        LDA MM_BLEN
                        STA MM_LENGTH
                        LDA MM_BLEN+1
                        STA MM_LENGTH+1
                        SEC
                        LDA MM_BLEN
                        SBC #$01
                        STA MM_THROUGH
                        LDA MM_BLEN+1
                        SBC #$00
                        CLC
                        ADC #$50
                        STA MM_THROUGH+1
                        JSR MM_DEST_ARGS
                        BCS MM_LEGACY_LONG_252
                        JMP MM_BM_BAD
MM_LEGACY_LONG_252:
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_254
                        JMP MM_BM_BAD
MM_LEGACY_LONG_254:
                        JSR MM_CONFIRM
                        BCS MM_LEGACY_LONG_256
                        JMP MM_BM_CANCEL
MM_LEGACY_LONG_256:
                        JMP MM_COPY_RUN

MM_SOURCE_ARGS:            JSR MM_BANK
                        BCS MM_LEGACY_LONG_260
                        JMP MM_ARGS_FAIL
MM_LEGACY_LONG_260:
                        STA MM_SB
                        JSR MM_RANGE
                        BCS MM_LEGACY_LONG_263
                        JMP MM_ARGS_FAIL
MM_LEGACY_LONG_263:
                        JSR MM_SCALE_RANGE
                        LDA MM_SB
                        JSR MM_VALID_RANGE
                        BCS MM_LEGACY_LONG_267
                        JMP MM_ARGS_FAIL
MM_LEGACY_LONG_267:
                        JSR MM_SOURCE_FIELDS
MM_GET_LENGTH:             SEC
                        LDA MM_THROUGH
                        SBC MM_FROM
                        STA MM_LENGTH
                        LDA MM_THROUGH+1
                        SBC MM_FROM+1
                        STA MM_LENGTH+1
                        INC MM_LENGTH
                        BNE MM_LENGTH_OK
                        INC MM_LENGTH+1
MM_LENGTH_OK:              SEC
                        RTS
MM_SOURCE_FIELDS:          LDA MM_FIRST
                        STA MM_FROM
                        LDA MM_FIRST+1
                        STA MM_FROM+1
                        LDA MM_LAST
                        STA MM_THROUGH
                        LDA MM_LAST+1
                        STA MM_THROUGH+1
                        RTS
MM_DEST_ARGS:              JSR MM_BANK
                        BCC MM_ARGS_FAIL
                        STA MM_DB
                        JSR MM_NUMBER
                        BCC MM_ARGS_FAIL
                        LDA MM_DB
                        CMP #$FF
                        BEQ MM_DEST_RAW
                        LDA MM_NUM+1
                        BNE MM_DEST_RAW
                        LDA MM_NUM
                        CMP #$08
                        BCC MM_DEST_RAW
                        CMP #$10
                        BCS MM_DEST_RAW
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA MM_NUM+1
                        STZ MM_NUM
MM_DEST_RAW:               LDA MM_NUM
                        STA MM_TO
                        LDA MM_NUM+1
                        STA MM_TO+1
MM_DEST_END:               SEC
                        LDA MM_LENGTH
                        SBC #$01
                        STA MM_TOEND
                        LDA MM_LENGTH+1
                        SBC #$00
                        STA MM_TOEND+1
                        CLC
                        LDA MM_TO
                        ADC MM_TOEND
                        STA MM_TOEND
                        LDA MM_TO+1
                        ADC MM_TOEND+1
                        STA MM_TOEND+1
                        BCS MM_ARGS_FAIL
                        LDA MM_TO
                        STA MM_FIRST
                        LDA MM_TO+1
                        STA MM_FIRST+1
                        LDA MM_TOEND
                        STA MM_LAST
                        LDA MM_TOEND+1
                        STA MM_LAST+1
                        LDA MM_DB
                        BRA MM_VALID_RANGE
MM_ARGS_FAIL:              CLC
                        RTS

; RAM ranges exclude zero page/stack, this utility, editor/state, monitor/I/O.
; The same rule applies to sources so streaming cannot read its own scratch.
MM_VALID_RANGE:            PHA
                        LDA MM_LAST
                        CMP MM_FIRST
                        LDA MM_LAST+1
                        SBC MM_FIRST+1
                        PLA
                        BCC MM_RANGE_FAIL
                        CMP #$FF
                        BEQ MM_RANGE_RAM
                        LDA MM_FIRST+1
                        CMP #$80
                        RTS
MM_RANGE_RAM:              LDA MM_FIRST+1
                        CMP #$02
                        BCC MM_RANGE_FAIL
                        LDA MM_LAST+1
                        CMP #$67
                        BCS MM_RANGE_FAIL
                        CMP #$65
                        BCC MM_RTC_RAM_CONTINUE
                        BIT SVC_ACTIVE
                        BNE MM_RANGE_FAIL
MM_RTC_RAM_CONTINUE:
MM_RANGE_EDITOR:           LDA MM_LAST+1
                        CMP #$50
                        BCC MM_RANGE_OK
                        LDA MM_FIRST+1
                        CMP #$64
                        BCC MM_RANGE_FAIL
MM_RANGE_OK:               SEC
                        RTS
MM_RANGE_FAIL:             CLC
                        RTS

; Exact operation line plus normalized destination is shown before confirmation.
MM_CONFIRM:
        LDA MM_DB
        LDX MM_TO+1
        LDY MM_TOEND+1
        JSR MS_RESERVED
        BCC MS_CONFIRM_CONTINUE
        JMP MM_CONFIRM_NO
MS_CONFIRM_CONTINUE:       LDA MM_DB
                        CMP #2
                        BNE MM_X28_CONFIRM_OTHER
                        JMP MM_CONFIRM_NO
MM_X28_CONFIRM_OTHER:      LDA MM_DB
                        CMP #$03
                        BNE MM_CONFIRM_ALLOWED
                        LDA MM_TOEND+1
                        CMP #$A0
                        BCC MM_LEGACY_LONG_387
                        JMP MM_CONFIRM_NO
MM_LEGACY_LONG_387:
                        LDA MM_DB
                        CMP #3
                        BNE MM_CONFIRM_ALLOWED
                        LDA MM_TO+1
                        AND #$F0
                        CMP #$80
                        BNE MM_RTC_MX_LONG_457
                        JMP MM_CONFIRM_NO
MM_RTC_MX_LONG_457:
                        CMP #$90
                        BNE MM_RTC_MX_LONG_459
                        JMP MM_CONFIRM_NO
MM_RTC_MX_LONG_459:
MM_CONFIRM_ALLOWED:        STZ MM_DANGER
                        LDX #<MM_PLAN_TEXT
                        LDY #>MM_PLAN_TEXT
                        JSR MM_PRINT
                        LDX #<MM_BM_LINE
                        LDY #>MM_BM_LINE
                        JSR MM_PRINT
                        LDX #<MM_DEST_TEXT
                        LDY #>MM_DEST_TEXT
                        JSR MM_PRINT
                        LDA MM_DB
                        JSR MM_SPACE_NAME
                        LDA #':'
                        JSR MM_PUTC
                        LDA MM_TO+1
                        JSR MM_HEX
                        LDA MM_TO
                        JSR MM_HEX
                        LDA #'-'
                        JSR MM_PUTC
                        LDA MM_TOEND+1
                        JSR MM_HEX
                        LDA MM_TOEND
                        JSR MM_HEX
                        LDA MM_DB
                        CMP #$03
                        BNE MM_CONFIRM_FIRST
                        LDA MM_TOEND+1
                        CMP #$F0
                        BCC MM_CONFIRM_FIRST
                        INC MM_DANGER
MM_CONFIRM_FIRST:          LDX #<MM_CONFIRM_TEXT
                        LDY #>MM_CONFIRM_TEXT
                        JSR MM_PRINT
                        JSR MM_READLINE
                        BCC MM_CONFIRM_NO
                        LDA MM_BM_LINE
                        CMP #'Y'
                        BNE MM_CONFIRM_NO
                        LDA MM_BM_LINE+1
                        BNE MM_CONFIRM_NO
                        LDA MM_DANGER
                        BEQ MM_CONFIRM_YES
                        LDX #<MM_B3F_TEXT
                        LDY #>MM_B3F_TEXT
                        JSR MM_PRINT
                        JSR MM_READLINE
                        BCC MM_CONFIRM_NO
                        LDA MM_BM_LINE
                        CMP #'B'
                        BNE MM_CONFIRM_NO
                        LDA MM_BM_LINE+1
                        CMP #'3'
                        BNE MM_CONFIRM_NO
                        LDA MM_BM_LINE+2
                        CMP #'F'
                        BNE MM_CONFIRM_NO
                        LDA MM_BM_LINE+3
                        BNE MM_CONFIRM_NO
MM_CONFIRM_YES:            SEC
                        RTS
MM_CONFIRM_NO:             CLC
                        RTS

; Direction-aware streaming gives memmove semantics even for overlapping flash
; ranges. Construct a complete destination sector before programming any byte.
MM_SET_POINTERS:           STZ MM_REVERSE
                        LDA MM_FROM
                        STA MM_SRC
                        LDA MM_FROM+1
                        STA MM_SRC+1
                        LDA MM_TO
                        STA MM_DST
                        LDA MM_TO+1
                        STA MM_DST+1
                        LDA MM_LENGTH
                        STA MM_CNT
                        LDA MM_LENGTH+1
                        STA MM_CNT+1
                        LDA MM_SB
                        CMP MM_DB
                        BNE MM_POINTERS_DONE
                        LDA MM_TO
                        CMP MM_FROM
                        LDA MM_TO+1
                        SBC MM_FROM+1
                        BCC MM_POINTERS_DONE
                        LDA MM_THROUGH
                        CMP MM_TO
                        LDA MM_THROUGH+1
                        SBC MM_TO+1
                        BCC MM_POINTERS_DONE
                        INC MM_REVERSE
                        LDA MM_THROUGH
                        STA MM_SRC
                        LDA MM_THROUGH+1
                        STA MM_SRC+1
                        LDA MM_TOEND
                        STA MM_DST
                        LDA MM_TOEND+1
                        STA MM_DST+1
MM_POINTERS_DONE:          RTS
MM_COPY_RUN:               JSR MM_SET_POINTERS
                        LDA MM_DB
                        CMP #$FF
                        BEQ MM_COPY_RAM
MM_COPY_SECTOR:            JSR MM_CHECK_CANCEL
                        LDA MM_DB
                        STA V2_SELECTED
                        LDA MM_DST+1
                        AND #$F0
                        STA V2_SECTOR
                        JSR X28_C6
MM_COPY_BYTE:              JSR MM_READ_SOURCE
                        STA MM_BYTE
                        LDA MM_DST
                        STA MM_BUF
                        LDA MM_DST+1
                        AND #$0F
                        CLC
                        ADC #$68
                        STA MM_BUF+1
                        LDA MM_BYTE
                        STA (MM_BUF)
                        JSR MM_ADVANCE
                        BEQ MM_COPY_COMMIT
                        LDA MM_DST+1
                        AND #$F0
                        CMP V2_SECTOR
                        BEQ MM_COPY_BYTE
MM_COPY_COMMIT:            JSR MM_CHECK_CANCEL
                        LDA MM_DB
                        STA V2_SELECTED
                        CMP MM_RESIDENT
                        BNE MM_COPY_ANALYZE
                        LDA V2_SECTOR
                        CMP #$F0
                        BNE MM_COPY_ANALYZE
                        LDA #$01
                        STA MM_TOUCHED
MM_COPY_ANALYZE:           JSR X28_C7
                        STZ V2_SELF
                        JSR X28_C5
                        BCC MM_LEGACY_LONG_531
                        JMP MM_BM_FAIL
MM_LEGACY_LONG_531:
                        LDA MM_CNT
                        ORA MM_CNT+1
                        BNE MM_COPY_SECTOR
                        JMP MM_BM_DONE
MM_COPY_RAM:               JSR MM_CHECK_CANCEL
                        JSR MM_READ_SOURCE
                        STA (MM_DST)
                        CMP (MM_DST)
                        BEQ MM_LEGACY_LONG_540
                        JMP MM_BM_FAIL
MM_LEGACY_LONG_540:
                        JSR MM_ADVANCE
                        BNE MM_COPY_RAM
                        JMP MM_BM_DONE
MM_CHECK_CANCEL:           JSR $7E76
                        BCC MM_LEGACY_LONG_545
                        JMP MM_BM_CANCEL
MM_LEGACY_LONG_545:
                        RTS
MM_READ_SOURCE:            LDA MM_SB
                        CMP #$FD
                        BEQ MM_READ_FF
                        CMP #$04
                        BCS MM_READ_RAM
                        JSR MM_V2W_SELECT
MM_READ_RAM:               JSR X28_R1
                        RTS
MM_READ_FF:                LDA #$FF
                        RTS
MM_ADVANCE:                LDA MM_CNT
                        BNE MM_ADV_COUNT
                        DEC MM_CNT+1
MM_ADV_COUNT:              DEC MM_CNT
                        LDA MM_REVERSE
                        BEQ MM_ADV_FORWARD
                        LDA MM_SRC
                        BNE MM_ADV_SRC_DOWN
                        DEC MM_SRC+1
MM_ADV_SRC_DOWN:           DEC MM_SRC
                        LDA MM_DST
                        BNE MM_ADV_DST_DOWN
                        DEC MM_DST+1
MM_ADV_DST_DOWN:           DEC MM_DST
                        BRA MM_ADV_DONE
MM_ADV_FORWARD:            INC MM_SRC
                        BNE MM_ADV_DST_UP
                        INC MM_SRC+1
MM_ADV_DST_UP:             INC MM_DST
                        BNE MM_ADV_DONE
                        INC MM_DST+1
MM_ADV_DONE:               LDA MM_CNT
                        ORA MM_CNT+1
                        RTS
MM_COMPARE_RUN:            JSR MM_SET_POINTERS
MM_COMPARE_BYTE:           JSR MM_CHECK_CANCEL
                        JSR MM_READ_SOURCE
                        STA MM_BYTE
                        LDA MM_DB
                        CMP #$04
                        BCS MM_COMPARE_RAM
                        JSR MM_V2W_SELECT
MM_COMPARE_RAM:            JSR X28_R2
                        CMP MM_BYTE
                        BNE MM_COMPARE_DIFFERENT
                        JSR MM_ADVANCE
                        BNE MM_COMPARE_BYTE
                        LDX #<MM_MATCH_TEXT
                        LDY #>MM_MATCH_TEXT
                        JMP MM_MESSAGE
MM_COMPARE_DIFFERENT: JSR B29_ERROR_HOOK
      LDX #<MM_DIFFERENT_TEXT
                        LDY #>MM_DIFFERENT_TEXT
                        JSR MM_PRINT
                        LDA MM_DST+1
                        JSR MM_HEX
                        LDA MM_DST
                        JSR MM_HEX
                        JMP MM_BM_MENU

; R reads up to 4 KiB into the independent editor buffer. W is the only
; editor command that changes a destination. Copy/erase never consume it.
; Stage the utility's immutable image into the editor, including FF padding.
; S 8 -> original $2000-$2FFF; S 9 -> original $3000-$3FFF.
MM_BM_STAGE:               JMP MM_BM_BAD
MM_BM_READ:                JSR MM_SOURCE_ARGS
                        BCS MM_LEGACY_LONG_655
                        JMP MM_BM_BAD
MM_LEGACY_LONG_655:
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_657
                        JMP MM_BM_BAD
MM_LEGACY_LONG_657:
                        JSR MM_LENGTH_4K
                        BCS MM_LEGACY_LONG_659
                        JMP MM_BM_BAD
MM_LEGACY_LONG_659:
                        LDA MM_LENGTH
                        STA MM_BLEN
                        STA MM_CNT
                        LDA MM_LENGTH+1
                        STA MM_BLEN+1
                        STA MM_CNT+1
                        LDA MM_FROM
                        STA MM_SRC
                        LDA MM_FROM+1
                        STA MM_SRC+1
                        STZ MM_DST
                        LDA #$50
                        STA MM_DST+1
                        STZ MM_REVERSE
MM_READ_BUFFER_LOOP:       JSR MM_READ_SOURCE
                        STA (MM_DST)
                        JSR MM_ADVANCE
                        BNE MM_READ_BUFFER_LOOP
                        STZ MM_DIRTY
                        LDX #<MM_BUFFER_TEXT
                        LDY #>MM_BUFFER_TEXT
                        JMP MM_MESSAGE
MM_LENGTH_4K:              LDA MM_LENGTH
                        ORA MM_LENGTH+1
                        BNE MM_LEGACY_LONG_684
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_684:
                        LDA MM_LENGTH+1
                        CMP #$10
                        BCS MM_LEGACY_LONG_687
                        JMP MM_RANGE_OK
MM_LEGACY_LONG_687:
                        BEQ MM_LEGACY_LONG_688
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_688:
                        LDA MM_LENGTH
                        BEQ MM_LEGACY_LONG_690
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_690:
                        SEC
                        RTS
MM_BUFFER_PRESENT:        LDA MM_BLEN
                        ORA MM_BLEN+1
                        BNE MM_LEGACY_LONG_695
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_695:
                        SEC
                        RTS
MM_EDITOR_RANGE:           JSR MM_BUFFER_PRESENT
                        BCS MM_LEGACY_LONG_699
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_699:
                        LDA MM_LAST
                        CMP MM_FIRST
                        LDA MM_LAST+1
                        SBC MM_FIRST+1
                        BCS MM_LEGACY_LONG_704
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_704:
                        LDA MM_LAST
                        CMP MM_BLEN
                        LDA MM_LAST+1
                        SBC MM_BLEN+1
                        BCC MM_LEGACY_LONG_709
                        JMP MM_RANGE_FAIL
MM_LEGACY_LONG_709:
                        SEC
                        RTS
MM_BM_PATCH:               JSR MM_BUFFER_PRESENT
                        BCS MM_LEGACY_LONG_713
                        JMP MM_BM_BAD
MM_LEGACY_LONG_713:
                        LDA MM_INDEX
                        STA MM_SAVED_INDEX
                        JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_717
                        JMP MM_BM_BAD
MM_LEGACY_LONG_717:
                        LDA MM_NUM
                        STA MM_OFFSET
                        LDA MM_NUM+1
                        STA MM_OFFSET+1
                        STZ MM_DIGITS
MM_PATCH_PREFLIGHT:        JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_724
                        JMP MM_BM_BAD
MM_LEGACY_LONG_724:
                        LDA MM_NUM+1
                        BEQ MM_LEGACY_LONG_726
                        JMP MM_BM_BAD
MM_LEGACY_LONG_726:
                        LDA MM_OFFSET
                        CMP MM_BLEN
                        LDA MM_OFFSET+1
                        SBC MM_BLEN+1
                        BCC MM_LEGACY_LONG_731
                        JMP MM_BM_BAD
MM_LEGACY_LONG_731:
                        INC MM_OFFSET
                        BNE MM_PATCH_TEST_END
                        INC MM_OFFSET+1
MM_PATCH_TEST_END:         JSR MM_SPACES
                        BNE MM_PATCH_PREFLIGHT
; Reparse offset, then the already validated bytes. No partial edits on error.
                        LDA MM_SAVED_INDEX
                        STA MM_INDEX
                        JSR MM_NUMBER
                        LDA MM_NUM
                        STA MM_DST
                        LDA MM_NUM+1
                        CLC
                        ADC #$50
                        STA MM_DST+1
MM_PATCH_STORE:            JSR MM_NUMBER
                        LDA MM_NUM
                        STA (MM_DST)
                        INC MM_DST
                        BNE MM_PATCH_MORE
                        INC MM_DST+1
MM_PATCH_MORE:             JSR MM_SPACES
                        BNE MM_PATCH_STORE
                        INC MM_DIRTY
                        JMP MM_BUFFER_EDITED
MM_BM_FILL:                JSR MM_RANGE
                        BCS MM_LEGACY_LONG_758
                        JMP MM_BM_BAD
MM_LEGACY_LONG_758:
                        JSR MM_EDITOR_RANGE
                        BCS MM_LEGACY_LONG_760
                        JMP MM_BM_BAD
MM_LEGACY_LONG_760:
                        JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_762
                        JMP MM_BM_BAD
MM_LEGACY_LONG_762:
                        LDA MM_NUM+1
                        BEQ MM_LEGACY_LONG_764
                        JMP MM_BM_BAD
MM_LEGACY_LONG_764:
                        LDA MM_NUM
                        STA MM_VALUE
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_768
                        JMP MM_BM_BAD
MM_LEGACY_LONG_768:
                        JSR MM_SOURCE_FIELDS
                        JSR MM_GET_LENGTH
                        LDA MM_FIRST
                        STA MM_DST
                        LDA MM_FIRST+1
                        CLC
                        ADC #$50
                        STA MM_DST+1
                        BRA MM_FILL_BUFFER
MM_BM_NEW:                 JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_779
                        JMP MM_BM_BAD
MM_LEGACY_LONG_779:
                        LDA MM_NUM
                        STA MM_LENGTH
                        LDA MM_NUM+1
                        STA MM_LENGTH+1
                        JSR MM_LENGTH_4K
                        BCS MM_LEGACY_LONG_785
                        JMP MM_BM_BAD
MM_LEGACY_LONG_785:
                        JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_787
                        JMP MM_BM_BAD
MM_LEGACY_LONG_787:
                        LDA MM_NUM+1
                        BEQ MM_LEGACY_LONG_789
                        JMP MM_BM_BAD
MM_LEGACY_LONG_789:
                        LDA MM_NUM
                        STA MM_VALUE
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_793
                        JMP MM_BM_BAD
MM_LEGACY_LONG_793:
                        LDA MM_LENGTH
                        STA MM_BLEN
                        LDA MM_LENGTH+1
                        STA MM_BLEN+1
                        STZ MM_DST
                        LDA #$50
                        STA MM_DST+1
MM_FILL_BUFFER:            LDA MM_LENGTH
                        STA MM_CNT
                        LDA MM_LENGTH+1
                        STA MM_CNT+1
                        STZ MM_REVERSE
MM_FILL_LOOP:              LDA MM_VALUE
                        STA (MM_DST)
                        JSR MM_ADVANCE
                        BNE MM_FILL_LOOP
                        INC MM_DIRTY
MM_BUFFER_EDITED:          LDX #<MM_EDITED_TEXT
                        LDY #>MM_EDITED_TEXT
                        JMP MM_MESSAGE
MM_BM_DISPLAY:             JSR MM_BUFFER_PRESENT
                        BCS MM_LEGACY_LONG_815
                        JMP MM_BM_BAD
MM_LEGACY_LONG_815:
                        JSR MM_SPACES
                        BNE MM_DISPLAY_RANGE
                        STZ MM_FIRST
                        STZ MM_FIRST+1
                        SEC
                        LDA MM_BLEN
                        SBC #$01
                        STA MM_LAST
                        LDA MM_BLEN+1
                        SBC #$00
                        STA MM_LAST+1
                        BRA MM_DISPLAY_READY
MM_DISPLAY_RANGE:          JSR MM_RANGE
                        BCS MM_LEGACY_LONG_829
                        JMP MM_BM_BAD
MM_LEGACY_LONG_829:
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_831
                        JMP MM_BM_BAD
MM_LEGACY_LONG_831:
                        JSR MM_EDITOR_RANGE
                        BCS MM_LEGACY_LONG_833
                        JMP MM_BM_BAD
MM_LEGACY_LONG_833:
MM_DISPLAY_READY:          JSR MM_SOURCE_FIELDS
                        JSR MM_GET_LENGTH
                        LDA MM_FIRST
                        STA MM_OFFSET
                        STA MM_SRC
                        LDA MM_FIRST+1
                        STA MM_OFFSET+1
                        CLC
                        ADC #$50
                        STA MM_SRC+1
                        LDA MM_LENGTH
                        STA MM_CNT
                        LDA MM_LENGTH+1
                        STA MM_CNT+1
                        STZ MM_REVERSE
MM_DISPLAY_ROW:            JSR MM_CHECK_CANCEL
                        JSR MM_NL
                        LDA MM_OFFSET+1
                        JSR MM_HEX
                        LDA MM_OFFSET
                        JSR MM_HEX
                        LDA #':'
                        JSR MM_PUTC
                        LDX #$10
MM_DISPLAY_BYTE:           LDA #' '
                        JSR MM_PUTC
                        JSR X28_R1
                        JSR MM_HEX
                        INC MM_OFFSET
                        BNE MM_DISPLAY_NEXT
                        INC MM_OFFSET+1
MM_DISPLAY_NEXT:           JSR MM_ADVANCE
                        BNE MM_LEGACY_LONG_866
                        JMP MM_BM_MENU
MM_LEGACY_LONG_866:
                        DEX
                        BNE MM_DISPLAY_BYTE
                        BRA MM_DISPLAY_ROW
MM_BM_CRC:                 JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_871
                        JMP MM_BM_BAD
MM_LEGACY_LONG_871:
                        JSR MM_BUFFER_PRESENT
                        BCS MM_LEGACY_LONG_873
                        JMP MM_BM_BAD
MM_LEGACY_LONG_873:
                        STZ MM_SRC
                        LDA #$50
                        STA MM_SRC+1
                        LDA MM_BLEN
                        STA MM_CNT
                        LDA MM_BLEN+1
                        STA MM_CNT+1
                        STZ MM_REVERSE
                        LDA #$FF
                        STA MM_CRC
                        STA MM_CRC+1
MM_CRC_BYTE:               JSR X28_R1
                        EOR MM_CRC+1
                        STA MM_CRC+1
                        LDX #$08
MM_CRC_BIT:                ASL MM_CRC
                        ROL MM_CRC+1
                        BCC MM_CRC_NEXT
                        LDA MM_CRC
                        EOR #$21
                        STA MM_CRC
                        LDA MM_CRC+1
                        EOR #$10
                        STA MM_CRC+1
MM_CRC_NEXT:               DEX
                        BNE MM_CRC_BIT
                        JSR MM_ADVANCE
                        BNE MM_CRC_BYTE
                        LDX #<MM_CRC_TEXT
                        LDY #>MM_CRC_TEXT
                        JSR MM_PRINT
                        LDA MM_CRC+1
                        JSR MM_HEX
                        LDA MM_CRC
                        JSR MM_HEX
                        JMP MM_BM_MENU

; Three RAM-only map views. M defaults to ranges; T returns to maintenance.
MM_MAP_VIEW EQU $6134
MM_MAP_ONCE EQU $6135
MM_MAP_META EQU $6136
MM_MAP_RANGE_END EQU $6138
MM_MAP_KIND EQU $613A
MM_MAP_START EQU $613B
MM_MAP_TABLE_RETURN EQU $613D

MM_BM_MAP:                JSR MM_SPACES
                        BEQ MM_MAP_DEFAULT
                        JSR MM_NUMBER
                        BCS MM_LEGACY_LONG_923
                        JMP MM_BM_BAD
MM_LEGACY_LONG_923:
                        LDA MM_NUM+1
                        BEQ MM_LEGACY_LONG_925
                        JMP MM_BM_BAD
MM_LEGACY_LONG_925:
                        LDA MM_NUM
                        BNE MM_LEGACY_LONG_927
                        JMP MM_BM_BAD
MM_LEGACY_LONG_927:
                        CMP #$04
                        BCC MM_LEGACY_LONG_929
                        JMP MM_BM_BAD
MM_LEGACY_LONG_929:
                        BRA MM_MAP_ARGUMENT
MM_MAP_DEFAULT:           LDA #$02
MM_MAP_ARGUMENT:          STA MM_MAP_VIEW
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_934
                        JMP MM_BM_BAD
MM_LEGACY_LONG_934:
MM_BM_MAP_START:          JSR X28_C4
                        STZ MM_MAP_META
                        BCC MM_MAP_NO_META
                        INC MM_MAP_META
MM_MAP_NO_META:           JSR MM_MAP_APP_PREPARE
                        LDA MM_MAP_VIEW
                        CMP #$01
                        BEQ MM_MAP_GRID_TITLE
                        CMP #$03
                        BEQ MM_MAP_DETAIL_TITLE
                        LDX #<MM_MAP_RANGES_TEXT
                        LDY #>MM_MAP_RANGES_TEXT
                        JMP MM_MAP_TITLE
MM_MAP_GRID_TITLE:        LDX #<MM_MAP_GRID_TEXT
                        LDY #>MM_MAP_GRID_TEXT
                        JMP MM_MAP_TITLE
MM_MAP_DETAIL_TITLE:      LDX #<MM_MAP_DETAIL_TEXT
                        LDY #>MM_MAP_DETAIL_TEXT
MM_MAP_TITLE:             JSR MM_PRINT
                        LDA SVC_ACTIVE
                        BPL MM_RTC_RAM_MAP_DONE
                        LDX #<MM_RTC_RAM_TEXT
                        LDY #>MM_RTC_RAM_TEXT
                        JSR MM_PRINT
MM_RTC_RAM_MAP_DONE:
                        STZ MM_MAPBANK
MM_MAP_BANK:              JSR MM_CHECK_CANCEL
                        LDA MM_MAPBANK
                        JSR MM_V2W_SELECT
                        LDA #$80
                        STA MM_MAPSEC
MM_MAP_SECTOR:            STZ MM_SRC
                        LDA MM_MAPSEC
                        STA MM_SRC+1
                        LDX #$10
                        LDY #$00
MM_MAP_SCAN:              JSR X28_R3
                        CMP #$FF
                        BNE MM_MAP_USED
                        INY
                        BNE MM_MAP_SCAN
                        INC MM_SRC+1
                        DEX
                        BNE MM_MAP_SCAN
                        LDA #'E'
                        BRA MM_MAP_CHAR
MM_MAP_USED:              LDA #'U'
MM_MAP_CHAR:              PHA
                        LDA MM_MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAY
                        PLA
                        STA MM_MAP_STATUS,Y
                        LDA MM_MAPSEC
                        CLC
                        ADC #$10
                        STA MM_MAPSEC
                        BNE MM_MAP_SECTOR
                        STZ MM_MAP_OWNER_END
                        STZ MM_MAP_OWNER_END+1
                        LDA #$FF
                        STA MM_MAP_APP_OWNER
                        LDA #$80
                        STA MM_MAPSEC
                        LDA MM_MAP_VIEW
                        CMP #$01
                        BNE MM_MAP_ROWS
                        LDA MM_MAPBANK
                        JSR MM_SPACE_NAME
                        LDA #' '
                        JSR MM_PUTC
MM_MAP_GRID_SECTOR:       JSR MM_MAP_IDENTIFY
                        LDA MM_MAP_KIND
                        JSR MM_PUTC
                        LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_GRID_INACTIVE
                        LDA MM_MAPSEC
                        CMP BOOT_ACTIVE
                        BNE MM_MAP_GRID_INACTIVE
                        LDA #'*'
                        BRA MM_MAP_GRID_MARK
MM_MAP_GRID_INACTIVE:     LDA #' '
MM_MAP_GRID_MARK:         JSR MM_PUTC
                        LDA #' '
                        JSR MM_PUTC
                        LDA MM_MAPSEC
                        CLC
                        ADC #$10
                        STA MM_MAPSEC
                        BNE MM_MAP_GRID_SECTOR
                        JMP MM_MAP_BANK_END
MM_MAP_ROWS:              JSR MM_MAP_IDENTIFY
                        LDA MM_MAP_VIEW
                        CMP #$02
                        BEQ MM_LEGACY_LONG_1029
                        JMP MM_MAP_DETAIL_ROW
MM_LEGACY_LONG_1029:
                        LDA MM_MAP_KIND
                        CMP #'+'
                        BNE MM_LEGACY_LONG_1032
                        JMP MM_MAP_ROW_ADVANCE
MM_LEGACY_LONG_1032:
                        LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_RANGE_ROW
                        LDA MM_MAPSEC
                        CMP #$D0
                        BNE MM_LEGACY_LONG_1038
                        JMP MM_MAP_ROW_ADVANCE
MM_LEGACY_LONG_1038:
MM_MAP_RANGE_ROW:         STZ MM_MAP_START
                        LDA MM_MAPSEC
                        STA MM_MAP_START+1
                        LDA #$FF
                        STA MM_MAP_RANGE_END
                        LDA MM_MAPSEC
                        ORA #$0F
                        STA MM_MAP_RANGE_END+1
                        LDA MM_MAP_KIND
                        CMP #'S'
                        BNE MM_MAP_RANGE_RESERVED
                        SEC
                        LDA MM_MAP_OWNER_END
                        SBC #$01
                        STA MM_MAP_RANGE_END
                        LDA MM_MAP_OWNER_END+1
                        SBC #$00
                        STA MM_MAP_RANGE_END+1
                        JMP MM_MAP_RANGE_PRINT
MM_MAP_RANGE_RESERVED:    LDA MM_MAP_KIND
                        CMP #'P'
                        BNE MM_MAP_RANGE_OTHER
                        LDX MM_MAP_APP_OWNER
                        LDA MM_MAP_APPS+14,X
                        STA MM_MAP_START
                        LDA MM_MAP_APPS+15,X
                        STA MM_MAP_START+1
                        SEC
                        LDA MM_MAP_OWNER_END
                        SBC #$01
                        STA MM_MAP_RANGE_END
                        LDA MM_MAP_OWNER_END+1
                        SBC #$00
                        STA MM_MAP_RANGE_END+1
                        JSR MM_MAP_APP_PREFIX
                        JMP MM_MAP_RANGE_PRINT
MM_MAP_RANGE_OTHER:       LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_RANGE_PRINT
                        LDA MM_MAPSEC
                        CMP #$C0
                        BNE MM_MAP_RANGE_PRINT
                        LDA #$DF
                        STA MM_MAP_RANGE_END+1
MM_MAP_RANGE_PRINT:       JSR MM_MAP_RANGE_PREFIX
                        JSR MM_MAP_DESCRIPTION
                        JSR MM_MAP_ACCESS
                        LDA MM_MAP_KIND
                        CMP #'S'
                        BEQ MM_MAP_RANGE_TAIL
                        CMP #'P'
                        BEQ MM_LEGACY_LONG_1090
                        JMP MM_MAP_ROW_ADVANCE
MM_LEGACY_LONG_1090:
MM_MAP_RANGE_TAIL:
                        JSR MM_MAP_RECORD_TAIL
                        JMP MM_MAP_ROW_ADVANCE
MM_MAP_DETAIL_ROW:        LDA MM_MAPBANK
                        JSR MM_SPACE_NAME
                        LDA #':'
                        JSR MM_PUTC
                        LDA MM_MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        JSR MM_MAP_NIBBLE
                        JSR MM_MAP_SPACE
                        LDA MM_MAPSEC
                        JSR MM_HEX
                        LDA #$00
                        JSR MM_HEX
                        LDA #'-'
                        JSR MM_PUTC
                        LDA MM_MAPSEC
                        ORA #$0F
                        JSR MM_HEX
                        LDA #$FF
                        JSR MM_HEX
                        JSR MM_MAP_SPACE
                        LDA MM_MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA MM_MAP_STATUS,X
                        JSR MM_PUTC
                        JSR MM_MAP_SPACE
                        LDA MM_MAP_META
                        BEQ MM_MAP_WEAR_UNKNOWN
                        LDA MM_MAPBANK
                        ASL A
                        ASL A
                        ASL A
                        STX MM_BYTE
                        ORA MM_BYTE
                        STA MM_BYTE
                        ASL A
                        CLC
                        ADC MM_BYTE
                        TAX
                        LDA $671A,X
                        JSR MM_HEX
                        LDA $6719,X
                        JSR MM_HEX
                        LDA $6718,X
                        JSR MM_HEX
                        BRA MM_MAP_WEAR_DONE
MM_MAP_WEAR_UNKNOWN:     LDX #<MM_MAP_UNKNOWN_COUNT
                        LDY #>MM_MAP_UNKNOWN_COUNT
                        JSR MM_PRINT
MM_MAP_WEAR_DONE:         JSR MM_MAP_SPACE
                        JSR MM_MAP_DESCRIPTION
                        JSR MM_MAP_ACCESS
MM_MAP_ROW_ADVANCE:       LDA MM_MAPSEC
                        CLC
                        ADC #$10
                        STA MM_MAPSEC
                        BEQ MM_LEGACY_LONG_1158
                        JMP MM_MAP_ROWS
MM_LEGACY_LONG_1158:
MM_MAP_BANK_END:          JSR MM_NL
                        INC MM_MAPBANK
                        LDA MM_MAPBANK
                        CMP #$04
                        BEQ MM_LEGACY_LONG_1163
                        JMP MM_MAP_BANK
MM_LEGACY_LONG_1163:
                        LDA MM_MAP_VIEW
                        CMP #$01
                        BEQ MM_MAP_GRID_LEGEND
                        CMP #$03
                        BNE MM_MAP_ACCESS_NOTE
                        LDX #<MM_MAP_DETAIL_LEGEND_TEXT
                        LDY #>MM_MAP_DETAIL_LEGEND_TEXT
                        JSR MM_PRINT
                        BRA MM_MAP_ACCESS_NOTE
MM_MAP_GRID_LEGEND:
                        LDX #<MM_MAP_LEGEND_TEXT
                        LDY #>MM_MAP_LEGEND_TEXT
                        JSR MM_PRINT
MM_MAP_ACCESS_NOTE:        LDX #<MM_MAP_ACCESS_NOTE_TEXT
                        LDY #>MM_MAP_ACCESS_NOTE_TEXT
                        JSR MM_PRINT
                        LDA MM_MAP_ONCE
                        BEQ MM_MAP_TO_MENU
                        STZ MM_MAP_ONCE
                        LDA MM_RESIDENT
                        JSR MM_V2W_SELECT
                        JMP X28_C14
MM_MAP_TO_MENU:           JMP MM_BM_MENU

MM_MAP_IDENTIFY:          LDA MM_MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA #'.'
                        LDY MM_MAP_STATUS,X
                        CPY #'E'
                        BEQ MM_MAP_STORE_KIND
                        LDA #'U'
                        PHA
                        LDA MM_MAPBANK
                        CMP #3
                        BNE MM_RTC_MAP_OTHER
                        LDA MM_MAPSEC
                        CMP #$80
                        BEQ MM_JOURNAL_MAP_KIND
                        CMP #$90
                        BNE MM_RTC_MAP_OTHER
MM_JOURNAL_MAP_KIND:
                        PLA
                        LDA #'I'
                        STA MM_MAP_KIND
                        RTS
MM_RTC_MAP_OTHER:          PLA
MM_MAP_STORE_KIND:        STA MM_MAP_KIND
                        JSR MM_MAP_FIRMWARE
                        BCC MM_MF_NORMAL_KIND
                        RTS
MM_MF_NORMAL_KIND:
                        LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_IDENTIFY_RECORD
                        LDA MM_MAPSEC
                        CMP #$A0
                        BCC MM_MAP_IDENTIFY_RECORD
                        SEC
                        SBC #$A0
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        TAX
                        LDA MM_MAP_CODES,X
                        CPX #$03
                        BNE MM_MAP_STORE_RESERVED
                        LDY MM_MAP_STATUS+5
                        CPY #'E'
                        BNE MM_MAP_STORE_RESERVED
                        LDA #'j'
MM_MAP_STORE_RESERVED:    STA MM_MAP_KIND
                        RTS
MM_MAP_IDENTIFY_RECORD:   LDA MM_MAP_APP_OWNER
                        CMP #$FF
                        BEQ MM_MAP_IDENTIFY_SR
                        STZ MM_MAP_OWNER_END
                        STZ MM_MAP_OWNER_END+1
                        LDA #$FF
                        STA MM_MAP_APP_OWNER
MM_MAP_IDENTIFY_SR:       LDA MM_MAPSEC
                        CMP MM_MAP_OWNER_END+1
                        BCC MM_MAP_IDENTIFY_CONT
                        BNE MM_MAP_IDENTIFY_HEADER
                        LDA MM_MAP_OWNER_END
                        BNE MM_MAP_IDENTIFY_CONT
MM_MAP_IDENTIFY_HEADER:   STZ MM_SRC
                        LDA MM_MAPSEC
                        STA MM_SRC+1
                        JSR MM_MAP_RECORD_HEADER
                        BCC MM_MAP_IDENTIFY_APP
                        LDA #'S'
                        STA MM_MAP_KIND
                        RTS
MM_MAP_IDENTIFY_CONT:     LDA #'+'
                        STA MM_MAP_KIND
                        RTS
MM_MAP_IDENTIFY_APP:      JSR MM_MAP_APP_LOOKUP
                        BCS MM_MAP_IDENTIFY_DONE
MM_MAP_IDENTIFY_BOOT:     LDA MM_MAPSEC
                        CMP #$F0
                        BNE MM_MAP_IDENTIFY_DONE
                        JSR MM_MAP_APP_VECTORS
                        BCS MM_MAP_IDENTIFY_DONE
                        JSR X28_R13
                        CMP #$80
                        BCC MM_MAP_IDENTIFY_DONE
                        CMP #$FF
                        BNE MM_MAP_IDENTIFY_IS_BOOT
                        JSR X28_R14
                        CMP #$FF
                        BEQ MM_MAP_IDENTIFY_DONE
MM_MAP_IDENTIFY_IS_BOOT:  LDA #'K'
                        STA MM_MAP_KIND
MM_MAP_IDENTIFY_DONE:     RTS

MM_MAP_DESCRIPTION:      LDA MM_MAP_KIND
                        CMP #'F'
                        BNE MM_MF_NORMAL_DESCRIPTION
                        JMP MM_MF_DESCRIPTION
MM_MF_NORMAL_DESCRIPTION:
                        CMP #'I'
                        BNE MM_RTC_MAP_DESCRIPTION
                        LDX #<MM_RTC_OWNER_TEXT
                        LDY #>MM_RTC_OWNER_TEXT
                        JMP MM_PRINT
MM_RTC_MAP_DESCRIPTION:   LDA MM_MAP_KIND
                        CMP #'P'
                        BNE MM_LEGACY_LONG_1269
                        JMP MM_MAP_DESC_APP
MM_LEGACY_LONG_1269:
                        CMP #'V'
                        BNE MM_LEGACY_LONG_1271
                        JMP MM_MAP_DESC_VECTORS
MM_LEGACY_LONG_1271:
                        CMP #'S'
                        BEQ MM_MAP_DESC_RECORD
                        CMP #'+'
                        BEQ MM_MAP_DESC_CONT
                        CMP #'.'
                        BNE MM_LEGACY_LONG_1277
                        JMP MM_MAP_DESC_ERASED
MM_LEGACY_LONG_1277:
                        CMP #'K'
                        BNE MM_LEGACY_LONG_1279
                        JMP MM_MAP_DESC_BOOT
MM_LEGACY_LONG_1279:
                        LDA MM_MAPBANK
                        CMP #$03
                        BEQ MM_LEGACY_LONG_1282
                        JMP MM_MAP_DESC_UNKNOWN
MM_LEGACY_LONG_1282:
                        LDA MM_MAPSEC
                        CMP #$A0
                        BCC MM_MAP_DESC_UNKNOWN
                        SEC
                        SBC #$A0
                        LSR A
                        LSR A
                        LSR A
                        TAX
                        LDA MM_MAP_RESERVED+1,X
                        TAY
                        LDA MM_MAP_RESERVED,X
                        TAX
                        JSR MM_PRINT
                        LDA MM_MAPSEC
                        CMP #$C0
                        BCS MM_MAP_DESC_DONE
                        STZ V2_PTR
                        STA V2_PTR+1
                        STA BOOT_DEST
                        JSR X28_C11
                        BCC MM_MAP_DESC_INVALID
                        LDX #<MM_MAP_VALID_TEXT
                        LDY #>MM_MAP_VALID_TEXT
                        JSR MM_PRINT
                        LDY #$0B
MM_MAP_DESC_GENERATION:   JSR X28_R4
                        JSR MM_HEX
                        DEY
                        CPY #$07
                        BNE MM_MAP_DESC_GENERATION
                        LDA MM_MAPSEC
                        CMP BOOT_ACTIVE
                        BNE MM_MAP_DESC_DONE
                        LDX #<MM_MAP_ACTIVE_TEXT
                        LDY #>MM_MAP_ACTIVE_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_INVALID:      LDX #<MM_MAP_INVALID_TEXT
                        LDY #>MM_MAP_INVALID_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_RECORD:      LDX #<MM_MAP_RECORD_TEXT
                        LDY #>MM_MAP_RECORD_TEXT
                        JSR MM_PRINT
                        JMP MM_MAP_RECORD_LABEL
MM_MAP_DESC_CONT:        LDA MM_MAP_APP_OWNER
                        CMP #$FF
                        BEQ MM_MAP_DESC_SR_CONT
                        JSR MM_MAP_DESC_APP
                        BRA MM_MAP_DESC_CONT_TEXT
MM_MAP_DESC_SR_CONT:     JSR MM_MAP_DESC_RECORD
MM_MAP_DESC_CONT_TEXT:
                        LDX #<MM_MAP_CONTINUED_TEXT
                        LDY #>MM_MAP_CONTINUED_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_ERASED:      LDX #<MM_MAP_ERASED_TEXT
                        LDY #>MM_MAP_ERASED_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_BOOT:        LDX #<MM_MAP_BOOT_TEXT
                        LDY #>MM_MAP_BOOT_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_UNKNOWN:     LDX #<MM_MAP_UNKNOWN_TEXT
                        LDY #>MM_MAP_UNKNOWN_TEXT
                        JMP MM_PRINT
MM_MAP_DESC_DONE:        RTS
MM_MAP_ACCESS:
        LDA MM_MAPBANK
        LDX MM_MAPSEC
        LDY MM_MAPSEC
        JSR MS_RESERVED
        BCC MS_ACCESS_CONTINUE
        LDX #<MM_MAP_PROTECTED_TEXT
        LDY #>MM_MAP_PROTECTED_TEXT
        JMP MM_MAP_ACCESS_PRINT
MS_ACCESS_CONTINUE:
                        LDA MM_MAP_KIND
                        CMP #'F'
                        BNE MM_MF_NORMAL_ACCESS
                        LDX #<MM_MF_RESERVED_TEXT
                        LDY #>MM_MF_RESERVED_TEXT
                        BRA MM_MAP_ACCESS_PRINT
MM_MF_NORMAL_ACCESS:      LDX #<MM_MAP_WRITABLE_TEXT
                        LDY #>MM_MAP_WRITABLE_TEXT
                        LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_ACCESS_PRINT
                        LDA MM_MAPSEC
                        CMP #$80
                        BEQ MM_RTC_MAP_PROTECTED
                        CMP #$90
                        BEQ MM_RTC_MAP_PROTECTED
                        CMP #$A0
                        BCC MM_MAP_ACCESS_PRINT
MM_RTC_MAP_PROTECTED:     LDX #<MM_MAP_PROTECTED_TEXT
                        LDY #>MM_MAP_PROTECTED_TEXT
MM_MAP_ACCESS_PRINT:     JSR MM_PRINT
                        JMP MM_NL
MM_MAP_RANGE_PREFIX:     LDA MM_MAPBANK
                        JSR MM_SPACE_NAME
                        JSR MM_MAP_SPACE
                        LDA MM_MAP_START+1
                        JSR MM_HEX
                        LDA MM_MAP_START
                        JSR MM_HEX
                        LDA #'-'
                        JSR MM_PUTC
                        LDA MM_MAP_RANGE_END+1
                        JSR MM_HEX
                        LDA MM_MAP_RANGE_END
                        JSR MM_HEX
MM_MAP_SPACE:            LDA #' '
                        JMP MM_PUTC
MM_MAP_NIBBLE:           CMP #$0A
                        BCC MM_MAP_DIGIT
                        ADC #$06
MM_MAP_DIGIT:            CLC
                        ADC #'0'
                        JMP MM_PUTC
MM_MAP_RECORD_TAIL:      LDA MM_MAP_OWNER_END
                        STA MM_SRC
                        STA MM_MAP_START
                        LDA MM_MAP_OWNER_END+1
                        STA MM_SRC+1
                        STA MM_MAP_START+1
                        AND #$0F
                        ORA MM_SRC
                        BEQ MM_MAP_TAIL_DONE
                        LDA MM_SRC+1
                        ORA #$0F
                        STA MM_MAP_RANGE_END+1
                        LDA #$FF
                        STA MM_MAP_RANGE_END
MM_MAP_TAIL_SCAN:        JSR X28_R1
                        CMP #$FF
                        BNE MM_MAP_TAIL_DONE
                        INC MM_SRC
                        BNE MM_MAP_TAIL_SCAN
                        INC MM_SRC+1
                        LDA MM_SRC+1
                        AND #$0F
                        BNE MM_MAP_TAIL_SCAN
                        JSR MM_MAP_RANGE_PREFIX
                        LDA MM_MAP_KIND
                        CMP #'P'
                        BNE MM_MAP_TAIL_SR
                        JSR MM_MAP_DESC_APP_PAD
                        BRA MM_MAP_TAIL_ACCESS
MM_MAP_TAIL_SR:
                        JSR MM_MAP_DESC_ERASED
MM_MAP_TAIL_ACCESS:
                        JSR MM_MAP_ACCESS
MM_MAP_TAIL_DONE:        RTS

; The monitor prompt supports a one-shot RAM return for utility table calls.
MM_BM_TABLE:             LDX MM_INDEX
                        LDY #$01
                        LDA #'T'
                        STA V2_LINE
MM_BM_TABLE_COPY:        LDA MM_BM_LINE,X
                        STA V2_LINE,Y
                        BEQ MM_BM_TABLE_GO
                        INX
                        INY
                        CPY #$28
                        BNE MM_BM_TABLE_COPY
                        JMP MM_BM_BAD
MM_BM_TABLE_GO:          LDA #<MM_BM_TABLE_DONE
                        STA $7DFA
                        LDA #>MM_BM_TABLE_DONE
                        STA $7DFB
                        LDA #$54
                        STA $7DF9
                        LDA MM_RESIDENT
                        JSR MM_V2W_SELECT
                        JMP X28_C15
MM_BM_TABLE_DONE:        JMP MM_BM_MENU

MM_MAP_CODES:            DB "ABJJXR"
MM_MAP_GRID_TEXT:        DB "   8  9  A  B  C  D  E  F",$0D,$0A,0
MM_MAP_RANGES_TEXT:      DB "BANK RANGE CONTENTS ACCESS",$0D,$0A,0
MM_MAP_DETAIL_TEXT:      DB "SECTOR RANGE E/U ERASE-ATTEMPTS CONTENTS ACCESS",$0D,$0A,0
MM_MAP_LEGEND_TEXT:      DB "I RTC/I2C; S record; + continued; U untagged; . erased; K boot-vector",$0D,$0A
                        DB "B0:8-D source arena; B1:9 source; A DEBUG.",$0D,$0A
                       DB "F firmware assets; P application; V application-bank vectors",$0D,$0A
                       DB "A/B monitors; J/j journal used/erased; X extension; R recovery",$0D,$0A
                       DB "B2:D800-E1FF status; B2:F local/board + VERSION.",$0D,$0A
                       DB "* active.",$0D,$0A,0
MM_MAP_DETAIL_LEGEND_TEXT: DB "E = all FF; U = programmed. ERASE-ATTEMPTS are hexadecimal.",$0D,$0A,0
MM_MAP_ACCESS_NOTE_TEXT:   DB "Reserved: B0:8-D; B1:9/A/E/F; B2; B3.",$0D,$0A,0
MM_MAP_ERASED_TEXT:      DB "Erased",0
MM_MAP_VALID_TEXT:       DB " VALID gen ",0
MM_MAP_INVALID_TEXT:     DB " INVALID",0
MM_MAP_ACTIVE_TEXT:      DB " active",0
MM_MAP_WRITABLE_TEXT:    DB " writable",0
MM_MAP_PROTECTED_TEXT:   DB " protected",0
MM_MAP_UNKNOWN_COUNT:    DB "??????",0

MM_BM_QUIT:                JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_1458
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1458:
                        LDA MM_TOUCHED
                        BNE MM_QUIT_REFUSE
                        LDA MM_RESIDENT
                        JSR MM_V2W_SELECT
                        JMP X28_C14
MM_QUIT_REFUSE:            LDX #<MM_QUIT_TEXT
                        LDY #>MM_QUIT_TEXT
                        JMP MM_MESSAGE
MM_BM_BOOT:                JSR MM_BANK
                        BCS MM_LEGACY_LONG_1468
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1468:
                        CMP #$FF
                        BNE MM_LEGACY_LONG_1470
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1470:
                        STA MM_MAPBANK
                        JSR MM_ENDLINE
                        BCS MM_LEGACY_LONG_1473
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1473:
                        LDA MM_MAPBANK
                        JSR MM_V2W_SELECT
                        JSR X28_R14
                        STA MM_DST
                        JSR X28_R13
                        STA MM_DST+1
                        CMP #$80
                        BCS MM_LEGACY_LONG_1481
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1481:
                        CMP #$FF
                        BNE MM_BOOT_GO
                        LDA MM_DST
                        CMP #$FF
                        BNE MM_LEGACY_LONG_1486
                        JMP MM_BM_BAD
MM_LEGACY_LONG_1486:
MM_BOOT_GO:                SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDA MM_DST
                        STA X28_CALL+1
                        LDA MM_DST+1
                        STA X28_CALL+2
                        LDA MM_MAPBANK
                        STA X28_CALL_BANK
                        JMP X28_TAIL

; Parser: uppercase hexadecimal, inclusive ranges, space R or bank 0-3.
MM_SPACES:                 LDX MM_INDEX
MM_SPACE_LOOP:             LDA MM_BM_LINE,X
                        CMP #' '
                        BNE MM_SPACE_DONE
                        INX
                        BRA MM_SPACE_LOOP
MM_SPACE_DONE:             STX MM_INDEX
                        CMP #$00
                        RTS
MM_ENDLINE:                JSR MM_SPACES
                        BNE MM_PARSE_NO
                        SEC
                        RTS
MM_BANK:                   JSR MM_SPACES
                        CMP #'R'
                        BEQ MM_BANK_RAM
                        SEC
                        SBC #'0'
                        CMP #$04
                        BCS MM_PARSE_NO
                        BRA MM_BANK_END
MM_BANK_RAM:               LDA #$FF
MM_BANK_END:               PHA
                        INC MM_INDEX
                        LDX MM_INDEX
                        LDA MM_BM_LINE,X
                        BEQ MM_BANK_OK
                        CMP #' '
                        BNE MM_BANK_BAD
MM_BANK_OK:                PLA
                        SEC
                        RTS
MM_BANK_BAD:               PLA
MM_PARSE_NO:               CLC
                        RTS
MM_NUMBER:                 JSR MM_SPACES
                        STZ MM_NUM
                        STZ MM_NUM+1
                        STZ MM_DIGITS
MM_NUMBER_LOOP:            LDX MM_INDEX
                        LDA MM_BM_LINE,X
                        JSR MM_NIBBLE
                        BCC MM_NUMBER_END
                        STA MM_BYTE
                        INC MM_DIGITS
                        LDA MM_DIGITS
                        CMP #$05
                        BCS MM_PARSE_NO
                        ASL MM_NUM
                        ROL MM_NUM+1
                        ASL MM_NUM
                        ROL MM_NUM+1
                        ASL MM_NUM
                        ROL MM_NUM+1
                        ASL MM_NUM
                        ROL MM_NUM+1
                        LDA MM_NUM
                        ORA MM_BYTE
                        STA MM_NUM
                        INC MM_INDEX
                        BRA MM_NUMBER_LOOP
MM_NUMBER_END:             LDA MM_DIGITS
                        BEQ MM_PARSE_NO
                        SEC
                        RTS
MM_RANGE:                  JSR MM_NUMBER
                        BCC MM_PARSE_NO
                        LDA MM_NUM
                        STA MM_FIRST
                        STA MM_LAST
                        LDA MM_NUM+1
                        STA MM_FIRST+1
                        STA MM_LAST+1
                        LDX MM_INDEX
                        LDA MM_BM_LINE,X
                        CMP #'-'
                        BNE MM_RANGE_ORDER
                        INC MM_INDEX
                        JSR MM_NUMBER
                        BCC MM_PARSE_NO
                        LDA MM_NUM
                        STA MM_LAST
                        LDA MM_NUM+1
                        STA MM_LAST+1
MM_RANGE_ORDER:            LDA MM_LAST
                        CMP MM_FIRST
                        LDA MM_LAST+1
                        SBC MM_FIRST+1
                        RTS
MM_SCALE_RANGE:            LDA MM_SB
                        CMP #$FF
                        BEQ MM_SCALE_DONE
                        LDA MM_FIRST+1
                        ORA MM_LAST+1
                        BNE MM_SCALE_DONE
                        LDA MM_FIRST
                        CMP #$08
                        BCC MM_SCALE_DONE
                        LDA MM_LAST
                        CMP #$10
                        BCS MM_SCALE_DONE
                        LDA MM_FIRST
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA MM_FIRST+1
                        STZ MM_FIRST
                        LDA MM_LAST
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        ORA #$0F
                        STA MM_LAST+1
                        LDA #$FF
                        STA MM_LAST
MM_SCALE_DONE:             RTS

MM_READLINE:               STZ MM_LINELEN
                        STZ MM_OVERFLOW
MM_LINE_WAIT:              JSR MM_GETC
                        CMP #$1B
                        BEQ MM_LINE_CANCEL
                        CMP #$03
                        BEQ MM_LINE_CANCEL
                        CMP #$0A
                        BEQ MM_LINE_WAIT
                        CMP #$0D
                        BEQ MM_LINE_DONE
                        CMP #$08
                        BEQ MM_LINE_BACK
                        CMP #$7F
                        BEQ MM_LINE_BACK
                        CMP #$20
                        BCC MM_LINE_WAIT
                        CMP #'a'
                        BCC MM_LINE_CHAR
                        CMP #'z'+1
                        BCS MM_LINE_CHAR
                        AND #$DF
MM_LINE_CHAR:              LDX MM_LINELEN
                        CPX #$4F
                        BCS MM_LINE_FULL
                        STA MM_BM_LINE,X
                        INC MM_LINELEN
                        JSR MM_PUTC
                        JMP MM_LINE_WAIT
MM_LINE_FULL:              LDA #$01
                        STA MM_OVERFLOW
                        JMP MM_LINE_WAIT
MM_LINE_BACK:              LDA MM_LINELEN
                        BEQ MM_LINE_WAIT
                        DEC MM_LINELEN
                        LDA #$08
                        JSR MM_PUTC
                        LDA #' '
                        JSR MM_PUTC
                        LDA #$08
                        JSR MM_PUTC
                        JMP MM_LINE_WAIT
MM_LINE_DONE:              LDX MM_LINELEN
                        STZ MM_BM_LINE,X
                        JSR MM_NL
                        LDA MM_OVERFLOW
                        BNE MM_LINE_CANCEL
                        SEC
                        RTS
MM_LINE_CANCEL: JSR B29_CANCEL_HOOK
            CLC
                        RTS
MM_PRINT:                  STX MM_TXT
                        STY MM_TXT+1
                        LDY #$00
MM_PRINT_BYTE:             LDA (MM_TXT),Y
                        BEQ MM_PRINT_DONE
                        JSR MM_PUTC
                        INY
                        BNE MM_PRINT_BYTE
                        INC MM_TXT+1
                        BRA MM_PRINT_BYTE
MM_PRINT_DONE:             RTS
MM_SPACE_NAME:             CMP #$FF
                        BEQ MM_SPACE_RAM
                        PHA
                        LDA #'B'
                        JSR MM_PUTC
                        PLA
                        ORA #'0'
                        JMP MM_PUTC
MM_SPACE_RAM:              LDA #'R'
                        JMP MM_PUTC

; Local RAM flash engine. It never executes ROM or uses the optional E code.
MM_V2W_SELECT:
        STA X28_BANK
        TAX
        LDA $7FEC
        AND #$11
        ORA MM_BANK_BITS,X
        RTS
MM_BANK_BITS DB $CC,$CE,$EC,$EE
MM_MAP_STATUS EQU $6128
MM_MAP_OWNER_END EQU $6130
MM_MAP_OWNER_LABEL EQU $6132
MM_MAP_RECORD_HEADER:     LDY #$00
                        JSR X28_R3
                        CMP #'S'
                        BEQ MM_LEGACY_LONG_1701
                        JMP MM_MAP_HEADER_BAD
MM_LEGACY_LONG_1701:
                        INY
                        JSR X28_R3
                        CMP #'R'
                        BEQ MM_LEGACY_LONG_1705
                        JMP MM_MAP_HEADER_BAD
MM_LEGACY_LONG_1705:
                        INY
                        JSR X28_R3
                        CMP #$01
                        BNE MM_MAP_HEADER_BAD
                        INY
                        JSR X28_R3
                        CMP #$3F
                        BNE MM_MAP_HEADER_BAD
                        LDY #$06
                        JSR X28_R3
                        STA MM_CNT
                        INY
                        JSR X28_R3
                        STA MM_CNT+1
                        ORA MM_CNT
                        BEQ MM_MAP_HEADER_BAD
                        LDA MM_CNT
                        CLC
                        ADC #$18
                        STA MM_CNT
                        LDA MM_CNT+1
                        ADC MM_SRC+1
                        BCS MM_MAP_HEADER_BAD
                        STA MM_CNT+1
                        CMP #$E0
                        BCC MM_MAP_HEADER_LIMIT
                        BNE MM_MAP_HEADER_BAD
                        LDA MM_CNT
                        BNE MM_MAP_HEADER_BAD
MM_MAP_HEADER_LIMIT:      LDA MM_MAPBANK
                        CMP #$03
                        BNE MM_MAP_HEADER_LABEL
                        LDA MM_CNT+1
                        CMP #$A0
                        BCC MM_MAP_HEADER_LABEL
                        BNE MM_MAP_HEADER_BAD
                        LDA MM_CNT
                        BNE MM_MAP_HEADER_BAD
MM_MAP_HEADER_LABEL:      LDY #$08
MM_MAP_HEADER_CHAR:       JSR X28_R3
                        BEQ MM_MAP_HEADER_PAD
                        CMP #$21
                        BCC MM_MAP_HEADER_BAD
                        CMP #$7F
                        BCS MM_MAP_HEADER_BAD
                        INY
                        CPY #$18
                        BNE MM_MAP_HEADER_CHAR
                        BRA MM_MAP_HEADER_VALID
MM_MAP_HEADER_PAD:        JSR X28_R3
                        BNE MM_MAP_HEADER_BAD
                        INY
                        CPY #$18
                        BNE MM_MAP_HEADER_PAD
MM_MAP_HEADER_VALID:      LDA MM_CNT
                        STA MM_MAP_OWNER_END
                        LDA MM_CNT+1
                        STA MM_MAP_OWNER_END+1
                        LDA #$08
                        STA MM_MAP_OWNER_LABEL
                        LDA MM_SRC+1
                        STA MM_MAP_OWNER_LABEL+1
                        SEC
                        RTS
MM_MAP_HEADER_BAD:        CLC
                        RTS
MM_MAP_RECORD_LABEL:      LDA MM_MAP_OWNER_LABEL
                        STA MM_SRC
                        LDA MM_MAP_OWNER_LABEL+1
                        STA MM_SRC+1
                        LDY #$00
MM_MAP_RECORD_CHAR:       JSR X28_R3
                        BEQ MM_MAP_RECORD_DONE
                        JSR MM_PUTC
                        INY
                        CPY #$10
                        BNE MM_MAP_RECORD_CHAR
MM_MAP_RECORD_DONE:       RTS

MM_MAP_RESERVED:          DW MM_MAP_SLOT_A,MM_MAP_SLOT_B,MM_MAP_JOURNAL,MM_MAP_JOURNAL,MM_MAP_EXTENSION,MM_MAP_RECOVERY
; The ACCESS column carries protection; avoid duplicating it in CONTENTS.
MM_MAP_SLOT_A:            DB "Monitor slot A",0
MM_MAP_SLOT_B:            DB "Monitor slot B",0
MM_MAP_JOURNAL:           DB "Config/wear journal [reserved]",0
MM_MAP_EXTENSION:         DB "S/R/T and preserved bytes",0
MM_MAP_RECOVERY:          DB "Fixed boot/recovery and vectors",0
MM_MAP_UNKNOWN_TEXT:      DB "Used; owner untagged",0
MM_MAP_BOOT_TEXT:         DB "Boot image; see RESET vector",0
MM_MAP_RECORD_TEXT:       DB "SR ",0
MM_MAP_CONTINUED_TEXT:    DB " (continued)",0

MM_MAP_CRC_INIT EQU $FAB4
MM_MAP_CRC_BYTE EQU $FABD
; Compact cache: eight 24-byte rows, wholly inside the existing state reservation.
; Name[12], bank, conflict flag, start[2], exclusive end[2], unused[6].
MM_MAP_APP_OWNER EQU $613D
MM_MAP_APP_SLOT EQU $613E
MM_MAP_APP_OFFSET EQU $613F
MM_MAP_APPS EQU $6140

MM_MAP_APP_PREPARE:       LDX #$00
MM_MAP_APP_CLEAR:         STZ MM_MAP_APPS,X
                        INX
                        CPX #$C0
                        BNE MM_MAP_APP_CLEAR
                        LDA #$03
                        JSR MM_V2W_SELECT
                        LDA #$03
                        STA V2_SELECTED
                        LDX #$03
MM_MAP_APP_EXT_HEADER:    JSR X28_R15
                        CMP MM_MAP_APP_EXT_ID,X
                        BEQ MM_LEGACY_LONG_1818
                        JMP MM_MAP_APP_PREP_DONE
MM_LEGACY_LONG_1818:
                        DEX
                        BPL MM_MAP_APP_EXT_HEADER
                        LDX #$07
MM_MAP_APP_CAPABILITY:    JSR X28_R16
                        CMP MM_MAP_APP_CAP_ID,X
                        BEQ MM_LEGACY_LONG_1824
                        JMP MM_MAP_APP_PREP_DONE
MM_LEGACY_LONG_1824:
                        DEX
                        BPL MM_MAP_APP_CAPABILITY
                        LDX #$03
MM_MAP_APP_TABLE_HEADER:  JSR X28_R17
                        CMP MM_MAP_APP_TABLE_ID,X
                        BNE MM_MAP_APP_PREP_DONE
                        DEX
                        BPL MM_MAP_APP_TABLE_HEADER
                        JSR X28_R18
                        CMP #$4C
                        BNE MM_MAP_APP_PREP_DONE
                        JSR X28_C12
                        STZ MM_SRC
                        LDA #$E0
                        STA MM_SRC+1
MM_MAP_APP_EXT_CRC:       JSR X28_R1
                        JSR X28_C13
                        INC MM_SRC
                        BNE MM_MAP_APP_EXT_CRC
                        INC MM_SRC+1
                        LDA MM_SRC+1
                        CMP #$E8
                        BNE MM_MAP_APP_EXT_CRC
                        LDA J_CRC
                        ORA J_CRC+1
                        BNE MM_MAP_APP_PREP_DONE
                        STZ MM_MAP_APP_SLOT
                        STZ MM_MAP_APP_OFFSET
MM_MAP_APP_PROBE:         JSR MM_CHECK_CANCEL
                        LDA MM_MAP_APP_SLOT
                        JSR X28_C10
                        BCC MM_MAP_APP_NEXT
                        LDA MM_MAP_APP_OFFSET
                        CLC
                        ADC #$40
                        STA MM_SRC
                        LDA #$61
                        STA MM_SRC+1
                        LDY #$0F
MM_MAP_APP_COPY:          LDA $7D90,Y
                        STA (MM_SRC),Y
                        DEY
                        BPL MM_MAP_APP_COPY
                        LDY #$0D
                        LDA #$00
                        STA (MM_SRC),Y
                        LDA $7DC4
                        LDY #$10
                        STA (MM_SRC),Y
                        INY
                        LDA $7DC5
                        STA (MM_SRC),Y
MM_MAP_APP_NEXT:          LDA MM_MAP_APP_OFFSET
                        CLC
                        ADC #$18
                        STA MM_MAP_APP_OFFSET
                        INC MM_MAP_APP_SLOT
                        LDA MM_MAP_APP_SLOT
                        CMP #$08
                        BNE MM_MAP_APP_PROBE
                        JSR MM_MAP_APP_CONFLICTS
MM_MAP_APP_PREP_DONE:     RTS

; Shared sectors are ambiguous for a sector map. Suppress every conflicting
; descriptor, even if its exact byte extent does not overlap another image.
MM_MAP_APP_CONFLICTS:     LDX #$00
MM_MAP_APP_OUTER:         TXA
                        CLC
                        ADC #$18
                        TAY
MM_MAP_APP_PAIR:          CPY #$C0
                        BEQ MM_MAP_APP_OUTER_NEXT
                        LDA MM_MAP_APPS,X
                        BEQ MM_MAP_APP_PAIR_NEXT
                        LDA MM_MAP_APPS,Y
                        BEQ MM_MAP_APP_PAIR_NEXT
                        LDA MM_MAP_APPS+12,X
                        CMP MM_MAP_APPS+12,Y
                        BNE MM_MAP_APP_PAIR_NEXT
                        LDA MM_MAP_APPS+15,X
                        AND #$F0
                        STA MM_BYTE
                        LDA MM_MAP_APPS+17,Y
                        PHA
                        LDA MM_MAP_APPS+16,Y
                        BNE MM_MAP_APP_Y_END
                        PLA
                        DEC A
                        BRA MM_MAP_APP_Y_LAST
MM_MAP_APP_Y_END:         PLA
MM_MAP_APP_Y_LAST:        AND #$F0
                        CMP MM_BYTE
                        BCC MM_MAP_APP_PAIR_NEXT
                        LDA MM_MAP_APPS+15,Y
                        AND #$F0
                        STA MM_BYTE
                        LDA MM_MAP_APPS+17,X
                        PHA
                        LDA MM_MAP_APPS+16,X
                        BNE MM_MAP_APP_X_END
                        PLA
                        DEC A
                        BRA MM_MAP_APP_X_LAST
MM_MAP_APP_X_END:         PLA
MM_MAP_APP_X_LAST:        AND #$F0
                        CMP MM_BYTE
                        BCC MM_MAP_APP_PAIR_NEXT
                        LDA #$01
                        STA MM_MAP_APPS+13,X
                        STA MM_MAP_APPS+13,Y
MM_MAP_APP_PAIR_NEXT:     TYA
                        CLC
                        ADC #$18
                        TAY
                        BRA MM_MAP_APP_PAIR
MM_MAP_APP_OUTER_NEXT:    TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MM_MAP_APP_OUTER
                        RTS

MM_MAP_APP_LOOKUP:        LDX #$00
MM_MAP_APP_FIND:          LDA MM_MAP_APPS,X
                        BEQ MM_MAP_APP_FIND_NEXT
                        LDA MM_MAP_APPS+13,X
                        BNE MM_MAP_APP_FIND_NEXT
                        LDA MM_MAP_APPS+12,X
                        CMP MM_MAPBANK
                        BNE MM_MAP_APP_FIND_NEXT
                        LDA MM_MAP_APPS+15,X
                        AND #$F0
                        CMP MM_MAPSEC
                        BCC MM_MAP_APP_CHECK_END
                        BNE MM_MAP_APP_FIND_NEXT
MM_MAP_APP_CHECK_END:     LDA MM_MAP_APPS+17,X
                        PHA
                        LDA MM_MAP_APPS+16,X
                        BNE MM_MAP_APP_END_HIGH
                        PLA
                        DEC A
                        BRA MM_MAP_APP_LAST_HIGH
MM_MAP_APP_END_HIGH:      PLA
MM_MAP_APP_LAST_HIGH:     AND #$F0
                        CMP MM_MAPSEC
                        BCC MM_MAP_APP_FIND_NEXT
                        STX MM_MAP_APP_OWNER
                        LDA MM_MAP_APPS+16,X
                        STA MM_MAP_OWNER_END
                        LDA MM_MAP_APPS+17,X
                        STA MM_MAP_OWNER_END+1
                        TXA
                        CLC
                        ADC #$40
                        STA MM_MAP_OWNER_LABEL
                        LDA #$61
                        STA MM_MAP_OWNER_LABEL+1
                        LDA #'+'
                        STA MM_MAP_KIND
                        LDA MM_MAP_APPS+15,X
                        AND #$F0
                        CMP MM_MAPSEC
                        BNE MM_MAP_APP_FOUND
                        LDA #'P'
                        STA MM_MAP_KIND
MM_MAP_APP_FOUND:         SEC
                        RTS
MM_MAP_APP_FIND_NEXT:     TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MM_MAP_APP_FIND
                        CLC
                        RTS

MM_MAP_APP_VECTORS:       LDX #$00
MM_MAP_APP_VECTOR_NEXT:   LDA MM_MAP_APPS,X
                        BEQ MM_MAP_APP_VECTOR_SKIP
                        LDA MM_MAP_APPS+13,X
                        BNE MM_MAP_APP_VECTOR_SKIP
                        LDA MM_MAP_APPS+12,X
                        CMP MM_MAPBANK
                        BNE MM_MAP_APP_VECTOR_SKIP
                        LDA #'V'
                        STA MM_MAP_KIND
                        SEC
                        RTS
MM_MAP_APP_VECTOR_SKIP:   TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MM_MAP_APP_VECTOR_NEXT
                        CLC
                        RTS

; Show any bytes preceding a nonaligned app separately, preserving exact extent.
MM_MAP_APP_PREFIX:        LDA MM_MAP_START
                        BNE MM_MAP_APP_PREFIX_SHOW
                        LDA MM_MAP_START+1
                        CMP MM_MAPSEC
                        BEQ MM_MAP_APP_PREFIX_DONE
MM_MAP_APP_PREFIX_SHOW:   LDA MM_MAP_START+1
                        PHA
                        LDA MM_MAP_START
                        PHA
                        LDA MM_MAP_RANGE_END+1
                        PHA
                        LDA MM_MAP_RANGE_END
                        PHA
                        SEC
                        LDA MM_MAP_START
                        SBC #$01
                        STA MM_MAP_RANGE_END
                        LDA MM_MAP_START+1
                        SBC #$00
                        STA MM_MAP_RANGE_END+1
                        STZ MM_MAP_START
                        STZ MM_SRC
                        LDA MM_MAPSEC
                        STA MM_MAP_START+1
                        STA MM_SRC+1
MM_MAP_APP_PREFIX_SCAN:   JSR X28_R1
                        CMP #$FF
                        BNE MM_MAP_APP_PREFIX_USED
                        LDA MM_SRC+1
                        CMP MM_MAP_RANGE_END+1
                        BNE MM_MAP_APP_PREFIX_ADV
                        LDA MM_SRC
                        CMP MM_MAP_RANGE_END
                        BEQ MM_MAP_APP_PREFIX_ERASED
MM_MAP_APP_PREFIX_ADV:    INC MM_SRC
                        BNE MM_MAP_APP_PREFIX_SCAN
                        INC MM_SRC+1
                        BRA MM_MAP_APP_PREFIX_SCAN
MM_MAP_APP_PREFIX_ERASED: JSR MM_MAP_RANGE_PREFIX
                        JSR MM_MAP_DESC_ERASED
                        BRA MM_MAP_APP_PREFIX_ACCESS
MM_MAP_APP_PREFIX_USED:   JSR MM_MAP_RANGE_PREFIX
                        JSR MM_MAP_DESC_UNKNOWN
MM_MAP_APP_PREFIX_ACCESS: JSR MM_MAP_ACCESS
                        PLA
                        STA MM_MAP_RANGE_END
                        PLA
                        STA MM_MAP_RANGE_END+1
                        PLA
                        STA MM_MAP_START
                        PLA
                        STA MM_MAP_START+1
MM_MAP_APP_PREFIX_DONE:   RTS

MM_MAP_DESC_APP:          LDX #<MM_MAP_APP_TEXT
                        LDY #>MM_MAP_APP_TEXT
                        JSR MM_PRINT
                        JMP MM_MAP_RECORD_LABEL
MM_MAP_DESC_APP_PAD:      LDX #<MM_MAP_APP_PAD_TEXT
                        LDY #>MM_MAP_APP_PAD_TEXT
                        JSR MM_PRINT
                        JSR MM_MAP_RECORD_LABEL
                        LDX #<MM_MAP_APP_PAD_END
                        LDY #>MM_MAP_APP_PAD_END
                        JMP MM_PRINT
MM_MAP_DESC_VECTORS:      LDX #<MM_MAP_APP_VECTOR_TEXT
                        LDY #>MM_MAP_APP_VECTOR_TEXT
                        JMP MM_PRINT

MM_MAP_APP_EXT_ID:        DB "NA",$01,$3F
MM_MAP_APP_CAP_ID:        DB "MP",$01,$08,$11,$E0,$90,$7D
MM_MAP_APP_TABLE_ID:      DB "AT",$01,$08
MM_MAP_APP_TEXT:          DB "APP ",0
MM_MAP_APP_PAD_TEXT:      DB "Erased; ",0
MM_MAP_APP_PAD_END:       DB " sector padding",0
MM_MAP_APP_VECTOR_TEXT:   DB "Application-bank vectors",0

MM_RTC_OWNER_TEXT: DB "RTC/I2C or journal services",0
MM_RTC_RAM_TEXT: DB "MAINT RAM: 5000-63FF buffers/state; 7B90-7BFF gateway",$0D,$0A,0
MM_TITLE:                  DB $0D,$0A,"STR8-N BANK MAINT 2.4",$0D,$0A,0
MM_PROMPT:                 DB $0D,$0A,"BM> ",0
MM_HELP:                   DB "NAME [1-8 characters | CLEAR] (YES required)",13,10
                        DB "X bank NAME S NAME / X S NAME bank NAME",13,10
                        DB $0D,$0A,"BANKS AND MEMORY",$0D,$0A
                        DB " M [1|2|3] Grid / ranges (default) / wear",$0D,$0A
                        DB " E bank 8[-F] Erase sectors",$0D,$0A
                        DB " C src range dst start Copy RAM or flash",$0D,$0A
                        DB " V src range dst start Compare RAM or flash",$0D,$0A
                        DB $0D,$0A,"EDITOR BUFFER (4 KiB)",$0D,$0A
                        DB " R src range Read into buffer",$0D,$0A
                        DB " D [offset[-end]] Display buffer",$0D,$0A
                        DB " P offset byte ... Patch bytes",$0D,$0A
                        DB " F offset[-end] byte Fill bytes",$0D,$0A
                        DB " N length byte Create filled buffer",$0D,$0A
                        DB " K Buffer CRC16",$0D,$0A
                        DB " W dst start Write buffer and verify",$0D,$0A
                        DB $0D,$0A,"CONTROL",$0D,$0A
                        DB " T [bank|first-last] Stored records",$0D,$0A
                        DB " J bank Boot selected bank",$0D,$0A
                        DB " Q Return to monitor",$0D,$0A
                        DB " ? Show this menu",$0D,$0A
                        DB $0D,$0A," src/dst: R = RAM, 0-3 = flash bank. Numbers are hex.",$0D,$0A
                        DB " Flash 8-F = sectors. Editor offsets: 000-FFF.",$0D,$0A
                        DB " Writes need Y. Reserved source/firmware protected.",$0D,$0A,0
MM_BAD:                    DB "INVALID / PROTECTED RANGE",$0D,$0A,0
MM_CANCEL:                 DB "CANCELED (completed sectors retained)",$0D,$0A,0
MM_FAILED:                 DB "WRITE/VERIFY FAILED; STOPPED",$0D,$0A,0
MM_DONE:                   DB "VERIFIED",$0D,$0A,0
MM_PLAN_TEXT:              DB "PLAN ",0
MM_DEST_TEXT:              DB $0D,$0A,"DEST ",0
MM_CONFIRM_TEXT:           DB $0D,$0A,"WRITE? TYPE Y> ",0
MM_B3F_TEXT:               DB "B3:F includes boot code/config/vectors. TYPE B3F> ",0
MM_MATCH_TEXT:             DB "MATCH",$0D,$0A,0
MM_DIFFERENT_TEXT:         DB "DIFFERENT AT DEST ",0
MM_BUFFER_TEXT:            DB "BUFFER LOADED; D/P/F/K then W to commit",$0D,$0A,0
MM_EDITED_TEXT:            DB "BUFFER CHANGED; W to commit",$0D,$0A,0
MM_CRC_TEXT:               DB "CRC16-CCITT-FALSE ",0
MM_MAP_HEADER:             DB "SECTORS 8 9 A B C D E F (E=erased U=used)",$0D,$0A
                        DB "B3: A/B monitors; C/D journals; E S/R/T; F recovery (protected)",$0D,$0A,0
MM_RESET_TEXT:             DB " RESET ",0
MM_QUIT_TEXT:              DB "RESIDENT F CHANGED; stay in RAM or J bank",$0D,$0A,0
; X bank NAME S NAME / X S NAME bank NAME. Verified copy, source retained.
; Fixed version-paired SRAM hooks are private to this foreground utility.
MM_X_REQ EQU $6300
MM_X_SOURCE_NAME EQU $6320
MM_X_META EQU $6330
MM_X_HEAD EQU $6340
MM_X_BANK EQU $6380
MM_X_DIRECTION EQU $6381
MM_X_FLASH EQU $6382
MM_X_PAYLOAD EQU $6384
MM_X_DEST EQU $6386
MM_X_FOUND EQU $6388
MM_X_STARTED EQU $6389
MM_X_OFFSET EQU $638A
MM_X_SCAN EQU $638C
MM_X_BP EQU $638E
MM_X_VALUE EQU $6390
MM_X_INDEX EQU $6391
MM_X_ERROR EQU $6392
MM_X_COPY:
        LDX #31
MM_X_ZERO:
        STZ MM_X_REQ,X
        DEX
                        BPL MM_X_ZERO
        STZ MM_X_DIRECTION
        STZ MM_X_STARTED
        JSR MM_X_SPACE
                        BCS MM_X_LONG_28
                        JMP MM_X_BAD
MM_X_LONG_28:
        STA MM_X_BANK
        CMP #$FF
                        BNE MM_X_PARSE_SOURCE
        INC MM_X_DIRECTION
MM_X_PARSE_SOURCE:
        LDA #<MM_X_SOURCE_NAME
        STA MM_TXT
        LDA #>MM_X_SOURCE_NAME
        STA MM_TXT+1
        JSR MM_X_NAME
                        BCS MM_X_LONG_39
                        JMP MM_X_BAD
MM_X_LONG_39:
        JSR MM_X_SPACE
                        BCS MM_X_LONG_41
                        JMP MM_X_BAD
MM_X_LONG_41:
        LDX MM_X_DIRECTION
                        BNE MM_X_DEST_FLASH
        CMP #$FF
                        BEQ MM_X_LONG_45
                        JMP MM_X_BAD
MM_X_LONG_45:
                        BRA MM_X_PARSE_DEST
MM_X_DEST_FLASH:
        CMP #$FF
                        BNE MM_X_LONG_49
                        JMP MM_X_BAD
MM_X_LONG_49:
        STA MM_X_BANK
MM_X_PARSE_DEST:
        LDA #<MM_X_REQ+8
        STA MM_TXT
        LDA #>MM_X_REQ+8
        STA MM_TXT+1
        JSR MM_X_NAME
                        BCS MM_X_LONG_57
                        JMP MM_X_BAD
MM_X_LONG_57:
        JSR MM_ENDLINE
                        BCS MM_X_LONG_59
                        JMP MM_X_BAD
MM_X_LONG_59:
        LDX #15
MM_X_KEEP_DEST_NAME:
        LDA MM_X_REQ+8,X
        STA MM_X_DEST_NAME,X
        DEX
                        BPL MM_X_KEEP_DEST_NAME
        ; MAINT remains flash-only, on both sides of the transfer.
        LDX #4
MM_X_MAINT_SOURCE:
        LDA MM_X_SOURCE_NAME,X
        CMP MM_X_MAINT_NAME,X
                        BNE MM_X_CHECK_DEST
        DEX
                        BPL MM_X_MAINT_SOURCE
        JMP MM_X_BAD
MM_X_CHECK_DEST:
        LDA MM_X_DIRECTION
        BEQ MM_X28_X_DEST_OK
        LDA MM_X_BANK
        CMP #2
        BNE MM_X28_X_DEST_OK
        JMP MM_X_BAD
MM_X28_X_DEST_OK:
        LDX #4
MM_X_MAINT_DEST:
        LDA MM_X_REQ+8,X
        CMP MM_X_MAINT_NAME,X
                        BNE MM_X_DISCOVER
        DEX
                        BPL MM_X_MAINT_DEST
        JMP MM_X_BAD
MM_X_DISCOVER:
        LDX #3
MM_X_EXEC_CHECK:
        JSR X28_R0
        CMP MM_X_EXEC_MAGIC,X
                        BEQ MM_X_LONG_89
                        JMP MM_X_FAIL
MM_X_LONG_89:
        DEX
                        BPL MM_X_EXEC_CHECK
        JSR SM_INIT
                        BCS MM_X_LONG_94
                        JMP MM_X_FAIL
MM_X_LONG_94:
        LDA MM_X_DIRECTION
                        BNE MM_X_FROM_SRAM
        JSR MM_X_FIND_FLASH
                        BCS MM_X_LONG_98
                        JMP MM_X_FAIL
MM_X_LONG_98:
        LDX #5
MM_X_FLASH_META:
        LDA MM_X_HEAD+4,X
        STA MM_X_REQ+2,X
        DEX
                        BPL MM_X_FLASH_META
        ; Flash has no independent entry field; it runs at its load address.
        LDA MM_X_HEAD+4
        STA MM_X_REQ+6
        LDA MM_X_HEAD+5
        STA MM_X_REQ+7
        JSR MM_X_END_RANGE
        LDA #1
        STA MM_X_REQ
        JSR MM_X_CONFIRM
                        BCS MM_X_LONG_114
                        JMP MM_X_CANCEL
MM_X_LONG_114:
        LDA #<MM_X_READ_BYTE
        STA SM_D_SOURCE_BYTE_HOOK
        LDA #>MM_X_READ_BYTE
        STA SM_D_SOURCE_BYTE_HOOK+1
        LDA #<MM_X_SAVE_CHUNK
        STA SM_D_SAVE_TRANSFER_HOOK
        LDA #>MM_X_SAVE_CHUNK
        STA SM_D_SAVE_TRANSFER_HOOK+1
        JSR MM_X_API
        JMP MM_X_RESULT
MM_X_FROM_SRAM:
        LDA MM_X_BANK
        BNE MS_COPY_ALLOWED
        JMP MM_X_BAD
MS_COPY_ALLOWED:
        ; A verified restore reaches this hook only after metadata/payload CRC.
        LDX #15
MM_X_SRAM_NAME:
        LDA MM_X_SOURCE_NAME,X
        STA MM_X_REQ+8,X
        DEX
                        BPL MM_X_SRAM_NAME
        LDA #2
        STA MM_X_REQ
        LDA #<MM_X_INSPECT
        STA SM_D_RESTORE_TRANSFER_HOOK
        LDA #>MM_X_INSPECT
        STA SM_D_RESTORE_TRANSFER_HOOK+1
        JSR MM_X_API
        CMP #$46
                        BEQ MM_X_LONG_141
                        JMP MM_X_FAIL
MM_X_LONG_141:
        LDX #3
MM_X_KEEP_META:
        LDA SM_D_LOAD,X
        STA MM_X_META,X
        DEX
                        BPL MM_X_KEEP_META
        LDA SM_D_ENTRY
        STA MM_X_META+4
        LDA SM_D_ENTRY+1
        STA MM_X_META+5
        LDA SM_D_BEST_SEQ
        STA MM_X_META+6
        LDA SM_D_BEST_SEQ+1
        STA MM_X_META+7
        LDA MM_X_META
        CMP MM_X_META+4
                        BEQ MM_X_LONG_158
                        JMP MM_X_BAD
MM_X_LONG_158:
        LDA MM_X_META+1
        CMP MM_X_META+5
                        BEQ MM_X_LONG_161
                        JMP MM_X_BAD
MM_X_LONG_161:
        ; SR v1 cannot express a distinct/restore-only SRAM entry point.
        LDA MM_X_BANK
        STA $7D2C
        CLC
        LDA MM_X_META+2
        ADC #24
        STA $7D2D
        LDA MM_X_META+3
        ADC #0
        STA $7D2E
                        BCC MM_X_LONG_172
                        JMP MM_X_FAIL
MM_X_LONG_172:
        LDA #5
        JSR X28_C1
                        BCS MM_X_LONG_175
                        JMP MM_X_FAIL
MM_X_LONG_175:
        STA MM_X_FLASH
        STX MM_X_FLASH+1
        STA MM_X_DEST
        STX MM_X_DEST+1
        LDX #<MM_X_ADDRESS_TEXT
        LDY #>MM_X_ADDRESS_TEXT
        JSR MM_PRINT
        LDA MM_X_BANK
        JSR MM_HEX
        LDA #':'
        JSR MM_PUTC
        LDA MM_X_FLASH+1
        JSR MM_HEX
        LDA MM_X_FLASH
        JSR MM_HEX
        JSR MM_NL
        JSR MM_X_CONFIRM
                        BCC MM_X_CANCEL
        ; AUTO uses staging, so reload the manager before the actual copy.
        JSR SM_INIT
                        BCC MM_X_FAIL
        LDA #<MM_X_RESTORE_CHUNK
        STA SM_D_RESTORE_TRANSFER_HOOK
        LDA #>MM_X_RESTORE_CHUNK
        STA SM_D_RESTORE_TRANSFER_HOOK+1
        JSR MM_X_API
                        BCC MM_X_RESULT
        ; Header marker is programmed only after verified restore CRC succeeds.
        CLC
        LDA MM_X_FLASH
        ADC #3
        STA MM_X_DEST
        LDA MM_X_FLASH+1
        ADC #0
        STA MM_X_DEST+1
        LDA #$3F
        JSR MM_X_PROGRAM
                        BCC MM_X_FAIL
        LDA #0
MM_X_RESULT:
        STA MM_X_ERROR
        JSR MM_X_UNHOOK
        LDA MM_X_ERROR
                        BNE MM_X_FAIL_TEXT
        LDX #<MM_X_DONE_TEXT
        LDY #>MM_X_DONE_TEXT
        JMP MM_MESSAGE
MM_X_BAD: JSR B29_ERROR_HOOK

        JSR MM_X_UNHOOK
        JMP MM_BM_BAD
MM_X_CANCEL:
        JSR MM_X_UNHOOK
        JMP MM_BM_CANCEL
MM_X_FAIL: JSR B29_ERROR_HOOK

        JSR MM_X_UNHOOK
MM_X_FAIL_TEXT: JSR B29_ERROR_HOOK

        LDX #<MM_X_FAIL_MESSAGE
        LDY #>MM_X_FAIL_MESSAGE
        JMP MM_MESSAGE
MM_X_UNHOOK:
        STZ SM_D_SOURCE_BYTE_HOOK
        STZ SM_D_SOURCE_BYTE_HOOK+1
        STZ SM_D_SAVE_TRANSFER_HOOK
        STZ SM_D_SAVE_TRANSFER_HOOK+1
        STZ SM_D_RESTORE_TRANSFER_HOOK
        STZ SM_D_RESTORE_TRANSFER_HOOK+1
        STZ V2_NMI_HOLD
        LDA MM_RESIDENT
        STA V2_SELECTED
        JSR MM_V2W_SELECT
        RTS
MM_X_API:
        LDA #<MM_X_REQ
        LDX #>MM_X_REQ
        JMP SM_C_API
MM_X_INSPECT:
        LDA #$46
        RTS
MM_X_CONFIRM:
        LDX #<MM_X_CONFIRM_TEXT
        LDY #>MM_X_CONFIRM_TEXT
        JSR MM_PRINT
        JSR MM_READLINE
                        BCC MM_X_CONFIRM_NO
        LDA MM_BM_LINE
        CMP #'Y'
                        BNE MM_X_CONFIRM_NO
        LDA MM_BM_LINE+1
                        BNE MM_X_CONFIRM_NO
        SEC
        RTS
MM_X_CONFIRM_NO:
        CLC
        RTS
MM_X_SPACE:
        JSR MM_SPACES
        CMP #'S'
                        BNE MM_X_FLASH_SPACE
        LDA #$FF
                        BRA MM_X_SPACE_END
MM_X_FLASH_SPACE:
        SEC
        SBC #'0'
        CMP #3
                        BCS MM_X_PARSE_NO
MM_X_SPACE_END:
        PHA
        INC MM_INDEX
        LDX MM_INDEX
        LDA MM_BM_LINE,X
        CMP #' '
                        BNE MM_X_SPACE_BAD
        PLA
        SEC
        RTS
MM_X_SPACE_BAD:
        PLA
MM_X_PARSE_NO:
        CLC
        RTS
MM_X_NAME:
        JSR MM_SPACES
        LDY #15
MM_X_NAME_ZERO:
        LDA #0
        STA (MM_TXT),Y
        DEY
                        BPL MM_X_NAME_ZERO
        LDY #0
MM_X_NAME_CHAR:
        LDX MM_INDEX
        LDA MM_BM_LINE,X
                        BEQ MM_X_NAME_END
        CMP #' '
                        BEQ MM_X_NAME_END
        CPY #16
                        BCS MM_X_PARSE_NO
        CMP #'-'
                        BEQ MM_X_NAME_OK
        CMP #'_'
                        BEQ MM_X_NAME_OK
        CMP #'0'
                        BCC MM_X_PARSE_NO
        CMP #'9'+1
                        BCC MM_X_NAME_OK
        CMP #'A'
                        BCC MM_X_PARSE_NO
        CMP #'Z'+1
                        BCS MM_X_PARSE_NO
MM_X_NAME_OK:
        STA (MM_TXT),Y
        INY
        INC MM_INDEX
                        BRA MM_X_NAME_CHAR
MM_X_NAME_END:
        CPY #1
        RTS
; Flash search, protecting complete SR extents, refusing ambiguous names.
MM_X_FIND_FLASH:
        STZ MM_X_FOUND
        STZ MM_X_SCAN
        LDA #$80
        STA MM_X_SCAN+1
MM_X_FIND_NEXT:
        LDA MM_X_SCAN+1
        CMP #$E0
                        BCC MM_X_LONG_343
                        JMP MM_X_FIND_DONE
MM_X_LONG_343:
        LDA MM_X_BANK
        CMP #2
                        BNE MM_X_FIND_READ
        LDA MM_X_SCAN+1
        CMP #$D8
                        BCC MM_X_FIND_READ
        CMP #$E0
                        BCS MM_X_FIND_READ
        STZ MM_X_SCAN
        LDA #$E0
        STA MM_X_SCAN+1
MM_X_FIND_READ:
        LDA MM_X_SCAN
        STA V2_ADDR
        LDA MM_X_SCAN+1
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR MM_X_READ
        LDY #15
MM_X_FIND_ERASED:
        LDA V2_BYTES,Y
        CMP #$FF
                        BNE MM_X_FIND_HEADER
        DEY
                        BPL MM_X_FIND_ERASED
        CLC
        LDA MM_X_SCAN
        ADC #16
        STA MM_X_SCAN
                        BCC MM_X_FIND_NEXT
        INC MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_HEADER:
        LDA V2_BYTES+3
        CMP #$3F
                        BEQ MM_X_FIND_MAGIC
        CMP #$FF
                        BEQ MM_X_LONG_382
                        JMP MM_X_FIND_BYTE
MM_X_LONG_382:
MM_X_FIND_MAGIC:
        LDX #2
MM_X_FIND_ID:
        LDA V2_BYTES,X
        CMP MM_X_RECORD_ID,X
                        BEQ MM_X_LONG_388
                        JMP MM_X_FIND_BYTE
MM_X_LONG_388:
        DEX
                        BPL MM_X_FIND_ID
        LDX #15
MM_X_COPY_HEAD:
        LDA V2_BYTES,X
        STA MM_X_HEAD,X
        DEX
                        BPL MM_X_COPY_HEAD
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
                        BCC MM_X_HEAD_TAIL
        INC V2_ADDR+1
MM_X_HEAD_TAIL:
        LDA #8
        STA V2_COUNT
        JSR MM_X_READ
        LDX #7
MM_X_COPY_TAIL:
        LDA V2_BYTES,X
        STA MM_X_HEAD+16,X
        DEX
                        BPL MM_X_COPY_TAIL
        LDA MM_X_HEAD+6
        ORA MM_X_HEAD+7
                        BNE MM_X_LONG_415
                        JMP MM_X_FIND_BYTE
MM_X_LONG_415:
        LDA MM_X_HEAD+5
        CMP #2
                        BCS MM_X_LONG_418
                        JMP MM_X_FIND_BYTE
MM_X_LONG_418:
        CLC
        LDA MM_X_HEAD+4
        ADC MM_X_HEAD+6
        STA MM_X_OFFSET
        LDA MM_X_HEAD+5
        ADC MM_X_HEAD+7
                        BCC MM_X_LONG_425
                        JMP MM_X_FIND_BYTE
MM_X_LONG_425:
        CMP #$65
                        BCC MM_X_FIND_RANGE_OK
                        BEQ MM_X_LONG_428
                        JMP MM_X_FIND_BYTE
MM_X_LONG_428:
        LDA MM_X_OFFSET
                        BEQ MM_X_LONG_430
                        JMP MM_X_FIND_BYTE
MM_X_LONG_430:
MM_X_FIND_RANGE_OK:
        CLC
        LDA MM_X_SCAN
        ADC #24
        STA MM_X_OFFSET
        LDA MM_X_SCAN+1
        ADC #0
        STA MM_X_OFFSET+1
        CLC
        LDA MM_X_OFFSET
        ADC MM_X_HEAD+6
        STA MM_X_BP
        LDA MM_X_OFFSET+1
        ADC MM_X_HEAD+7
                        BCS MM_X_FIND_BYTE
        CMP #$E0
                        BCC MM_X_FIND_END_OK
                        BNE MM_X_FIND_BYTE
        LDX MM_X_BP
                        BNE MM_X_FIND_BYTE
MM_X_FIND_END_OK:
        STA MM_X_BP+1
        LDA MM_X_HEAD+3
        CMP #$3F
                        BNE MM_X_FIND_SKIP
        LDX #15
MM_X_FIND_NAME:
        LDA MM_X_HEAD+8,X
        CMP MM_X_SOURCE_NAME,X
                        BNE MM_X_FIND_SKIP
        DEX
                        BPL MM_X_FIND_NAME
        LDA MM_X_FOUND
                        BEQ MM_X_FOUND_FIRST
        LDA #2
        STA MM_X_FOUND
                        BRA MM_X_FOUND_KEEP
MM_X_FOUND_FIRST:
        INC MM_X_FOUND
MM_X_FOUND_KEEP:
        LDA MM_X_SCAN
        STA MM_X_FLASH
        LDA MM_X_SCAN+1
        STA MM_X_FLASH+1
        LDA MM_X_OFFSET
        STA MM_X_PAYLOAD
        LDA MM_X_OFFSET+1
        STA MM_X_PAYLOAD+1
        LDX #3
MM_X_FIND_SAVE:
        LDA MM_X_HEAD+4,X
        STA MM_X_META,X
        DEX
                        BPL MM_X_FIND_SAVE
MM_X_FIND_SKIP:
        LDA MM_X_BP
        STA MM_X_SCAN
        LDA MM_X_BP+1
        STA MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_BYTE:
        INC MM_X_SCAN
                        BEQ MM_X_LONG_493
                        JMP MM_X_FIND_NEXT
MM_X_LONG_493:
        INC MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_DONE:
        LDA MM_X_FOUND
        CMP #1
                        BEQ MM_X_LONG_499
                        JMP MM_X_PARSE_NO
MM_X_LONG_499:
        LDX #3
MM_X_FIND_RESTORE:
        LDA MM_X_META,X
        STA MM_X_HEAD+4,X
        DEX
                        BPL MM_X_FIND_RESTORE
        SEC
        RTS
MM_X_END_RANGE:
        CLC
        LDA MM_X_HEAD+4
        ADC MM_X_HEAD+6
        STA MM_X_REQ+4
        LDA MM_X_HEAD+5
        ADC MM_X_HEAD+7
        STA MM_X_REQ+5
        LDA MM_X_REQ+4
                        BNE MM_X_END_LOW
        DEC MM_X_REQ+5
MM_X_END_LOW:
        DEC MM_X_REQ+4
        RTS
; Source byte for SAVE CRC: map logical PTR to flash payload.
MM_X_READ_BYTE:
        SEC
        LDA $D2
        SBC SM_D_LOAD
        STA V2_ADDR
        LDA $D3
        SBC SM_D_LOAD+1
        STA V2_ADDR+1
        CLC
        LDA V2_ADDR
        ADC MM_X_PAYLOAD
        STA V2_ADDR
        LDA V2_ADDR+1
        ADC MM_X_PAYLOAD+1
        STA V2_ADDR+1
        LDA #1
        STA V2_COUNT
        JSR MM_X_READ
        LDA V2_BYTES
        LDY #0
        RTS
MM_X_READ:
        LDA MM_X_BANK
        STA V2_SELECTED
        JMP X28_C8
; Source transfer uses preserved BUF, never the source application's RAM.
MM_X_SAVE_CHUNK:
        LDA SM_D_BP
        STA MM_X_BP
        STA $D2
        LDA SM_D_BP+1
        STA MM_X_BP+1
        STA $D3
        STZ MM_X_INDEX
MM_X_FILL_CHUNK:
        JSR MM_X_READ_BYTE
        LDX MM_X_INDEX
        STA $6400,X
        INC $D2
                        BNE MM_X_FILL_NEXT
        INC $D3
MM_X_FILL_NEXT:
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP SM_D_COUNT
                        BNE MM_X_FILL_CHUNK
        JSR MM_X_STAGE_BP
        LDA #2
        JSR SM_C_TRANSFER
                        BRA MM_X_UNSTAGE_BP
MM_X_STAGE_BP:
        STZ SM_D_BP
        LDA #$64
        STA SM_D_BP+1
        RTS
MM_X_UNSTAGE_BP:
        PHA
        LDA MM_X_BP
        STA SM_D_BP
        LDA MM_X_BP+1
        STA SM_D_BP+1
        PLA
        RTS
MM_X_RESTORE_CHUNK:
        LDA MM_X_STARTED
                        BNE MM_X_RESTORE_DATA
        LDX #3
MM_X_MATCH_META:
        LDA SM_D_LOAD,X
        CMP MM_X_META,X
                        BEQ MM_X_LONG_593
                        JMP MM_X_HOOK_FAIL
MM_X_LONG_593:
        DEX
                        BPL MM_X_MATCH_META
        LDA SM_D_ENTRY
        CMP MM_X_META+4
                        BEQ MM_X_LONG_598
                        JMP MM_X_HOOK_FAIL
MM_X_LONG_598:
        LDA SM_D_ENTRY+1
        CMP MM_X_META+5
                        BEQ MM_X_LONG_601
                        JMP MM_X_HOOK_FAIL
MM_X_LONG_601:
        LDA SM_D_BEST_SEQ
        CMP MM_X_META+6
                        BNE MM_X_HOOK_FAIL
        LDA SM_D_BEST_SEQ+1
        CMP MM_X_META+7
                        BNE MM_X_HOOK_FAIL
        INC MM_X_STARTED
        LDX #3
MM_X_NEW_HEAD:
        LDA MM_X_RECORD_ID,X
        STA MM_X_HEAD,X
        LDA MM_X_META,X
        STA MM_X_HEAD+4,X
        DEX
                        BPL MM_X_NEW_HEAD
        LDA #$FF
        STA MM_X_HEAD+3
        ; Destination name survived READLINE in X_REQ; source name is kept
        ; separately. X_REQ now contains source, destination needs own copy.
        LDX #15
MM_X_NEW_NAME:
        LDA MM_X_DEST_NAME,X
        STA MM_X_HEAD+8,X
        DEX
                        BPL MM_X_NEW_NAME
        STZ MM_X_INDEX
MM_X_WRITE_HEAD:
        LDX MM_X_INDEX
        LDA MM_X_HEAD,X
        JSR MM_X_PROGRAM
                        BCC MM_X_HOOK_FAIL
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP #24
                        BNE MM_X_WRITE_HEAD
MM_X_RESTORE_DATA:
        LDA SM_D_BP
        STA MM_X_BP
        LDA SM_D_BP+1
        STA MM_X_BP+1
        JSR MM_X_STAGE_BP
        LDA #1
        JSR SM_C_TRANSFER
        JSR MM_X_UNSTAGE_BP
        CMP #0
                        BNE MM_X_HOOK_FAIL
        STZ MM_X_INDEX
MM_X_PROGRAM_DATA:
        LDX MM_X_INDEX
        LDA $6400,X
        JSR MM_X_PROGRAM
                        BCC MM_X_HOOK_FAIL
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP SM_D_COUNT
                        BNE MM_X_PROGRAM_DATA
        LDA #0
        RTS
MM_X_HOOK_FAIL:
        LDA #$46
        RTS
; Program fresh bytes only, read back each, never erase any occupied space.
MM_X_PROGRAM:
        STA MM_X_VALUE
        LDA MM_X_DEST
        STA V2_ADDR
        STA V2_FLASH_PTR
        LDA MM_X_DEST+1
        STA V2_ADDR+1
        STA V2_FLASH_PTR+1
        LDA #1
        STA V2_COUNT
        STA V2_NMI_HOLD
        JSR MM_X_READ
        LDA V2_BYTES
        CMP #$FF
                        BNE MM_X_PROGRAM_FAIL
        LDA MM_X_VALUE
        CMP #$FF
                        BEQ MM_X_PROGRAM_OK
        STA V2_FLASH_DATA
        LDA MM_X_BANK
        JSR MM_V2W_SELECT
        JSR X28_C9
        PHP
        LDA MM_RESIDENT
        JSR MM_V2W_SELECT
        PLP
                        BCC MM_X_PROGRAM_FAIL
        JSR MM_X_READ
        LDA V2_BYTES
        CMP MM_X_VALUE
                        BNE MM_X_PROGRAM_FAIL
MM_X_PROGRAM_OK:
        INC MM_X_DEST
                        BNE MM_X_PROGRAM_NO_CARRY
        INC MM_X_DEST+1
MM_X_PROGRAM_NO_CARRY:
        SEC
        RTS
MM_X_PROGRAM_FAIL:
        CLC
        RTS
MM_X_DEST_NAME EQU $6200
MM_X_RECORD_ID DB "SR",1,$3F
MM_X_EXEC_MAGIC DB "ED",1,3
MM_X_MAINT_NAME DB "MAINT"
MM_X_ADDRESS_TEXT DB "Destination B",0
MM_X_CONFIRM_TEXT DB "Copy program; source retained. Y to confirm: ",0
MM_X_DONE_TEXT DB "Copied and verified; source retained.",13,10,0
MM_X_FAIL_MESSAGE DB "Copy failed; source retained. Destination may be pending.",13,10,0

MM_BN_FLASH_BYTE EQU $7B03
MM_TZ_PTR EQU $D6
MM_TZ_SUM EQU $6210
MM_TZ_CRC:
        LDA #$FF
        STA MM_TZ_SUM
        STA MM_TZ_SUM+1
        LDY #0
MM_TZ_CRC_BYTE:
        JSR X28_R5
        EOR MM_TZ_SUM+1
        STA MM_TZ_SUM+1
        LDX #8
MM_TZ_CRC_BIT:
        ASL MM_TZ_SUM
        ROL MM_TZ_SUM+1
                        BCC MM_TZ_CRC_NEXT
        LDA MM_TZ_SUM
        EOR #$21
        STA MM_TZ_SUM
        LDA MM_TZ_SUM+1
        EOR #$10
        STA MM_TZ_SUM+1
MM_TZ_CRC_NEXT:
        DEX
                        BNE MM_TZ_CRC_BIT
        INY
        CPY #28
                        BNE MM_TZ_CRC_BYTE
        RTS
; BN,1,0; sequence LE32; length 0..8; eight zero-padded printable bytes;
; reserved FF through byte 27; CRC16 LE at 28; FF at 30; commit 0 at 31.
; Shared append-only EI/TZ tail. Uncommitted and malformed slots stay occupied.
MM_BN_READ:
        STZ MM_BN_LENGTH
        STZ MM_BN_FREE+1
        LDX #3
MM_BN_RESET:
        STZ MM_BN_SEQ,X
        DEX
                        BPL MM_BN_RESET
        LDA X28_BANK
        PHA
        LDA #3
        STA X28_BANK
        STZ MM_TZ_PTR
        LDA #$9C
        STA MM_TZ_PTR+1
MM_BN_SLOT:
        LDY #0
MM_BN_BLANK:
        JSR X28_R5
        CMP #$FF
                        BNE MM_BN_CHECK
        INY
        CPY #32
                        BNE MM_BN_BLANK
        LDA MM_BN_FREE+1
                        BEQ MM_BN_LONG_3261
                        JMP MM_BN_NEXT
MM_BN_LONG_3261:
        LDA MM_TZ_PTR
        STA MM_BN_FREE
        LDA MM_TZ_PTR+1
        STA MM_BN_FREE+1
                        JMP MM_BN_NEXT
MM_BN_CHECK:
        LDY #31
        JSR X28_R5
                        BEQ MM_BN_LONG_3270
                        JMP MM_BN_NEXT
MM_BN_LONG_3270:
        LDY #3
MM_BN_HEADER:
        JSR X28_R5
        CMP MM_BN_MAGIC,Y
                        BNE MM_BN_NEXT
        DEY
                        BPL MM_BN_HEADER
        JSR MM_TZ_CRC
        LDY #28
        JSR X28_R5
        CMP MM_TZ_SUM
                        BNE MM_BN_NEXT
        INY
        JSR X28_R5
        CMP MM_TZ_SUM+1
                        BNE MM_BN_NEXT
        LDY #8
        JSR X28_R5
        CMP #9
                        BCS MM_BN_NEXT
        STA MM_BN_WORK
        TAX
MM_BN_CHAR_CHECK:
        INY
        CPY #17
                        BEQ MM_BN_NEWEST
        JSR X28_R5
        CPX #0
                        BEQ MM_BN_PADDING
        CMP #$21
                        BCC MM_BN_NEXT
        CMP #$7F
                        BCS MM_BN_NEXT
        DEX
                        JMP MM_BN_CHAR_CHECK
MM_BN_PADDING:
        CMP #0
                        BNE MM_BN_NEXT
                        JMP MM_BN_CHAR_CHECK
MM_BN_NEWEST:
        LDY #7
        LDX #3
MM_BN_NEWER:
        JSR X28_R5
        CMP MM_BN_SEQ,X
                        BCC MM_BN_NEXT
                        BNE MM_BN_KEEP
        DEY
        DEX
                        BPL MM_BN_NEWER
MM_BN_KEEP:
        LDY #7
        LDX #3
MM_BN_COPY_SEQ:
        JSR X28_R5
        STA MM_BN_SEQ,X
        DEY
        DEX
                        BPL MM_BN_COPY_SEQ
        LDA MM_BN_WORK
        STA MM_BN_LENGTH
        LDY #9
        LDX #0
MM_BN_COPY:
        JSR X28_R5
        STA MM_BN_TEXT,X
        INY
        INX
        CPX #8
                        BNE MM_BN_COPY
MM_BN_NEXT:
        LDA MM_TZ_PTR
        CLC
        ADC #32
        STA MM_TZ_PTR
                        BCC MM_BN_PAGE
        INC MM_TZ_PTR+1
MM_BN_PAGE:
        LDA MM_TZ_PTR+1
        CMP #$A0
                        BEQ MM_BN_LONG_3351
                        JMP MM_BN_SLOT
MM_BN_LONG_3351:
        PLA
        STA X28_BANK
        RTS
MM_BN_SHOW:
        JSR MM_BN_READ
        LDA MM_BN_LENGTH
                        BEQ MM_BN_SHOW_DONE
        LDX #<MM_BN_LABEL
        LDY #>MM_BN_LABEL
        JSR MM_PRINT
        LDX #0
MM_BN_PRINT:
        LDA MM_BN_TEXT,X
        JSR $7E6D
        INX
        CPX MM_BN_LENGTH
                        BNE MM_BN_PRINT
        JSR $7E7F
MM_BN_SHOW_DONE:
        RTS
MM_BN_MAGIC DB "BN",1,0
MM_BN_LABEL DB "Board: ",0
MM_BN_LENGTH EQU $6212
MM_BN_WORK EQU $6213
MM_BN_TEXT EQU $6214
MM_BN_SEQ EQU $621C
MM_BN_FREE EQU $6220
; NAME [1..8 non-space printable characters | CLEAR]. READLINE canonicalizes case.
; Recognize the whole word before the existing N (new-sector buffer) command.
MM_BN_TRY:
        LDX #3
MM_BN_COMMAND_WORD:
        LDA MM_BM_LINE,X
        CMP MM_BN_WORD,X
                        BEQ MM_BN_LONG_3386
                        JMP MM_BN_NOT_COMMAND
MM_BN_LONG_3386:
        DEX
                        BPL MM_BN_COMMAND_WORD
        LDA MM_LINELEN
        CMP #4
                        BNE MM_BN_LONG_3391
                        JMP MM_BN_QUERY
MM_BN_LONG_3391:
        LDA MM_BM_LINE+4
        CMP #' '
                        BEQ MM_BN_LONG_3394
                        JMP MM_BN_BAD
MM_BN_LONG_3394:
        LDA MM_LINELEN
        SEC
        SBC #5
                        BNE MM_BN_LONG_3398
                        JMP MM_BN_BAD
MM_BN_LONG_3398:
        CMP #9
                        BCC MM_BN_LONG_3400
                        JMP MM_BN_BAD
MM_BN_LONG_3400:
        STA MM_BN_PENDING_LENGTH
        LDX #7
MM_BN_ZERO_PENDING:
        STZ MM_BN_PENDING,X
        DEX
                        BPL MM_BN_ZERO_PENDING
        LDX #0
MM_BN_ARGUMENT:
        LDA MM_BM_LINE+5,X
        CMP #$21
                        BCS MM_BN_LONG_3411
                        JMP MM_BN_BAD
MM_BN_LONG_3411:
        CMP #$7F
                        BCC MM_BN_LONG_3413
                        JMP MM_BN_BAD
MM_BN_LONG_3413:
        STA MM_BN_PENDING,X
        INX
        CPX MM_BN_PENDING_LENGTH
                        BNE MM_BN_ARGUMENT
        LDA MM_BN_PENDING_LENGTH
        CMP #5
                        BNE MM_BN_PREPARE
        LDX #4
MM_BN_CLEAR_WORD:
        LDA MM_BN_PENDING,X
        CMP MM_BN_CLEAR_TEXT,X
                        BNE MM_BN_PREPARE
        DEX
                        BPL MM_BN_CLEAR_WORD
        STZ MM_BN_PENDING_LENGTH
        LDX #7
MM_BN_CLEAR_PENDING:
        STZ MM_BN_PENDING,X
        DEX
                        BPL MM_BN_CLEAR_PENDING
MM_BN_PREPARE:
        JSR MM_BN_READ
        LDA MM_BN_PENDING_LENGTH
        CMP MM_BN_LENGTH
                        BNE MM_BN_CONFIRM
                        BEQ MM_BN_COMPARE_START
MM_BN_COMPARE_START:
        TAX
                        BEQ MM_BN_QUERY
        DEX
MM_BN_COMPARE:
        LDA MM_BN_PENDING,X
        CMP MM_BN_TEXT,X
                        BNE MM_BN_CONFIRM
        DEX
                        BPL MM_BN_COMPARE
                        JMP MM_BN_QUERY
MM_BN_CONFIRM:
        LDX #<MM_BN_WARNING
        LDY #>MM_BN_WARNING
        JSR MM_PRINT
        JSR MM_READLINE
                        BCS MM_BN_LONG_3456
                        JMP MM_BM_CANCEL
MM_BN_LONG_3456:
        LDA MM_LINELEN
        CMP #3
                        BEQ MM_BN_LONG_3459
                        JMP MM_BM_CANCEL
MM_BN_LONG_3459:
        LDX #2
MM_BN_YES:
        LDA MM_BM_LINE,X
        CMP MM_BN_YES_TEXT,X
                        BEQ MM_BN_LONG_3464
                        JMP MM_BM_CANCEL
MM_BN_LONG_3464:
        DEX
                        BPL MM_BN_YES
        JSR MM_BN_SAVE
                        BCC MM_BN_FAILED
MM_BN_QUERY:
        JSR MM_BN_SHOW
        LDA MM_BN_LENGTH
                        BNE MM_BN_MENU
        LDX #<MM_BN_UNNAMED
        LDY #>MM_BN_UNNAMED
        JSR MM_PRINT
MM_BN_MENU:
        JMP MM_BM_MENU
MM_BN_BAD: JSR B29_ERROR_HOOK

        LDX #<MM_BN_USAGE
        LDY #>MM_BN_USAGE
        JMP MM_MESSAGE
MM_BN_FAILED: JSR B29_ERROR_HOOK

        LDX #<MM_BN_FAILURE
        LDY #>MM_BN_FAILURE
        JMP MM_MESSAGE
MM_BN_NOT_COMMAND:
        CLC
        RTS
MM_BN_WORD DB "NAME"
MM_BN_CLEAR_TEXT DB "CLEAR"
MM_BN_YES_TEXT DB "YES"
MM_BN_WARNING DB "Save board name? Type YES: ",0
MM_BN_USAGE DB "NAME [1-8 characters | CLEAR]",13,10,0
MM_BN_UNNAMED DB "Board: unnamed",13,10,0
MM_BN_FAILURE DB "Name not saved; full, incompatible or write failed. No erase.",13,10,0
MM_BN_PENDING_LENGTH EQU $6222
MM_BN_PENDING EQU $6223
MM_BN_SAVE:
        LDA X28_BANK
        PHA
        LDA #3
        STA X28_BANK
        LDX #3
MM_BN_FORMAT_CHECK:
        JSR X28_R19
        CMP MM_BN_JOURNAL_MAGIC,X
                        BNE MM_BN_FORMAT_BAD
        DEX
                        BPL MM_BN_FORMAT_CHECK
        PLA
        STA X28_BANK
        JSR MM_BN_READ
        LDA MM_BN_FREE+1
                        BEQ MM_BN_REFUSE
        LDX #3
MM_BN_SEQ_FULL:
        LDA MM_BN_SEQ,X
        CMP #$FF
                        BNE MM_BN_RECORD
        DEX
                        BPL MM_BN_SEQ_FULL
MM_BN_REFUSE:
        CLC
        RTS
MM_BN_FORMAT_BAD:
        PLA
        STA X28_BANK
                        JMP MM_BN_REFUSE
MM_BN_RECORD:
        LDX #31
        LDA #$FF
MM_BN_FILL:
        STA MM_BN_RECORD_BYTES,X
        DEX
                        BPL MM_BN_FILL
        LDX #3
MM_BN_RECORD_HEADER:
        LDA MM_BN_MAGIC,X
        STA MM_BN_RECORD_BYTES,X
        DEX
                        BPL MM_BN_RECORD_HEADER
        INC MM_BN_SEQ
                        BNE MM_BN_SEQUENCE_READY
        INC MM_BN_SEQ+1
                        BNE MM_BN_SEQUENCE_READY
        INC MM_BN_SEQ+2
                        BNE MM_BN_SEQUENCE_READY
        INC MM_BN_SEQ+3
MM_BN_SEQUENCE_READY:
        LDX #3
MM_BN_SEQUENCE:
        LDA MM_BN_SEQ,X
        STA MM_BN_RECORD_BYTES+4,X
        DEX
                        BPL MM_BN_SEQUENCE
        LDA MM_BN_PENDING_LENGTH
        STA MM_BN_RECORD_BYTES+8
        LDX #7
MM_BN_PAYLOAD:
        LDA MM_BN_PENDING,X
        STA MM_BN_RECORD_BYTES+9,X
        DEX
                        BPL MM_BN_PAYLOAD
        LDA #<MM_BN_RECORD_BYTES
        STA MM_TZ_PTR
        LDA #>MM_BN_RECORD_BYTES
        STA MM_TZ_PTR+1
        JSR MM_TZ_CRC
        LDA MM_TZ_SUM
        STA MM_BN_RECORD_BYTES+28
        LDA MM_TZ_SUM+1
        STA MM_BN_RECORD_BYTES+29
        LDX #31
MM_BN_SAVE_ZP:
        LDA $E0,X
        STA MM_BN_ZP,X
        DEX
                        BPL MM_BN_SAVE_ZP
        LDA X28_BANK
        STA MM_BN_BANK
        LDA #3
        STA X28_BANK
        LDA $7FA0
        STA MM_BN_LED
        LDA #3
        STA $F3
        LDA #1
        STA $F4
        STZ MM_BN_INDEX
        STZ MM_BN_ERROR
MM_BN_WRITE:
        LDX MM_BN_INDEX
        LDA MM_BN_RECORD_BYTES,X
        CMP #$FF
                        BEQ MM_BN_NEXT_BYTE
        STA $F0
        TXA
        CLC
        ADC MM_BN_FREE
        STA $E4
        LDA MM_BN_FREE+1
        ADC #0
        STA $E5
        JSR X28_C9
                        BCC MM_BN_WRITE_FAILED
MM_BN_NEXT_BYTE:
        INC MM_BN_INDEX
        LDA MM_BN_INDEX
        CMP #31
                        BNE MM_BN_WRITE
        LDA MM_BN_FREE
        STA MM_TZ_PTR
        LDA MM_BN_FREE+1
        STA MM_TZ_PTR+1
        LDY #30
MM_BN_VERIFY:
        JSR X28_R5
        CMP MM_BN_RECORD_BYTES,Y
                        BNE MM_BN_WRITE_FAILED
        DEY
                        BPL MM_BN_VERIFY
        LDA MM_BN_FREE
        CLC
        ADC #31
        STA $E4
        LDA MM_BN_FREE+1
        ADC #0
        STA $E5
        STZ $F0
        JSR X28_C9
                        BCC MM_BN_WRITE_FAILED
        LDY #31
        JSR X28_R5
                        BNE MM_BN_WRITE_FAILED
                        BRA MM_BN_RESTORE
MM_BN_WRITE_FAILED:
        INC MM_BN_ERROR
MM_BN_RESTORE:
        LDA MM_BN_LED
        STA $7FA0
        LDA MM_BN_BANK
        STA X28_BANK
        LDX #31
MM_BN_RESTORE_ZP:
        LDA MM_BN_ZP,X
        STA $E0,X
        DEX
                        BPL MM_BN_RESTORE_ZP
        LDA MM_BN_ERROR
                        BEQ MM_BN_LONG_3652
                        JMP MM_BN_REFUSE
MM_BN_LONG_3652:
        JSR MM_BN_READ
        LDA MM_BN_LENGTH
        CMP MM_BN_PENDING_LENGTH
                        BEQ MM_BN_LONG_3656
                        JMP MM_BN_REFUSE
MM_BN_LONG_3656:
        LDX #7
MM_BN_READBACK:
        LDA MM_BN_TEXT,X
        CMP MM_BN_PENDING,X
                        BEQ MM_BN_LONG_3661
                        JMP MM_BN_REFUSE
MM_BN_LONG_3661:
        DEX
                        BPL MM_BN_READBACK
        SEC
        RTS
MM_BN_JOURNAL_MAGIC DB "PJ",6,1
MM_BN_BANK EQU $622B
MM_BN_LED EQU $622C
MM_BN_INDEX EQU $622D
MM_BN_ERROR EQU $622E
MM_BN_RECORD_BYTES EQU $622F
MM_BN_ZP EQU $624F

; Called while bank 2 is visible. Identify sealed assets, never by address alone.
MM_MAP_FIRMWARE:
        LDA MM_MAPBANK
        CMP #1
        BNE DM_OTHER_BANK
        LDA MM_MAPSEC
        CMP #$90
        BEQ MS_SOURCE_CHECK
        CMP #$A0
        BEQ DM_CHECK
        JMP MM_MF_NO
MS_SOURCE_CHECK:
        LDA #$90
        LDY #$A0
        LDX #12
        JSR MM_MF_CHECK
        BCS DM_VALID
        JMP MM_MF_NO
DM_CHECK:
        LDA #$A0
        LDY #$B0
        LDX #8
        JSR MM_MF_CHECK
        BCS DM_VALID
        JMP MM_MF_NO
DM_VALID:
        JMP MM_MF_YES
DM_OTHER_BANK:
        LDA MM_MAPBANK
        CMP #2
                        BNE MM_MF_NO
        LDA MM_MAPSEC
        CMP #$E0
        BCS MM_X28_MAP_ASSET
        BRA MM_MF_YES
MM_X28_MAP_ASSET:
        CMP #$E0
                        BEQ MM_MF_STATUS
        CMP #$F0
                        BNE MM_MF_NO
        ; Both independent assets must validate before labelling sector E.
        LDA #$F0
        LDY #$F7
        LDX #4
        JSR MM_MF_CHECK
                        BCC MM_MF_NO
        LDA #$F8
        LDY #$00
        LDX #0
        JSR MM_MF_CHECK
                        BCC MM_MF_NO
                        BRA MM_MF_YES
MM_MF_STATUS:
        LDA #$D8
        LDY #$E2
        LDX #0
        JSR MM_MF_CHECK
                        BCC MM_MF_NO
MM_MF_YES:
        LDA #'F'
        STA MM_MAP_KIND
        SEC
        RTS
MM_MF_NO:
        CLC
        RTS
; A=start page, Y=exclusive end page, X=header index. All code executes in RAM.
MM_MF_CHECK:
        STA MM_SRC+1
        STZ MM_SRC
        STY MM_MF_END
        LDY #0
MM_MF_HEADER:
        JSR X28_R3
        CMP MM_MF_MAGIC,X
                        BNE MM_MF_NO
        INX
        INY
        CPY #4
                        BNE MM_MF_HEADER
        LDA #$FF
        STA MM_CRC
        STA MM_CRC+1
        LDY #0
MM_MF_BYTE:
        JSR X28_R3
        EOR MM_CRC+1
        STA MM_CRC+1
        LDX #8
MM_MF_BIT:
        ASL MM_CRC
        ROL MM_CRC+1
                        BCC MM_MF_NEXT
        LDA MM_CRC
        EOR #$21
        STA MM_CRC
        LDA MM_CRC+1
        EOR #$10
        STA MM_CRC+1
MM_MF_NEXT:
        DEX
                        BNE MM_MF_BIT
        INY
                        BNE MM_MF_BYTE
        INC MM_SRC+1
        LDA MM_SRC+1
        CMP MM_MF_END
                        BNE MM_MF_BYTE
        LDA MM_CRC
        ORA MM_CRC+1
                        BNE MM_MF_NO
        SEC
        RTS
MM_MF_DESCRIPTION:
        LDA MM_MAPBANK
        CMP #1
        BNE DM_DESCRIPTION_OTHER
        LDX #<MS_SOURCE_TEXT
        LDY #>MS_SOURCE_TEXT
        LDA MM_MAPSEC
        CMP #$90
        BEQ MS_SOURCE_DESCRIPTION
        LDX #<DM_DEBUG_TEXT
        LDY #>DM_DEBUG_TEXT
MS_SOURCE_DESCRIPTION:
        JMP MM_PRINT
DM_DESCRIPTION_OTHER:
        LDA MM_MAPSEC
        CMP #$E0
        BCS MM_X28_MAP_DESC_ASSET
        LDX #<MM_X28_UTIL_TEXT
        LDY #>MM_X28_UTIL_TEXT
        JMP MM_PRINT
MM_X28_MAP_DESC_ASSET:
        LDX #<MM_MF_STATUS_TEXT
        LDY #>MM_MF_STATUS_TEXT
        LDA MM_MAPSEC
        CMP #$E0
                        BEQ MM_MF_PRINT
        LDX #<MM_MF_LOCAL_TEXT
        LDY #>MM_MF_LOCAL_TEXT
MM_MF_PRINT:
        JMP MM_PRINT
MM_MF_STATUS_TEXT DB "Firmware status formatter D800-E1FF",0
MM_MF_LOCAL_TEXT DB "Local/board F000-F6FF; VERSION F800-FFFF",0
MM_MF_RESERVED_TEXT DB " reserved",0
DM_DEBUG_TEXT DB "DEBUG (DBG1) A000-AFFF",0
MS_SOURCE_TEXT DB "ASM source 9000-9FFF",0
MM_MF_MAGIC DB "BS",1,3,"LT",1,1,"DG",1,1,"NS",1,1
MM_MF_END EQU $626F

MM_X28_UTIL_TEXT DB "Flash utilities 8000-D7FF",0
        DS 62
MM_BM_END:
