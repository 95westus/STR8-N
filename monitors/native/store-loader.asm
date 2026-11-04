; Transient MON parser-area tail. The complete owner source0200-66FF stays
; untouched while loading the independently sealed PROGRAM provider.
; Enter only after a live YES and with the request at69D0; return via RTS.
        MODULE STORE_LOADER
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "store-provider-pin.inc"
        CODE
ST_START:
        STZ $E2
        LDA #$9F
        STA $E3
        STZ $E6
        LDA #$6B
        STA $E7
        LDA #2
        STA $F3
        LDA #64
        STA $EA
        LDA #52
        STA $69F0
ST_READ:
        JSR V2W_READ
        LDY #63
ST_COPY:
        LDA $7C80,Y
        STA ($E6),Y
        DEY
        BPL ST_COPY
        CLC
        LDA $E2
        ADC #64
        STA $E2
        BCC ST_SOURCE_READY
        INC $E3
ST_SOURCE_READY:
        CLC
        LDA $E6
        ADC #64
        STA $E6
        BCC ST_DEST_READY
        INC $E7
ST_DEST_READY:
        DEC $69F0
        BNE ST_READ
        LDA #3
        STA $F3
        STZ $E6
        LDA #$6B
        STA $E7
        LDA #$FF
        STA $69F4
        STA $69F5
        LDX #13
        LDY #0
ST_CRC_BYTE:
        LDA ($E6),Y
        EOR $69F5
        STA $69F5
        PHY
        LDY #8
ST_CRC_BIT:
        ASL $69F4
        ROL $69F5
        BCC ST_CRC_NEXT
        LDA $69F4
        EOR #$21
        STA $69F4
        LDA $69F5
        EOR #$10
        STA $69F5
ST_CRC_NEXT:
        DEY
        BNE ST_CRC_BIT
        PLY
        INY
        BNE ST_CRC_BYTE
        INC $E7
        DEX
        BNE ST_CRC_BYTE
        LDA $69F4
        ORA $69F5
        BNE ST_BAD
        LDA $77FE
        CMP #STORE_PROVIDER_CRC_HI
        BNE ST_BAD
        LDA $77FF
        CMP #STORE_PROVIDER_CRC_LO
        BNE ST_BAD
        LDA #$D0
        LDX #$69
        JSR $6B15
        BRA ST_RESULT
ST_BAD:
        LDA #$81
ST_RESULT:
        STA $69F6
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDA $69F6
        BNE ST_ERROR
        SEC
        RTS
ST_ERROR:
        CLC
        RTS
ST_END:
        ENDMOD
        END
