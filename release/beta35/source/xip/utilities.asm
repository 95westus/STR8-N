        MODULE XIP_UTILITIES
        XDEF X28_END
        INCLUDE "kernel.inc"
        INCLUDE "system.inc"
        CODE
X28_HEADER: DB "UX",2,42
        JMP MM_START
        JMP SM_ENTRY
        JMP WK_ENTRY
        JMP ED_START
        JMP X28_APPS
X28_GATE_IMAGE:
        INCLUDE "gate-image.inc"
X28_WORK_STUB:
        INCLUDE "work-stub.inc"
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
                        CMP #$01
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R10
                        CMP #$09
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R11
                        CMP #$67
                        BNE MM_BM_UNSUPPORTED
                        JSR X28_R12
                        CMP #$EC
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
MM_CONFIRM:                LDA MM_DB
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
                       DB "F firmware assets; P application; V application-bank vectors",$0D,$0A
                       DB "A/B monitors; J/j journal used/erased; X extension; R recovery",$0D,$0A
                       DB "B2:D800-E1FF status; B2:F local/board + VERSION.",$0D,$0A
                       DB "* active.",$0D,$0A,0
MM_MAP_DETAIL_LEGEND_TEXT: DB "E = all FF; U = programmed. ERASE-ATTEMPTS are hexadecimal.",$0D,$0A,0
MM_MAP_ACCESS_NOTE_TEXT:   DB "Erased does not mean available. B2 utilities and B3:8-F protected.",$0D,$0A,0
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
                        DB "  M [1|2|3]                   Grid / ranges (default) / wear",$0D,$0A
                        DB "  E bank 8[-F]                Erase sectors",$0D,$0A
                        DB "  C src range dst start       Copy RAM or flash",$0D,$0A
                        DB "  V src range dst start       Compare RAM or flash",$0D,$0A
                        DB $0D,$0A,"EDITOR BUFFER (4 KiB)",$0D,$0A
                        DB "  R src range                 Read into buffer",$0D,$0A
                        DB "  D [offset[-end]]            Display buffer",$0D,$0A
                        DB "  P offset byte ...           Patch bytes",$0D,$0A
                        DB "  F offset[-end] byte         Fill bytes",$0D,$0A
                        DB "  N length byte               Create filled buffer",$0D,$0A
                        DB "  K                           Buffer CRC16",$0D,$0A
                        DB "  W dst start                 Write buffer and verify",$0D,$0A
                        DB $0D,$0A,"CONTROL",$0D,$0A
                        DB "  T [bank|first-last]          Stored records",$0D,$0A
                        DB "  J bank                      Boot selected bank",$0D,$0A
                        DB "  Q                           Return to monitor",$0D,$0A
                        DB "  ?                           Show this menu",$0D,$0A
                        DB $0D,$0A,"  src/dst: R = RAM, 0-3 = flash bank. Numbers are hex.",$0D,$0A
                        DB "  Flash 8-F = sectors. Editor offsets: 000-FFF.",$0D,$0A
                        DB "  Writes: Y to confirm. B2 utilities and B3:8-F protected.",$0D,$0A,0
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
MM_MF_MAGIC DB "BS",1,3,"LT",1,1
MM_MF_END EQU $626F

MM_X28_UTIL_TEXT DB "Flash utilities 8000-D7FF",0
MM_BM_END:
SM_INIT:
        LDX #47
SM_CLEAR:
        STZ $67C7,X
        DEX
        BPL SM_CLEAR
        SEC
        RTS
SM_ENTRY:
        JSR SM_INIT
        BRA SM_C_START
; SRAM 1.0: standalone foreground manager. Linked at 6C00, R image at 4000.
; Borrows 6800-6AFF (tables/state) and 6C00-77FF (code), not journal 6Bxx.
; 6400-643F is a preserved transfer window; restore copies directly to target.
SM_C_TEXT EQU $D0
SM_C_PTR EQU $D2
SM_C_DST EQU $D4
SM_C_REC EQU $D6
SM_C_BUF EQU $6400
SM_C_DIR EQU $6900
SM_C_BACKUP EQU $6A00
SM_C_EXPECTED EQU $6A40
SM_C_BITMAP EQU $6A80
SM_C_REQUEST EQU $6AA0
SM_C_LINE EQU $6AC0
SM_C_R EQU $6650
SM_C_MANAGED EQU $66AE
SM_C_PUTC EQU $7E6D
SM_C_GETC EQU $7E70
SM_C_HEX EQU $7E7C
SM_C_NL EQU $7E7F
SM_C_START:  JMP SM_C_CONSOLE
        JMP SM_C_API
; API: A/X points to 32-byte request in user RAM. Foreground, SEI/CLD.
; op 0=query,1=save,2=restore,3=run,4=delete,5=reclaim,6=format.
; bytes 1=0,2..3=start,4..5=inclusive end,6..7=entry (0=restore only),
; 8..23=name (uppercase, zero padded),24..31=format key "FORMAT!!".
SM_C_API:    SEI
        CLD
        STA SM_C_PTR
        STX SM_C_PTR+1
        CPX #2
                        BCC SM_C_API_BAD
        CPX #$65
                        BCS SM_C_API_BAD
        CPX #$64
                        BNE SM_C_API_COPY
        CMP #$E1
                        BCS SM_C_API_BAD
SM_C_API_COPY:
        LDY #31
SM_C_API_COPY_LOOP:
        LDA (SM_C_PTR),Y
        STA SM_C_REQUEST,Y
        DEY
                        BPL SM_C_API_COPY_LOOP
        JSR SM_C_OPERATION
        CMP #0
                        BNE SM_C_API_ERROR
        SEC
        RTS
SM_C_API_BAD:LDA #$44
SM_C_API_ERROR:
        CLC
        RTS
SM_C_OPERATION:
        STZ SM_D_COPYING
        STZ SM_D_STATUS
        LDX #63
SM_C_BACKUP_LOOP:
        LDA SM_C_BUF,X
        STA SM_C_BACKUP,X
        DEX
                        BPL SM_C_BACKUP_LOOP
        JSR SM_C_DISCOVER
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST+1
                        BNE SM_C_ARG_BAD
        LDA SM_C_REQUEST
        CMP #7
                        BCS SM_C_ARG_BAD
        CMP #6
                        BNE SM_C_BM_LONG_78
                        JMP SM_C_FORMAT
SM_C_BM_LONG_78:
        JSR SM_C_MOUNT
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST
                        BEQ SM_C_FINISH
        CMP #5
                        BNE SM_C_BM_LONG_84
                        JMP SM_C_RECLAIM
SM_C_BM_LONG_84:
        JSR SM_C_NAME_CHECK
                        BNE SM_C_FINISH
        JSR SM_C_FIND_NAME
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST
        CMP #1
                        BNE SM_C_BM_LONG_91
                        JMP SM_C_SAVE
SM_C_BM_LONG_91:
        CMP #4
                        BNE SM_C_BM_LONG_93
                        JMP SM_C_DELETE
SM_C_BM_LONG_93:
        LDA SM_D_BEST
        CMP #8
                        BCS SM_C_NOT_FOUND
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_NOT_FOUND
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_FINISH
        JMP SM_C_RESTORE
SM_C_ARG_BAD:LDA #$44
                        JMP SM_C_FINISH
SM_C_NOT_FOUND:
        LDA #$42
SM_C_FINISH: STA SM_D_STATUS
        LDA SM_D_COPYING
                        BNE SM_C_FINISH_RESULT
        JSR SM_C_RESTORE_BUF
SM_C_FINISH_RESULT:
        LDA SM_D_STATUS
        RTS
SM_C_RESTORE_BUF:
        LDX #63
SM_C_RESTORE_BUF_LOOP:
        LDA SM_C_BACKUP,X
        STA SM_C_BUF,X
        DEX
                        BPL SM_C_RESTORE_BUF_LOOP
        RTS
SM_C_DISCOVER:
        LDX #2
SM_C_DISCOVER_LOOP:
        LDA $7D04,X
        CMP SM_D_SV_MAGIC,X
                        BNE SM_C_ABSENT
        DEX
                        BPL SM_C_DISCOVER_LOOP
        LDA $7D07
        AND #8
                        BEQ SM_C_ABSENT
        LDA $7D08
                        BNE SM_C_ABSENT
        LDA $7D09
        CMP #$65
                        BNE SM_C_ABSENT
        LDX #3
SM_C_SM_CHECK:
        LDA $66A2,X
        CMP SM_D_SM_MAGIC,X
                        BNE SM_C_ABSENT
        DEX
                        BPL SM_C_SM_CHECK
        LDA #1
        STA SM_C_MANAGED
        STZ SM_D_COUNT
        LDA #0
        JSR SM_C_TRANSFER
        RTS
SM_C_ABSENT: LDA #$80
        RTS
; Each manager write is a privileged cooperative operation. Public clients
; never receive a setter. No IRQ/NMI service callers or concurrent managers.
SM_C_TRANSFER:
        PHA
        LDX #15
SM_C_TRANSFER_CLEAR:
        STZ SM_C_R,X
        DEX
                        BPL SM_C_TRANSFER_CLEAR
        LDA SM_D_ADDR
        STA SM_C_R+2
        LDA SM_D_ADDR+1
        STA SM_C_R+3
        LDA SM_D_BP
        STA SM_C_R+5
        LDA SM_D_BP+1
        STA SM_C_R+6
        LDA SM_D_COUNT
        STA SM_C_R+7
        PLA
        STA SM_C_R
        CMP #2
                        BNE SM_C_TRANSFER_READ
        PHP
        SEI
        STZ SM_C_MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA SM_C_MANAGED
        PLA
        PLP
                        BRA SM_C_TRANSFER_DONE
SM_C_TRANSFER_READ:
        JSR $66A6
SM_C_TRANSFER_DONE:
        CMP #0
                        BNE SM_C_TRANSFER_RETURN
        LDA SM_C_R
                        BEQ SM_C_TRANSFER_RETURN
        LDA SM_C_R+9
        CMP SM_D_COUNT
                        BNE SM_C_TRANSFER_SHORT
        LDA #0
SM_C_TRANSFER_RETURN:
        RTS
SM_C_TRANSFER_SHORT:
        LDA #7
        RTS
SM_C_BUF_POINTER:
        STZ SM_D_BP
        LDA #$64
        STA SM_D_BP+1
        RTS
SM_C_READ_BLOCK:
        JSR SM_C_BUF_POINTER
        LDA #64
        STA SM_D_COUNT
        LDA #1
        BRA SM_C_TRANSFER
SM_C_MOUNT:  STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BEQ SM_C_BM_LONG_218
                        JMP SM_C_MOUNT_RETURN
SM_C_BM_LONG_218:
        LDA SM_C_BUF+63
        CMP #$A5
                        BEQ SM_C_BM_LONG_221
                        JMP SM_C_UNFORMATTED
SM_C_BM_LONG_221:
        LDX #59
SM_C_LAYOUT_CHECK:
        JSR SM_A_SELECT_LAYOUT
                        BEQ SM_C_BM_LONG_225
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_225:
        LDX #31
SM_C_MAP_CLEAR:
        STZ SM_C_BITMAP,X
        DEX
                        BPL SM_C_MAP_CLEAR
        LDA #$FF
        STA SM_C_BITMAP
        STZ SM_D_SEQUENCE
        STZ SM_D_SEQUENCE+1
        STZ SM_D_USED
        STZ SM_D_INDEX
        LDA #8
        STA SM_D_FREE_SLOT
SM_C_SLOT_SCAN:
        JSR SM_C_SLOT_ADDRESS
        JSR SM_C_READ_BLOCK
                        BEQ SM_C_BM_LONG_242
                        JMP SM_C_MOUNT_RETURN
SM_C_BM_LONG_242:
        JSR SM_C_INDEX_REC
        LDY #31
SM_C_CACHE_LOOP:
        LDA SM_C_BUF,Y
        STA (SM_C_REC),Y
        DEY
                        BPL SM_C_CACHE_LOOP
        LDA SM_C_BUF+63
        LDY #3
        STA (SM_C_REC),Y
        CMP #$A5
                        BEQ SM_C_SLOT_COMMITTED
        LDA SM_D_INDEX
        STA SM_D_FREE_SLOT
                        JMP SM_C_NEXT_SLOT
SM_C_SLOT_COMMITTED:
        JSR SM_C_HEADER_CRC
                        BEQ SM_C_BM_LONG_260
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_260:
        LDA SM_C_BUF+3
        ORA SM_C_BUF+62
                        BEQ SM_C_BM_LONG_263
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_263:
        LDX #59
SM_C_SLOT_RESERVED:
        LDA SM_C_BUF,X
                        BEQ SM_C_BM_LONG_267
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_267:
        DEX
        CPX #31
                        BNE SM_C_SLOT_RESERVED
        LDA #<SM_C_BUF+16
        STA SM_C_TEXT
        LDA #>SM_C_BUF+16
        STA SM_C_TEXT+1
        JSR SM_C_CHECK_NAME_PTR
                        BEQ SM_C_BM_LONG_276
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_276:
        LDA SM_C_BUF
        CMP #'S'
                        BEQ SM_C_BM_LONG_279
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_279:
        LDA SM_C_BUF+1
        CMP #'P'
                        BEQ SM_C_BM_LONG_282
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_282:
        LDA SM_C_BUF+2
        CMP #1
                        BEQ SM_C_BM_LONG_285
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_285:
        LDA SM_C_BUF+15
        CMP #2
                        BEQ SM_C_TOMBSTONE_CHECK
        CMP #1
                        BEQ SM_C_BM_LONG_290
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_290:
        LDA SM_C_BUF+4
        STA SM_D_LOAD
        LDA SM_C_BUF+5
        STA SM_D_LOAD+1
        LDA SM_C_BUF+6
        STA SM_D_LENGTH
        LDA SM_C_BUF+7
        STA SM_D_LENGTH+1
        LDA SM_C_BUF+8
        STA SM_D_ENTRY
        LDA SM_C_BUF+9
        STA SM_D_ENTRY+1
        JSR SM_C_RANGE_CHECK
                        BNE SM_C_CORRUPT
        LDA SM_C_BUF+14
        CMP #8
                        BCC SM_C_CORRUPT
        STA SM_D_PAGE
        JSR SM_C_PAGE_COUNT
        LDA SM_D_PAGE
        CLC
        ADC SM_D_PAGES
        JSR SM_A_EXTENT_LIMIT
                        BNE SM_C_CORRUPT
SM_C_SLOT_MARK:
        JSR SM_C_MARK_PAGES
                        BNE SM_C_CORRUPT
                        BRA SM_C_SLOT_SEQUENCE
SM_C_TOMBSTONE_CHECK:
        LDA SM_C_BUF+6
        ORA SM_C_BUF+7
        ORA SM_C_BUF+14
                        BNE SM_C_CORRUPT
SM_C_SLOT_SEQUENCE:
        LDA SM_C_BUF+10
        ORA SM_C_BUF+11
                        BEQ SM_C_CORRUPT
        LDA SM_C_BUF+11
        CMP SM_D_SEQUENCE+1
                        BCC SM_C_NEXT_SLOT
                        BNE SM_C_SEQ_UPDATE
        LDA SM_C_BUF+10
        CMP SM_D_SEQUENCE
                        BCC SM_C_NEXT_SLOT
SM_C_SEQ_UPDATE:
        LDA SM_C_BUF+10
        STA SM_D_SEQUENCE
        LDA SM_C_BUF+11
        STA SM_D_SEQUENCE+1
SM_C_NEXT_SLOT:
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BEQ SM_C_BM_LONG_344
                        JMP SM_C_SLOT_SCAN
SM_C_BM_LONG_344:
        LDA #0
SM_C_MOUNT_RETURN:
        RTS
SM_C_UNFORMATTED:
        LDA #$40
        RTS
SM_C_CORRUPT:LDA #$41
        RTS
SM_C_INDEX_REC:
        LDA #$69
        STA SM_C_REC+1
        LDA SM_D_INDEX
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA SM_C_REC
        RTS
SM_C_BEST_REC:
        LDA SM_D_INDEX
        PHA
        LDA SM_D_BEST
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        PLA
        STA SM_D_INDEX
        RTS
SM_C_SLOT_ADDRESS:
        LDA SM_D_INDEX
        INC A
        LSR A
        LSR A
        STA SM_D_ADDR+1
        LDA SM_D_INDEX
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA SM_D_ADDR
        RTS
SM_C_PAGE_COUNT:
        LDA SM_D_LENGTH+1
        STA SM_D_PAGES
        LDA SM_D_LENGTH
                        BEQ SM_C_PAGE_COUNT_DONE
        INC SM_D_PAGES
SM_C_PAGE_COUNT_DONE:
        RTS
; MAP_BIT returns mask A, byte offset X for page PAGE. No wrap permitted.
SM_C_MAP_BIT:
        LDA SM_D_PAGE
        AND #7
        TAY
        LDA SM_D_MASKS,Y
        PHA
        LDA SM_D_PAGE
        LSR A
        LSR A
        LSR A
        TAX
        PLA
        RTS
SM_C_MARK_PAGES:
        JSR SM_C_MAP_BIT
        STA SM_D_MASK
        AND SM_C_BITMAP,X
                        BNE SM_C_CORRUPT
        LDA SM_D_MASK
        ORA SM_C_BITMAP,X
        STA SM_C_BITMAP,X
        INC SM_D_USED
        INC SM_D_PAGE
        DEC SM_D_PAGES
                        BNE SM_C_MARK_PAGES
        LDA #0
        RTS
SM_C_ALLOCATE:
        JSR SM_C_PAGE_COUNT
        STZ SM_D_RUN_LENGTH
        LDA #8
        STA SM_D_PAGE
SM_C_ALLOC_LOOP:
        JSR SM_C_MAP_BIT
        AND SM_C_BITMAP,X
                        BNE SM_C_ALLOC_OCCUPIED
        LDA SM_D_RUN_LENGTH
                        BNE SM_C_ALLOC_EXTEND
        LDA SM_D_PAGE
        STA SM_D_FIRST_PAGE
SM_C_ALLOC_EXTEND:
        INC SM_D_RUN_LENGTH
        LDA SM_D_RUN_LENGTH
        CMP SM_D_PAGES
                        BEQ SM_C_ALLOC_DONE
                        BRA SM_C_ALLOC_NEXT
SM_C_ALLOC_OCCUPIED:
        STZ SM_D_RUN_LENGTH
SM_C_ALLOC_NEXT:
        INC SM_D_PAGE
        LDA SM_D_PAGE
        CMP SM_D_LIMIT
                        BNE SM_C_ALLOC_LOOP
SM_C_FULL:   LDA #$43
        RTS
SM_C_ALLOC_DONE:
        LDA #0
        RTS
SM_C_NAME_CHECK:
        LDA #<SM_C_REQUEST+8
        STA SM_C_TEXT
        LDA #>SM_C_REQUEST+8
        STA SM_C_TEXT+1
SM_C_CHECK_NAME_PTR:
        STZ SM_D_PAD
        LDY #0
SM_C_NAME_LOOP:
        LDA (SM_C_TEXT),Y
                        BEQ SM_C_NAME_PAD
        LDX SM_D_PAD
                        BNE SM_C_NAME_BAD
        CMP #'-'
                        BEQ SM_C_NAME_NEXT
        CMP #'_'
                        BEQ SM_C_NAME_NEXT
        CMP #'0'
                        BCC SM_C_NAME_BAD
        CMP #'9'+1
                        BCC SM_C_NAME_NEXT
        CMP #'A'
                        BCC SM_C_NAME_BAD
        CMP #'Z'+1
                        BCS SM_C_NAME_BAD
                        BRA SM_C_NAME_NEXT
SM_C_NAME_PAD:
        INC SM_D_PAD
SM_C_NAME_NEXT:
        INY
        CPY #16
                        BNE SM_C_NAME_LOOP
        LDA (SM_C_TEXT)
                        BEQ SM_C_NAME_BAD
        LDA #0
        RTS
SM_C_NAME_BAD:
        LDA #$44
        RTS
SM_C_FIND_NAME:
        STZ SM_D_AMBIG
        LDA #8
        STA SM_D_BEST
        STZ SM_D_BEST_SEQ
        STZ SM_D_BEST_SEQ+1
        STZ SM_D_INDEX
SM_C_FIND_LOOP:
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_FIND_NEXT
        LDY #16
        LDX #0
SM_C_FIND_COMPARE:
        LDA (SM_C_REC),Y
        CMP SM_C_REQUEST+8,X
                        BNE SM_C_FIND_NEXT
        INY
        INX
        CPX #16
                        BNE SM_C_FIND_COMPARE
        LDY #11
        LDA (SM_C_REC),Y
        CMP SM_D_BEST_SEQ+1
                        BCC SM_C_FIND_NEXT
                        BNE SM_C_FIND_UPDATE
        DEY
        LDA (SM_C_REC),Y
        CMP SM_D_BEST_SEQ
                        BCC SM_C_FIND_NEXT
                        BNE SM_C_FIND_UPDATE
        LDA #$41
        STA SM_D_AMBIG
                        BRA SM_C_FIND_NEXT
SM_C_FIND_UPDATE:
        STZ SM_D_AMBIG
        LDY #10
        LDA (SM_C_REC),Y
        STA SM_D_BEST_SEQ
        INY
        LDA (SM_C_REC),Y
        STA SM_D_BEST_SEQ+1
        LDA SM_D_INDEX
        STA SM_D_BEST
SM_C_FIND_NEXT:
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BNE SM_C_FIND_LOOP
        LDA SM_D_AMBIG
        RTS
SM_C_RANGE_CHECK:
        LDA SM_D_LENGTH
        ORA SM_D_LENGTH+1
                        BEQ SM_C_NAME_BAD
        LDA SM_D_LOAD+1
        CMP #2
                        BCC SM_C_NAME_BAD
        CLC
        LDA SM_D_LOAD
        ADC SM_D_LENGTH
        STA SM_D_END_ADDR
        LDA SM_D_LOAD+1
        ADC SM_D_LENGTH+1
        STA SM_D_END_ADDR+1
                        BCC SM_C_BM_LONG_563
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_563:
        LDA SM_D_END_ADDR
                        BNE SM_C_RANGE_LIMIT
        DEC SM_D_END_ADDR+1
SM_C_RANGE_LIMIT:
        DEC SM_D_END_ADDR
        LDA SM_D_END_ADDR+1
        CMP $7D0B
                        BCC SM_C_RANGE_ENTRY
                        BEQ SM_C_BM_LONG_572
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_572:
        LDA SM_D_END_ADDR
        CMP $7D0A
                        BCC SM_C_RANGE_ENTRY
                        BEQ SM_C_BM_LONG_576
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_576:
SM_C_RANGE_ENTRY:
        LDA SM_D_ENTRY
        ORA SM_D_ENTRY+1
                        BEQ SM_C_RANGE_OK
        LDA SM_D_ENTRY
        SEC
        SBC SM_D_LOAD
        LDA SM_D_ENTRY+1
        SBC SM_D_LOAD+1
                        BCS SM_C_BM_LONG_586
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_586:
        LDA SM_D_END_ADDR
        SEC
        SBC SM_D_ENTRY
        LDA SM_D_END_ADDR+1
        SBC SM_D_ENTRY+1
                        BCS SM_C_BM_LONG_592
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_592:
SM_C_RANGE_OK:
        LDA #0
        RTS
SM_C_SAVE:   JSR SM_C_RESTORE_BUF
        LDA SM_C_REQUEST+2
        STA SM_D_LOAD
        LDA SM_C_REQUEST+3
        STA SM_D_LOAD+1
        SEC
        LDA SM_C_REQUEST+4
        SBC SM_D_LOAD
        STA SM_D_LENGTH
        LDA SM_C_REQUEST+5
        SBC SM_D_LOAD+1
        STA SM_D_LENGTH+1
                        BCS SM_C_BM_LONG_608
                        JMP SM_C_SAVE_BAD
SM_C_BM_LONG_608:
        INC SM_D_LENGTH
                        BNE SM_C_SAVE_LENGTH
        INC SM_D_LENGTH+1
SM_C_SAVE_LENGTH:
        LDA SM_C_REQUEST+6
        STA SM_D_ENTRY
        LDA SM_C_REQUEST+7
        STA SM_D_ENTRY+1
        JSR SM_C_RANGE_CHECK
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_ALLOCATE
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_NEW_RECORD
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_CRC_INIT
        LDA SM_D_LOAD
        STA SM_C_PTR
        LDA SM_D_LOAD+1
        STA SM_C_PTR+1
        JSR SM_C_SET_LEFT
SM_C_SAVE_CRC_LOOP:
        LDY #0
        JSR SM_S_SOURCE_BYTE
        JSR SM_C_CRC_BYTE
        INC SM_C_PTR
                        BNE SM_C_SAVE_CRC_NEXT
        INC SM_C_PTR+1
SM_C_SAVE_CRC_NEXT:
        JSR SM_C_DEC_LEFT
                        BNE SM_C_SAVE_CRC_LOOP
        LDY #12
        LDA SM_D_CRC
        STA (SM_C_REC),Y
        INY
        LDA SM_D_CRC+1
        STA (SM_C_REC),Y
        STZ SM_D_ADDR
        LDA SM_D_FIRST_PAGE
        STA SM_D_ADDR+1
        LDA SM_D_LOAD
        STA SM_D_BP
        LDA SM_D_LOAD+1
        STA SM_D_BP+1
        JSR SM_C_SET_LEFT
SM_C_SAVE_WRITE_LOOP:
        JSR SM_C_CHUNK
        JSR SM_S_SAVE_TRANSFER
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_ADVANCE
                        BNE SM_C_SAVE_WRITE_LOOP
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_PUBLISH
SM_C_SAVE_RETURN:
        JMP SM_C_FINISH
SM_C_SAVE_BAD:
        LDA #$44
                        JMP SM_C_SAVE_RETURN
SM_C_DELETE:
        LDA SM_D_BEST
        CMP #8
                        BCC SM_C_BM_LONG_670
                        JMP SM_C_NOT_FOUND
SM_C_BM_LONG_670:
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BEQ SM_C_BM_LONG_675
                        JMP SM_C_NOT_FOUND
SM_C_BM_LONG_675:
        STZ SM_D_LENGTH
        STZ SM_D_LENGTH+1
        STZ SM_D_FIRST_PAGE
        JSR SM_C_NEW_RECORD
                        BNE SM_C_SAVE_RETURN
        LDY #15
        LDA #2
        STA (SM_C_REC),Y
        JSR SM_C_PUBLISH
                        JMP SM_C_SAVE_RETURN
SM_C_NEW_RECORD:
        LDA SM_D_FREE_SLOT
        CMP #8
                        BCC SM_C_BM_LONG_689
                        JMP SM_C_FULL
SM_C_BM_LONG_689:
        LDA SM_D_SEQUENCE
        AND SM_D_SEQUENCE+1
        CMP #$FF
                        BEQ SM_C_SEQ_FULL
        INC SM_D_SEQUENCE
                        BNE SM_C_NEW_SEQ
        INC SM_D_SEQUENCE+1
SM_C_NEW_SEQ:
        LDA SM_D_FREE_SLOT
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #31
        LDA #0
SM_C_NEW_CLEAR:
        STA (SM_C_REC),Y
        DEY
                        BPL SM_C_NEW_CLEAR
        LDA #'S'
        STA (SM_C_REC)
        LDY #1
        LDA #'P'
        STA (SM_C_REC),Y
        INY
        LDA #1
        STA (SM_C_REC),Y
        LDY #4
        LDA SM_D_LOAD
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LOAD+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LENGTH
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LENGTH+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_ENTRY
        STA (SM_C_REC),Y
        INY
        LDA SM_D_ENTRY+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_SEQUENCE
        STA (SM_C_REC),Y
        INY
        LDA SM_D_SEQUENCE+1
        STA (SM_C_REC),Y
        LDY #14
        LDA SM_D_FIRST_PAGE
        STA (SM_C_REC),Y
        INY
        LDA #1
        STA (SM_C_REC),Y
        LDY #16
        LDX #0
SM_C_NEW_NAME:
        LDA SM_C_REQUEST+8,X
        STA (SM_C_REC),Y
        INY
        INX
        CPX #16
                        BNE SM_C_NEW_NAME
        LDA #0
        RTS
SM_C_SEQ_FULL:
        LDA #$48
        RTS
; Unpublished slot was free on mount. Payload is fully verified before header.
SM_C_PUBLISH:
        LDY #63
        LDA #0
SM_C_PUBLISH_CLEAR:
        STA SM_C_BUF,Y
        DEY
        CPY #31
                        BNE SM_C_PUBLISH_CLEAR
SM_C_PUBLISH_COPY:
        LDA (SM_C_REC),Y
        STA SM_C_BUF,Y
        DEY
                        BPL SM_C_PUBLISH_COPY
        JSR SM_C_SEAL_HEADER
        JSR SM_C_SLOT_ADDRESS
        JSR SM_C_WRITE_VERIFY
                        BNE SM_C_PUBLISH_RETURN
        LDA #$A5
        JSR SM_C_COMMIT_BYTE
SM_C_PUBLISH_RETURN:
        RTS
SM_C_COMMIT_BYTE:
        STA SM_C_BUF
        LDA SM_D_ADDR
        CLC
        ADC #63
        STA SM_D_ADDR
                        BCC SM_C_COMMIT_ADDR
        INC SM_D_ADDR+1
SM_C_COMMIT_ADDR:
        JSR SM_C_BUF_POINTER
        LDA #1
        STA SM_D_COUNT
        BRA SM_C_WRITE_VERIFY_COUNT
SM_C_WRITE_VERIFY:
        JSR SM_C_BUF_POINTER
        LDA #64
        STA SM_D_COUNT
SM_C_WRITE_VERIFY_COUNT:
        LDX SM_D_COUNT
        DEX
SM_C_VERIFY_BACKUP:
        LDA SM_C_BUF,X
        STA SM_C_EXPECTED,X
        DEX
                        BPL SM_C_VERIFY_BACKUP
        LDA #2
        JSR SM_C_TRANSFER
                        BNE SM_C_WRITE_RETURN
        LDA #1
        JSR SM_C_TRANSFER
                        BNE SM_C_WRITE_RETURN
        LDX SM_D_COUNT
        DEX
SM_C_VERIFY_COMPARE:
        LDA SM_C_BUF,X
        CMP SM_C_EXPECTED,X
                        BNE SM_C_CRC_BAD
        DEX
                        BPL SM_C_VERIFY_COMPARE
        LDA #0
SM_C_WRITE_RETURN:
        RTS
SM_C_CRC_BAD:LDA #$45
        RTS
SM_C_LOAD_RECORD:
        LDY #4
        LDA (SM_C_REC),Y
        STA SM_D_LOAD
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LOAD+1
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LENGTH
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LENGTH+1
        INY
        LDA (SM_C_REC),Y
        STA SM_D_ENTRY
        INY
        LDA (SM_C_REC),Y
        STA SM_D_ENTRY+1
        LDY #14
        LDA (SM_C_REC),Y
        STA SM_D_ADDR+1
        STZ SM_D_ADDR
SM_C_SET_LEFT:
        LDA SM_D_LENGTH
        STA SM_D_LEFT
        LDA SM_D_LENGTH+1
        STA SM_D_LEFT+1
        RTS
SM_C_CHUNK:  LDA #64
        LDX SM_D_LEFT+1
                        BNE SM_C_CHUNK_DONE
        CMP SM_D_LEFT
                        BCC SM_C_CHUNK_DONE
        LDA SM_D_LEFT
SM_C_CHUNK_DONE:
        STA SM_D_COUNT
        RTS
SM_C_ADVANCE:
        CLC
        LDA SM_D_BP
        ADC SM_D_COUNT
        STA SM_D_BP
                        BCC SM_C_ADVANCE_ADDR
        INC SM_D_BP+1
SM_C_ADVANCE_ADDR:
        CLC
        LDA SM_D_ADDR
        ADC SM_D_COUNT
        STA SM_D_ADDR
                        BCC SM_C_ADVANCE_LEFT
        INC SM_D_ADDR+1
SM_C_ADVANCE_LEFT:
        SEC
        LDA SM_D_LEFT
        SBC SM_D_COUNT
        STA SM_D_LEFT
        LDA SM_D_LEFT+1
        SBC #0
        STA SM_D_LEFT+1
        ORA SM_D_LEFT
        RTS
SM_C_DEC_LEFT:
        LDA SM_D_LEFT
                        BNE SM_C_DEC_LOW
        DEC SM_D_LEFT+1
SM_C_DEC_LOW:DEC SM_D_LEFT
        LDA SM_D_LEFT
        ORA SM_D_LEFT+1
        RTS
SM_C_VERIFY_PAYLOAD:
        JSR SM_C_LOAD_RECORD
        JSR SM_C_CRC_INIT
SM_C_PAYLOAD_LOOP:
        JSR SM_C_BUF_POINTER
        JSR SM_C_CHUNK
        LDA #1
        JSR SM_C_TRANSFER
                        BNE SM_C_PAYLOAD_RETURN
        LDY #0
SM_C_PAYLOAD_CRC:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY SM_D_COUNT
                        BNE SM_C_PAYLOAD_CRC
        JSR SM_C_ADVANCE
                        BNE SM_C_PAYLOAD_LOOP
        LDY #12
        LDA (SM_C_REC),Y
        CMP SM_D_CRC
                        BEQ SM_C_BM_LONG_916
                        JMP SM_C_CRC_BAD
SM_C_BM_LONG_916:
        INY
        LDA (SM_C_REC),Y
        CMP SM_D_CRC+1
                        BEQ SM_C_BM_LONG_920
                        JMP SM_C_CRC_BAD
SM_C_BM_LONG_920:
        LDA #0
SM_C_PAYLOAD_RETURN:
        RTS
SM_C_RESTORE:
        JSR SM_C_LOAD_RECORD
        JSR SM_C_RANGE_CHECK
                        BEQ SM_C_BM_LONG_927
                        JMP SM_C_SAVE_RETURN
SM_C_BM_LONG_927:
        LDA SM_C_REQUEST
        CMP #3
                        BNE SM_C_RESTORE_BEGIN
        LDA SM_D_ENTRY
        ORA SM_D_ENTRY+1
                        BEQ SM_C_NO_RUN
SM_C_RESTORE_BEGIN:
        JSR SM_C_RESTORE_BUF
        JSR SM_S_COPY_BEGIN
        LDA SM_D_LOAD
        STA SM_D_BP
        LDA SM_D_LOAD+1
        STA SM_D_BP+1
        JSR SM_C_CRC_INIT
SM_C_RESTORE_LOOP:
        JSR SM_C_CHUNK
        JSR SM_S_RESTORE_TRANSFER
                        BNE SM_C_PARTIAL
        LDA SM_D_BP
        STA SM_C_PTR
        LDA SM_D_BP+1
        STA SM_C_PTR+1
        LDY #0
SM_C_RESTORE_CRC:
        JSR SM_S_SOURCE_BYTE
        JSR SM_C_CRC_BYTE
        INY
        CPY SM_D_COUNT
                        BNE SM_C_RESTORE_CRC
        JSR SM_C_ADVANCE
                        BNE SM_C_RESTORE_LOOP
        LDY #12
        LDA (SM_C_REC),Y
        CMP SM_D_CRC
                        BNE SM_C_PARTIAL
        INY
        LDA (SM_C_REC),Y
        CMP SM_D_CRC+1
                        BNE SM_C_PARTIAL
        LDA SM_C_REQUEST
        CMP #3
                        BNE SM_C_RESTORE_OK
        LDA SM_D_ENTRY
        STA $FE
        LDA SM_D_ENTRY+1
        STA $FF
        JSR B29_APP_CHECK
        BCS B29_APP_OK
        LDA #$4A
        JMP SM_C_FINISH
B29_APP_OK:
        JMP X28_EXEC
SM_C_RESTORE_OK:
        LDA #0
        JMP SM_C_FINISH
SM_C_PARTIAL:LDA #$46
        JMP SM_C_FINISH
SM_C_NO_RUN: LDA #$47
        JMP SM_C_FINISH
; Bounded reclaim: only superseded records. Validate newest live payload first.
; Tombstones remain until FORMAT; no data moves and no automatic collection.
SM_C_RECLAIM:
        STZ SM_D_GC_INDEX
        STZ SM_D_GC_PASS
SM_C_GC_LOOP:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_GC_NEXT
        LDY #16
        LDX #0
SM_C_GC_NAME:
        LDA (SM_C_REC),Y
        STA SM_C_REQUEST+8,X
        INY
        INX
        CPX #16
                        BNE SM_C_GC_NAME
        JSR SM_C_FIND_NAME
                        BNE SM_C_GC_RETURN
        LDA SM_D_BEST
        CMP SM_D_GC_INDEX
                        BNE SM_C_GC_SUPERSEDED
        LDA SM_D_GC_PASS
                        BEQ SM_C_GC_NEXT
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #2
                        BEQ SM_C_GC_CLEAR
                        BRA SM_C_GC_NEXT
SM_C_GC_SUPERSEDED:
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_GC_CLEAR
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_GC_RETURN
SM_C_GC_CLEAR:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_SLOT_ADDRESS
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_GC_RETURN
        JSR SM_C_INDEX_REC
        LDY #3
        LDA #0
        STA (SM_C_REC),Y
SM_C_GC_NEXT:
        INC SM_D_GC_INDEX
        LDA SM_D_GC_INDEX
        CMP #8
                        BNE SM_C_GC_LOOP
        LDA SM_D_GC_PASS
                        BNE SM_C_GC_DONE
        INC SM_D_GC_PASS
        STZ SM_D_GC_INDEX
                        BRA SM_C_GC_LOOP
SM_C_GC_DONE:
        LDA #0
SM_C_GC_RETURN:
        JMP SM_C_FINISH
SM_C_FORMAT: LDX #7
SM_C_FORMAT_KEY:
        LDA SM_C_REQUEST+24,X
        CMP SM_D_FORMAT_MAGIC,X
                        BEQ SM_C_BM_LONG_1050
                        JMP SM_C_ARG_BAD
SM_C_BM_LONG_1050:
        DEX
                        BPL SM_C_FORMAT_KEY
        JSR SM_A_FORMAT_GUARD
                        BNE SM_C_FORMAT_RETURN
        ; Invalidate and verify layout first. Never clear directory under a
        ; still-valid old header. Interrupted format requires explicit retry.
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_FORMAT_RETURN
        STZ SM_D_INDEX
SM_C_FORMAT_SLOTS:
        JSR SM_C_SLOT_ADDRESS
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_FORMAT_RETURN
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BNE SM_C_FORMAT_SLOTS
        LDX #59
SM_C_FORMAT_LAYOUT:
        LDA SM_D_LAYOUT,X
        STA SM_C_BUF,X
        DEX
                        BPL SM_C_FORMAT_LAYOUT
        STZ SM_C_BUF+62
        STZ SM_C_BUF+63
        JSR SM_C_SEAL_HEADER
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_WRITE_VERIFY
                        BNE SM_C_FORMAT_RETURN
        LDA #$A5
        JSR SM_C_COMMIT_BYTE
SM_C_FORMAT_RETURN:
        JMP SM_C_FINISH
SM_C_CRC_INIT:
        LDA #$FF
        STA SM_D_CRC
        STA SM_D_CRC+1
        RTS
SM_C_CRC_BYTE:
        EOR SM_D_CRC+1
        STA SM_D_CRC+1
        LDX #8
SM_C_CRC_BIT:
        ASL SM_D_CRC
        ROL SM_D_CRC+1
                        BCC SM_C_CRC_NEXT
        LDA SM_D_CRC
        EOR #$21
        STA SM_D_CRC
        LDA SM_D_CRC+1
        EOR #$10
        STA SM_D_CRC+1
SM_C_CRC_NEXT:
        DEX
                        BNE SM_C_CRC_BIT
        RTS
SM_C_HEADER_CRC:
        JSR SM_C_CRC_INIT
        LDY #0
SM_C_HEADER_CRC_LOOP:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY #62
                        BNE SM_C_HEADER_CRC_LOOP
        LDA SM_D_CRC
        ORA SM_D_CRC+1
        RTS
SM_C_SEAL_HEADER:
        JSR SM_C_CRC_INIT
        LDY #0
SM_C_SEAL_LOOP:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY #60
                        BNE SM_C_SEAL_LOOP
        LDA SM_D_CRC+1
        STA SM_C_BUF+60
        LDA SM_D_CRC
        STA SM_C_BUF+61
        RTS
SM_C_CONSOLE:
        SEI
        CLD
        LDX #<SM_D_TITLE
        LDY #>SM_D_TITLE
        JSR SM_C_PRINT
        JSR SM_C_HELP
SM_C_PROMPT: LDX #<SM_D_PROMPT_TEXT
        LDY #>SM_D_PROMPT_TEXT
        JSR SM_C_PRINT
        JSR B29_LINE_2
                        BCC SM_C_PROMPT
        LDX #31
SM_C_REQUEST_CLEAR:
        STZ SM_C_REQUEST,X
        DEX
                        BPL SM_C_REQUEST_CLEAR
        LDA SM_C_LINE+1
                        BEQ SM_C_CON_COMMAND
        LDA SM_C_LINE
        CMP #'S'
                        BEQ SM_C_CON_COMMAND
        CMP #'SM_C_R'
                        BEQ SM_C_CON_COMMAND
        CMP #'G'
                        BEQ SM_C_CON_COMMAND
        CMP #'D'
                        BEQ SM_C_BM_LONG_1165
                        JMP SM_C_CON_BAD
SM_C_BM_LONG_1165:
SM_C_CON_COMMAND:
        LDA SM_C_LINE
        CMP #'Q'
                        BNE SM_C_BM_LONG_1169
                        JMP SM_C_QUIT
SM_C_BM_LONG_1169:
        CMP #'?'
                        BNE SM_C_BM_LONG_1171
                        JMP SM_C_CON_HELP
SM_C_BM_LONG_1171:
        CMP #'T'
                        BNE SM_C_BM_LONG_1173
                        JMP SM_C_TABLE
SM_C_BM_LONG_1173:
        CMP #'C'
                        BNE SM_C_BM_LONG_1175
                        JMP SM_C_CON_RECLAIM
SM_C_BM_LONG_1175:
        CMP #'F'
                        BNE SM_C_BM_LONG_1177
                        JMP SM_C_CON_FORMAT
SM_C_BM_LONG_1177:
        CMP #'S'
                        BEQ SM_C_CON_SAVE
        CMP #'SM_C_R'
                        BEQ SM_C_CON_RESTORE
        CMP #'G'
                        BEQ SM_C_CON_RUN
        CMP #'D'
                        BNE SM_C_CON_BAD
        LDA #4
                        JMP SM_C_CON_NAMED
SM_C_CON_RUN:LDA #3
                        JMP SM_C_CON_NAMED
SM_C_CON_RESTORE:
        LDA #2
SM_C_CON_NAMED:
        STA SM_C_REQUEST
        JSR SM_C_PARSE_NAME
                        BCC SM_C_CON_BAD
        LDA SM_C_LINE,X
                        BNE SM_C_CON_BAD
                        JMP SM_C_CON_DO
SM_C_CON_SAVE:
        LDA #1
        STA SM_C_REQUEST
        JSR SM_C_PARSE_NAME
                        BCC SM_C_CON_BAD
        LDY #2
SM_C_PARSE_WORDS:
        LDA SM_C_LINE,X
        CMP #' '
                        BNE SM_C_CON_BAD
        INX
        JSR SM_C_PARSE_HEX
                        BCC SM_C_CON_BAD
        LDA SM_D_WORD
        STA SM_C_REQUEST,Y
        INY
        LDA SM_D_WORD+1
        STA SM_C_REQUEST,Y
        INY
        CPY #8
                        BNE SM_C_PARSE_WORDS
        LDA SM_C_LINE,X
                        BNE SM_C_CON_BAD
SM_C_CON_DO: JSR SM_C_OPERATION
SM_C_CON_RESULT:
        CMP #0
        BEQ B29_SRAM_OK
        JSR B29_ERROR_HOOK
B29_SRAM_OK:
        PHA
        LDX #<SM_D_RESULT_TEXT
        LDY #>SM_D_RESULT_TEXT
        JSR SM_C_PRINT
        PLA
        JSR SM_C_HEX
        JSR SM_C_NL
        JMP SM_C_PROMPT
SM_C_CON_BAD:LDA #$44
                        JMP SM_C_CON_RESULT
SM_C_CON_RECLAIM:
        LDA #5
        STA SM_C_REQUEST
                        JMP SM_C_CON_DO
SM_C_CON_FORMAT:
        LDX #<SM_D_CONFIRM_TEXT
        LDY #>SM_D_CONFIRM_TEXT
        JSR SM_C_PRINT
        JSR SM_C_READLINE
                        BCS SM_C_BM_LONG_1243
                        JMP SM_C_PROMPT
SM_C_BM_LONG_1243:
        LDX #11
SM_C_CONFIRM_CHECK:
        LDA SM_C_LINE,X
        CMP SM_D_CONFIRM_MAGIC,X
                        BNE SM_C_CON_BAD
        DEX
                        BPL SM_C_CONFIRM_CHECK
        LDX #7
SM_C_CON_FORMAT_KEY:
        LDA SM_D_FORMAT_MAGIC,X
        STA SM_C_REQUEST+24,X
        DEX
                        BPL SM_C_CON_FORMAT_KEY
        LDA #6
        STA SM_C_REQUEST
                        JMP SM_C_CON_DO
SM_C_CON_HELP:
        JSR SM_C_HELP
        JMP SM_C_PROMPT
SM_C_QUIT:   JMP $7E67
SM_C_HELP:   LDX #<SM_D_HELP_TEXT
        LDY #>SM_D_HELP_TEXT
        JMP SM_C_PRINT
SM_C_TABLE:  JSR SM_C_OPERATION
                        BNE SM_C_CON_RESULT
        STZ SM_D_GC_INDEX
SM_C_TABLE_LOOP:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_TABLE_NEXT
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_TABLE_NEXT
        LDY #16
        LDX #0
SM_C_TABLE_NAME_COPY:
        LDA (SM_C_REC),Y
        STA SM_C_REQUEST+8,X
        INY
        INX
        CPX #16
                        BNE SM_C_TABLE_NAME_COPY
        JSR SM_C_FIND_NAME
                        BEQ SM_C_BM_LONG_1292
                        JMP SM_C_CON_RESULT
SM_C_BM_LONG_1292:
        LDA SM_D_BEST
        CMP SM_D_GC_INDEX
                        BNE SM_C_TABLE_NEXT
        JSR SM_C_BEST_REC
        LDY #16
SM_C_TABLE_NAME:
        LDA (SM_C_REC),Y
                        BEQ SM_C_TABLE_FIELDS
        JSR SM_C_PUTC
        INY
        CPY #32
                        BNE SM_C_TABLE_NAME
SM_C_TABLE_FIELDS:
        LDA #' '
        JSR SM_C_PUTC
        LDY #5
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        DEY
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        LDA #' '
        JSR SM_C_PUTC
        LDY #7
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        DEY
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        JSR SM_C_NL
SM_C_TABLE_NEXT:
        INC SM_D_GC_INDEX
        LDA SM_D_GC_INDEX
        CMP #8
                        BNE SM_C_TABLE_LOOP
        LDX #<SM_D_FREE_TEXT
        LDY #>SM_D_FREE_TEXT
        JSR SM_C_PRINT
        JSR SM_A_FREE_PAGES
        JSR SM_C_HEX
        LDA #0
        JSR SM_C_HEX
        JSR SM_C_NL
        JMP SM_C_PROMPT
SM_C_PARSE_NAME:
        LDX #1
        LDA SM_C_LINE,X
        CMP #' '
                        BNE SM_C_PARSE_FAIL
        INX
        LDY #0
SM_C_PARSE_NAME_LOOP:
        LDA SM_C_LINE,X
                        BEQ SM_C_PARSE_NAME_DONE
        CMP #' '
                        BEQ SM_C_PARSE_NAME_DONE
        CPY #16
                        BCS SM_C_PARSE_FAIL
        STA SM_C_REQUEST+8,Y
        INY
        INX
                        BRA SM_C_PARSE_NAME_LOOP
SM_C_PARSE_NAME_DONE:
        CPY #0
                        BEQ SM_C_PARSE_FAIL
        SEC
        RTS
SM_C_PARSE_HEX:
        STZ SM_D_WORD
        STZ SM_D_WORD+1
        LDA #4
        STA SM_D_DIGITS
SM_C_PARSE_HEX_LOOP:
        LDA SM_C_LINE,X
        CMP #'0'
                        BCC SM_C_PARSE_FAIL
        CMP #'9'+1
                        BCC SM_C_PARSE_DIGIT
        CMP #'A'
                        BCC SM_C_PARSE_FAIL
        CMP #'F'+1
                        BCS SM_C_PARSE_FAIL
        SEC
        SBC #7
SM_C_PARSE_DIGIT:
        SEC
        SBC #'0'
        PHX
        LDX #4
SM_C_PARSE_SHIFT:
        ASL SM_D_WORD
        ROL SM_D_WORD+1
        DEX
                        BNE SM_C_PARSE_SHIFT
        PLX
        ORA SM_D_WORD
        STA SM_D_WORD
        INX
        DEC SM_D_DIGITS
                        BNE SM_C_PARSE_HEX_LOOP
        SEC
        RTS
SM_C_PARSE_FAIL:
        CLC
        RTS
SM_C_READLINE:
        STZ SM_D_LINE_LENGTH
        STZ SM_D_OVERFLOW
SM_C_LINE_WAIT:
        JSR SM_C_GETC
        CMP #3
                        BEQ SM_C_LINE_CANCEL
        CMP #$1B
                        BEQ SM_C_LINE_CANCEL
        CMP #10
                        BEQ SM_C_LINE_WAIT
        CMP #13
                        BEQ SM_C_LINE_DONE
        CMP #8
                        BEQ SM_C_LINE_BACK
        CMP #$7F
                        BEQ SM_C_LINE_BACK
        CMP #$20
                        BCC SM_C_LINE_WAIT
        CMP #'a'
                        BCC SM_C_LINE_CHAR
        CMP #'z'+1
                        BCS SM_C_LINE_CHAR
        AND #$DF
SM_C_LINE_CHAR:
        LDX SM_D_LINE_LENGTH
        CPX #39
                        BCS SM_C_LINE_FULL
        STA SM_C_LINE,X
        INC SM_D_LINE_LENGTH
        JSR SM_C_PUTC
                        JMP SM_C_LINE_WAIT
SM_C_LINE_FULL:
        LDA #1
        STA SM_D_OVERFLOW
                        JMP SM_C_LINE_WAIT
SM_C_LINE_BACK:
        LDA SM_D_LINE_LENGTH
                        BEQ SM_C_LINE_WAIT
        DEC SM_D_LINE_LENGTH
        LDA #8
        JSR SM_C_PUTC
        LDA #' '
        JSR SM_C_PUTC
        LDA #8
        JSR SM_C_PUTC
                        JMP SM_C_LINE_WAIT
SM_C_LINE_DONE:
        LDX SM_D_LINE_LENGTH
        STZ SM_C_LINE,X
        JSR SM_C_NL
        LDA SM_D_OVERFLOW
                        BNE SM_C_LINE_CANCEL
        SEC
        RTS
SM_C_LINE_CANCEL: JSR B29_CANCEL_HOOK

        JSR SM_C_NL
        CLC
        RTS
SM_C_PRINT:  STX SM_C_TEXT
        STY SM_C_TEXT+1
        LDY #0
SM_C_PRINT_LOOP:
        LDA (SM_C_TEXT),Y
                        BEQ SM_C_PRINT_DONE
        JSR SM_C_PUTC
        INY
                        BRA SM_C_PRINT_LOOP
SM_C_PRINT_DONE:
        RTS
SM_C_APP_END:

; SRAM 1.1 layout reader: primary only. WORK repairs interrupted primary.
SM_A_SELECT_LAYOUT:
        JSR SM_C_HEADER_CRC
                        BEQ SM_A_BM_LONG_8
                        JMP SM_A_LAYOUT_BAD
SM_A_BM_LONG_8:
        LDA SM_S_BUF
        CMP #'S'
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+1
        CMP #'S'
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+3
        CMP #8
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+4
        CMP #8
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+2
        CMP #1
                        BEQ SM_A_SELECT_LEGACY
        CMP #2
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+7
        ORA SM_S_BUF+62
                        BNE SM_A_LAYOUT_BAD
        LDX #59
SM_A_LAYOUT_RESERVED:
        LDA SM_S_BUF,X
                        BNE SM_A_LAYOUT_BAD
        DEX
        CPX #11
                        BNE SM_A_LAYOUT_RESERVED
        LDA SM_S_BUF+8
        ORA SM_S_BUF+9
        ORA SM_S_BUF+10
        ORA SM_S_BUF+11
                        BEQ SM_A_LAYOUT_BAD
        LDA SM_S_BUF+5
        AND #$3F
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+6
                        BEQ SM_A_SELECT_SMALL
        CMP #1
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+5
                        BNE SM_A_LAYOUT_BAD
                        JMP SM_A_SELECT_OK
SM_A_SELECT_SMALL:
        LDA SM_S_BUF+5
                        BEQ SM_A_LAYOUT_BAD
SM_A_SELECT_OK:
        LDA SM_S_BUF+5
        STA SM_D_LIMIT
        LDA #0
        RTS
SM_A_SELECT_LEGACY:
        LDX #59
SM_A_LEGACY_COMPARE:
        LDA SM_S_BUF,X
        CMP SM_D_LAYOUT,X
                        BNE SM_A_LAYOUT_BAD
        DEX
                        BPL SM_A_LEGACY_COMPARE
                        JMP SM_A_SELECT_OK
SM_A_LAYOUT_BAD:
        LDA #$41
        RTS
SM_A_EXTENT_LIMIT:
                        BCC SM_A_EXTENT_NORMAL
                        BNE SM_A_LAYOUT_BAD
        LDX SM_D_LIMIT
                        BNE SM_A_LAYOUT_BAD
                        BRA SM_A_EXTENT_OK
SM_A_EXTENT_NORMAL:
        LDX SM_D_LIMIT
                        BEQ SM_A_EXTENT_OK
        CMP SM_D_LIMIT
                        BCC SM_A_EXTENT_OK
                        BNE SM_A_LAYOUT_BAD
SM_A_EXTENT_OK:
        LDA #0
        RTS
SM_A_FREE_PAGES:
        LDA SM_D_LIMIT
        SEC
        SBC #8
        SEC
        SBC SM_D_USED
        RTS
SM_A_FORMAT_GUARD:
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BNE SM_A_GUARD_RETURN
        JSR SM_A_CHECK_V2
                        BNE SM_A_GUARD_RETURN
        LDA #$40
        STA SM_D_ADDR
        LDA #2
        STA SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BNE SM_A_GUARD_RETURN
SM_A_CHECK_V2:
        LDA SM_S_BUF+2
        CMP #2
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF+63
        CMP #$A5
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF
        CMP #'S'
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF+1
        CMP #'S'
                        BNE SM_A_GUARD_OK
        LDA #$49
SM_A_GUARD_RETURN:
        RTS
SM_A_GUARD_OK:
        LDA #0
        RTS
SM_A_AUX_END:

; Trusted MAINT streaming hooks. Ordinary SRAM API/console uses zero hooks.
SM_S_PTR EQU $D2
SM_S_BUF EQU $6400
SM_S_SOURCE_BYTE:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_STAGED_BYTE
        LDA SM_D_SOURCE_BYTE_HOOK+1
                        BNE SM_S_HOOK_BYTE
        LDA (SM_S_PTR),Y
        RTS
SM_S_STAGED_BYTE:
        LDA SM_S_BUF,Y
        RTS
SM_S_HOOK_BYTE:
        JMP (SM_D_SOURCE_BYTE_HOOK)
SM_S_SAVE_TRANSFER:
        LDA SM_D_SAVE_TRANSFER_HOOK+1
                        BNE SM_S_HOOK_SAVE
        LDA #2
        JMP SM_C_TRANSFER
SM_S_HOOK_SAVE:
        JMP (SM_D_SAVE_TRANSFER_HOOK)
SM_S_RESTORE_TRANSFER:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_HOOK_RESTORE
        LDA #1
        JMP SM_C_TRANSFER
SM_S_HOOK_RESTORE:
        JMP (SM_D_RESTORE_TRANSFER_HOOK)
SM_S_COPY_BEGIN:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_COPY_RETURN
        INC SM_D_COPYING
SM_S_COPY_RETURN:
        RTS
SM_S_EXT_END:

SM_D_SV_MAGIC DB "SV",1
SM_D_SM_MAGIC DB "SM",1,1
SM_D_MASKS DB 1,2,4,8,16,32,64,128
; SS v1: 8 x 64 directory at 0040; data 0800-FFFF; workspace 10000-1FFDF.
SM_D_LAYOUT DB "SS",1,8,8,0,1,0
        DS 52
SM_D_FORMAT_MAGIC DB "FORMAT!!"
SM_D_CONFIRM_MAGIC DB "FORMAT SRAM",0
SM_D_TITLE DB "SRAM 1.4",13,10,0
SM_D_PROMPT_TEXT DB "SRAM> ",0
SM_D_HELP_TEXT DB "S name start end entry; R/G/D name; T C F Q",13,10,0
SM_D_CONFIRM_TEXT DB "Type FORMAT SRAM: ",0
SM_D_RESULT_TEXT DB "SRAM: ",0
SM_D_FREE_TEXT DB "Free bytes: $",0
SM_D_ADDR EQU $67C7
SM_D_BP EQU $67C9
SM_D_LEFT EQU $67CB
SM_D_LOAD EQU $67CD
SM_D_LENGTH EQU $67CF
SM_D_END_ADDR EQU $67D1
SM_D_ENTRY EQU $67D3
SM_D_CRC EQU $67D5
SM_D_SEQUENCE EQU $67D7
SM_D_BEST_SEQ EQU $67D9
SM_D_WORD EQU $67DB
SM_D_COUNT EQU $67DD
SM_D_STATUS EQU $67DE
SM_D_COPYING EQU $67DF
SM_D_INDEX EQU $67E0
SM_D_FREE_SLOT EQU $67E1
SM_D_BEST EQU $67E2
SM_D_USED EQU $67E3
SM_D_PAGE EQU $67E4
SM_D_PAGES EQU $67E5
SM_D_MASK EQU $67E6
SM_D_RUN_LENGTH EQU $67E7
SM_D_FIRST_PAGE EQU $67E8
SM_D_PAD EQU $67E9
SM_D_GC_INDEX EQU $67EA
SM_D_GC_PASS EQU $67EB
SM_D_DIGITS EQU $67EC
SM_D_LINE_LENGTH EQU $67ED
SM_D_OVERFLOW EQU $67EE
SM_D_AMBIG EQU $67EF
SM_D_LIMIT EQU $67F0
SM_D_SOURCE_BYTE_HOOK EQU $67F1
SM_D_SAVE_TRANSFER_HOOK EQU $67F3
SM_D_RESTORE_TRANSFER_HOOK EQU $67F5
SM_D_DATA_END:
WK_ENTRY:  JSR WK_SAVE_WINDOW
        JSR WK_CLEAR_STATE
        JMP WK_CONSOLE
WK_SAVE_WINDOW:
        PHA
        PHX
        LDX #63
WK_SAVE_WINDOW_LOOP:
        LDA $6400,X
        STA $6A40,X
        DEX
        BPL WK_SAVE_WINDOW_LOOP
        PLX
        PLA
        RTS
WK_RESTORE_WINDOW:
        PHA
        PHX
        LDX #63
WK_RESTORE_WINDOW_LOOP:
        LDA $6A40,X
        STA $6400,X
        DEX
        BPL WK_RESTORE_WINDOW_LOOP
        PLX
        PLA
        RTS
WK_CLEAR_STATE:
        PHX
        LDX #0
WK_CLEAR_LOOP:
        STZ $6800,X
        STZ $6900,X
        INX
        BNE WK_CLEAR_LOOP
        LDX #30
WK_CLEAR_TAIL:
        STZ $6A00,X
        DEX
        BPL WK_CLEAR_TAIL
        PLX
        RTS
; Optional application library, not additional resident RAM. W65C02S/816E.
WK_P EQU $D0
WK_Q EQU $D2
WK_C EQU $D4
WK_R EQU $6650
WK_RESET_LATCH EQU $66AF
WK_MANAGED EQU $66AE
WK_PUTC EQU $7E6D
WK_GETC EQU $7E70
WK_HEX EQU $7E7C
WK_NL EQU $7E7F
WK_START:  JMP WK_CONSOLE
        BRA WK_API
        DB "WK",1,2
WK_API:    JSR WK_SAVE_WINDOW
        JSR WK_CLEAR_STATE
        SEI
        CLD
        STA WK_C
        STX WK_C+1
        LDA #32
        STA WK_N
        JSR WK_CPU_RANGE
                        BNE WK_API_RETURN
        LDY #31
WK_COPY_REQUEST:
        LDA (WK_C),Y
        STA WK_REQ,Y
        DEY
                        BPL WK_COPY_REQUEST
        JSR WK_OPERATION
        PHA
        LDY #31
WK_COPY_RESULT:
        LDA WK_REQ,Y
        STA (WK_C),Y
        DEY
                        BPL WK_COPY_RESULT
        PLA
WK_API_RETURN:
        JSR WK_RESTORE_WINDOW
        CMP #0
                        BNE WK_API_ERROR
        SEC
        RTS
WK_API_ERROR:
        CLC
        RTS
WK_OPERATION:
        STZ WK_CHECKING
        JSR WK_DISCOVER
                        BEQ WK_BM_LONG_52
                        JMP WK_OP_RETURN
WK_BM_LONG_52:
        LDA WK_REQ+1
                        BNE WK_BAD_ARG
        LDA WK_REQ
        CMP #9
                        BCS WK_BAD_ARG
        CMP #6
                        BNE WK_BM_LONG_59
                        JMP WK_FORMAT
WK_BM_LONG_59:
        CMP #7
                        BNE WK_BM_LONG_61
                        JMP WK_UPGRADE
WK_BM_LONG_61:
        JSR WK_LOAD_LAYOUT
                        BNE WK_OP_RETURN
        LDA WK_REQ
                        BNE WK_BM_LONG_65
                        JMP WK_QUERY
WK_BM_LONG_65:
        LDA WK_LEGACY
                        BNE WK_NEED_UPGRADE
        LDA WK_REQ
        CMP #8
                        BNE WK_BM_LONG_70
                        JMP WK_REPAIR
WK_BM_LONG_70:
        JSR WK_SESSION_LOAD
                        BNE WK_OP_RETURN
        LDA WK_RESET_LATCH
                        BNE WK_SESSION_READY
        JSR WK_NEW_EPOCH
                        BNE WK_OP_RETURN
WK_SESSION_READY:
        JSR WK_LOAD_CLAIMS
                        BNE WK_OP_RETURN
        JSR WK_PROGRAM_CHECK
                        BNE WK_OP_RETURN
        LDA WK_REQ
        CMP #5
                        BNE WK_BM_LONG_84
                        JMP WK_RESIZE
WK_BM_LONG_84:
        LDA WK_REQ+2
        ORA WK_REQ+3
                        BEQ WK_BAD_ARG
        LDA WK_REQ
        CMP #1
                        BNE WK_BM_LONG_90
                        JMP WK_CLAIM
WK_BM_LONG_90:
        JSR WK_HANDLE
                        BNE WK_OP_RETURN
        LDA WK_REQ
        CMP #2
                        BNE WK_BM_LONG_95
                        JMP WK_RELEASE
WK_BM_LONG_95:
        JMP WK_IO
WK_OP_RETURN:
        RTS
WK_BAD_ARG:LDA #$44
        RTS
WK_BAD_META:
        LDA #$41
        RTS
WK_NEED_UPGRADE:
        LDA #$49
        RTS
WK_STALE:  LDA #$4B
        RTS
WK_FULL:   LDA #$43
        RTS
WK_VERIFY_BAD:
        LDA #$45
        RTS
WK_EXHAUSTED:
        LDA #$48
        RTS
WK_DISCOVER:
        LDX #2
WK_DISCOVER_SV:
        LDA $7D04,X
        CMP WK_SV_MAGIC,X
                        BNE WK_ABSENT
        DEX
                        BPL WK_DISCOVER_SV
        LDA $7D07
        AND #8
                        BEQ WK_ABSENT
        LDA $7D08
                        BNE WK_ABSENT
        LDA $7D09
        CMP #$65
                        BNE WK_ABSENT
        LDX #3
WK_DISCOVER_SM:
        LDA $66A2,X
        CMP WK_SM_MAGIC,X
                        BNE WK_ABSENT
        DEX
                        BPL WK_DISCOVER_SM
        STZ WK_N
        LDA #0
        JMP WK_TRANSFER
WK_ABSENT: LDA #$80
        RTS
WK_BUF_PTR:
        LDA #<WK_BUF
        STA WK_BP
        LDA #>WK_BUF
        STA WK_BP+1
        RTS
WK_TRANSFER:
        PHA
        LDX #15
WK_REQUEST_ZERO:
        STZ WK_R,X
        DEX
                        BPL WK_REQUEST_ZERO
        LDX #2
WK_REQUEST_ADDR:
        LDA WK_ADDR,X
        STA WK_R+2,X
        DEX
                        BPL WK_REQUEST_ADDR
        LDA WK_BP
        STA WK_R+5
        LDA WK_BP+1
        STA WK_R+6
        LDA WK_N
        STA WK_R+7
        PLA
        STA WK_R
        CMP #2
                        BNE WK_TRAN_READ
        STZ WK_MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA WK_MANAGED
        PLA
                        BRA WK_TRAN_RESULT
WK_TRAN_READ:
        JSR $66A6
WK_TRAN_RESULT:
        CMP #0
                        BNE WK_TRAN_RETURN
        LDA WK_R
                        BEQ WK_TRAN_RETURN
        LDA WK_R+9
        CMP WK_N
                        BNE WK_TRAN_SHORT
        LDA #0
WK_TRAN_RETURN:
        RTS
WK_TRAN_SHORT:
        LDA #7
        RTS
WK_READ64: LDA #64
                        BRA WK_READ_N
WK_READ32: LDA #32
WK_READ_N: STA WK_N
        JSR WK_BUF_PTR
        LDA #1
        JMP WK_TRANSFER
WK_WRITE_VERIFY:
        JSR WK_BUF_PTR
        LDX WK_N
        DEX
WK_EXPECT_COPY:
        LDA WK_BUF,X
        STA WK_EXPECT,X
        DEX
                        BPL WK_EXPECT_COPY
        LDA #2
        JSR WK_TRANSFER
                        BNE WK_WRITE_RETURN
        LDA #1
        JSR WK_TRANSFER
                        BNE WK_WRITE_RETURN
        LDX WK_N
        DEX
WK_EXPECT_CHECK:
        LDA WK_BUF,X
        CMP WK_EXPECT,X
                        BEQ WK_BM_LONG_224
                        JMP WK_VERIFY_BAD
WK_BM_LONG_224:
        DEX
                        BPL WK_EXPECT_CHECK
        LDA #0
WK_WRITE_RETURN:
        RTS
; Publish a 32/64-byte packet. Invalidate/verify old final marker first.
WK_PUBLISH:
        LDA WK_N
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_PUB_RETURN
        LDX WK_PACKET_N
        DEX
WK_PUB_RESTORE:
        LDA WK_EXPECT_PACKET,X
        STA WK_BUF,X
        DEX
                        BPL WK_PUB_RESTORE
        LDA WK_PACKET_N
        STA WK_N
        JSR WK_WRITE_VERIFY
                        BNE WK_PUB_RETURN
        LDA #$A5
        JSR WK_MARKER
WK_PUB_RETURN:
        RTS
WK_SAVE_PACKET:
        LDX WK_N
        DEX
WK_PACKET_COPY:
        LDA WK_BUF,X
        STA WK_EXPECT_PACKET,X
        DEX
                        BPL WK_PACKET_COPY
        RTS
WK_MARKER:
        PHA
        LDX #2
WK_MARK_SAVE:
        LDA WK_ADDR,X
        STA WK_SAVE_ADDR,X
        DEX
                        BPL WK_MARK_SAVE
        LDA WK_PACKET_N
        DEC A
        CLC
        ADC WK_ADDR
        STA WK_ADDR
                        BCC WK_MARK_ADDR
        INC WK_ADDR+1
                        BNE WK_MARK_ADDR
        INC WK_ADDR+2
WK_MARK_ADDR:
        PLA
        STA WK_BUF
        LDA #1
        STA WK_N
        JSR WK_WRITE_VERIFY
        PHA
        LDX #2
WK_MARK_RESTORE:
        LDA WK_SAVE_ADDR,X
        STA WK_ADDR,X
        DEX
                        BPL WK_MARK_RESTORE
        PLA
        CMP #0
        RTS
WK_CRC_INIT:
        LDA #$FF
        STA WK_CRC
        STA WK_CRC+1
        RTS
WK_CRC_BYTE:
        EOR WK_CRC+1
        STA WK_CRC+1
        LDX #8
WK_CRC_BIT:
        ASL WK_CRC
        ROL WK_CRC+1
                        BCC WK_CRC_NEXT
        LDA WK_CRC
        EOR #$21
        STA WK_CRC
        LDA WK_CRC+1
        EOR #$10
        STA WK_CRC+1
WK_CRC_NEXT:
        DEX
                        BNE WK_CRC_BIT
        RTS
WK_HEADER_CRC:
        LDA WK_N
        SEC
        SBC #2
                        BRA WK_CRC_BUFFER
WK_SEAL:   LDA WK_N
        SEC
        SBC #4
        JSR WK_CRC_BUFFER
        LDA WK_CRC+1
        STA WK_BUF,Y
        INY
        LDA WK_CRC
        STA WK_BUF,Y
        RTS
WK_CRC_BUFFER:
        STA WK_CRC_N
        JSR WK_CRC_INIT
        LDY #0
WK_CRC_LOOP:
        LDA WK_BUF,Y
        JSR WK_CRC_BYTE
        INY
        CPY WK_CRC_N
                        BNE WK_CRC_LOOP
        LDA WK_CRC
        ORA WK_CRC+1
        RTS
WK_ZERO_BUF:
        LDX #63
WK_ZERO_LOOP:
        STZ WK_BUF,X
        DEX
                        BPL WK_ZERO_LOOP
        RTS
WK_ZERO_ADDR:
        STZ WK_ADDR
        STZ WK_ADDR+1
        STZ WK_ADDR+2
        RTS
WK_LOAD_LAYOUT:
        STZ WK_FALLBACK
        JSR WK_ZERO_ADDR
        JSR WK_READ64
                        BEQ WK_BM_LONG_361
                        JMP WK_LAYOUT_RETURN
WK_BM_LONG_361:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_PRIMARY_FOUND
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        JSR WK_READ64
                        BEQ WK_BM_LONG_370
                        JMP WK_LAYOUT_RETURN
WK_BM_LONG_370:
        INC WK_FALLBACK
WK_PRIMARY_FOUND:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_BM_LONG_375
                        JMP WK_UNFORMATTED
WK_BM_LONG_375:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_377
                        JMP WK_BAD_META
WK_BM_LONG_377:
        LDA WK_BUF+7
        ORA WK_BUF+62
                        BEQ WK_BM_LONG_380
                        JMP WK_BAD_META
WK_BM_LONG_380:
        LDX #59
WK_LAYOUT_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_384
                        JMP WK_BAD_META
WK_BM_LONG_384:
        DEX
        CPX #11
                        BNE WK_LAYOUT_RESERVED
        LDA WK_BUF
        CMP #'S'
                        BEQ WK_BM_LONG_390
                        JMP WK_BAD_META
WK_BM_LONG_390:
        LDA WK_BUF+1
        CMP #'S'
                        BEQ WK_BM_LONG_393
                        JMP WK_BAD_META
WK_BM_LONG_393:
        LDA WK_BUF+3
        CMP #8
                        BEQ WK_BM_LONG_396
                        JMP WK_BAD_META
WK_BM_LONG_396:
        LDA WK_BUF+4
        CMP #8
                        BEQ WK_BM_LONG_399
                        JMP WK_BAD_META
WK_BM_LONG_399:
        LDA WK_BUF+2
        CMP #1
                        BEQ WK_LEGACY_LAYOUT
        CMP #2
                        BEQ WK_BM_LONG_404
                        JMP WK_BAD_META
WK_BM_LONG_404:
        STZ WK_LEGACY
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BNE WK_BM_LONG_410
                        JMP WK_BAD_META
WK_BM_LONG_410:
                        BRA WK_LAYOUT_LIMIT
WK_LEGACY_LAYOUT:
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BEQ WK_BM_LONG_417
                        JMP WK_BAD_META
WK_BM_LONG_417:
        LDA WK_FALLBACK
                        BEQ WK_BM_LONG_419
                        JMP WK_BAD_META
WK_BM_LONG_419:
        LDA #1
        STA WK_LEGACY
        LDA WK_BUF+5
                        BEQ WK_BM_LONG_423
                        JMP WK_BAD_META
WK_BM_LONG_423:
        LDA WK_BUF+6
        CMP #1
                        BEQ WK_BM_LONG_426
                        JMP WK_BAD_META
WK_BM_LONG_426:
WK_LAYOUT_LIMIT:
        LDA WK_BUF+5
        AND #$3F
                        BEQ WK_BM_LONG_430
                        JMP WK_BAD_META
WK_BM_LONG_430:
        LDA WK_BUF+6
                        BEQ WK_LIMIT_SMALL
        CMP #1
                        BEQ WK_BM_LONG_434
                        JMP WK_BAD_META
WK_BM_LONG_434:
        LDA WK_BUF+5
                        BEQ WK_BM_LONG_436
                        JMP WK_BAD_META
WK_BM_LONG_436:
        LDA #4
                        BRA WK_LIMIT_SET
WK_LIMIT_SMALL:
        LDA WK_BUF+5
                        BNE WK_BM_LONG_441
                        JMP WK_BAD_META
WK_BM_LONG_441:
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
WK_LIMIT_SET:
        STA WK_UNITS
        LDX #63
WK_LAYOUT_COPY:
        LDA WK_BUF,X
        STA WK_LAYOUT,X
        DEX
                        BPL WK_LAYOUT_COPY
        LDA #0
WK_LAYOUT_RETURN:
        RTS
WK_UNFORMATTED:
        LDA #$40
        RTS
WK_QUERY:  STZ WK_REQ+12
        LDA WK_LAYOUT+5
        STA WK_REQ+13
        LDA WK_LAYOUT+6
        STA WK_REQ+14
        LDA #$E0
        STA WK_REQ+18
        SEC
        LDA #$FF
        SBC WK_LAYOUT+5
        STA WK_REQ+19
        LDA #1
        SBC WK_LAYOUT+6
        STA WK_REQ+20
        LDA WK_UNITS
        STA WK_REQ+21
        LDA WK_LEGACY
        STA WK_REQ+22
        LDA WK_FALLBACK
        STA WK_REQ+23
        LDA #0
        RTS
WK_SESSION_LOAD:
        STZ WK_SESSION_VALID
        LDA #$80
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        STZ WK_ADDR+2
WK_SESSION_SCAN:
        JSR WK_READ64
                        BEQ WK_BM_LONG_493
                        JMP WK_SESSION_RETURN
WK_BM_LONG_493:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_BM_LONG_496
                        JMP WK_SESSION_NEXT
WK_BM_LONG_496:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_498
                        JMP WK_BAD_META
WK_BM_LONG_498:
        LDX #2
WK_SESSION_MAGIC:
        LDA WK_BUF,X
        CMP WK_WS_MAGIC,X
                        BEQ WK_BM_LONG_503
                        JMP WK_BAD_META
WK_BM_LONG_503:
        DEX
                        BPL WK_SESSION_MAGIC
        LDA WK_BUF+3
        ORA WK_BUF+62
                        BEQ WK_BM_LONG_508
                        JMP WK_BAD_META
WK_BM_LONG_508:
        LDX #59
WK_SESSION_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_512
                        JMP WK_BAD_META
WK_BM_LONG_512:
        DEX
        CPX #13
                        BNE WK_SESSION_RESERVED
        LDA WK_BUF+4
        ORA WK_BUF+5
        ORA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_520
                        JMP WK_BAD_META
WK_BM_LONG_520:
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BNE WK_BM_LONG_525
                        JMP WK_BAD_META
WK_BM_LONG_525:
        LDA WK_SESSION_VALID
                        BEQ WK_SESSION_SELECT
        LDX #3
WK_SESSION_COMPARE:
        LDA WK_BUF+4,X
        CMP WK_SESSION+4,X
                        BCC WK_SESSION_NEXT
                        BNE WK_SESSION_SELECT
        DEX
                        BPL WK_SESSION_COMPARE
        JMP WK_BAD_META
WK_SESSION_SELECT:
        INC WK_SESSION_VALID
        LDA WK_ADDR
        STA WK_SESSION_ADDR
        LDX #63
WK_SESSION_COPY:
        LDA WK_BUF,X
        STA WK_SESSION,X
        DEX
                        BPL WK_SESSION_COPY
WK_SESSION_NEXT:
        LDA WK_ADDR
        CMP #$C0
                        BEQ WK_SESSION_END
        LDA #$C0
        STA WK_ADDR
                        JMP WK_SESSION_SCAN
WK_SESSION_END:
        LDA WK_SESSION_VALID
                        BNE WK_BM_LONG_556
                        JMP WK_BAD_META
WK_BM_LONG_556:
        LDA #0
WK_SESSION_RETURN:
        RTS
WK_INC_REVISION:
        LDX #0
WK_REV_INCREMENT:
        INC WK_SESSION+4,X
                        BNE WK_REV_OK
        INX
        CPX #4
                        BNE WK_REV_INCREMENT
        JMP WK_EXHAUSTED
WK_REV_OK: LDA #0
        RTS
WK_NEW_EPOCH:
        LDX #0
WK_EPOCH_INCREMENT:
        INC WK_SESSION+8,X
                        BNE WK_EPOCH_OK
        INX
        CPX #4
                        BNE WK_EPOCH_INCREMENT
        JMP WK_EXHAUSTED
WK_EPOCH_OK:
        STZ WK_SESSION+12
        STZ WK_SESSION+13
        JSR WK_SESSION_COMMIT
                        BNE WK_EPOCH_RETURN
        LDA #1
        STA WK_RESET_LATCH
        LDA #0
WK_EPOCH_RETURN:
        RTS
WK_SESSION_COMMIT:
        JSR WK_INC_REVISION
                        BNE WK_EPOCH_RETURN
        LDX #63
WK_SESSION_PREP:
        LDA WK_SESSION,X
        STA WK_BUF,X
        DEX
                        BPL WK_SESSION_PREP
        STZ WK_BUF+63
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        LDA WK_SESSION_ADDR
        EOR #$40
        STA WK_ADDR
        STA WK_SESSION_ADDR
        LDA #2
        STA WK_ADDR+1
        STZ WK_ADDR+2
        JMP WK_PUBLISH
WK_LOAD_CLAIMS:
        LDA #4
        STA WK_FREE_SLOT
        STZ WK_SLOT
WK_CLAIMS_SCAN:
        JSR WK_CLAIM_ADDRESS
        JSR WK_READ32
                        BEQ WK_BM_LONG_619
                        JMP WK_CLAIMS_RETURN
WK_BM_LONG_619:
        LDA WK_BUF+31
        CMP #$A5
                        BEQ WK_BM_LONG_622
                        JMP WK_CLAIMS_FREE
WK_BM_LONG_622:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_624
                        JMP WK_BAD_META
WK_BM_LONG_624:
        LDX #2
WK_CLAIM_MAGIC:
        LDA WK_BUF,X
        CMP WK_WC_MAGIC,X
                        BEQ WK_BM_LONG_629
                        JMP WK_BAD_META
WK_BM_LONG_629:
        DEX
                        BPL WK_CLAIM_MAGIC
        LDA WK_BUF+3
        ORA WK_BUF+15
        ORA WK_BUF+19
        ORA WK_BUF+30
                        BEQ WK_BM_LONG_636
                        JMP WK_BAD_META
WK_BM_LONG_636:
        LDX #27
WK_CLAIM_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_640
                        JMP WK_BAD_META
WK_BM_LONG_640:
        DEX
        CPX #19
                        BNE WK_CLAIM_RESERVED
        LDX #3
WK_CLAIM_EPOCH:
        LDA WK_BUF+8,X
        CMP WK_SESSION+8,X
                        BNE WK_CLAIMS_FREE
        DEX
                        BPL WK_CLAIM_EPOCH
        LDA WK_BUF+4
        ORA WK_BUF+5
                        BNE WK_BM_LONG_653
                        JMP WK_BAD_META
WK_BM_LONG_653:
        LDA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_656
                        JMP WK_BAD_META
WK_BM_LONG_656:
        LDA WK_BUF+12
                        BEQ WK_BM_LONG_658
                        JMP WK_BAD_META
WK_BM_LONG_658:
        LDA WK_BUF+16
        ORA WK_BUF+17
        ORA WK_BUF+18
                        BNE WK_BM_LONG_662
                        JMP WK_BAD_META
WK_BM_LONG_662:
        LDX #2
WK_CLAIM_SPAN:
        LDA WK_BUF+12,X
        STA WK_POS,X
        LDA WK_BUF+16,X
        STA WK_SIZE,X
        DEX
                        BPL WK_CLAIM_SPAN
        JSR WK_SPAN_END
                        BEQ WK_BM_LONG_672
                        JMP WK_BAD_META
WK_BM_LONG_672:
        LDA WK_POS+2
        CMP WK_LAYOUT+6
                        BCS WK_BM_LONG_675
                        JMP WK_BAD_META
WK_BM_LONG_675:
                        BNE WK_CLAIMS_CACHE
        LDA WK_POS+1
        CMP WK_LAYOUT+5
                        BCS WK_BM_LONG_679
                        JMP WK_BAD_META
WK_BM_LONG_679:
                        BRA WK_CLAIMS_CACHE
WK_CLAIMS_FREE:
        STZ WK_BUF+31
        LDA WK_SLOT
        STA WK_FREE_SLOT
WK_CLAIMS_CACHE:
        JSR WK_SLOT_POINTER
        LDY #31
WK_CLAIM_CACHE_COPY:
        LDA WK_BUF,Y
        STA (WK_P),Y
        DEY
                        BPL WK_CLAIM_CACHE_COPY
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BEQ WK_BM_LONG_696
                        JMP WK_CLAIMS_SCAN
WK_BM_LONG_696:
        JSR WK_CHECK_OVERLAPS
WK_CLAIMS_RETURN:
        RTS
WK_CHECK_OVERLAPS:
        LDA #1
        STA WK_CHECKING
        STZ WK_CHECK_SLOT
WK_CHECK_OUTER:
        LDA WK_CHECK_SLOT
        STA WK_SLOT
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_CHECK_NEXT
        LDY #12
        LDX #0
WK_CHECK_START_COPY:
        LDA (WK_P),Y
        STA WK_POS,X
        INY
        INX
        CPX #3
                        BNE WK_CHECK_START_COPY
        LDY #16
        LDX #0
WK_CHECK_SIZE_COPY:
        LDA (WK_P),Y
        STA WK_SIZE,X
        INY
        INX
        CPX #3
                        BNE WK_CHECK_SIZE_COPY
        JSR WK_ALLOC_RESTART
                        BNE WK_CLAIMS_RETURN
WK_CHECK_NEXT:
        INC WK_CHECK_SLOT
        LDA WK_CHECK_SLOT
        CMP #4
                        BNE WK_CHECK_OUTER
        STZ WK_CHECKING
        LDA #0
        RTS
WK_CLAIM_ADDRESS:
        LDA WK_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        LDA #3
        STA WK_ADDR+1
        STZ WK_ADDR+2
        RTS
WK_SLOT_POINTER:
        LDA WK_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #<WK_CLAIMS
        STA WK_P
        LDA #>WK_CLAIMS
        ADC #0
        STA WK_P+1
        RTS
WK_SPAN_END:
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_SPAN_ADD:
        LDA WK_POS,X
        ADC WK_SIZE,X
        STA WK_END_POS,X
        INX
        DEC WK_ARITH_N
                        BNE WK_SPAN_ADD
                        BCC WK_BM_LONG_778
                        JMP WK_BAD_ARG
WK_BM_LONG_778:
        LDX #2
WK_SPAN_BOUND:
        LDA WK_END_POS,X
        CMP WK_MAX_END,X
                        BCC WK_SPAN_OK
                        BEQ WK_BM_LONG_784
                        JMP WK_BAD_ARG
WK_BM_LONG_784:
        DEX
                        BPL WK_SPAN_BOUND
WK_SPAN_OK:LDA #0
        RTS
WK_CLAIM:  LDA WK_FREE_SLOT
        CMP #4
                        BCC WK_BM_LONG_791
                        JMP WK_FULL
WK_BM_LONG_791:
        LDX #2
WK_CLAIM_SIZE:
        LDA WK_REQ+18,X
        STA WK_SIZE,X
        DEX
                        BPL WK_CLAIM_SIZE
        LDA WK_SIZE
        ORA WK_SIZE+1
        ORA WK_SIZE+2
                        BNE WK_BM_LONG_801
                        JMP WK_BAD_ARG
WK_BM_LONG_801:
        STZ WK_POS
        LDA WK_LAYOUT+5
        STA WK_POS+1
        LDA WK_LAYOUT+6
        STA WK_POS+2
WK_ALLOC_RESTART:
        JSR WK_SPAN_END
                        BEQ WK_BM_LONG_809
                        JMP WK_FULL
WK_BM_LONG_809:
        STZ WK_SLOT
WK_ALLOC_SCAN:
        LDA WK_CHECKING
                        BEQ WK_ALLOC_CHECK
        LDA WK_SLOT
        CMP WK_CHECK_SLOT
                        BNE WK_BM_LONG_816
                        JMP WK_ALLOC_NEXT
WK_BM_LONG_816:
WK_ALLOC_CHECK:
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_ALLOC_NEXT
        ; candidate end <= claim start: no overlap.
        LDY #14
        LDX #2
WK_ALLOC_BEFORE:
        LDA WK_END_POS,X
        CMP (WK_P),Y
                        BCC WK_ALLOC_NEXT
                        BNE WK_ALLOC_AFTER_START
        DEY
        DEX
                        BPL WK_ALLOC_BEFORE
                        JMP WK_ALLOC_NEXT
WK_ALLOC_AFTER_START:
        ; candidate start >= claim end: no overlap.
        LDY #12
        CLC
        LDX #0
WK_ALLOC_OLD_END:
        LDA (WK_P),Y
        STA WK_OLD_END,X
        INY
        INX
        CPX #3
                        BNE WK_ALLOC_OLD_END
        LDY #16
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_ALLOC_OLD_ADD:
        LDA (WK_P),Y
        ADC WK_OLD_END,X
        STA WK_OLD_END,X
        INY
        INX
        DEC WK_ARITH_N
                        BNE WK_ALLOC_OLD_ADD
        LDX #2
WK_ALLOC_AFTER:
        LDA WK_POS,X
        CMP WK_OLD_END,X
                        BCC WK_ALLOC_COLLISION
                        BNE WK_ALLOC_NEXT
        DEX
                        BPL WK_ALLOC_AFTER
                        JMP WK_ALLOC_NEXT
WK_ALLOC_COLLISION:
        LDA WK_CHECKING
                        BEQ WK_BM_LONG_871
                        JMP WK_BAD_META
WK_BM_LONG_871:
        STZ WK_POS
        LDA WK_OLD_END
        CMP #1
        LDA WK_OLD_END+1
        ADC #0
        STA WK_POS+1
        LDA WK_OLD_END+2
        ADC #0
        STA WK_POS+2
                        JMP WK_ALLOC_RESTART
WK_ALLOC_NEXT:
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BEQ WK_BM_LONG_886
                        JMP WK_ALLOC_SCAN
WK_BM_LONG_886:
        LDA WK_CHECKING
                        BEQ WK_ALLOC_PUBLISH
        LDA #0
        RTS
WK_ALLOC_PUBLISH:
        LDA WK_SESSION+12
        AND WK_SESSION+13
        CMP #$FF
                        BNE WK_BM_LONG_895
                        JMP WK_EXHAUSTED
WK_BM_LONG_895:
        INC WK_SESSION+12
                        BNE WK_CLAIM_TICKET
        INC WK_SESSION+13
WK_CLAIM_TICKET:
        JSR WK_SESSION_COMMIT
                        BEQ WK_BM_LONG_901
                        JMP WK_CLAIMS_RETURN
WK_BM_LONG_901:
        JSR WK_ZERO_BUF
        LDX #2
WK_CLAIM_NEW_MAGIC:
        LDA WK_WC_MAGIC,X
        STA WK_BUF,X
        DEX
                        BPL WK_CLAIM_NEW_MAGIC
        LDX #1
WK_CLAIM_OWNER:
        LDA WK_REQ+2,X
        STA WK_BUF+4,X
        LDA WK_SESSION+12,X
        STA WK_BUF+6,X
        DEX
                        BPL WK_CLAIM_OWNER
        LDX #3
WK_CLAIM_NEW_EPOCH:
        LDA WK_SESSION+8,X
        STA WK_BUF+8,X
        STA WK_REQ+6,X
        DEX
                        BPL WK_CLAIM_NEW_EPOCH
        LDX #2
WK_CLAIM_NEW_SPAN:
        LDA WK_POS,X
        STA WK_BUF+12,X
        LDA WK_SIZE,X
        STA WK_BUF+16,X
        STZ WK_REQ+12,X
        DEX
                        BPL WK_CLAIM_NEW_SPAN
        LDA WK_FREE_SLOT
        STA WK_SLOT
        STA WK_REQ+4
        STZ WK_REQ+5
        LDA WK_SESSION+12
        STA WK_REQ+10
        LDA WK_SESSION+13
        STA WK_REQ+11
        LDA #32
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        JSR WK_CLAIM_ADDRESS
        JMP WK_PUBLISH
WK_HANDLE:
        LDA WK_REQ+5
                        BEQ WK_BM_LONG_949
                        JMP WK_STALE
WK_BM_LONG_949:
        LDA WK_REQ+4
        CMP #4
                        BCC WK_BM_LONG_952
                        JMP WK_STALE
WK_BM_LONG_952:
        STA WK_SLOT
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BEQ WK_BM_LONG_958
                        JMP WK_STALE
WK_BM_LONG_958:
        LDY #4
        LDX #2
WK_HANDLE_OWNER:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_964
                        JMP WK_STALE
WK_BM_LONG_964:
        INY
        INX
        CPX #4
                        BNE WK_HANDLE_OWNER
        LDY #6
        LDX #10
WK_HANDLE_TICKET:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_974
                        JMP WK_STALE
WK_BM_LONG_974:
        INY
        INX
        CPX #12
                        BNE WK_HANDLE_TICKET
        LDY #8
        LDX #6
WK_HANDLE_EPOCH:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_984
                        JMP WK_STALE
WK_BM_LONG_984:
        INY
        INX
        CPX #10
                        BNE WK_HANDLE_EPOCH
        LDA #0
        RTS
WK_RELEASE:
        JSR WK_CLAIM_ADDRESS
        LDA #32
        STA WK_PACKET_N
        LDA #0
        JMP WK_MARKER
WK_IO:     LDA WK_REQ+15
                        BNE WK_BM_LONG_998
                        JMP WK_BAD_ARG
WK_BM_LONG_998:
        CMP #65
                        BCC WK_BM_LONG_1000
                        JMP WK_BAD_ARG
WK_BM_LONG_1000:
        STA WK_N
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_IO_OFFSET_END:
        LDA WK_REQ+12,X
        ADC WK_N
        STA WK_END_POS,X
        INX
        LDA #0
        STA WK_N
        DEC WK_ARITH_N
                        BNE WK_IO_OFFSET_END
                        BCC WK_BM_LONG_1015
                        JMP WK_BAD_ARG
WK_BM_LONG_1015:
        LDY #18
        LDX #2
WK_IO_BOUND:
        LDA WK_END_POS,X
        CMP (WK_P),Y
                        BCC WK_IO_ADDRESS
                        BEQ WK_BM_LONG_1022
                        JMP WK_BAD_ARG
WK_BM_LONG_1022:
        DEY
        DEX
                        BPL WK_IO_BOUND
WK_IO_ADDRESS:
        LDY #12
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_IO_ADDRESS_ADD:
        LDA (WK_P),Y
        ADC WK_REQ+12,X
        STA WK_ADDR,X
        INY
        INX
        DEC WK_ARITH_N
                        BNE WK_IO_ADDRESS_ADD
        LDA WK_REQ+15
        STA WK_N
        LDA WK_REQ+16
        STA WK_BP
        LDA WK_REQ+17
        STA WK_BP+1
        LDA WK_BP
        PHA
        LDA WK_BP+1
        PHA
        LDA WK_C
        STA WK_SAVE_C
        LDA WK_C+1
        STA WK_SAVE_C+1
        LDA WK_BP
        STA WK_C
        LDA WK_BP+1
        STA WK_C+1
        JSR WK_CPU_RANGE
        STA WK_ERROR
        PLA
        STA WK_BP+1
        PLA
        STA WK_BP
        LDA WK_SAVE_C
        STA WK_C
        LDA WK_SAVE_C+1
        STA WK_C+1
        LDA WK_ERROR
                        BEQ WK_BM_LONG_1069
                        JMP WK_OP_RETURN
WK_BM_LONG_1069:
        ; READ cannot overwrite the caller's request/result block.
        LDA WK_REQ
        CMP #3
                        BNE WK_IO_TRANSFER
        LDA WK_BP
        CLC
        ADC WK_N
        STA WK_TEMP
        LDA WK_BP+1
        ADC #0
        CMP WK_C+1
                        BCC WK_IO_TRANSFER
                        BNE WK_IO_READ_AFTER
        LDA WK_TEMP
        CMP WK_C
                        BCC WK_IO_TRANSFER
                        BEQ WK_IO_TRANSFER
WK_IO_READ_AFTER:
        LDA WK_C
        CLC
        ADC #32
        STA WK_TEMP
        LDA WK_C+1
        ADC #0
        CMP WK_BP+1
                        BCC WK_IO_TRANSFER
                        BEQ WK_BM_LONG_1096
                        JMP WK_BAD_ARG
WK_BM_LONG_1096:
        LDA WK_TEMP
        CMP WK_BP
                        BCC WK_IO_TRANSFER
                        BEQ WK_BM_LONG_1100
                        JMP WK_BAD_ARG
WK_BM_LONG_1100:
WK_IO_TRANSFER:
        LDA WK_REQ
        CMP #4
                        BNE WK_IO_READ
        LDA WK_BP
        STA WK_Q
        LDA WK_BP+1
        STA WK_Q+1
        LDY #0
WK_IO_STAGE:
        LDA (WK_Q),Y
        STA WK_BUF,Y
        INY
        CPY WK_N
                        BNE WK_IO_STAGE
        JSR WK_WRITE_VERIFY
                        BRA WK_IO_RESULT
WK_IO_READ:
        LDA #1
        JSR WK_TRANSFER
WK_IO_RESULT:
        PHA
        LDA WK_R+9
        STA WK_REQ+22
        LDA WK_R+10
        STA WK_REQ+23
        PLA
        CMP #0
        RTS
WK_CPU_RANGE:
        LDA WK_C+1
        CMP #2
                        BCS WK_BM_LONG_1133
                        JMP WK_BAD_ARG
WK_BM_LONG_1133:
        CLC
        LDA WK_C
        ADC WK_N
        STA WK_TEMP
        LDA WK_C+1
        ADC #0
        STA WK_TEMP+1
                        BCC WK_BM_LONG_1141
                        JMP WK_BAD_ARG
WK_BM_LONG_1141:
        CMP #$65
                        BCC WK_CPU_LIBRARY
                        BEQ WK_BM_LONG_1144
                        JMP WK_BAD_ARG
WK_BM_LONG_1144:
        LDA WK_TEMP
                        BEQ WK_BM_LONG_1146
                        JMP WK_BAD_ARG
WK_BM_LONG_1146:
WK_CPU_LIBRARY:
        LDA WK_TEMP+1
        CMP #>$5000
                        BCC WK_CPU_OK
                        BNE WK_CPU_AFTER
        LDA WK_TEMP
                        BEQ WK_CPU_OK
WK_CPU_AFTER:
        LDA WK_C+1
        CMP #>$5040
                        BCS WK_BM_LONG_1157
                        JMP WK_BAD_ARG
WK_BM_LONG_1157:
                        BNE WK_CPU_OK
        LDA WK_C
        CMP #<$5040
                        BCS WK_BM_LONG_1161
                        JMP WK_BAD_ARG
WK_BM_LONG_1161:
WK_CPU_OK:
        LDA WK_TEMP+1
        CMP #$64
        BCC WK_WINDOW_OK
        BNE WK_WINDOW_START
        LDA WK_TEMP
        BEQ WK_WINDOW_OK
WK_WINDOW_START:
        LDA WK_C+1
        CMP #$64
        BCC WK_WINDOW_BAD
        BNE WK_WINDOW_OK
        LDA WK_C
        CMP #$40
        BCS WK_WINDOW_OK
WK_WINDOW_BAD:
        JMP WK_BAD_ARG
WK_WINDOW_OK: LDA #0
        RTS
WK_PROGRAM_CHECK:
        STZ WK_PROG_SLOT
WK_PROG_SCAN:
        LDA WK_PROG_SLOT
        INC A
        LSR A
        LSR A
        STA WK_ADDR+1
        LDA WK_PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        STZ WK_ADDR+2
        JSR WK_READ64
                        BEQ WK_BM_LONG_1184
                        JMP WK_PROG_RETURN
WK_BM_LONG_1184:
        LDA WK_BUF+63
        CMP #$A5
                        BNE WK_PROG_NEXT
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_1189
                        JMP WK_BAD_META
WK_BM_LONG_1189:
        LDX #2
WK_PROG_MAGIC:
        LDA WK_BUF,X
        CMP WK_SP_MAGIC,X
                        BEQ WK_BM_LONG_1194
                        JMP WK_BAD_META
WK_BM_LONG_1194:
        DEX
                        BPL WK_PROG_MAGIC
        LDA WK_BUF+15
        CMP #2
                        BEQ WK_PROG_TOMBSTONE
        CMP #1
                        BEQ WK_BM_LONG_1201
                        JMP WK_BAD_META
WK_BM_LONG_1201:
        LDA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_1204
                        JMP WK_BAD_META
WK_BM_LONG_1204:
        LDA WK_BUF+14
        CMP #8
                        BCS WK_BM_LONG_1207
                        JMP WK_BAD_META
WK_BM_LONG_1207:
        LDA WK_BUF+6
        CMP #1
        LDA WK_BUF+7
        ADC WK_BUF+14
        STA WK_PAGE_END
        LDA #0
        ADC #0
        STA WK_PAGE_END+1
        CMP WK_LAYOUT+6
                        BCC WK_PROG_NEXT
                        BEQ WK_BM_LONG_1218
                        JMP WK_BAD_META
WK_BM_LONG_1218:
        LDA WK_PAGE_END
        CMP WK_LAYOUT+5
                        BCC WK_PROG_NEXT
                        BEQ WK_PROG_NEXT
        JMP WK_BAD_META
WK_PROG_TOMBSTONE:
        LDA WK_BUF+6
        ORA WK_BUF+7
        ORA WK_BUF+14
                        BEQ WK_BM_LONG_1228
                        JMP WK_BAD_META
WK_BM_LONG_1228:
WK_PROG_NEXT:
        INC WK_PROG_SLOT
        LDA WK_PROG_SLOT
        CMP #8
                        BEQ WK_BM_LONG_1233
                        JMP WK_PROG_SCAN
WK_BM_LONG_1233:
        LDA #0
WK_PROG_RETURN:
        RTS
WK_RESIZE: LDX #7
WK_RESIZE_KEY:
        LDA WK_REQ+24,X
        CMP WK_RESIZE_MAGIC,X
                        BEQ WK_BM_LONG_1241
                        JMP WK_BAD_ARG
WK_BM_LONG_1241:
        DEX
                        BPL WK_RESIZE_KEY
        LDA WK_REQ+21
                        BNE WK_BM_LONG_1245
                        JMP WK_BAD_ARG
WK_BM_LONG_1245:
        CMP #5
                        BCC WK_BM_LONG_1247
                        JMP WK_BAD_ARG
WK_BM_LONG_1247:
        CMP WK_UNITS
                        BNE WK_BM_LONG_1249
                        JMP WK_QUERY
WK_BM_LONG_1249:
        STA WK_NEW_UNITS
        ; Check prospective boundary against all saved records and claims.
        LDA WK_LAYOUT+5
        PHA
        LDA WK_LAYOUT+6
        PHA
        JSR WK_NEW_BOUNDARY
        JSR WK_PROGRAM_CHECK
        STA WK_ERROR
        STZ WK_SLOT
WK_RESIZE_CLAIMS:
        LDA WK_ERROR
                        BNE WK_RESIZE_RESTORE
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_RESIZE_NEXT
        LDY #14
        LDA (WK_P),Y
        CMP WK_LAYOUT+6
                        BCC WK_RESIZE_CONFLICT
                        BNE WK_RESIZE_NEXT
        DEY
        LDA (WK_P),Y
        CMP WK_LAYOUT+5
                        BCC WK_RESIZE_CONFLICT
WK_RESIZE_NEXT:
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BNE WK_RESIZE_CLAIMS
                        BRA WK_RESIZE_RESTORE
WK_RESIZE_CONFLICT:
        LDA #$4A
        STA WK_ERROR
WK_RESIZE_RESTORE:
        PLA
        STA WK_LAYOUT+6
        PLA
        STA WK_LAYOUT+5
        LDA WK_ERROR
                        BEQ WK_BM_LONG_1292
                        JMP WK_OP_RETURN
WK_BM_LONG_1292:
        JSR WK_REPAIR_PRIMARY
                        BEQ WK_BM_LONG_1294
                        JMP WK_OP_RETURN
WK_BM_LONG_1294:
        JSR WK_NEW_BOUNDARY
        JSR WK_LAYOUT_INCREMENT
                        BEQ WK_BM_LONG_1297
                        JMP WK_OP_RETURN
WK_BM_LONG_1297:
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1299
                        JMP WK_OP_RETURN
WK_BM_LONG_1299:
        LDA WK_NEW_UNITS
        STA WK_UNITS
        JMP WK_QUERY
WK_NEW_BOUNDARY:
        LDA WK_NEW_UNITS
        LSR A
        LSR A
        STA WK_LAYOUT+6
        LDA WK_NEW_UNITS
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_LAYOUT+5
        RTS
WK_LAYOUT_INCREMENT:
        LDX #0
WK_LAYOUT_INC:
        INC WK_LAYOUT+8,X
                        BNE WK_LAYOUT_INC_OK
        INX
        CPX #4
                        BNE WK_LAYOUT_INC
        JMP WK_EXHAUSTED
WK_LAYOUT_INC_OK:
        LDA #0
        RTS
WK_LAYOUT_PACKET:
        LDX #63
WK_LAYOUT_PACKET_COPY:
        LDA WK_LAYOUT,X
        STA WK_BUF,X
        DEX
                        BPL WK_LAYOUT_PACKET_COPY
        STZ WK_BUF+63
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JMP WK_SAVE_PACKET
WK_LAYOUT_UPDATE:
        JSR WK_LAYOUT_PACKET
        JSR WK_ZERO_ADDR
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        JSR WK_PUBLISH
                        BNE WK_LAYOUT_WRITE_RETURN
        ; A remains authoritative until verified invalidation. Then B is
        ; authoritative; STORE refuses until A is repaired/republished.
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_LAYOUT_WRITE_RETURN
        BRA WK_WRITE_PRIMARY
WK_REPAIR_PRIMARY:
        LDA WK_FALLBACK
                        BEQ WK_LAYOUT_WRITE_RETURN
WK_WRITE_PRIMARY:
        JSR WK_LAYOUT_PACKET
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_N
        JSR WK_PUBLISH
                        BNE WK_LAYOUT_WRITE_RETURN
        STZ WK_FALLBACK
        LDA #0
WK_LAYOUT_WRITE_RETURN:
        RTS
WK_REPAIR: LDX #7
WK_REPAIR_KEY:
        LDA WK_REQ+24,X
        CMP WK_REPAIR_MAGIC,X
                        BEQ WK_BM_LONG_1377
                        JMP WK_BAD_ARG
WK_BM_LONG_1377:
        DEX
                        BPL WK_REPAIR_KEY
        BRA WK_REPAIR_PRIMARY
WK_UPGRADE:
        LDX #7
WK_UPGRADE_KEY:
        LDA WK_REQ+24,X
        CMP WK_UPGRADE_MAGIC,X
                        BEQ WK_BM_LONG_1386
                        JMP WK_BAD_ARG
WK_BM_LONG_1386:
        DEX
                        BPL WK_UPGRADE_KEY
        JSR WK_LOAD_LAYOUT
                        BEQ WK_BM_LONG_1390
                        JMP WK_OP_RETURN
WK_BM_LONG_1390:
        LDA WK_LEGACY
                        BEQ WK_UPGRADE_ALREADY
        JSR WK_PROGRAM_CHECK
                        BEQ WK_BM_LONG_1394
                        JMP WK_OP_RETURN
WK_BM_LONG_1394:
        JSR WK_INITIAL_SESSION
                        BEQ WK_BM_LONG_1396
                        JMP WK_OP_RETURN
WK_BM_LONG_1396:
        LDA #2
        STA WK_LAYOUT+2
        LDA #1
        STA WK_LAYOUT+8
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1402
                        JMP WK_OP_RETURN
WK_BM_LONG_1402:
        STZ WK_LEGACY
WK_UPGRADE_ALREADY:
        LDA #0
        RTS
WK_FORMAT: LDX #7
WK_FORMAT_KEY:
        LDA WK_REQ+24,X
        CMP WK_FORMAT_MAGIC,X
                        BEQ WK_BM_LONG_1411
                        JMP WK_BAD_ARG
WK_BM_LONG_1411:
        DEX
                        BPL WK_FORMAT_KEY
        ; Both layout markers invalidated before changing any record.
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1420
                        JMP WK_OP_RETURN
WK_BM_LONG_1420:
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1427
                        JMP WK_OP_RETURN
WK_BM_LONG_1427:
        STZ WK_PROG_SLOT
WK_FORMAT_DIRECTORY:
        LDA WK_PROG_SLOT
        INC A
        LSR A
        LSR A
        STA WK_ADDR+1
        LDA WK_PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1447
                        JMP WK_OP_RETURN
WK_BM_LONG_1447:
        INC WK_PROG_SLOT
        LDA WK_PROG_SLOT
        CMP #8
                        BNE WK_FORMAT_DIRECTORY
        ; Clear every claim marker, including corrupt old-epoch packets.
        ; LOAD_CLAIMS validates committed headers before checking epochs.
        JSR WK_CLEAR_CLAIMS
                        BEQ WK_BM_LONG_1455
                        JMP WK_OP_RETURN
WK_BM_LONG_1455:
        ; Retain a valid epoch counter when formatting an existing store.
        JSR WK_SESSION_LOAD
                        BNE WK_FORMAT_FRESH_SESSION
        JSR WK_NEW_EPOCH
                        BEQ WK_BM_LONG_1460
                        JMP WK_OP_RETURN
WK_BM_LONG_1460:
                        BRA WK_FORMAT_LAYOUT
WK_FORMAT_FRESH_SESSION:
        JSR WK_INITIAL_SESSION_RECORD
                        BEQ WK_BM_LONG_1464
                        JMP WK_OP_RETURN
WK_BM_LONG_1464:
WK_FORMAT_LAYOUT:
        JSR WK_ZERO_BUF
        LDX #7
WK_FORMAT_LAYOUT_COPY:
        LDA WK_INITIAL_LAYOUT,X
        STA WK_LAYOUT,X
        DEX
                        BPL WK_FORMAT_LAYOUT_COPY
        LDX #63
WK_FORMAT_LAYOUT_ZERO:
        STZ WK_LAYOUT,X
        DEX
        CPX #7
                        BNE WK_FORMAT_LAYOUT_ZERO
        LDA #1
        STA WK_LAYOUT+8
        STZ WK_FALLBACK
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1483
                        JMP WK_OP_RETURN
WK_BM_LONG_1483:
        LDA #0
        RTS
WK_CLEAR_CLAIMS:
        STZ WK_SLOT
WK_INIT_CLEAR_CLAIMS:
        JSR WK_CLAIM_ADDRESS
        LDA #32
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BNE WK_INIT_CLEAR_CLAIMS
        LDA #0
        RTS
WK_INITIAL_SESSION:
        ; Explicit FORMAT/UPGRADE initializes only management cells.
        JSR WK_CLEAR_CLAIMS
                        BNE WK_INIT_RETURN
WK_INITIAL_SESSION_RECORD:
        LDA #$80
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        LDA #$C0
        STA WK_ADDR
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        JSR WK_ZERO_BUF
        LDX #2
WK_INIT_WS_MAGIC:
        LDA WK_WS_MAGIC,X
        STA WK_BUF,X
        DEX
                        BPL WK_INIT_WS_MAGIC
        LDA #1
        STA WK_BUF+4
        STA WK_BUF+8
        LDX #63
WK_INIT_SESSION_COPY:
        LDA WK_BUF,X
        STA WK_SESSION,X
        DEX
                        BPL WK_INIT_SESSION_COPY
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        LDA #$80
        STA WK_ADDR
        STA WK_SESSION_ADDR
        JSR WK_PUBLISH
                        BNE WK_INIT_RETURN
        LDA #1
        STA WK_RESET_LATCH
        LDA #0
WK_INIT_RETURN:
        RTS
WK_CONSOLE:
        SEI
        CLD
        LDX #<WK_TITLE
        LDY #>WK_TITLE
        JSR WK_PRINT
WK_CON_HELP_TEXT:
        LDX #<WK_HELP_TEXT
        LDY #>WK_HELP_TEXT
        JSR WK_PRINT
WK_PROMPT: LDX #<WK_PROMPT_TEXT
        LDY #>WK_PROMPT_TEXT
        JSR WK_PRINT
        JSR B29_LINE_3
                        BCC WK_PROMPT
        LDX #31
WK_CON_CLEAR:
        STZ WK_REQ,X
        DEX
                        BPL WK_CON_CLEAR
        LDA WK_LINE
                        BEQ WK_PROMPT
        CMP #'WK_P'
                        BEQ WK_CON_RESIZE
        CMP #'H'
                        BEQ WK_CON_HELP
        LDX WK_LINE+1
                        BEQ WK_BM_LONG_1577
                        JMP WK_CON_BAD
WK_BM_LONG_1577:
        CMP #'WK_Q'
                        BNE WK_BM_LONG_1579
                        JMP WK_QUIT
WK_BM_LONG_1579:
        CMP #'?'
                        BEQ WK_CON_QUERY
        CMP #'F'
                        BNE WK_BM_LONG_1583
                        JMP WK_CON_FORMAT
WK_BM_LONG_1583:
        CMP #'U'
                        BNE WK_BM_LONG_1585
                        JMP WK_CON_UPGRADE
WK_BM_LONG_1585:
        CMP #'V'
                        BNE WK_BM_LONG_1587
                        JMP WK_CON_REPAIR
WK_BM_LONG_1587:
        LDA #$44
                        JMP WK_CON_RESULT
WK_CON_HELP:
        LDX #4
WK_CON_HELP_MATCH:
        LDA WK_LINE,X
        CMP WK_HELP_COMMAND,X
                        BEQ WK_BM_LONG_1595
                        JMP WK_CON_BAD
WK_BM_LONG_1595:
        DEX
                        BPL WK_CON_HELP_MATCH
                        BRA WK_CON_HELP_TEXT
WK_CON_QUERY:
        JSR WK_OPERATION
                        BEQ WK_BM_LONG_1601
                        JMP WK_CON_RESULT
WK_BM_LONG_1601:
        JSR WK_CAPACITY_TEXT
                        JMP WK_PROMPT
WK_CON_RESIZE:
        LDA WK_LINE+1
        CMP #' '
                        BEQ WK_BM_LONG_1607
                        JMP WK_CON_BAD
WK_BM_LONG_1607:
        LDA WK_LINE+4
                        BEQ WK_BM_LONG_1609
                        JMP WK_CON_BAD
WK_BM_LONG_1609:
        LDX #6
WK_CON_SIZE_MATCH:
        LDA WK_LINE+2
        CMP WK_UNIT_TEXT,X
                        BNE WK_CON_SIZE_NEXT
        LDA WK_LINE+3
        CMP WK_UNIT_TEXT+1,X
                        BEQ WK_CON_SIZE_FOUND
WK_CON_SIZE_NEXT:
        DEX
        DEX
                        BPL WK_CON_SIZE_MATCH
                        JMP WK_CON_BAD
WK_CON_SIZE_FOUND:
        TXA
        LSR A
        INC A
        STA WK_CON_UNITS
        JSR WK_OPERATION
                        BEQ WK_BM_LONG_1629
                        JMP WK_CON_RESULT
WK_BM_LONG_1629:
        LDA WK_CON_UNITS
        CMP WK_REQ+21
                        BNE WK_CON_SIZE_PREVIEW
        LDX #<WK_NO_CHANGE_TEXT
        LDY #>WK_NO_CHANGE_TEXT
                        JMP WK_CON_MESSAGE
WK_CON_SIZE_PREVIEW:
        STA WK_REQ+21
        JSR WK_CAPACITY_TEXT
        LDA #5
        LDX #<WK_RESIZE_MAGIC
        LDY #>WK_RESIZE_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_FORMAT:
        LDA #6
        LDX #<WK_FORMAT_MAGIC
        LDY #>WK_FORMAT_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_UPGRADE:
        LDA #7
        LDX #<WK_UPGRADE_MAGIC
        LDY #>WK_UPGRADE_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_REPAIR:
        LDA #8
        LDX #<WK_REPAIR_MAGIC
        LDY #>WK_REPAIR_MAGIC
WK_CON_CONFIRM:
        STA WK_REQ
        STX WK_Q
        STY WK_Q+1
        LDY #7
WK_CON_KEY_COPY:
        LDA (WK_Q),Y
        STA WK_REQ+24,Y
        DEY
                        BPL WK_CON_KEY_COPY
        LDX #<WK_CONFIRM_TEXT
        LDY #>WK_CONFIRM_TEXT
        LDA WK_REQ
        CMP #6
                        BEQ WK_CON_FORMAT_PROMPT
        CMP #5
                        BNE WK_CON_PROMPT_CONFIRM
        LDX #<WK_APPLY_TEXT
        LDY #>WK_APPLY_TEXT
                        BRA WK_CON_PROMPT_CONFIRM
WK_CON_FORMAT_PROMPT:
        LDX #<WK_FORMAT_TEXT
        LDY #>WK_FORMAT_TEXT
WK_CON_PROMPT_CONFIRM:
        JSR WK_PRINT
        JSR WK_LINE_READ
                        BCC WK_CON_CANCEL
        LDA WK_REQ
        CMP #5
                        BEQ WK_CON_CHECK_Y
        CMP #6
                        BNE WK_CON_CHECK_YES
        LDX #11
WK_CON_FORMAT_CONFIRM:
        LDA WK_LINE,X
        CMP WK_FORMAT_CONFIRM,X
                        BNE WK_CON_CANCEL
        DEX
                        BPL WK_CON_FORMAT_CONFIRM
                        BRA WK_CON_EXEC
WK_CON_CHECK_Y:
        LDA WK_LINE
        CMP #'Y'
                        BNE WK_CON_CANCEL
        LDA WK_LINE+1
                        BEQ WK_CON_EXEC
                        BRA WK_CON_CANCEL
WK_CON_CHECK_YES:
        LDX #3
WK_CON_YES:
        LDA WK_LINE,X
        CMP WK_YES_MAGIC,X
                        BNE WK_CON_CANCEL
        DEX
                        BPL WK_CON_YES
WK_CON_EXEC:
        JSR WK_OPERATION
WK_CON_RESULT:
        CMP #0
                        BNE WK_CON_ERROR
        LDA WK_REQ
        SEC
        SBC #5
        TAX
        LDA WK_SUCCESS_LO,X
        LDY WK_SUCCESS_HI,X
        TAX
                        JMP WK_CON_MESSAGE
WK_CON_ERROR: JSR B29_ERROR_HOOK

        LDX #WK_STATUS_COUNT-1
WK_CON_STATUS_MATCH:
        CMP WK_STATUS_CODES,X
                        BEQ WK_CON_STATUS_TEXT
        DEX
                        BPL WK_CON_STATUS_MATCH
        PHA
        LDX #<WK_RESULT_TEXT
        LDY #>WK_RESULT_TEXT
        JSR WK_PRINT
        PLA
        JSR WK_HEX
        JSR WK_NL
        JMP WK_PROMPT
WK_CON_STATUS_TEXT:
        LDY WK_STATUS_HI,X
        LDA WK_STATUS_LO,X
        TAX
WK_CON_MESSAGE:
        JSR WK_PRINT
        JMP WK_PROMPT
WK_CON_CANCEL: JSR B29_ERROR_HOOK

        LDX #<WK_CANCELED_TEXT
        LDY #>WK_CANCELED_TEXT
                        JMP WK_CON_MESSAGE
WK_CON_BAD:LDA #$44
                        JMP WK_CON_RESULT
WK_QUIT:   JSR WK_RESTORE_WINDOW
        JMP $7E67
; Four fixed layouts: small decimal tables avoid a general 24-bit formatter.
WK_CAPACITY_TEXT:
        LDX #<WK_PROGRAM_TEXT
        LDY #>WK_PROGRAM_TEXT
        JSR WK_PRINT
        LDA WK_REQ+21
        DEC A
        ASL A
        TAX
        LDA WK_UNIT_TEXT,X
        JSR WK_PUTC
        INX
        LDA WK_UNIT_TEXT,X
        JSR WK_PUTC
        LDX #<WK_WORKSPACE_TEXT
        LDY #>WK_WORKSPACE_TEXT
        JSR WK_PRINT
        LDA WK_REQ+21
        DEC A
        TAX
        LDY WK_CAPACITY_HI,X
        LDA WK_CAPACITY_LO,X
        TAX
        JSR WK_PRINT
        LDX #<WK_BYTES_TEXT
        LDY #>WK_BYTES_TEXT
        BRA WK_PRINT
WK_LINE_READ:
        STZ WK_LINE_N
        STZ WK_OVERFLOW
WK_LINE_WAIT:
        JSR WK_GETC
        CMP #3
                        BEQ WK_LINE_CANCEL
        CMP #$1B
                        BEQ WK_LINE_CANCEL
        CMP #10
                        BEQ WK_LINE_WAIT
        CMP #13
                        BEQ WK_LINE_END
        CMP #'a'
                        BCC WK_LINE_CHAR
        CMP #'z'+1
                        BCS WK_LINE_CHAR
        AND #$DF
WK_LINE_CHAR:
        LDX WK_LINE_N
        CPX #15
                        BCS WK_LINE_FULL
        STA WK_LINE,X
        INC WK_LINE_N
        JSR WK_PUTC
                        JMP WK_LINE_WAIT
WK_LINE_FULL:
        LDA #1
        STA WK_OVERFLOW
                        JMP WK_LINE_WAIT
WK_LINE_END:
        LDX WK_LINE_N
        STZ WK_LINE,X
        JSR WK_NL
        LDA WK_OVERFLOW
                        BNE WK_LINE_CANCEL
        SEC
        RTS
WK_LINE_CANCEL: JSR B29_CANCEL_HOOK

        JSR WK_NL
        CLC
        RTS
WK_PRINT:  STX WK_Q
        STY WK_Q+1
        LDY #0
WK_PRINT_LOOP:
        LDA (WK_Q),Y
                        BEQ WK_PRINT_END
        JSR WK_PUTC
        INY
                        BRA WK_PRINT_LOOP
WK_PRINT_END:
        RTS
WK_SV_MAGIC DB "SV",1
WK_SM_MAGIC DB "SM",1,1
WK_WS_MAGIC DB "WS",1
WK_WC_MAGIC DB "WC",1
WK_SP_MAGIC DB "SP",1
WK_INITIAL_LAYOUT DB "SS",2,8,8,0,1,0
WK_MAX_END DB $E0,$FF,1
WK_FORMAT_MAGIC DB "FORMAT!!"
WK_RESIZE_MAGIC DB "RESIZE!!"
WK_UPGRADE_MAGIC DB "UPGRADE!"
WK_REPAIR_MAGIC DB "REPAIR!!"
WK_YES_MAGIC DB "YES",0
WK_FORMAT_CONFIRM DB "FORMAT SRAM",0
WK_TITLE DB "WORK 1.4",13,10,0
WK_HELP_COMMAND DB "HELP",0
WK_HELP_TEXT DB "? capacity; P 16/32/48/64 (KiB); U upgrade; V repair; F format; HELP; Q",13,10,0
WK_PROMPT_TEXT DB "WORK> ",0
WK_UNIT_TEXT DB "16324864"
WK_PROGRAM_TEXT DB "Programs: ",0
WK_WORKSPACE_TEXT DB " KiB; workspace: ",0
WK_BYTES_TEXT DB " bytes",13,10,0
WK_CAP16 DB "114656",0
WK_CAP32 DB "98272",0
WK_CAP48 DB "81888",0
WK_CAP64 DB "65504",0
WK_CAPACITY_LO DB <WK_CAP16,<WK_CAP32,<WK_CAP48,<WK_CAP64
WK_CAPACITY_HI DB >WK_CAP16,>WK_CAP32,>WK_CAP48,>WK_CAP64
WK_APPLY_TEXT DB "Apply? [y/N]: ",0
WK_CONFIRM_TEXT DB "Changes storage metadata. Type YES: ",0
WK_FORMAT_TEXT DB "Clear program/claim metadata. Type FORMAT SRAM: ",0
WK_RESULT_TEXT DB "WORK error: $",0
WK_NO_CHANGE_TEXT DB "No change.",13,10,0
WK_CANCELED_TEXT DB "Canceled.",13,10,0
WK_RESIZED_TEXT DB "Resized.",13,10,0
WK_FORMATTED_TEXT DB "Formatted.",13,10,0
WK_UPGRADED_TEXT DB "Upgraded.",13,10,0
WK_REPAIRED_TEXT DB "Repaired.",13,10,0
WK_SUCCESS_LO DB <WK_RESIZED_TEXT,<WK_FORMATTED_TEXT,<WK_UPGRADED_TEXT,<WK_REPAIRED_TEXT
WK_SUCCESS_HI DB >WK_RESIZED_TEXT,>WK_FORMATTED_TEXT,>WK_UPGRADED_TEXT,>WK_REPAIRED_TEXT
WK_STATUS_COUNT EQU 8
WK_STATUS_CODES DB $40,$41,$44,$45,$48,$49,$4A,$80
WK_UNINITIALIZED_TEXT DB "Storage not initialized.",13,10,0
WK_INVALID_STORAGE_TEXT DB "Storage invalid or program exceeds boundary.",13,10,0
WK_INVALID_COMMAND_TEXT DB "Invalid command. Use HELP.",13,10,0
WK_VERIFY_TEXT DB "Write verification failed.",13,10,0
WK_EXHAUSTED_TEXT DB "Counter exhausted.",13,10,0
WK_UPGRADE_TEXT DB "Upgrade required. Use U.",13,10,0
WK_CONFLICT_TEXT DB "Resize refused: workspace overlaps.",13,10,0
WK_ABSENT_TEXT DB "SPI SRAM unavailable.",13,10,0
WK_STATUS_LO DB <WK_UNINITIALIZED_TEXT,<WK_INVALID_STORAGE_TEXT,<WK_INVALID_COMMAND_TEXT,<WK_VERIFY_TEXT,<WK_EXHAUSTED_TEXT,<WK_UPGRADE_TEXT,<WK_CONFLICT_TEXT,<WK_ABSENT_TEXT
WK_STATUS_HI DB >WK_UNINITIALIZED_TEXT,>WK_INVALID_STORAGE_TEXT,>WK_INVALID_COMMAND_TEXT,>WK_VERIFY_TEXT,>WK_EXHAUSTED_TEXT,>WK_UPGRADE_TEXT,>WK_CONFLICT_TEXT,>WK_ABSENT_TEXT
WK_REQ EQU $6800
WK_BUF EQU $6400
WK_EXPECT EQU $6860
WK_EXPECT_PACKET EQU $68A0
WK_LAYOUT EQU $68E0
WK_SESSION EQU $6920
WK_CLAIMS EQU $6960
WK_LINE EQU $69E0
WK_ADDR EQU $69F0
WK_SAVE_ADDR EQU $69F3
WK_POS EQU $69F6
WK_SIZE EQU $69F9
WK_END_POS EQU $69FC
WK_OLD_END EQU $69FF
WK_BP EQU $6A02
WK_SAVE_C EQU $6A04
WK_CRC EQU $6A06
WK_TEMP EQU $6A08
WK_PAGE_END EQU $6A0A
WK_N EQU $6A0C
WK_CRC_N EQU $6A0D
WK_PACKET_N EQU $6A0E
WK_ERROR EQU $6A0F
WK_LEGACY EQU $6A10
WK_FALLBACK EQU $6A11
WK_UNITS EQU $6A12
WK_NEW_UNITS EQU $6A13
WK_SESSION_VALID EQU $6A14
WK_SESSION_ADDR EQU $6A15
WK_SLOT EQU $6A16
WK_FREE_SLOT EQU $6A17
WK_PROG_SLOT EQU $6A18
WK_LINE_N EQU $6A19
WK_OVERFLOW EQU $6A1A
WK_ARITH_N EQU $6A1B
WK_CHECKING EQU $6A1C
WK_CHECK_SLOT EQU $6A1D
WK_CON_UNITS EQU $6A1E
WK_APP_END:
; Saved per-board EDU mode. No calls or accesses to service RAM $6500-$66FF.
ED_PTR EQU $D0
ED_CFG EQU $7D80
ED_PUTC EQU $7E6D
ED_GETC EQU $7E70
ED_START:  SEI
        CLD
        LDX #3
ED_CHECK:  JSR X28_R0
        CMP ED_MAGIC,X
                        BEQ ED_BM_LONG_20
                        JMP ED_ABSENT
ED_BM_LONG_20:
        DEX
                        BPL ED_CHECK
        LDA $7D27
                        BNE ED_BM_LONG_24
                        JMP ED_ABSENT
ED_BM_LONG_24:
        CMP #3
                        BCC ED_BM_LONG_26
                        JMP ED_ABSENT
ED_BM_LONG_26:
        LDX #<ED_TITLE
        LDY #>ED_TITLE
        JSR ED_PRINT
        LDA #1
        JSR X28_C1
        LDX #<ED_COMMAND_TEXT
        LDY #>ED_COMMAND_TEXT
        JSR ED_PRINT
ED_PROMPT: LDX #<ED_PROMPT_TEXT
        LDY #>ED_PROMPT_TEXT
        JSR ED_PRINT
        JSR B29_LINE_4
                        BCC ED_PROMPT
        LDA ED_LINE
                        BEQ ED_PROMPT
        CMP #'O'
                        BEQ ED_SET_MODE
        LDA ED_LINE+1
                        BEQ ED_BM_LONG_45
                        JMP ED_BAD
ED_BM_LONG_45:
        LDA ED_LINE
        CMP #'Q'
                        BNE ED_BM_LONG_48
                        JMP ED_QUIT
ED_BM_LONG_48:
        CMP #'?'
                        BEQ ED_BM_LONG_50
                        JMP ED_BAD
ED_BM_LONG_50:
        LDA #1
        JSR X28_C1
                        JMP ED_PROMPT
ED_SET_MODE:
        LDA ED_LINE+1
        CMP #'N'
                        BEQ ED_SET_ON
        CMP #'F'
                        BNE ED_BAD
        LDA ED_LINE+2
        CMP #'F'
                        BNE ED_BAD
        LDA ED_LINE+3
                        BNE ED_BAD
        LDA #$A5
                        BRA ED_SET_TARGET
ED_SET_ON: LDA ED_LINE+2
                        BNE ED_BAD
ED_SET_TARGET:
        STA ED_TARGET
        JSR ED_READ_CONFIG
                        BCC ED_CONFIG_BAD
        LDA ED_CFG+13
        CMP ED_TARGET
                        BNE ED_CONFIRM
        LDX #<ED_UNCHANGED_TEXT
        LDY #>ED_UNCHANGED_TEXT
                        JMP ED_MESSAGE
ED_CONFIRM:
        LDX #<ED_CONFIRM_TEXT
        LDY #>ED_CONFIRM_TEXT
        JSR ED_PRINT
        JSR ED_READ_LINE
                        BCC ED_CANCEL
        LDA ED_LINE
        CMP #'Y'
                        BNE ED_CANCEL
        LDA ED_LINE+1
                        BNE ED_CANCEL
        LDA ED_TARGET
        STA ED_CFG+13
        ; The validated format remains 1. EF50 computes F6/F7 even when the
        ; changed mode makes the old checksum disagree; publish the new sums.
        JSR X28_C2
        LDA $F6
        STA ED_CFG+14
        LDA $F7
        STA ED_CFG+15
        JSR X28_C3
                        BCC ED_SAVE_BAD
        JSR ED_READ_CONFIG
                        BCC ED_SAVE_BAD
        LDA ED_CFG+13
        CMP ED_TARGET
                        BNE ED_SAVE_BAD
        STA $7D28
        LDX #<ED_SAVED_OK
        LDY #>ED_SAVED_OK
                        JMP ED_MESSAGE
ED_CANCEL: JSR B29_ERROR_HOOK
 LDX #<ED_CANCEL_TEXT
        LDY #>ED_CANCEL_TEXT
                        JMP ED_MESSAGE
ED_BAD: JSR B29_ERROR_HOOK
    LDX #<ED_BAD_TEXT
        LDY #>ED_BAD_TEXT
                        JMP ED_MESSAGE
ED_CONFIG_BAD: JSR B29_ERROR_HOOK

        LDX #<ED_CONFIG_TEXT
        LDY #>ED_CONFIG_TEXT
                        JMP ED_MESSAGE
ED_SAVE_BAD: JSR B29_ERROR_HOOK

        LDX #<ED_FAILED_TEXT
        LDY #>ED_FAILED_TEXT
ED_MESSAGE:
        JSR ED_PRINT
        JMP ED_PROMPT
ED_ABSENT: JSR B29_ERROR_HOOK
 LDX #<ED_ABSENT_TEXT
        LDY #>ED_ABSENT_TEXT
        JSR ED_PRINT
ED_QUIT:   JMP X28_C0
ED_READ_CONFIG:
        JSR X28_C4
                        BCC ED_RETURN
        JMP X28_C2
ED_PRINT:  STX ED_PTR
        STY ED_PTR+1
        LDY #0
ED_PRINT_NEXT:
        LDA (ED_PTR),Y
                        BEQ ED_RETURN
        JSR ED_PUTC
        INY
                        BRA ED_PRINT_NEXT
ED_RETURN: RTS
ED_READ_LINE:
        STZ ED_COUNT
        STZ ED_OVERFLOW
ED_READ_NEXT:
        JSR ED_GETC
        CMP #3
                        BEQ ED_READ_CANCEL
        CMP #$1B
                        BEQ ED_READ_CANCEL
        CMP #10
                        BEQ ED_READ_NEXT
        CMP #13
                        BEQ ED_READ_DONE
        CMP #'a'
                        BCC ED_READ_CHAR
        CMP #'z'+1
                        BCS ED_READ_CHAR
        AND #$DF
ED_READ_CHAR:
        LDX ED_COUNT
        CPX #7
                        BCS ED_READ_FULL
        STA ED_LINE,X
        INC ED_COUNT
        JSR ED_PUTC
                        JMP ED_READ_NEXT
ED_READ_FULL:
        LDA #1
        STA ED_OVERFLOW
                        JMP ED_READ_NEXT
ED_READ_DONE:
        LDX ED_COUNT
        STZ ED_LINE,X
        JSR $7E7F
        LDA ED_OVERFLOW
                        BNE ED_READ_CANCEL
        SEC
        RTS
ED_READ_CANCEL: JSR B29_CANCEL_HOOK

        JSR $7E7F
        CLC
        RTS
ED_MAGIC DB "ED",1,3
ED_TITLE DB "EDU 1.4",0
ED_COMMAND_TEXT DB "ON OFF ? Q",13,10,0
ED_PROMPT_TEXT DB "EDU> ",0
ED_CONFIRM_TEXT DB "Apply after RESET? [y/N]: ",0
ED_UNCHANGED_TEXT DB "No change.",13,10,0
ED_SAVED_OK DB "Saved; RESET required.",13,10,0
ED_CANCEL_TEXT DB "Canceled.",13,10,0
ED_BAD_TEXT DB "Use ? ON OFF Q.",13,10,0
ED_CONFIG_TEXT DB "No valid startup settings.",13,10,0
ED_FAILED_TEXT DB "Save failed.",13,10,0
ED_ABSENT_TEXT DB "EDU mode software unavailable.",13,10,0
ED_LINE EQU $7CF0
ED_COUNT EQU $7CF8
ED_OVERFLOW EQU $7CF9
ED_TARGET EQU $7CFA
ED_OLD_BANK EQU $7CFB
ED_APP_END:
X28_C0:
        PHP
        PHA
        LDA #<$7E67
        STA X28_CALL+1
        LDA #>$7E67
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_C1:
        PHP
        PHA
        LDA #<$EF09
        STA X28_CALL+1
        LDA #>$EF09
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C2:
        PHP
        PHA
        LDA #<$EF00
        STA X28_CALL+1
        LDA #>$EF00
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C3:
        PHP
        PHA
        LDA #<$F039
        STA X28_CALL+1
        LDA #>$F039
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C4:
        PHP
        PHA
        LDA #<$F0B2
        STA X28_CALL+1
        LDA #>$F0B2
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C5:
        PHP
        PHA
        LDA #<K_V2W_MUTATE
        STA X28_CALL+1
        LDA #>K_V2W_MUTATE
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C6:
        PHP
        PHA
        LDA #<K_V2W_SNAPSHOT
        STA X28_CALL+1
        LDA #>K_V2W_SNAPSHOT
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C7:
        PHP
        PHA
        LDA #<K_V2W_ANALYZE
        STA X28_CALL+1
        LDA #>K_V2W_ANALYZE
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C8:
        PHP
        PHA
        LDA #<K_V2W_READ
        STA X28_CALL+1
        LDA #>K_V2W_READ
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C9:
        PHP
        PHA
        LDA #<K_V2W_BYTE
        STA X28_CALL+1
        LDA #>K_V2W_BYTE
        STA X28_CALL+2
        LDA V2_SELECTED
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C10:
        PHP
        PHA
        LDA #<$E011
        STA X28_CALL+1
        LDA #>$E011
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C11:
        PHP
        PHA
        LDA #<BOOT_SLOT_CHECK
        STA X28_CALL+1
        LDA #>BOOT_SLOT_CHECK
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C12:
        PHP
        PHA
        LDA #<$FAB4
        STA X28_CALL+1
        LDA #>$FAB4
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C13:
        PHP
        PHA
        LDA #<$FABD
        STA X28_CALL+1
        LDA #>$FABD
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C14:
        PHP
        PHA
        LDA #<$F007
        STA X28_CALL+1
        LDA #>$F007
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_C15:
        PHP
        PHA
        LDA #<$E80E
        STA X28_CALL+1
        LDA #>$E80E
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_R0:
        PHP
        PHA

        LDA #<$EE92
        STA X28_PTR
        LDA #>$EE92
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R0_PTR
        INC X28_PTR+1
X28_R0_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R1:
        PHP
        PHA

        LDA MM_SRC
        STA X28_PTR
        LDA MM_SRC+1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R2:
        PHP
        PHA

        LDA MM_DST
        STA X28_PTR
        LDA MM_DST+1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R3:
        PHP
        PHA

        LDA MM_SRC
        STA X28_PTR
        LDA MM_SRC+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R4:
        PHP
        PHA

        LDA V2_PTR
        STA X28_PTR
        LDA V2_PTR+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R5:
        PHP
        PHA

        LDA MM_TZ_PTR
        STA X28_PTR
        LDA MM_TZ_PTR+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R6:
        PHP
        PHA

        LDA #<$F0C1
        STA X28_PTR
        LDA #>$F0C1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R7:
        PHP
        PHA

        LDA #<$F0C2
        STA X28_PTR
        LDA #>$F0C2
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R8:
        PHP
        PHA

        LDA #<$F0C3
        STA X28_PTR
        LDA #>$F0C3
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R9:
        PHP
        PHA

        LDA #<$F684
        STA X28_PTR
        LDA #>$F684
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R10:
        PHP
        PHA

        LDA #<$F685
        STA X28_PTR
        LDA #>$F685
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R11:
        PHP
        PHA

        LDA #<$F686
        STA X28_PTR
        LDA #>$F686
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R12:
        PHP
        PHA

        LDA #<$F687
        STA X28_PTR
        LDA #>$F687
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R13:
        PHP
        PHA

        LDA #<$FFFD
        STA X28_PTR
        LDA #>$FFFD
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R14:
        PHP
        PHA

        LDA #<$FFFC
        STA X28_PTR
        LDA #>$FFFC
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R15:
        PHP
        PHA

        LDA #<$E000
        STA X28_PTR
        LDA #>$E000
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R15_PTR
        INC X28_PTR+1
X28_R15_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R16:
        PHP
        PHA

        LDA #<$E6E0
        STA X28_PTR
        LDA #>$E6E0
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R16_PTR
        INC X28_PTR+1
X28_R16_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R17:
        PHP
        PHA

        LDA #<$E6F0
        STA X28_PTR
        LDA #>$E6F0
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R17_PTR
        INC X28_PTR+1
X28_R17_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R18:
        PHP
        PHA

        LDA #<$E011
        STA X28_PTR
        LDA #>$E011
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R19:
        PHP
        PHA

        LDA #<$9000
        STA X28_PTR
        LDA #>$9000
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R19_PTR
        INC X28_PTR+1
X28_R19_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS
X28_APPS:
        LDX #15
X28_APPS_SAVE_ZP:
        LDA $D0,X
        PHA
        DEX
        BPL X28_APPS_SAVE_ZP
        LDX #<X28_APPS_TEXT
        LDY #>X28_APPS_TEXT
        JSR WK_PRINT
        LDX #0
X28_APPS_RESTORE_ZP:
        PLA
        STA $D0,X
        INX
        CPX #16
        BNE X28_APPS_RESTORE_ZP
        LDA $7D2E
        STA V2_SELECTED
        PHP
        PHA
        LDA #<$E19C
        STA X28_CALL+1
        LDA #>$E19C
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL
X28_APPS_TEXT DB 13,10,"MAINT FLASH B2",13,10,"SRAM FLASH B2",13,10,"WORK FLASH B2; API 5003",13,10,"EDU FLASH B2",13,10,0
B29_LINE_1:
        LDA $7D30
        CMP #$B0
        BNE B29_OLD_1
        LDA $7EF4
        CMP #$B9
        BNE B29_OLD_1
        LDA #1
        JMP $7C9F
B29_OLD_1: JMP MM_READLINE

B29_LINE_2:
        LDA $7D30
        CMP #$B0
        BNE B29_OLD_2
        LDA $7EF4
        CMP #$B9
        BNE B29_OLD_2
        LDA #2
        JMP $7C9F
B29_OLD_2: JMP SM_C_READLINE

B29_LINE_3:
        LDA $7D30
        CMP #$B0
        BNE B29_OLD_3
        LDA $7EF4
        CMP #$B9
        BNE B29_OLD_3
        LDA #3
        JMP $7C9F
B29_OLD_3: JMP WK_LINE_READ

B29_LINE_4:
        LDA $7D30
        CMP #$B0
        BNE B29_OLD_4
        LDA $7EF4
        CMP #$B9
        BNE B29_OLD_4
        LDA #4
        JMP $7C9F
B29_OLD_4: JMP ED_READ_LINE
B29_ERROR_HOOK:
        PHP
        PHA
        LDA $7D30
        CMP #$B0
        BNE B29_ERROR_DONE
        LDA $7EE4
        BEQ B29_ERROR_DONE
        LDA $7EE7
        CMP #2
        BEQ B29_ERROR_DONE
        LDA #1
        STA $7EE7
B29_ERROR_DONE:
        PLA
        PLP
        RTS
B29_CANCEL_HOOK:
        PHP
        PHA
        LDA $7D30
        CMP #$B0
        BNE B29_CANCEL_DONE
        LDA $7EE4
        BEQ B29_CANCEL_DONE
        LDA #2
        STA $7EE7
B29_CANCEL_DONE:
        PLA
        PLP
        RTS
B29_APP_CHECK:
        LDA $7EE4
        BEQ B29_APP_ACCEPT
        LDA $7D30
        CMP #$B0
        BNE B29_APP_ACCEPT
        LDY #0
        LDA ($FE),Y
        CMP #$80
        BNE B29_APP_REFUSE
        INY
        LDA ($FE),Y
        CMP #4
        BNE B29_APP_REFUSE
        LDY #5
B29_APP_MAGIC:
        LDA ($FE),Y
        CMP B29_APP_ID-2,Y
        BNE B29_APP_REFUSE
        DEY
        CPY #1
        BNE B29_APP_MAGIC
B29_APP_ACCEPT:
        SEC
        RTS
B29_APP_REFUSE:
        JSR B29_ERROR_HOOK
        CLC
        RTS
B29_APP_ID DB "BT",1,1
; Foreground command-boundary batch executive, linked in sealed B2 utilities.
B29_ACTIVE EQU $7EE4
B29_POS EQU $7EE5
B29_SIZE EQU $7EE6
B29_ERROR EQU $7EE7
B29_PROVIDER EQU $7EE8
B29_PORT EQU $7EE9
B29_ORIG EQU $7EEA
B29_PTR EQU $DC
B29_N EQU $7EEC
B29_START EQU $7EED
B29_LIMIT EQU $7EEE
B29_LENGTH EQU $7EEF
B29_OP EQU $7EF0
B29_LENPTR EQU $DE
B29_QUEUE EQU $7BD4
B29_RAM_MON EQU $7C90
B29_RAM_CLOCK EQU $7C94
B29_RAM_ERROR EQU $7C98
B29_RAM_APP EQU $7C9E
B29_RAM_COMMON EQU $7C9F

; Bit 7 means a complete interactive line has just been read. Only the
; monitor accepts BATCH; ordinary utility input retains its existing parser.
B29_ENGINE:
        STA B29_OP
        AND #$7F
        STA B29_PROVIDER
        ASL A
        TAX
        LDA B29_READERS,X
        STA B29_ORIG
        LDA B29_READERS+1,X
        STA B29_ORIG+1
        LDA B29_PROVIDER
                        BNE B29_NOT_MON
        LDA $7D30
        CLC
        ADC #B29_MON_DELTA
        STA B29_ORIG+1
B29_NOT_MON:
        LDA B29_OP
                        BMI B29_TYPED
        LDA B29_ACTIVE
                        BEQ B29_INTERACTIVE
        JSR $7E76
                        BCS B29_ESC
        LDY $F9
                        BEQ B29_POLL_DONE
        LDA $FD
        AND #63
        TAX
B29_POLL_ESC:
        LDA $7D40,X
        CMP #$1B
                        BEQ B29_ESC
        INX
        TXA
        AND #63
        TAX
        DEY
                        BNE B29_POLL_ESC
B29_POLL_DONE:
        LDA B29_ERROR
                        BEQ B29_NO_ERROR
        CMP #2
                        BEQ B29_ESC
                        BRA B29_FAILED
B29_NO_ERROR:
        LDA B29_POS
        CMP B29_SIZE
                        BCS B29_COMPLETED
        JMP B29_NEXT
B29_COMPLETED:
        LDX #<B29_DONE_TEXT
        LDY #>B29_DONE_TEXT
                        JMP B29_STOP
B29_ESC:
        JSR $7E79
        LDX #<B29_CANCEL_TEXT
        LDY #>B29_CANCEL_TEXT
                        JMP B29_STOP
B29_FAILED:
        LDX #<B29_FAIL_TEXT
        LDY #>B29_FAIL_TEXT
B29_STOP:
        STZ B29_ACTIVE
        STZ B29_ERROR
        JSR B29_PRINT
        LDX B29_PROVIDER
        LDA B29_PROMPT_LO,X
        LDY B29_PROMPT_HI,X
        TAX
        JSR B29_PRINT
B29_INTERACTIVE:
        CLC
        RTS
B29_TYPED:
        LDA B29_PROVIDER
                        BEQ B29_LONG_99
                        JMP B29_TYPED_RETURN
B29_LONG_99:
        JSR B30_ALIAS
        LDA $7C00
        CMP #'?'
                        BNE B29_TRY_BATCH
        LDA $7C01
                        BNE B29_TYPED_RETURN
        JSR B29_FULL_HELP
        STZ $7C00
                        JMP B29_TYPED_RETURN
B29_TRY_BATCH:
        LDX #5
B29_MATCH:
        LDA $7C00,X
        CMP B29_WORD,X
                        BNE B29_TYPED_RETURN
        DEX
                        BPL B29_MATCH
        LDX #6
        LDY #0
B29_CAPTURE:
        LDA $7C00,X
                        BEQ B29_CAPTURED
        CPY #34
                        BCS B29_SYNTAX
        STA B29_QUEUE,Y
        INX
        INY
                        BRA B29_CAPTURE
B29_CAPTURED:
        STY B29_SIZE
        CPY #0
                        BEQ B29_SYNTAX
        STZ B29_POS
        STZ B29_ERROR
        LDA #1
        STA B29_ACTIVE
        ; Validate all separators before executing the first command.
        LDX #0
        LDY #0
B29_VALIDATE:
        LDA B29_QUEUE,X
        CMP #';'
                        BEQ B29_SEPARATOR
        CMP #' '
                        BEQ B29_VALID_NEXT
        INY
                        BRA B29_VALID_NEXT
B29_SEPARATOR:
        CPY #0
                        BEQ B29_SYNTAX
        LDY #0
B29_VALID_NEXT:
        INX
        CPX B29_SIZE
                        BNE B29_VALIDATE
        CPY #0
                        BEQ B29_SYNTAX
                        JMP B29_NEXT
B29_SYNTAX:
        STZ B29_ACTIVE
        STZ B29_ERROR
        STZ $7C00
        LDX #<B29_SYNTAX_TEXT
        LDY #>B29_SYNTAX_TEXT
        JSR B29_PRINT
        LDX #0
        LDY #0
        SEC
        RTS
B29_TYPED_RETURN:
        SEC
        RTS
B29_NEXT:
        LDX B29_POS
B29_SKIP_SPACE:
        LDA B29_QUEUE,X
        CMP #' '
                        BNE B29_BEGIN
        INX
                        BRA B29_SKIP_SPACE
B29_BEGIN:
        STX B29_START
        LDY #0
B29_COUNT:
        CPX B29_SIZE
                        BEQ B29_COUNTED
        LDA B29_QUEUE,X
        CMP #';'
                        BEQ B29_COUNTED
        INY
        INX
                        BRA B29_COUNT
B29_COUNTED:
        CPX B29_SIZE
                        BEQ B29_POSITION
        INX
B29_POSITION:
        STX B29_POS
        ; Strip trailing spaces and check the current interpreter's bound.
        TYA
        CLC
        ADC B29_START
        TAX
B29_TRIM:
        DEX
        LDA B29_QUEUE,X
        CMP #' '
                        BNE B29_TRIMMED
        DEY
                        BRA B29_TRIM
B29_TRIMMED:
        STY B29_N
        LDX B29_PROVIDER
        TYA
        CMP B29_LIMITS,X
                        BCC B29_SEGMENT_FITS
        JMP B29_SEGMENT_BAD
B29_SEGMENT_FITS:
        TXA
        ASL A
        TAX
        LDA B29_LINES,X
        STA B29_PTR
        LDA B29_LINES+1,X
        STA B29_PTR+1
        LDA B29_LENGTHS,X
        STA B29_LENPTR
        LDA B29_LENGTHS+1,X
        STA B29_LENPTR+1
        LDA B29_PROVIDER
                        BNE B29_COPY_SETUP
        LDA #'B'
        JSR $7E6D
B29_MON_SUFFIX:
        LDA $F3
        ORA #'0'
        JSR $7E6D
        LDA #'>'
        JSR $7E6D
        LDA #' '
        JSR $7E6D
B29_COPY_SETUP:
        LDX B29_START
        LDY #0
B29_COPY:
        LDA B29_QUEUE,X
        STA (B29_PTR),Y
        JSR $7E6D
        INX
        INY
        CPY B29_N
                        BNE B29_COPY
        LDA #0
        STA (B29_PTR),Y
        LDA B29_N
        LDY #0
        STA (B29_LENPTR),Y
        JSR $7E7F
        ; Monitor batches deliberately exclude raw jumps/loaders/reset and
        ; unregistered RAM programs. Native launch commands are recognized.
        LDA B29_PROVIDER
                        BEQ B29_LONG_260
                        JMP B29_READY
B29_LONG_260:
        LDA $7C00
        CMP #'?'
                        BNE B29_MON_NOT_HELP
        LDA $7C01
                        BNE B29_SEGMENT_BAD
        JSR B29_FULL_HELP
        STZ $7C00
                        JMP B29_READY
B29_MON_NOT_HELP:
        JSR B30_ALIAS
        LDA $7C00
        CMP #'A'
        BNE B33_NOT_APP
        JSR B33_BATCH_APPS
        BCS B33_NOT_APP
        JMP B29_SEGMENT_BAD
B33_NOT_APP:
        LDA $7C00
        CMP #'R'
                        BEQ B29_MON_RUN
        LDX #0
B29_MON_ALLOWED:
        CMP B29_MON_KEYS,X
                        BEQ B29_READY
        INX
        CPX #8
                        BNE B29_MON_ALLOWED
                        JMP B29_SEGMENT_BAD
B29_MON_RUN:
        LDX #1
B29_RUN_SPACE:
        LDA $7C00,X
        CMP #' '
                        BNE B29_RUN_BANK
        INX
                        BRA B29_RUN_SPACE
B29_RUN_BANK:
        CMP #'2'
                        BNE B29_MON_NAME
        INX
B29_BANK_SPACE:
        LDA $7C00,X
        CMP #' '
                        BNE B29_MON_NAME
        INX
                        BRA B29_BANK_SPACE
B29_MON_NAME:
        STX B29_LIMIT
        LDY #0
B29_NATIVE_MATCH:
        LDA $7C00,X
        CMP B29_NATIVE_NAMES,Y
                        BNE B29_NATIVE_SKIP
        INX
        INY
        LDA $7C00,X
                        BEQ B29_NATIVE_END
                        JMP B29_NATIVE_MATCH
B29_NATIVE_END:
        LDA B29_NATIVE_NAMES,Y
                        BEQ B29_READY
B29_NATIVE_SKIP:
        LDA B29_NATIVE_NAMES,Y
        INY
        CMP #$FF
                        BEQ B29_SEGMENT_BAD
        CMP #0
                        BNE B29_NATIVE_SKIP
        LDX B29_LIMIT
                        JMP B29_NATIVE_MATCH
B29_SEGMENT_BAD:
        STZ B29_ACTIVE
        STZ B29_ERROR
        LDX #<B29_UNSUPPORTED_TEXT
        LDY #>B29_UNSUPPORTED_TEXT
        JSR B29_PRINT
        LDA B29_PROVIDER
                        BEQ B29_MON_EMPTY
        JMP B29_INTERACTIVE
B29_MON_EMPTY:
        STZ $7C00
B29_READY:
        STZ B29_ERROR
        LDX B29_N
        LDY #0
        SEC
        RTS
B29_PRINT:
        STX B29_PTR
        STY B29_PTR+1
        LDY #0
B29_PRINT_NEXT:
        LDA (B29_PTR),Y
                        BEQ B29_PRINT_DONE
        JSR $7E6D
        INY
                        BNE B29_PRINT_NEXT
        INC B29_PTR+1
                        BRA B29_PRINT_NEXT
B29_PRINT_DONE:
        RTS
B29_FULL_HELP:
        LDX #<B29_FULL_HELP_TEXT
        LDY #>B29_FULL_HELP_TEXT
        BRA B29_PRINT
B29_WORD DB "BATCH "
B29_MON_KEYS DB "?BDTWAMV"
B29_NATIVE_NAMES DB "MAINT",0,"SRAM",0,"WORK",0,"EDU",0,$FF
B29_DONE_TEXT DB 13,10,"BATCH done",13,10,0
B29_FAIL_TEXT DB 13,10,"BATCH stopped: command failed",13,10,0
B29_CANCEL_TEXT DB 13,10,"BATCH canceled",13,10,0
B29_SYNTAX_TEXT DB "BATCH: empty/long command list",13,10,0
B29_UNSUPPORTED_TEXT DB "BATCH stopped: unsupported/long command",13,10,0
B29_PROMPT_LO DB <B29_P0,<B29_P1,<B29_P2,<B29_P3,<B29_P4,<B29_P5
B29_PROMPT_HI DB >B29_P0,>B29_P1,>B29_P2,>B29_P3,>B29_P4,>B29_P5
B29_P0 DB 0
B29_P1 DB "BM> ",0
B29_P2 DB "SRAM> ",0
B29_P3 DB "WORK> ",0
B29_P4 DB "EDU> ",0
B29_P5 DB "CLOCK> ",0

B29_FULL_HELP_TEXT:
        DB $54,$49,$4D,$45,$0D,$0A,$42,$30,$2D,$33,$20,$44,$20,$61,$64,$64
        DB $72,$20,$5B,$65,$6E,$64,$5D,$20,$4D,$2F,$46,$20,$61,$64,$64,$72
        DB $20,$62,$79,$74,$65,$73,$20,$47,$20,$61,$64,$64,$72,$20,$4C,$0D
        DB $0A,$4D,$20,$5B,$31,$20,$67,$72,$69,$64,$7C,$32,$20,$72,$61,$6E
        DB $67,$65,$73,$7C,$33,$20,$77,$65,$61,$72,$5D,$0D,$0A,$49,$20,$73
        DB $74,$61,$72,$74,$20,$65,$6E,$64,$20,$57,$20,$55,$20,$41,$7C,$42
        DB $0D,$0A,$53,$20,$62,$61,$6E,$6B,$20,$66,$6C,$61,$73,$68,$20,$73
        DB $74,$61,$72,$74,$20,$65,$6E,$64,$20,$5B,$6E,$61,$6D,$65,$5D,$0D
        DB $0A,$52,$20,$5B,$62,$61,$6E,$6B,$5D,$20,$6E,$61,$6D,$65,$7C,$62
        DB $61,$6E,$6B,$20,$66,$6C,$61,$73,$68,$20,$5B,$4C,$5D,$0D,$0A,$54
        DB $20,$5B,$62,$61,$6E,$6B,$7C,$66,$69,$72,$73,$74,$2D,$6C,$61,$73
        DB $74,$5D,$0D,$0A,$4A,$30,$2D,$33,$20,$43,$20,$5B,$30,$7C,$31,$20
        DB $62,$61,$6E,$6B,$20,$61,$64,$64,$72,$7C,$56,$20,$64,$65,$6C,$61
        DB $79,$5D,$20,$50,$20,$5B,$41,$7C,$42,$5D,$0D,$0A,$4D,$41,$49,$4E
        DB $54,$20,$53,$52,$41,$4D,$20,$57,$4F,$52,$4B,$20,$45,$44,$55,$20
        DB $28,$52,$20,$6F,$70,$74,$69,$6F,$6E,$61,$6C,$29,$0D,$0A,$42,$41
        DB $54,$43,$48,$20,$63,$6D,$64,$3B,$63,$6D,$64,$20,$28,$33,$34,$20
        DB $74,$65,$78,$74,$20,$62,$79,$74,$65,$73,$29,$3B,$20,$45,$53,$43
        DB $20,$63,$61,$6E,$63,$65,$6C,$73,$0D,$0A,$00

B29_MON_DELTA EQU $0C
B29_READERS DW $ACF0,MM_READLINE,SM_C_READLINE,WK_LINE_READ,ED_READ_LINE,$25D1
B29_LINES DW $7C00,MM_BM_LINE,SM_C_LINE,WK_LINE,ED_LINE,$364B
B29_LENGTHS DW $7EEF,MM_LINELEN,SM_D_LINE_LENGTH,WK_LINE_N,ED_COUNT,$3633
B29_LIMITS DB 41,64,64,56,8,40
; Exact monitor aliases share the existing native-name table.
; Only called for provider zero. Do not intercept utility subcommands.
B30_ALIAS:
        LDX #0
B30_LEADING:
        LDA $7C00,X
        CMP #' '
        BNE B30_FIRST
        INX
        BRA B30_LEADING
B30_FIRST:
        STX B29_LIMIT
        LDY #0
B30_NAME:
        STY B29_LENGTH
        LDX B29_LIMIT
B30_MATCH:
        LDA B29_NATIVE_NAMES,Y
        BEQ B30_TAIL
        CMP #$FF
        BEQ B30_RETURN
        CMP $7C00,X
        BNE B30_NEXT
        INX
        INY
        BRA B30_MATCH
B30_TAIL:
        LDA $7C00,X
        BEQ B30_EXPAND
        CMP #' '
        BNE B30_NEXT
        INX
        BRA B30_TAIL
B30_NEXT:
        LDA B29_NATIVE_NAMES,Y
        CMP #$FF
        BEQ B30_RETURN
        INY
        CMP #0
        BNE B30_NEXT
        BRA B30_NAME
B30_EXPAND:
        LDY B29_LENGTH
        LDX #2
B30_COPY:
        LDA B29_NATIVE_NAMES,Y
        STA $7C00,X
        BEQ B30_PREFIX
        INX
        INY
        BRA B30_COPY
B30_PREFIX:
        STX B29_N
        LDA #'R'
        STA $7C00
        LDA #' '
        STA $7C01
B30_RETURN:
        RTS

B33_BATCH_APPS:
        LDX #0
B33_APPS_MATCH:
        LDA $7C00,X
        CMP B33_APPS_WORD,X
        BNE B33_APPS_BAD
        INX
        CPX #4
        BNE B33_APPS_MATCH
B33_APPS_TAIL:
        LDA $7C00,X
        BEQ B33_APPS_OK
        CMP #' '
        BNE B33_APPS_BAD
        INX
        BRA B33_APPS_TAIL
B33_APPS_OK: SEC
        RTS
B33_APPS_BAD: CLC
        RTS
B33_APPS_WORD DB "APPS"
X28_END:
        ENDMOD
