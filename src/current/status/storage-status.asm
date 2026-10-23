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
START:  DB "BS",1,3
        JMP DISPLAY
        JMP WEEKDAY
DISPLAY:
        STA KIND
        CMP #3
        BCC STORAGE_DISPLAY
        JMP STORAGE
STORAGE_DISPLAY:
        CMP #2
        BNE STATUS_DISPLAY
        JMP TIME_ONLY
STATUS_DISPLAY:
        TAX
        BNE STATUS_RAM
        LDA #3
        STA KIND
        JSR LOCAL_DISPLAY
        STZ KIND
STATUS_RAM:
        LDX #<RAM_TEXT
        LDY #>RAM_TEXT
        JSR PRINT
        LDA $7D0B
        JSR $7E7C
        LDA $7D0A
        JSR $7E7C
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
        JSR ALLOCATION
        JSR CLOCK
        LDA KIND
        BEQ RETURN
        LDA $7D2A
        BEQ EUI_ABSENT
        LDA $6BEE
        PHA
        JSR SHOW_EUI
        PLA
        STA $6BEE
        BRA RETURN
EUI_ABSENT:
        LDX #<EUI_UNAVAILABLE
        LDY #>EUI_UNAVAILABLE
        JSR PRINT
RETURN:
        LDA #6
        JMP $EF09
TIME_ONLY:
        LDA $7D2A
        BEQ TIME_UNAVAILABLE
        JSR $6504
        BCC TIME_UNAVAILABLE
        JSR LOCAL_DISPLAY
        SEC
        RTS
TIME_UNAVAILABLE:
        LDA KIND
        LSR A
        BEQ B29_NOT_TIME_ERROR
        INC $7EE7
B29_NOT_TIME_ERROR:
        LDX #<CLOCK_UNAVAILABLE
        LDY #>CLOCK_UNAVAILABLE
        JSR PRINT
        SEC
        RTS
CLOCK:  LDA $7D2A
        BEQ TIME_UNAVAILABLE
        LDA $7D25
        PHA
        LDA KIND
        BEQ CLOCK_BOOT
        LDA #1
        STA $7D25
CLOCK_BOOT:
        JSR $6504
        BCC CLOCK_NO_EVENT
        LDA $66C1
        AND #8
        BRA CLOCK_EVENT_READY
CLOCK_NO_EVENT:
        LDA #0
CLOCK_EVENT_READY:
        PHA
        BEQ CLOCK_CALL
        JSR $7E7F
CLOCK_CALL:
        JSR $8907
        PLA
        BEQ CLOCK_FORMAT
        JSR $7E7F
CLOCK_FORMAT:
        JSR LOCAL_DISPLAY
        PLA
        STA $7D25
        RTS
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
        JSR SRAM_PREFIX
        LDA $7D07
        AND #8
                        BNE BM_LONG_116
                        JMP UNAVAILABLE
BM_LONG_116:
        LDX #3
SM_HEADER:
        LDA $66A2,X
        CMP SM_MAGIC,X
                        BEQ BM_LONG_121
                        JMP UNAVAILABLE
BM_LONG_121:
        DEX
                        BPL SM_HEADER
        LDA KIND
                        BNE SPI_STARTUP_DONE
        JSR SPI_STARTUP_GUARD
                        BCS BM_LONG_127
                        JMP UNAVAILABLE
BM_LONG_127:
SPI_STARTUP_DONE:
        LDX #63
BACKUP: LDA BUF,X
        STA SAVED_WINDOW,X
        DEX
                        BPL BACKUP
        STZ FALLBACK
        STZ PAGE_LO
        STZ PAGE_HI
        JSR READ_LAYOUT
                        BEQ BM_LONG_138
                        JMP READ_FAILED
BM_LONG_138:
        LDA BUF+63
        CMP #$A5
                        BEQ VALIDATE
        INC FALLBACK
        LDA #$40
        STA PAGE_LO
        LDA #2
        STA PAGE_HI
        JSR READ_LAYOUT
                        BEQ BM_LONG_148
                        JMP READ_FAILED
BM_LONG_148:
        LDA BUF+63
        CMP #$A5
                        BEQ BM_LONG_151
                        JMP UNINITIALIZED
BM_LONG_151:
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
                        BEQ BM_LONG_162
                        JMP INVALID
BM_LONG_162:
        LDA BUF+7
        ORA BUF+62
                        BEQ BM_LONG_165
                        JMP INVALID
BM_LONG_165:
        LDX #59
RESERVED:
        LDA BUF,X
                        BEQ BM_LONG_169
                        JMP INVALID
BM_LONG_169:
        DEX
        CPX #11
                        BNE RESERVED
        LDX #3
HEADER: LDA BUF,X
        CMP LAYOUT_MAGIC,X
                        BEQ HEADER_NEXT
        CPX #2
                        BEQ BM_LONG_178
                        JMP INVALID
BM_LONG_178:
        CMP #1
                        BEQ BM_LONG_180
                        JMP INVALID
BM_LONG_180:
HEADER_NEXT:
        DEX
                        BPL HEADER
        LDA BUF+4
        CMP #8
                        BEQ BM_LONG_186
                        JMP INVALID
BM_LONG_186:
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        LDY BUF+2
        CPY #1
                        BNE MODERN
        CMP #0
                        BEQ BM_LONG_195
                        JMP INVALID
BM_LONG_195:
        LDA FALLBACK
        ORA BUF+5
                        BEQ BM_LONG_198
                        JMP INVALID
BM_LONG_198:
        LDA BUF+6
        CMP #1
                        BEQ BM_LONG_201
                        JMP INVALID
BM_LONG_201:
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
        JSR SRAM_PREFIX
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
                        JMP FINISH
READ_FAILED:
        LDX #<UNAVAILABLE_TEXT
        LDY #>UNAVAILABLE_TEXT
                        JMP FINISH
UNINITIALIZED:
        LDX #<UNINITIALIZED_TEXT
        LDY #>UNINITIALIZED_TEXT
                        JMP FINISH
REPAIR: LDX #<REPAIR_TEXT
        LDY #>REPAIR_TEXT
                        JMP FINISH
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
RAM_TEXT DB 13,10,"RAM $0200-$",0
EDU_TEXT DB "EDU ",0
PENDING_TEXT DB "RESET required: ",0
OFF_TEXT DB "OFF",13,10,0
ON_TEXT DB "ON",13,10,0
CLOCK_UNAVAILABLE DB 13,10,"RTCC: unavailable",0
EUI_UNAVAILABLE DB 13,10,"EUI unknown",0
PROGRAM_TEXT DB "PROGRAM payload ",0
WORK_TEXT DB "WORKSPACE ",0
BYTES_TEXT DB " bytes",13,10,0
UNAVAILABLE_TEXT DB "Unavailable",13,10,0
UNINITIALIZED_TEXT DB "Uninitialized",13,10,0
REPAIR_TEXT DB "Layout needs repair",13,10,0
INVALID_TEXT DB "Layout invalid",13,10,0
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
        INCLUDE "local-loader.inc"
WEEKDAY:
        LDA $66C6
        DEC A
        ASL A
        ASL A
        TAY
        LDX #4
WEEKDAY_CHAR:
        LDA WEEKDAYS,Y
        JSR $7E6D
        INY
        DEX
                        BNE WEEKDAY_CHAR
        RTS
WEEKDAYS DB "Mon Tue Wed Thu Fri Sat Sun "
SPI_STARTUP_GUARD:
        PHP
        SEI
        LDA $6660
        ORA $6669
                        BNE SPI_STARTUP_REFUSE
        LDA $7FCE
        AND #$18
                        BNE SPI_STARTUP_REFUSE
        LDA $7FCD
        AND #$18
                        BEQ SPI_STARTUP_SAFE
        LDA $7FCC
        AND #$F0
                        BNE SPI_STARTUP_REFUSE
        LDA $7FCB
        AND #$1E
                        BNE SPI_STARTUP_REFUSE
        LDA $7FC2
        AND #$0F
                        BNE SPI_STARTUP_REFUSE
        LDA $7FC0
        LDA $7FCD
        AND #$18
                        BNE SPI_STARTUP_REFUSE
SPI_STARTUP_SAFE:   PLP
        LDA #0
        SEC
        RTS
SPI_STARTUP_REFUSE:
        PLP
        LDA #1
        CLC
        RTS
        INCLUDE "storage-services.inc"
SRAM_PREFIX:
        LDX #<SRAM_TEXT
        LDY #>SRAM_TEXT
        JMP PRINT
SRAM_TEXT DB "SSRAM: ",0
APP_END:
        ENDMOD
