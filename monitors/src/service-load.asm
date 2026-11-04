; Three-sector tool loader, linked6900. Caller preserves6A at6700 before copy.
; Fixed sources05 (raw RAM) or83 (B2). Destinations4800-63FF and6B00-77FF.
        MODULE SERVICE_LOAD
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "workbench-interface.inc"
        INCLUDE "service-interface.inc"
        INCLUDE "service-foundation.inc"
SL_PTR EQU $E0
SL_COPY EQU $E6
SL_SOURCE EQU $68F0
SL_MODE EQU $68F1
SL_CRC EQU $68F2
SL_RESULT EQU $68F4
        CODE
SL_START:
        STA SL_SOURCE
        JMP SL_WORK
; This entire finish routine must remain below6A00, which it restores.
SL_FINISH:
        LDA #3
        JSR SB_F_SELECT
        LDX #0
SL_RESTORE:
        LDA $6700,X
        STA $6A00,X
        INX
        BNE SL_RESTORE
        LDA SL_RESULT
        BNE SL_FAILED
        JSR WB_INIT
        LDA SL_MODE
        BNE SL_BOOT
        SEC
        RTS
SL_BOOT:
        JMP WB_SHELL
SL_FAILED:
        LDA SL_MODE
        BNE SL_RECOVERY
        CLC
        RTS
SL_RECOVERY:
        JMP SB_F_RECOVERY
SL_WORK:
        SEI
        CLD
        LDA #$F0
        LDX #16
        JSR SL_CRC_PAGES
        LDA SL_CRC
        CMP #SB_F_CRC_LO
        BNE SL_LOCK
        LDA SL_CRC+1
        CMP #SB_F_CRC_HI
        BNE SL_LOCK
        LDA SL_SOURCE
        CMP #5
        BEQ SL_COPY_START
        CMP #$83
        BNE SL_FAIL
        LDA #2
        JSR SB_F_SELECT
        LDX #7
SL_BUNDLE_CHECK:
        LDA $8003,X
        CMP SL_BUNDLE,X
        BNE SL_FAIL
        DEX
        BPL SL_BUNDLE_CHECK
SL_COPY_START:
        STZ SL_PTR
        STZ SL_COPY
        LDA SL_SOURCE
        STA SL_PTR+1
        LDA #$48
        STA SL_COPY+1
        LDX #28
        JSR SL_COPY_PAGES
        LDA #$6B
        STA SL_COPY+1
        LDX #13
        JSR SL_COPY_PAGES
        LDA #3
        JSR SB_F_SELECT
        LDX #7
SL_HEADERS:
        LDA $4800,X
        CMP SL_MODULE,X
        BNE SL_FAIL
        LDA $6B00,X
        CMP SL_PROGRAM,X
        BNE SL_FAIL
        DEX
        BPL SL_HEADERS
        LDA #$48
        LDX #28
        JSR SL_CRC_PAGES
        LDA SL_CRC
        ORA SL_CRC+1
        BNE SL_FAIL
        LDA #$6B
        LDX #13
        JSR SL_CRC_PAGES
        LDA SL_CRC
        ORA SL_CRC+1
        BNE SL_FAIL
        STZ SL_RESULT
        JMP SL_FINISH
SL_FAIL:
        LDA #1
        STA SL_RESULT
        JMP SL_FINISH
SL_LOCK:
        BRA SL_LOCK
SL_COPY_PAGES:
        LDY #0
SL_COPY_BYTE:
        LDA (SL_PTR),Y
        STA (SL_COPY),Y
        INY
        BNE SL_COPY_BYTE
        INC SL_PTR+1
        INC SL_COPY+1
        DEX
        BNE SL_COPY_BYTE
        RTS
SL_CRC_PAGES:
        STZ SL_PTR
        STA SL_PTR+1
        LDA #$FF
        STA SL_CRC
        STA SL_CRC+1
        LDY #0
SL_CRC_BYTE:
        LDA (SL_PTR),Y
        EOR SL_CRC+1
        STA SL_CRC+1
        PHY
        LDY #8
SL_CRC_BIT:
        ASL SL_CRC
        ROL SL_CRC+1
        BCC SL_CRC_NEXT
        LDA SL_CRC
        EOR #$21
        STA SL_CRC
        LDA SL_CRC+1
        EOR #$10
        STA SL_CRC+1
SL_CRC_NEXT:
        DEY
        BNE SL_CRC_BIT
        PLY
        INY
        BNE SL_CRC_BYTE
        INC SL_PTR+1
        DEX
        BNE SL_CRC_BYTE
        RTS
SL_BUNDLE: DB "WF",3,28,"PR05"
SL_MODULE: DB "MW",2,28,"PR05"
SL_PROGRAM: DB "SP",1,13,"PR05"
SL_END:
        ENDMOD
        END
