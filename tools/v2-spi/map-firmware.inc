; Called while bank 2 is visible. Identify sealed assets, never by address alone.
MAP_FIRMWARE:
        LDA MAPBANK
        CMP #2
        BNE MF_NO
        LDA MAPSEC
        CMP #$D0
        BEQ MF_STATUS
        CMP #$E0
        BNE MF_NO
        ; Both independent assets must validate before labelling sector E.
        LDA #$E0
        LDY #$E7
        LDX #4
        JSR MF_CHECK
        BCC MF_NO
        LDA #$E8
        LDY #$F0
        LDX #0
        JSR MF_CHECK
        BCC MF_NO
        BRA MF_YES
MF_STATUS:
        LDA #$C8
        LDY #$D2
        LDX #0
        JSR MF_CHECK
        BCC MF_NO
MF_YES:
        LDA #'F'
        STA MAP_KIND
        SEC
        RTS
MF_NO:
        CLC
        RTS
; A=start page, Y=exclusive end page, X=header index. All code executes in RAM.
MF_CHECK:
        STA SRC+1
        STZ SRC
        STY MF_END
        LDY #0
MF_HEADER:
        LDA (SRC),Y
        CMP MF_MAGIC,X
        BNE MF_NO
        INX
        INY
        CPY #4
        BNE MF_HEADER
        LDA #$FF
        STA CRC
        STA CRC+1
        LDY #0
MF_BYTE:
        LDA (SRC),Y
        EOR CRC+1
        STA CRC+1
        LDX #8
MF_BIT:
        ASL CRC
        ROL CRC+1
        BCC MF_NEXT
        LDA CRC
        EOR #$21
        STA CRC
        LDA CRC+1
        EOR #$10
        STA CRC+1
MF_NEXT:
        DEX
        BNE MF_BIT
        INY
        BNE MF_BYTE
        INC SRC+1
        LDA SRC+1
        CMP MF_END
        BNE MF_BYTE
        LDA CRC
        ORA CRC+1
        BNE MF_NO
        SEC
        RTS
MF_DESCRIPTION:
        LDX #<MF_STATUS_TEXT
        LDY #>MF_STATUS_TEXT
        LDA MAPSEC
        CMP #$D0
        BEQ MF_PRINT
        LDX #<MF_LOCAL_TEXT
        LDY #>MF_LOCAL_TEXT
MF_PRINT:
        JMP PRINT
MF_STATUS_TEXT DB "Firmware status formatter C800-D1FF",0
MF_LOCAL_TEXT DB "Local/board E000-E6FF; VERSION E800-EFFF",0
MF_RESERVED_TEXT DB " reserved",0
MF_MAGIC DB "BS",1,3,"LT",1,1
MF_END DB 0
