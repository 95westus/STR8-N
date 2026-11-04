; RAM tail for native-to-native replacement. Caller restores original MON/ZP.
; Always admit all four loader pages before entering it. Kind at6778.
        MODULE NATIVE_HANDOFF
        INCLUDE "handoff-bindings.inc"
        CODE
HC_START:
        SEI
        CLD
        LDA #3
        JSR $7848
        LDX #0
HC_COPY:
        LDA $8C00,X
        STA $7000,X
        LDA $8D00,X
        STA $7100,X
        LDA $8E00,X
        STA $7200,X
        LDA $8F00,X
        STA $7300,X
        INX
        BNE HC_COPY
        STZ $E0
        LDA #$70
        STA $E1
        LDA #4
        STA $6779
        JSR HC_CRC_INIT
        LDY #0
HC_CRC:
        LDA ($E0),Y
        JSR HC_CRC_BYTE
        INY
        BNE HC_CRC
        INC $E1
        DEC $6779
        BNE HC_CRC
        LDA HC_CRC_VALUE
        ORA HC_CRC_VALUE+1
        BNE HC_BAD
        LDA $6778
        JMP $7008
HC_BAD:
        JMP $F004
HC_END:
        ENDMOD
        END
