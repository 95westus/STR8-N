; STR8-N bank maintenance 1.0, RAM entry $2000, no E extension dependency.
; Console uses the initialized, fixed v2 RAM ABI. All banking, flash work,
; command processing and constants execute in RAM, including after B3:F erase.
; The builder expands conditional branches to long branches before assembly.
                        MODULE BANK_MAINT_V2
                        XDEF START
                        XDEF BM_END
                        INCLUDE "str8n-v2-eq.inc"
SRC                     EQU $C0
DST                     EQU $C2
CNT                     EQU $C4
TXT                     EQU $C6
BUF                     EQU $C8
BM_LINE                 EQU $6000
NUM                     EQU $6100
FIRST                   EQU $6102
LAST                    EQU $6104
SB                      EQU $6106
DB                      EQU $6107
FROM                    EQU $6108
THROUGH                 EQU $610A
TO                      EQU $610C
TOEND                   EQU $610E
LENGTH                  EQU $6110
INDEX                   EQU $6112
LINELEN                 EQU $6113
REVERSE                 EQU $6114
MODE                    EQU $6115
DANGER                  EQU $6116
TOUCHED                 EQU $6117
RESIDENT                EQU $6118
BLEN                    EQU $611A
DIRTY                   EQU $611C
OFFSET                  EQU $611D
VALUE                   EQU $611F
SAVED_INDEX             EQU $6120
MAPBANK                 EQU $6121
MAPSEC                  EQU $6122
CRC                     EQU $6123
DIGITS                  EQU $6125
OVERFLOW                EQU $6126
BYTE                    EQU $6127
EDITOR                  EQU $5000
PUTC                    EQU $7E6D
GETC                    EQU $7E70
HEX                     EQU $7E7C
NL                      EQU $7E7F
NIBBLE                  EQU $7E82
                        CODE
START:                  SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDX #$2F
BM_INIT:                STZ $6100,X
                        DEX
                        BPL BM_INIT
                        LDA V2_RESIDENT
                        CMP #$04
                        BCS BM_UNSUPPORTED
                        STA RESIDENT
                        LDA $7E60
                        CMP #'R'
                        BNE BM_UNSUPPORTED
                        LDA $7E61
                        CMP #'A'
                        BNE BM_UNSUPPORTED
                        LDA $7E62
                        CMP #$01
                        BNE BM_UNSUPPORTED
                        LDA $7E63
                        CMP #$0D
                        BCC BM_UNSUPPORTED
                        LDX #<TITLE
                        LDY #>TITLE
                        JSR PRINT
                        STZ BM_LINE
                        JMP BM_HELP
; No unverified ABI calls on entry refusal. Return is unavailable after G.
BM_UNSUPPORTED:         JMP BM_UNSUPPORTED
BM_MENU:                LDX #$FF
                        TXS
                        LDA RESIDENT
                        JSR V2W_SELECT
                        LDX #<PROMPT
                        LDY #>PROMPT
                        JSR PRINT
                        JSR READLINE
                        BCC BM_CANCEL
                        STZ INDEX
                        JSR SPACES
                        BEQ BM_MENU
                        STA MODE
                        INC INDEX
                        CMP #'?'
                        BEQ BM_HELP
                        CMP #'M'
                        BEQ BM_MAP
                        CMP #'E'
                        BEQ BM_ERASE
                        CMP #'C'
                        BEQ BM_COPY
                        CMP #'V'
                        BEQ BM_COPY
                        CMP #'R'
                        BEQ BM_READ
                        CMP #'S'
                        BEQ BM_STAGE
                        CMP #'W'
                        BEQ BM_WRITE
                        CMP #'D'
                        BEQ BM_DISPLAY
                        CMP #'P'
                        BEQ BM_PATCH
                        CMP #'F'
                        BEQ BM_FILL
                        CMP #'N'
                        BEQ BM_NEW
                        CMP #'K'
                        BEQ BM_CRC
                        CMP #'J'
                        BEQ BM_BOOT
                        CMP #'Q'
                        BEQ BM_QUIT
                        JMP BM_BAD
BM_HELP:                JSR ENDLINE
                        BCC BM_BAD
                        LDX #<HELP
                        LDY #>HELP
                        JSR PRINT
                        JMP BM_MENU
BM_BAD:                 LDX #<BAD
                        LDY #>BAD
                        JMP MESSAGE
BM_CANCEL:              LDX #<CANCEL
                        LDY #>CANCEL
                        JMP MESSAGE
BM_FAIL:                LDX #<FAILED
                        LDY #>FAILED
                        JMP MESSAGE
BM_DONE:                LDA MODE
                        CMP #'W'
                        BNE BM_DONE_TEXT
                        STZ DIRTY
BM_DONE_TEXT:           LDX #<DONE
                        LDY #>DONE
MESSAGE:                JSR PRINT
                        JMP BM_MENU

; E bank sector[-sector]. A range is wholly validated before any mutation.
BM_ERASE:               JSR BANK
                        BCC BM_BAD
                        CMP #$FF
                        BEQ BM_BAD
                        STA DB
                        STA SB
                        JSR RANGE
                        BCC BM_BAD
                        LDA FIRST+1
                        ORA LAST+1
                        BNE BM_BAD
                        LDA FIRST
                        CMP #$08
                        BCC BM_BAD
                        LDA LAST
                        CMP #$10
                        BCS BM_BAD
                        JSR SCALE_RANGE
                        JSR ENDLINE
                        BCC BM_BAD
                        JSR SOURCE_FIELDS
                        LDA FIRST
                        STA TO
                        LDA FIRST+1
                        STA TO+1
                        JSR GET_LENGTH
                        JSR DEST_END
                        BCC BM_BAD
                        LDA #$FD
                        STA SB
                        JSR CONFIRM
                        BCC BM_CANCEL
                        JMP COPY_RUN

; C/V source-space range destination-space start. Flash 8-F shorthand is
; a sector/range; full addresses allow partial-sector copies with preservation.
BM_COPY:                JSR SOURCE_ARGS
                        BCC BM_BAD
                        JSR DEST_ARGS
                        BCC BM_BAD
                        JSR ENDLINE
                        BCC BM_BAD
                        LDA MODE
                        CMP #'V'
                        BEQ COMPARE_RUN
                        JSR CONFIRM
                        BCC BM_CANCEL
                        JMP COPY_RUN
BM_WRITE:               JSR BUFFER_PRESENT
                        BCC BM_BAD
                        LDA #$FE
                        STA SB
                        STZ FROM
                        LDA #$50
                        STA FROM+1
                        LDA BLEN
                        STA LENGTH
                        LDA BLEN+1
                        STA LENGTH+1
                        SEC
                        LDA BLEN
                        SBC #$01
                        STA THROUGH
                        LDA BLEN+1
                        SBC #$00
                        CLC
                        ADC #$50
                        STA THROUGH+1
                        JSR DEST_ARGS
                        BCC BM_BAD
                        JSR ENDLINE
                        BCC BM_BAD
                        JSR CONFIRM
                        BCC BM_CANCEL
                        JMP COPY_RUN

SOURCE_ARGS:            JSR BANK
                        BCC ARGS_FAIL
                        STA SB
                        JSR RANGE
                        BCC ARGS_FAIL
                        JSR SCALE_RANGE
                        LDA SB
                        JSR VALID_RANGE
                        BCC ARGS_FAIL
                        JSR SOURCE_FIELDS
GET_LENGTH:             SEC
                        LDA THROUGH
                        SBC FROM
                        STA LENGTH
                        LDA THROUGH+1
                        SBC FROM+1
                        STA LENGTH+1
                        INC LENGTH
                        BNE LENGTH_OK
                        INC LENGTH+1
LENGTH_OK:              SEC
                        RTS
SOURCE_FIELDS:          LDA FIRST
                        STA FROM
                        LDA FIRST+1
                        STA FROM+1
                        LDA LAST
                        STA THROUGH
                        LDA LAST+1
                        STA THROUGH+1
                        RTS
DEST_ARGS:              JSR BANK
                        BCC ARGS_FAIL
                        STA DB
                        JSR NUMBER
                        BCC ARGS_FAIL
                        LDA DB
                        CMP #$FF
                        BEQ DEST_RAW
                        LDA NUM+1
                        BNE DEST_RAW
                        LDA NUM
                        CMP #$08
                        BCC DEST_RAW
                        CMP #$10
                        BCS DEST_RAW
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA NUM+1
                        STZ NUM
DEST_RAW:               LDA NUM
                        STA TO
                        LDA NUM+1
                        STA TO+1
DEST_END:               SEC
                        LDA LENGTH
                        SBC #$01
                        STA TOEND
                        LDA LENGTH+1
                        SBC #$00
                        STA TOEND+1
                        CLC
                        LDA TO
                        ADC TOEND
                        STA TOEND
                        LDA TO+1
                        ADC TOEND+1
                        STA TOEND+1
                        BCS ARGS_FAIL
                        LDA TO
                        STA FIRST
                        LDA TO+1
                        STA FIRST+1
                        LDA TOEND
                        STA LAST
                        LDA TOEND+1
                        STA LAST+1
                        LDA DB
                        JMP VALID_RANGE
ARGS_FAIL:              CLC
                        RTS

; RAM ranges exclude zero page/stack, this utility, editor/state, monitor/I/O.
; The same rule applies to sources so streaming cannot read its own scratch.
VALID_RANGE:            PHA
                        LDA LAST
                        CMP FIRST
                        LDA LAST+1
                        SBC FIRST+1
                        PLA
                        BCC RANGE_FAIL
                        CMP #$FF
                        BEQ RANGE_RAM
                        LDA FIRST+1
                        CMP #$80
                        RTS
RANGE_RAM:              LDA FIRST+1
                        CMP #$02
                        BCC RANGE_FAIL
                        LDA LAST+1
                        CMP #$69
                        BCS RANGE_FAIL
                        CMP #$20
                        BCC RANGE_EDITOR
                        LDA FIRST
                        CMP #<BM_END
                        LDA FIRST+1
                        SBC #>BM_END
                        BCC RANGE_FAIL
RANGE_EDITOR:           LDA LAST+1
                        CMP #$50
                        BCC RANGE_OK
                        LDA FIRST+1
                        CMP #$62
                        BCC RANGE_FAIL
RANGE_OK:               SEC
                        RTS
RANGE_FAIL:             CLC
                        RTS

; Exact operation line plus normalized destination is shown before confirmation.
CONFIRM:                STZ DANGER
                        LDX #<PLAN_TEXT
                        LDY #>PLAN_TEXT
                        JSR PRINT
                        LDX #<BM_LINE
                        LDY #>BM_LINE
                        JSR PRINT
                        LDX #<DEST_TEXT
                        LDY #>DEST_TEXT
                        JSR PRINT
                        LDA DB
                        JSR SPACE_NAME
                        LDA #':'
                        JSR PUTC
                        LDA TO+1
                        JSR HEX
                        LDA TO
                        JSR HEX
                        LDA #'-'
                        JSR PUTC
                        LDA TOEND+1
                        JSR HEX
                        LDA TOEND
                        JSR HEX
                        LDA DB
                        CMP #$03
                        BNE CONFIRM_FIRST
                        LDA TOEND+1
                        CMP #$F0
                        BCC CONFIRM_FIRST
                        INC DANGER
CONFIRM_FIRST:          LDX #<CONFIRM_TEXT
                        LDY #>CONFIRM_TEXT
                        JSR PRINT
                        JSR READLINE
                        BCC CONFIRM_NO
                        LDA BM_LINE
                        CMP #'Y'
                        BNE CONFIRM_NO
                        LDA BM_LINE+1
                        BNE CONFIRM_NO
                        LDA DANGER
                        BEQ CONFIRM_YES
                        LDX #<B3F_TEXT
                        LDY #>B3F_TEXT
                        JSR PRINT
                        JSR READLINE
                        BCC CONFIRM_NO
                        LDA BM_LINE
                        CMP #'B'
                        BNE CONFIRM_NO
                        LDA BM_LINE+1
                        CMP #'3'
                        BNE CONFIRM_NO
                        LDA BM_LINE+2
                        CMP #'F'
                        BNE CONFIRM_NO
                        LDA BM_LINE+3
                        BNE CONFIRM_NO
CONFIRM_YES:            SEC
                        RTS
CONFIRM_NO:             CLC
                        RTS

; Direction-aware streaming gives memmove semantics even for overlapping flash
; ranges. Construct a complete destination sector before programming any byte.
SET_POINTERS:           STZ REVERSE
                        LDA FROM
                        STA SRC
                        LDA FROM+1
                        STA SRC+1
                        LDA TO
                        STA DST
                        LDA TO+1
                        STA DST+1
                        LDA LENGTH
                        STA CNT
                        LDA LENGTH+1
                        STA CNT+1
                        LDA SB
                        CMP DB
                        BNE POINTERS_DONE
                        LDA TO
                        CMP FROM
                        LDA TO+1
                        SBC FROM+1
                        BCC POINTERS_DONE
                        LDA THROUGH
                        CMP TO
                        LDA THROUGH+1
                        SBC TO+1
                        BCC POINTERS_DONE
                        INC REVERSE
                        LDA THROUGH
                        STA SRC
                        LDA THROUGH+1
                        STA SRC+1
                        LDA TOEND
                        STA DST
                        LDA TOEND+1
                        STA DST+1
POINTERS_DONE:          RTS
COPY_RUN:               JSR SET_POINTERS
                        LDA DB
                        CMP #$FF
                        BEQ COPY_RAM
COPY_SECTOR:            JSR CHECK_CANCEL
                        LDA DB
                        STA V2_SELECTED
                        LDA DST+1
                        AND #$F0
                        STA V2_SECTOR
                        JSR V2W_SNAPSHOT
COPY_BYTE:              JSR READ_SOURCE
                        STA BYTE
                        LDA DST
                        STA BUF
                        LDA DST+1
                        AND #$0F
                        CLC
                        ADC #$69
                        STA BUF+1
                        LDA BYTE
                        STA (BUF)
                        JSR ADVANCE
                        BEQ COPY_COMMIT
                        LDA DST+1
                        AND #$F0
                        CMP V2_SECTOR
                        BEQ COPY_BYTE
COPY_COMMIT:            JSR CHECK_CANCEL
                        LDA DB
                        STA V2_SELECTED
                        CMP RESIDENT
                        BNE COPY_ANALYZE
                        LDA V2_SECTOR
                        CMP #$F0
                        BNE COPY_ANALYZE
                        LDA #$01
                        STA TOUCHED
COPY_ANALYZE:           JSR V2W_ANALYZE
                        STZ V2_SELF
                        JSR V2W_MUTATE
                        BCS BM_FAIL
                        LDA CNT
                        ORA CNT+1
                        BNE COPY_SECTOR
                        JMP BM_DONE
COPY_RAM:               JSR CHECK_CANCEL
                        JSR READ_SOURCE
                        STA (DST)
                        CMP (DST)
                        BNE BM_FAIL
                        JSR ADVANCE
                        BNE COPY_RAM
                        JMP BM_DONE
CHECK_CANCEL:           JSR $7E76
                        BCS BM_CANCEL
                        RTS
READ_SOURCE:            LDA SB
                        CMP #$FD
                        BEQ READ_FF
                        CMP #$04
                        BCS READ_RAM
                        JSR V2W_SELECT
READ_RAM:               LDA (SRC)
                        RTS
READ_FF:                LDA #$FF
                        RTS
ADVANCE:                LDA CNT
                        BNE ADV_COUNT
                        DEC CNT+1
ADV_COUNT:              DEC CNT
                        LDA REVERSE
                        BEQ ADV_FORWARD
                        LDA SRC
                        BNE ADV_SRC_DOWN
                        DEC SRC+1
ADV_SRC_DOWN:           DEC SRC
                        LDA DST
                        BNE ADV_DST_DOWN
                        DEC DST+1
ADV_DST_DOWN:           DEC DST
                        BRA ADV_DONE
ADV_FORWARD:            INC SRC
                        BNE ADV_DST_UP
                        INC SRC+1
ADV_DST_UP:             INC DST
                        BNE ADV_DONE
                        INC DST+1
ADV_DONE:               LDA CNT
                        ORA CNT+1
                        RTS
COMPARE_RUN:            JSR SET_POINTERS
COMPARE_BYTE:           JSR CHECK_CANCEL
                        JSR READ_SOURCE
                        STA BYTE
                        LDA DB
                        CMP #$04
                        BCS COMPARE_RAM
                        JSR V2W_SELECT
COMPARE_RAM:            LDA (DST)
                        CMP BYTE
                        BNE COMPARE_DIFFERENT
                        JSR ADVANCE
                        BNE COMPARE_BYTE
                        LDX #<MATCH_TEXT
                        LDY #>MATCH_TEXT
                        JMP MESSAGE
COMPARE_DIFFERENT:      LDX #<DIFFERENT_TEXT
                        LDY #>DIFFERENT_TEXT
                        JSR PRINT
                        LDA DST+1
                        JSR HEX
                        LDA DST
                        JSR HEX
                        JMP BM_MENU

; R reads up to 4 KiB into the independent editor buffer. W is the only
; editor command that changes a destination. Copy/erase never consume it.
; Stage the utility's immutable image into the editor, including FF padding.
; S 8 -> original $2000-$2FFF; S 9 -> original $3000-$3FFF.
BM_STAGE:               JSR NUMBER
                        BCC BM_BAD
                        LDA NUM+1
                        BNE BM_BAD
                        LDA NUM
                        CMP #$08
                        BEQ STAGE_ARGUMENT
                        CMP #$09
                        BNE BM_BAD
STAGE_ARGUMENT:         STA VALUE
                        JSR ENDLINE
                        BCC BM_BAD
                        LDA VALUE
                        SEC
                        SBC #$06
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA SRC+1
                        STZ SRC
                        STZ DST
                        LDA #$50
                        STA DST+1
                        STZ CNT
                        STZ BLEN
                        LDA #$10
                        STA CNT+1
                        STA BLEN+1
                        STZ REVERSE
STAGE_BYTE:             LDA SRC
                        CMP #<BM_END
                        LDA SRC+1
                        SBC #>BM_END
                        BCS STAGE_PADDING
                        LDA (SRC)
                        BRA STAGE_STORE
STAGE_PADDING:          LDA #$FF
STAGE_STORE:            STA (DST)
                        JSR ADVANCE
                        BNE STAGE_BYTE
                        LDA #$01
                        STA DIRTY
                        JMP BUFFER_EDITED
BM_READ:                JSR SOURCE_ARGS
                        BCC BM_BAD
                        JSR ENDLINE
                        BCC BM_BAD
                        JSR LENGTH_4K
                        BCC BM_BAD
                        LDA LENGTH
                        STA BLEN
                        STA CNT
                        LDA LENGTH+1
                        STA BLEN+1
                        STA CNT+1
                        LDA FROM
                        STA SRC
                        LDA FROM+1
                        STA SRC+1
                        STZ DST
                        LDA #$50
                        STA DST+1
                        STZ REVERSE
READ_BUFFER_LOOP:       JSR READ_SOURCE
                        STA (DST)
                        JSR ADVANCE
                        BNE READ_BUFFER_LOOP
                        STZ DIRTY
                        LDX #<BUFFER_TEXT
                        LDY #>BUFFER_TEXT
                        JMP MESSAGE
LENGTH_4K:              LDA LENGTH
                        ORA LENGTH+1
                        BEQ RANGE_FAIL
                        LDA LENGTH+1
                        CMP #$10
                        BCC RANGE_OK
                        BNE RANGE_FAIL
                        LDA LENGTH
                        BNE RANGE_FAIL
                        SEC
                        RTS
BUFFER_PRESENT:        LDA BLEN
                        ORA BLEN+1
                        BEQ RANGE_FAIL
                        SEC
                        RTS
EDITOR_RANGE:           JSR BUFFER_PRESENT
                        BCC RANGE_FAIL
                        LDA LAST
                        CMP FIRST
                        LDA LAST+1
                        SBC FIRST+1
                        BCC RANGE_FAIL
                        LDA LAST
                        CMP BLEN
                        LDA LAST+1
                        SBC BLEN+1
                        BCS RANGE_FAIL
                        SEC
                        RTS
BM_PATCH:               JSR BUFFER_PRESENT
                        BCC BM_BAD
                        LDA INDEX
                        STA SAVED_INDEX
                        JSR NUMBER
                        BCC BM_BAD
                        LDA NUM
                        STA OFFSET
                        LDA NUM+1
                        STA OFFSET+1
                        STZ DIGITS
PATCH_PREFLIGHT:        JSR NUMBER
                        BCC BM_BAD
                        LDA NUM+1
                        BNE BM_BAD
                        LDA OFFSET
                        CMP BLEN
                        LDA OFFSET+1
                        SBC BLEN+1
                        BCS BM_BAD
                        INC OFFSET
                        BNE PATCH_TEST_END
                        INC OFFSET+1
PATCH_TEST_END:         JSR SPACES
                        BNE PATCH_PREFLIGHT
; Reparse offset, then the already validated bytes. No partial edits on error.
                        LDA SAVED_INDEX
                        STA INDEX
                        JSR NUMBER
                        LDA NUM
                        STA DST
                        LDA NUM+1
                        CLC
                        ADC #$50
                        STA DST+1
PATCH_STORE:            JSR NUMBER
                        LDA NUM
                        STA (DST)
                        INC DST
                        BNE PATCH_MORE
                        INC DST+1
PATCH_MORE:             JSR SPACES
                        BNE PATCH_STORE
                        INC DIRTY
                        JMP BUFFER_EDITED
BM_FILL:                JSR RANGE
                        BCC BM_BAD
                        JSR EDITOR_RANGE
                        BCC BM_BAD
                        JSR NUMBER
                        BCC BM_BAD
                        LDA NUM+1
                        BNE BM_BAD
                        LDA NUM
                        STA VALUE
                        JSR ENDLINE
                        BCC BM_BAD
                        JSR SOURCE_FIELDS
                        JSR GET_LENGTH
                        LDA FIRST
                        STA DST
                        LDA FIRST+1
                        CLC
                        ADC #$50
                        STA DST+1
                        JMP FILL_BUFFER
BM_NEW:                 JSR NUMBER
                        BCC BM_BAD
                        LDA NUM
                        STA LENGTH
                        LDA NUM+1
                        STA LENGTH+1
                        JSR LENGTH_4K
                        BCC BM_BAD
                        JSR NUMBER
                        BCC BM_BAD
                        LDA NUM+1
                        BNE BM_BAD
                        LDA NUM
                        STA VALUE
                        JSR ENDLINE
                        BCC BM_BAD
                        LDA LENGTH
                        STA BLEN
                        LDA LENGTH+1
                        STA BLEN+1
                        STZ DST
                        LDA #$50
                        STA DST+1
FILL_BUFFER:            LDA LENGTH
                        STA CNT
                        LDA LENGTH+1
                        STA CNT+1
                        STZ REVERSE
FILL_LOOP:              LDA VALUE
                        STA (DST)
                        JSR ADVANCE
                        BNE FILL_LOOP
                        INC DIRTY
BUFFER_EDITED:          LDX #<EDITED_TEXT
                        LDY #>EDITED_TEXT
                        JMP MESSAGE
BM_DISPLAY:             JSR BUFFER_PRESENT
                        BCC BM_BAD
                        JSR SPACES
                        BNE DISPLAY_RANGE
                        STZ FIRST
                        STZ FIRST+1
                        SEC
                        LDA BLEN
                        SBC #$01
                        STA LAST
                        LDA BLEN+1
                        SBC #$00
                        STA LAST+1
                        BRA DISPLAY_READY
DISPLAY_RANGE:          JSR RANGE
                        BCC BM_BAD
                        JSR ENDLINE
                        BCC BM_BAD
                        JSR EDITOR_RANGE
                        BCC BM_BAD
DISPLAY_READY:          JSR SOURCE_FIELDS
                        JSR GET_LENGTH
                        LDA FIRST
                        STA OFFSET
                        STA SRC
                        LDA FIRST+1
                        STA OFFSET+1
                        CLC
                        ADC #$50
                        STA SRC+1
                        LDA LENGTH
                        STA CNT
                        LDA LENGTH+1
                        STA CNT+1
                        STZ REVERSE
DISPLAY_ROW:            JSR CHECK_CANCEL
                        JSR NL
                        LDA OFFSET+1
                        JSR HEX
                        LDA OFFSET
                        JSR HEX
                        LDA #':'
                        JSR PUTC
                        LDX #$10
DISPLAY_BYTE:           LDA #' '
                        JSR PUTC
                        LDA (SRC)
                        JSR HEX
                        INC OFFSET
                        BNE DISPLAY_NEXT
                        INC OFFSET+1
DISPLAY_NEXT:           JSR ADVANCE
                        BEQ BM_MENU
                        DEX
                        BNE DISPLAY_BYTE
                        BRA DISPLAY_ROW
BM_CRC:                 JSR ENDLINE
                        BCC BM_BAD
                        JSR BUFFER_PRESENT
                        BCC BM_BAD
                        STZ SRC
                        LDA #$50
                        STA SRC+1
                        LDA BLEN
                        STA CNT
                        LDA BLEN+1
                        STA CNT+1
                        STZ REVERSE
                        LDA #$FF
                        STA CRC
                        STA CRC+1
CRC_BYTE:               LDA (SRC)
                        EOR CRC+1
                        STA CRC+1
                        LDX #$08
CRC_BIT:                ASL CRC
                        ROL CRC+1
                        BCC CRC_NEXT
                        LDA CRC
                        EOR #$21
                        STA CRC
                        LDA CRC+1
                        EOR #$10
                        STA CRC+1
CRC_NEXT:               DEX
                        BNE CRC_BIT
                        JSR ADVANCE
                        BNE CRC_BYTE
                        LDX #<CRC_TEXT
                        LDY #>CRC_TEXT
                        JSR PRINT
                        LDA CRC+1
                        JSR HEX
                        LDA CRC
                        JSR HEX
                        JMP BM_MENU

BM_MAP:                 JSR ENDLINE
                        BCC BM_BAD
                        LDX #<MAP_HEADER
                        LDY #>MAP_HEADER
                        JSR PRINT
                        STZ MAPBANK
MAP_BANK:               JSR CHECK_CANCEL
                        JSR NL
                        LDA MAPBANK
                        JSR SPACE_NAME
                        LDA #':'
                        JSR PUTC
                        LDA #$80
                        STA MAPSEC
MAP_SECTOR:             LDA MAPBANK
                        JSR V2W_SELECT
                        STZ SRC
                        LDA MAPSEC
                        STA SRC+1
                        LDX #$10
                        LDY #$00
MAP_SCAN:               LDA (SRC),Y
                        CMP #$FF
                        BNE MAP_USED
                        INY
                        BNE MAP_SCAN
                        INC SRC+1
                        DEX
                        BNE MAP_SCAN
                        LDA #'E'
                        BRA MAP_CHAR
MAP_USED:               LDA #'U'
MAP_CHAR:               JSR PUTC
                        CLC
                        LDA MAPSEC
                        ADC #$10
                        STA MAPSEC
                        BNE MAP_SECTOR
                        LDX #<RESET_TEXT
                        LDY #>RESET_TEXT
                        JSR PRINT
                        LDA $FFFD
                        JSR HEX
                        LDA $FFFC
                        JSR HEX
                        INC MAPBANK
                        LDA MAPBANK
                        CMP #$04
                        BNE MAP_BANK
                        JMP BM_MENU
BM_QUIT:                JSR ENDLINE
                        BCC BM_BAD
                        LDA TOUCHED
                        BNE QUIT_REFUSE
                        LDA RESIDENT
                        JSR V2W_SELECT
                        JMP $F007
QUIT_REFUSE:            LDX #<QUIT_TEXT
                        LDY #>QUIT_TEXT
                        JMP MESSAGE
BM_BOOT:                JSR BANK
                        BCC BM_BAD
                        CMP #$FF
                        BEQ BM_BAD
                        STA MAPBANK
                        JSR ENDLINE
                        BCC BM_BAD
                        LDA MAPBANK
                        JSR V2W_SELECT
                        LDA $FFFC
                        STA DST
                        LDA $FFFD
                        STA DST+1
                        CMP #$80
                        BCC BM_BAD
                        CMP #$FF
                        BNE BOOT_GO
                        LDA DST
                        CMP #$FF
                        BEQ BM_BAD
BOOT_GO:                SEI
                        CLD
                        LDX #$FF
                        TXS
                        JMP (DST)

; Parser: uppercase hexadecimal, inclusive ranges, space R or bank 0-3.
SPACES:                 LDX INDEX
SPACE_LOOP:             LDA BM_LINE,X
                        CMP #' '
                        BNE SPACE_DONE
                        INX
                        BRA SPACE_LOOP
SPACE_DONE:             STX INDEX
                        CMP #$00
                        RTS
ENDLINE:                JSR SPACES
                        BNE PARSE_NO
                        SEC
                        RTS
BANK:                   JSR SPACES
                        CMP #'R'
                        BEQ BANK_RAM
                        SEC
                        SBC #'0'
                        CMP #$04
                        BCS PARSE_NO
                        BRA BANK_END
BANK_RAM:               LDA #$FF
BANK_END:               PHA
                        INC INDEX
                        LDX INDEX
                        LDA BM_LINE,X
                        BEQ BANK_OK
                        CMP #' '
                        BNE BANK_BAD
BANK_OK:                PLA
                        SEC
                        RTS
BANK_BAD:               PLA
PARSE_NO:               CLC
                        RTS
NUMBER:                 JSR SPACES
                        STZ NUM
                        STZ NUM+1
                        STZ DIGITS
NUMBER_LOOP:            LDX INDEX
                        LDA BM_LINE,X
                        JSR NIBBLE
                        BCC NUMBER_END
                        STA BYTE
                        INC DIGITS
                        LDA DIGITS
                        CMP #$05
                        BCS PARSE_NO
                        ASL NUM
                        ROL NUM+1
                        ASL NUM
                        ROL NUM+1
                        ASL NUM
                        ROL NUM+1
                        ASL NUM
                        ROL NUM+1
                        LDA NUM
                        ORA BYTE
                        STA NUM
                        INC INDEX
                        BRA NUMBER_LOOP
NUMBER_END:             LDA DIGITS
                        BEQ PARSE_NO
                        SEC
                        RTS
RANGE:                  JSR NUMBER
                        BCC PARSE_NO
                        LDA NUM
                        STA FIRST
                        STA LAST
                        LDA NUM+1
                        STA FIRST+1
                        STA LAST+1
                        LDX INDEX
                        LDA BM_LINE,X
                        CMP #'-'
                        BNE RANGE_ORDER
                        INC INDEX
                        JSR NUMBER
                        BCC PARSE_NO
                        LDA NUM
                        STA LAST
                        LDA NUM+1
                        STA LAST+1
RANGE_ORDER:            LDA LAST
                        CMP FIRST
                        LDA LAST+1
                        SBC FIRST+1
                        RTS
SCALE_RANGE:            LDA SB
                        CMP #$FF
                        BEQ SCALE_DONE
                        LDA FIRST+1
                        ORA LAST+1
                        BNE SCALE_DONE
                        LDA FIRST
                        CMP #$08
                        BCC SCALE_DONE
                        LDA LAST
                        CMP #$10
                        BCS SCALE_DONE
                        LDA FIRST
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA FIRST+1
                        STZ FIRST
                        LDA LAST
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        ORA #$0F
                        STA LAST+1
                        LDA #$FF
                        STA LAST
SCALE_DONE:             RTS

READLINE:               STZ LINELEN
                        STZ OVERFLOW
LINE_WAIT:              JSR GETC
                        CMP #$03
                        BEQ LINE_CANCEL
                        CMP #$0A
                        BEQ LINE_WAIT
                        CMP #$0D
                        BEQ LINE_DONE
                        CMP #$08
                        BEQ LINE_BACK
                        CMP #$7F
                        BEQ LINE_BACK
                        CMP #$20
                        BCC LINE_WAIT
                        CMP #'a'
                        BCC LINE_CHAR
                        CMP #'z'+1
                        BCS LINE_CHAR
                        AND #$DF
LINE_CHAR:              LDX LINELEN
                        CPX #$4F
                        BCS LINE_FULL
                        STA BM_LINE,X
                        INC LINELEN
                        JSR PUTC
                        BRA LINE_WAIT
LINE_FULL:              LDA #$01
                        STA OVERFLOW
                        BRA LINE_WAIT
LINE_BACK:              LDA LINELEN
                        BEQ LINE_WAIT
                        DEC LINELEN
                        LDA #$08
                        JSR PUTC
                        LDA #' '
                        JSR PUTC
                        LDA #$08
                        JSR PUTC
                        BRA LINE_WAIT
LINE_DONE:              LDX LINELEN
                        STZ BM_LINE,X
                        JSR NL
                        LDA OVERFLOW
                        BNE LINE_CANCEL
                        SEC
                        RTS
LINE_CANCEL:            CLC
                        RTS
PRINT:                  STX TXT
                        STY TXT+1
                        LDY #$00
PRINT_BYTE:             LDA (TXT),Y
                        BEQ PRINT_DONE
                        JSR PUTC
                        INY
                        BNE PRINT_BYTE
                        INC TXT+1
                        BRA PRINT_BYTE
PRINT_DONE:             RTS
SPACE_NAME:             CMP #$FF
                        BEQ SPACE_RAM
                        PHA
                        LDA #'B'
                        JSR PUTC
                        PLA
                        ORA #'0'
                        JMP PUTC
SPACE_RAM:              LDA #'R'
                        JMP PUTC

; Local RAM flash engine. It never executes ROM or uses the optional E code.
V2W_SELECT:             TAX
                        LDA V2_PCR
                        AND #$11
                        ORA BANK_BITS,X
                        STA V2_PCR
                        RTS
BANK_BITS:              DB $CC,$CE,$EC,$EE
V2W_PUTC                EQU PUTC
V2W_GETC                EQU GETC
                        INCLUDE "str8n-v2-flash-worker.inc"
TITLE:                  DB $0D,$0A,"STR8-N BANK MAINT 1.0",$0D,$0A,0
PROMPT:                 DB $0D,$0A,"BM> ",0
HELP:                   DB $0D,$0A,"BANKS AND MEMORY",$0D,$0A
                        DB "  M                           Map banks and sectors",$0D,$0A
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
                        DB "  S 8 / S 9                   Stage program for storage",$0D,$0A
                        DB "  W dst start                 Write buffer and verify",$0D,$0A
                        DB $0D,$0A,"CONTROL",$0D,$0A
                        DB "  J bank                      Boot selected bank",$0D,$0A
                        DB "  Q                           Return to monitor",$0D,$0A
                        DB "  ?                           Show this menu",$0D,$0A
                        DB $0D,$0A,"  src/dst: R = RAM, 0-3 = flash bank. Numbers are hex.",$0D,$0A
                        DB "  Flash 8-F = sectors. Editor offsets: 000-FFF.",$0D,$0A
                        DB "  Writes: Y to confirm. B3:F also requires B3F.",$0D,$0A,0
BAD:                    DB "INVALID / PROTECTED RANGE",$0D,$0A,0
CANCEL:                 DB "CANCELED (completed sectors retained)",$0D,$0A,0
FAILED:                 DB "WRITE/VERIFY FAILED; STOPPED",$0D,$0A,0
DONE:                   DB "VERIFIED",$0D,$0A,0
PLAN_TEXT:              DB "PLAN ",0
DEST_TEXT:              DB $0D,$0A,"DEST ",0
CONFIRM_TEXT:           DB $0D,$0A,"WRITE? TYPE Y> ",0
B3F_TEXT:               DB "B3:F includes boot code/config/vectors. TYPE B3F> ",0
MATCH_TEXT:             DB "MATCH",$0D,$0A,0
DIFFERENT_TEXT:         DB "DIFFERENT AT DEST ",0
BUFFER_TEXT:            DB "BUFFER LOADED; D/P/F/K then W to commit",$0D,$0A,0
EDITED_TEXT:            DB "BUFFER CHANGED; W to commit",$0D,$0A,0
CRC_TEXT:               DB "CRC16-CCITT-FALSE ",0
MAP_HEADER:             DB "SECTORS 8 9 A B C D E F (E=erased U=used)",$0D,$0A,0
RESET_TEXT:             DB " RESET ",0
QUIT_TEXT:              DB "RESIDENT F CHANGED; stay in RAM or J bank",$0D,$0A,0
BM_END:
                        ENDMOD
                        END
