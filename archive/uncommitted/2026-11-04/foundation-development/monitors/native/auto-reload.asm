; AUTO has a live WB AREA. Reload only SP, without WB_INIT clearing that AREA.
; All execution after replacing the RAM gate stays below6B00, returning to E.
        MODULE AUTO_RELOAD
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "store-provider-pin.inc"
        CODE
TA_START:
        LDA #2
        JSR V2W_SELECT
        STZ $E0
        LDA #$9F
        STA $E1
        STZ $E2
        LDA #$6B
        STA $E3
        LDX #13
        LDY #0
TA_COPY:
        LDA ($E0),Y
        STA ($E2),Y
        INY
        BNE TA_COPY
        INC $E1
        INC $E3
        DEX
        BNE TA_COPY
        LDA #3
        JSR V2W_SELECT
        LDA #$48
        LDX #28
        JSR TA_CRC
        BNE TA_BAD
        LDA #$6B
        LDX #13
        JSR TA_CRC
        BNE TA_BAD
        LDA $77FE
        CMP #STORE_PROVIDER_CRC_HI
        BNE TA_BAD
        LDA $77FF
        CMP #STORE_PROVIDER_CRC_LO
        BNE TA_BAD
        LDA $6A00
        LDX #$40
        LDY #$68
        JSR $4808
        STA $6A00
        RTS
TA_BAD:
        LDX #<TA_BAD_TEXT
        LDY #>TA_BAD_TEXT
        JMP BOOT_PRINT
TA_CRC:
        STX $69F7
        STZ $E0
        STA $E1
        JSR J_CRC_INIT
        LDY #0
TA_CRC_BYTE:
        LDA ($E0),Y
        JSR J_CRC_BYTE
        INY
        BNE TA_CRC_BYTE
        INC $E1
        DEC $69F7
        BNE TA_CRC_BYTE
        LDA J_CRC
        ORA J_CRC+1
        RTS
TA_BAD_TEXT: DB "REFUSED: cached WB/SP CRC",13,10,0
TA_END:
        ENDMOD
        END
