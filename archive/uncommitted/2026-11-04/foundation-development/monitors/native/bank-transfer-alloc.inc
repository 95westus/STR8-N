; AUTO picks whole erased sectors, never unused bytes inside an opaque image.
; B0:8-D; B1:E-F (8-D contain installed utilities). No write/erase here.
MX_PAGE EQU $6393
MX_START EQU $6394
MX_NEED EQU $6395
MX_HAVE EQU $6396
MX_END EQU $6397
MB_X_ALLOC:
        LDA MM_X_BANK
        CMP #2
        BCS MX_NO
        LDX #$80
        LDY #$E0
        CMP #0
        BEQ MX_RANGE
        LDX #$E0
        LDY #0
MX_RANGE:
        STX MX_PAGE
        STX MX_START
        STY MX_END
        STZ MX_HAVE
        LDA $7D2E
        LSR A
        LSR A
        LSR A
        LSR A
        STA MX_NEED
        LDA $7D2E
        AND #$0F
        ORA $7D2D
        BEQ MX_SIZE
        INC MX_NEED
MX_SIZE:
        LDA MX_NEED
        BEQ MX_NO
MX_SECTOR:
        STZ V2_ADDR
        LDA MX_PAGE
        STA V2_ADDR+1
MX_CHUNK:
        LDA #16
        STA V2_COUNT
        JSR MM_X_READ
        LDY #15
MX_BLANK:
        LDA V2_BYTES,Y
        CMP #$FF
        BNE MX_OCCUPIED
        DEY
        BPL MX_BLANK
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
        BCC MX_CHUNK
        INC V2_ADDR+1
        LDA V2_ADDR+1
        AND #$0F
        BNE MX_CHUNK
        INC MX_HAVE
        LDA MX_HAVE
        CMP MX_NEED
        BCS MX_OK
        BRA MX_NEXT
MX_OCCUPIED:
        STZ MX_HAVE
        CLC
        LDA MX_PAGE
        ADC #16
        STA MX_START
MX_NEXT:
        CLC
        LDA MX_PAGE
        ADC #16
        STA MX_PAGE
        CMP MX_END
        BNE MX_SECTOR
MX_NO:
        CLC
        RTS
MX_OK:
        LDX MX_START
        LDA #0
        SEC
        RTS
