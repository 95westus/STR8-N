; Read-only view, borrowed staging RAM. 0 boot, 1 R EDU, 2 TIME.
        MODULE BOOT_STATUS
        XDEF START
        XDEF APP_END
        INCLUDE "status-links.inc"
PTR EQU $D0
R EQU $6650
BUF EQU $6400
J_CRC EQU $7D38
        CODE
START:  DB "BS",1,1
        JMP DISPLAY
DISPLAY:
        STA KIND
        CMP #2
        BEQ TIME_ONLY
        LDX #<RAM_TEXT
        LDY #>RAM_TEXT
        JSR PRINT
        LDA $7D0B
        JSR $7E7C
        LDA $7D0A
        JSR $7E7C
        JSR $7E7F
        JSR $7E7F
        LDX #<EDU_TEXT
        LDY #>EDU_TEXT
        JSR PRINT
        LDA $7D27
        CMP #2
        JSR MODE_TEXT
        LDA KIND
        BEQ NO_PENDING
        LDA #1
        LDY $7D28
        CPY #$A5
        BNE PENDING_MODE
        INC A
PENDING_MODE:
        CMP $7D27
        BEQ NO_PENDING
        PHA
        LDX #<PENDING_TEXT
        LDY #>PENDING_TEXT
        JSR PRINT
        PLA
        CMP #2
        JSR MODE_TEXT
NO_PENDING:
        LDA $7D27
        CMP #2
        BEQ RETURN
        JSR CLOCK
        LDA $7D2A
        BEQ EUI_ABSENT
        LDA $6BEE
        PHA
        JSR SHOW_EUI
        PLA
        STA $6BEE
        BRA EUI_DONE
EUI_ABSENT:
        LDX #<EUI_UNAVAILABLE
        LDY #>EUI_UNAVAILABLE
        JSR PRINT
EUI_DONE:
        JSR $7E7F
        JSR $7E7F
        JSR ALLOCATION
RETURN: SEC
        RTS
TIME_ONLY:
        JSR CLOCK
        SEC
        RTS
CLOCK:  LDA $7D2A
        BEQ CLOCK_ABSENT
        LDA $7D25
        PHA
        LDA KIND
        BEQ CLOCK_BOOT
        LDA #1
        STA $7D25
CLOCK_BOOT:
        JSR $8907
        PLA
        STA $7D25
        RTS
CLOCK_ABSENT:
        LDX #<CLOCK_UNAVAILABLE
        LDY #>CLOCK_UNAVAILABLE
        JMP PRINT
MODE_TEXT:
        BNE MODE_ON
        LDX #<OFF_TEXT
        LDY #>OFF_TEXT
        JMP PRINT
MODE_ON:
        LDX #<ON_TEXT
        LDY #>ON_TEXT
        JMP PRINT
ALLOCATION:
        LDA $7D07
        AND #8
        BEQ UNAVAILABLE
        LDX #3
SM_HEADER:
        LDA $66A2,X
        CMP SM_MAGIC,X
        BNE UNAVAILABLE
        DEX
        BPL SM_HEADER
        LDX #63
BACKUP: LDA BUF,X
        STA SAVED_WINDOW,X
        DEX
        BPL BACKUP
        STZ FALLBACK
        STZ PAGE_LO
        STZ PAGE_HI
        JSR READ_LAYOUT
        BNE READ_FAILED
        LDA BUF+63
        CMP #$A5
        BEQ VALIDATE
        INC FALLBACK
        LDA #$40
        STA PAGE_LO
        LDA #2
        STA PAGE_HI
        JSR READ_LAYOUT
        BNE READ_FAILED
        LDA BUF+63
        CMP #$A5
        BNE UNINITIALIZED
VALIDATE:
        JSR AP_CRC_INIT
        LDY #0
CRC:    LDA BUF,Y
        JSR AP_CRC_BYTE
        INY
        CPY #62
        BNE CRC
        LDA J_CRC
        ORA J_CRC+1
        BNE INVALID
        LDA BUF+7
        ORA BUF+62
        BNE INVALID
        LDX #59
RESERVED:
        LDA BUF,X
        BNE INVALID
        DEX
        CPX #11
        BNE RESERVED
        LDX #3
HEADER: LDA BUF,X
        CMP LAYOUT_MAGIC,X
        BEQ HEADER_NEXT
        CPX #2
        BNE INVALID
        CMP #1
        BNE INVALID
HEADER_NEXT:
        DEX
        BPL HEADER
        LDA BUF+4
        CMP #8
        BNE INVALID
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        LDY BUF+2
        CPY #1
        BNE MODERN
        CMP #0
        BNE INVALID
        LDA FALLBACK
        ORA BUF+5
        BNE INVALID
        LDA BUF+6
        CMP #1
        BNE INVALID
        BRA BOUNDARY
MODERN: CMP #0
        BEQ INVALID
BOUNDARY:
        LDA BUF+5
        AND #$3F
        BNE INVALID
        LDA BUF+6
        BEQ SMALL
        CMP #1
        BNE INVALID
        LDA BUF+5
        BNE INVALID
        LDA #4
        BRA UNITS
SMALL:  LDA BUF+5
        BEQ INVALID
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
UNITS:  DEC A
        STA UNIT
        LDA FALLBACK
        BNE REPAIR
        LDX #<PROGRAM_TEXT
        LDY #>PROGRAM_TEXT
        JSR PRINT
        LDX UNIT
        LDA PAYLOAD_LO,X
        LDY PAYLOAD_HI,X
        TAX
        JSR PRINT
        LDX #<BYTES_TEXT
        LDY #>BYTES_TEXT
        JSR PRINT
        LDX #<WORK_TEXT
        LDY #>WORK_TEXT
        JSR PRINT
        LDX UNIT
        LDA WORK_LO,X
        LDY WORK_HI,X
        TAX
        JSR PRINT
        LDX #<BYTES_TEXT
        LDY #>BYTES_TEXT
        BRA FINISH
READ_FAILED:
        LDX #<UNAVAILABLE_TEXT
        LDY #>UNAVAILABLE_TEXT
        BRA FINISH
UNINITIALIZED:
        LDX #<UNINITIALIZED_TEXT
        LDY #>UNINITIALIZED_TEXT
        BRA FINISH
REPAIR: LDX #<REPAIR_TEXT
        LDY #>REPAIR_TEXT
        BRA FINISH
INVALID:
        LDX #<INVALID_TEXT
        LDY #>INVALID_TEXT
FINISH: JSR PRINT
        LDX #63
RESTORE:
        LDA SAVED_WINDOW,X
        STA BUF,X
        DEX
        BPL RESTORE
        RTS
UNAVAILABLE:
        LDX #<UNAVAILABLE_TEXT
        LDY #>UNAVAILABLE_TEXT
        JMP PRINT
READ_LAYOUT:
        LDX #15
CLEAR:  STZ R,X
        DEX
        BPL CLEAR
        INC R
        LDA PAGE_LO
        STA R+2
        LDA PAGE_HI
        STA R+3
        LDA #$64
        STA R+6
        LDA #64
        STA R+7
        JSR $66A6
        CMP #0
        BNE READ_RETURN
        LDA R+9
        CMP #64
        BEQ READ_OK
        LDA #7
        RTS
READ_OK:
        LDA #0
READ_RETURN:
        RTS
PRINT:  JMP STATUS_PRINT
SM_MAGIC DB "SM",1,1
LAYOUT_MAGIC DB "SS",2,8
RAM_TEXT DB 13,10,13,10,"RAM $0200-$",0
EDU_TEXT DB "EDU ",0
PENDING_TEXT DB "EDU after RESET: ",0
OFF_TEXT DB "OFF",13,10,0
ON_TEXT DB "ON",13,10,0
CLOCK_UNAVAILABLE DB 13,10,"RTCC: unavailable",0
EUI_UNAVAILABLE DB 13,10,"RTCC: EUI unavailable",0
PROGRAM_TEXT DB "SSRAM: PROGRAM payload ",0
WORK_TEXT DB "SSRAM: WORKSPACE ",0
BYTES_TEXT DB " bytes",13,10,0
UNAVAILABLE_TEXT DB "SSRAM: Unavailable",13,10,0
UNINITIALIZED_TEXT DB "SSRAM: Allocation uninitialized",13,10,0
REPAIR_TEXT DB "SSRAM: Layout needs repair",13,10,0
INVALID_TEXT DB "SSRAM: Layout invalid",13,10,0
P16 DB "14336",0
P32 DB "30720",0
P48 DB "47104",0
P64 DB "63488",0
W16 DB "114656",0
W32 DB "98272",0
W48 DB "81888",0
W64 DB "65504",0
PAYLOAD_LO DB <P16,<P32,<P48,<P64
PAYLOAD_HI DB >P16,>P32,>P48,>P64
WORK_LO DB <W16,<W32,<W48,<W64
WORK_HI DB >W16,>W32,>W48,>W64
KIND DB 0
UNIT DB 0
FALLBACK DB 0
PAGE_LO DB 0
PAGE_HI DB 0
SAVED_WINDOW DS 64
APP_END:
        ENDMOD
