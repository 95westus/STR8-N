CD_SRC EQU $E0
CD_DST EQU $E2
CD_MATCH EQU $E6
CD_BANK EQU $6708
CD_LIMIT EQU $6709
CD_ORIGIN EQU $670B
CD_EXPECTED EQU $670D
CD_SOURCE_END EQU $670F
CD_FLAGS EQU $6711
CD_BITS EQU $6712
CD_DISTANCE EQU $6713
CD_LENGTH EQU $6715
; Copy the decoder only when needed. XP later reuses its scratch region.
MB_COPY_DECODER:
        LDA #1
        JSR V2W_SELECT
        LDX #0
MB_COPY_DECODER_LOOP:
        LDA $8100,X
        STA $6800,X
        LDA $8200,X
        STA $6900,X
        INX
        BNE MB_COPY_DECODER_LOOP
        RTS
MB_LOAD_XP:
        JSR MB_COPY_DECODER
        LDA $8014
        STA CD_SRC
        LDA $8015
        STA CD_SRC+1
        LDA $8016
        STA CD_SOURCE_END
        LDA $8017
        STA CD_SOURCE_END+1
        STZ CD_DST
        STZ CD_ORIGIN
        STZ CD_LIMIT
        STZ CD_EXPECTED
        STZ CD_EXPECTED+1
        LDA #$6B
        STA CD_DST+1
        STA CD_ORIGIN+1
        LDA #$78
        STA CD_LIMIT+1
        LDA #1
        STA CD_BANK
        JSR $6800
MB_XP_ADMIT:
        LDX #7
MB_XP_ID:
        LDA $6B00,X
        CMP MB_XP_MAGIC,X
        BNE MB_XP_BAD
        DEX
        BPL MB_XP_ID
        SEC
        RTS
MB_XP_BAD:
        CLC
        RTS
MB_XP_MAGIC: DB "XP",1,13,"PR05"
