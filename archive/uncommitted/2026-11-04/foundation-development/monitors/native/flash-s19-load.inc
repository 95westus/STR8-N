; The dense control library is split across existing RP padding. Concatenate
; into4000, check its full CRC/identity, then enable I. No NVM writes here.
FI_LIB_OK EQU $63F7
FI_LEFT EQU $63FA
FI_LIB_LOAD:
        STZ FI_LIB_OK
        STZ V2_BUF_PTR
        LDA #$40
        STA V2_BUF_PTR+1
        LDA #1
        JSR V2W_SELECT
        LDX #0
FI_LIB_PART:
        LDA FI_FRAGMENTS,X
        STA V2_PTR
        INX
        LDA FI_FRAGMENTS,X
        STA V2_PTR+1
        INX
        LDA FI_FRAGMENTS,X
        STA FI_LEFT
        INX
        LDA FI_FRAGMENTS,X
        STA FI_LEFT+1
        INX
FI_LIB_BYTE:
        LDA (V2_PTR)
        STA (V2_BUF_PTR)
        INC V2_PTR
        BNE FI_LIB_DEST
        INC V2_PTR+1
FI_LIB_DEST:
        INC V2_BUF_PTR
        BNE FI_LIB_LEFT
        INC V2_BUF_PTR+1
FI_LIB_LEFT:
        LDA FI_LEFT
        BNE FI_LIB_LOW
        DEC FI_LEFT+1
FI_LIB_LOW:
        DEC FI_LEFT
        LDA FI_LEFT
        ORA FI_LEFT+1
        BNE FI_LIB_BYTE
        CPX #12
        BCC FI_LIB_PART
        LDA #3
        JSR V2W_SELECT
        LDA V2_BUF_PTR
        STA FI_LEFT
        SEC
        LDA V2_BUF_PTR+1
        SBC #$40
        STA FI_LEFT+1
        STZ V2_PTR
        LDA #$40
        STA V2_PTR+1
        JSR J_CRC_INIT
FI_LIB_CRC:
        LDA (V2_PTR)
        JSR J_CRC_BYTE
        INC V2_PTR
        BNE FI_LIB_CRC_LEFT
        INC V2_PTR+1
FI_LIB_CRC_LEFT:
        LDA FI_LEFT
        BNE FI_LIB_CRC_LOW
        DEC FI_LEFT+1
FI_LIB_CRC_LOW:
        DEC FI_LEFT
        LDA FI_LEFT
        ORA FI_LEFT+1
        BNE FI_LIB_CRC
        LDA J_CRC
        ORA J_CRC+1
        BNE FI_LIB_BAD
        LDX #7
FI_LIB_ID:
        LDA $4000,X
        CMP FI_LIB_MAGIC,X
        BNE FI_LIB_BAD
        DEX
        BPL FI_LIB_ID
        INC FI_LIB_OK
        SEC
        RTS
FI_LIB_BAD:
        CLC
        RTS
FI_LIB_MAGIC: DB "FI",1,0,"PR05"
FI_FRAGMENTS: DB 0,0,0,0,0,0,0,0,0,0,0,0
