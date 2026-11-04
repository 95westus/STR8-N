; Decode only an admitted SS/01 or SS/02 primary. No directory/WORKSPACE writes.
SC_SRAM:
        JSR SD_SRAM
        BCC SC_SRAM_BAD
        JSR SC_CRC_INIT
        LDY #0
SC_PRIMARY_CRC:
        LDA ST_RECORD,Y
        JSR SC_CRC_BYTE
        INY
        CPY #62
        BCC SC_PRIMARY_CRC
        LDA SI_CRC
        ORA SI_CRC+1
        ORA ST_RECORD+62
        BNE SC_SRAM_BAD
        LDA ST_RECORD+63
        CMP #$A5
        BNE SC_SRAM_BAD
        LDA ST_RECORD
        CMP #'S'
        BNE SC_SRAM_BAD
        CMP ST_RECORD+1
        BNE SC_SRAM_BAD
        LDA ST_RECORD+3
        CMP #8
        BNE SC_SRAM_BAD
        CMP ST_RECORD+4
        BNE SC_SRAM_BAD
        LDA ST_RECORD+7
        BNE SC_SRAM_BAD
        LDX #59
SC_RESERVED:
        LDA ST_RECORD,X
        BNE SC_SRAM_BAD
        DEX
        CPX #11
        BNE SC_RESERVED
        LDA ST_RECORD+2
        CMP #1
        BNE SC_SS2
        LDA ST_RECORD+5
        ORA ST_RECORD+8
        ORA ST_RECORD+9
        ORA ST_RECORD+10
        ORA ST_RECORD+11
        BNE SC_SRAM_BAD
        LDA ST_RECORD+6
        CMP #1
        BEQ SC_SRAM_OK
SC_SRAM_BAD:
        CLC
        RTS
SC_SS2:
        CMP #2
        BNE SC_SRAM_BAD
        LDA ST_RECORD+8
        ORA ST_RECORD+9
        ORA ST_RECORD+10
        ORA ST_RECORD+11
        BEQ SC_SRAM_BAD
        LDA ST_RECORD+5
        AND #$3F
        BNE SC_SRAM_BAD
        LDA ST_RECORD+6
        BEQ SC_SMALL
        CMP #1
        BNE SC_SRAM_BAD
        LDA ST_RECORD+5
        BNE SC_SRAM_BAD
        BRA SC_SRAM_OK
SC_SMALL:
        LDA ST_RECORD+5
        BEQ SC_SRAM_BAD
SC_SRAM_OK:
        SEC
        RTS
