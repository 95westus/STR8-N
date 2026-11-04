; Validate all immutable STATUS extents before executing through a RAM gate.
; Gate occupies the24 unused bytes after frozen V2W_END, not owner RAM.
M_STATUS:
        SEC
        BRA MS_VIEW
M_STARTUP_STATUS:
        CLC
MS_VIEW:
        PHP
        LDX #<M_TITLE
        LDY #>M_TITLE
        JSR M_PUTS
        PLP
        PHP
        BCC MS_VIEW_READY
        LDX #<M_VERSION_DETAIL
        LDY #>M_VERSION_DETAIL
        JSR M_PUTS
        LDX #<M_ABI_TEXT
        LDY #>M_ABI_TEXT
        JSR M_PUTS
MS_VIEW_READY:
        LDA MU_EDU
        BEQ MS_RTC_OFF
        JSR MR_SAMPLE
        STA MR_ERROR
        BRA MS_RTC_READY
MS_RTC_OFF:
        STZ MR_VALID
MS_RTC_READY:
        STZ ST_FLAGS
        JSR M_READ_WEAR
        BCC MS_NO_SNAPSHOT
        LDA #$80
        STA ST_FLAGS
MS_NO_SNAPSHOT:
        JSR MS_ADMIT
        BCC MS_UNAVAILABLE
        LDX #MS_GATE_END-MS_GATE-1
MS_GATE_COPY:
        LDA MS_GATE,X
        STA ST_CALL,X
        DEX
        BPL MS_GATE_COPY
        LDA #<M_READ_WEAR
        STA ST_WEAR_VECTOR
        LDA #>M_READ_WEAR
        STA ST_WEAR_VECTOR+1
        ; The exact frozen SELECT and the private20-byte gate preserve C.
        ; C=0: startup, C=1: VERSION's CPU and validated slot inventory.
        PLP
        LDA #2
        LDX #3
        JMP ST_CALL
MS_UNAVAILABLE:
        PLP
        LDX #<MS_UNAVAILABLE_TEXT
        LDY #>MS_UNAVAILABLE_TEXT
        JMP M_PUTS
MS_ADMIT:
        LDA F_SELECTED
        PHA
        LDA #2
        STA F_SELECTED
        LDX #0
MS_EXTENT:
        LDA MS_EXTENTS,X
        STA F_ADDR
        LDA MS_EXTENTS+1,X
        STA F_ADDR+1
        LDA MS_EXTENTS+2,X
        STA M_LEFT
        LDA MS_EXTENTS+3,X
        STA M_LEFT+1
        JSR M_CRC_START
MS_READ:
        LDA #16
        LDY M_LEFT+1
        BNE MS_CHUNK
        CMP M_LEFT
        BCC MS_CHUNK
        LDA M_LEFT
MS_CHUNK:
        STA M_ROW
        STA F_COUNT
        PHX
        JSR MON_F_READ
        PLX
        LDY #0
MS_CHECKSUM:
        LDA F_BYTES,Y
        JSR M_CRC_BYTE
        INY
        CPY M_ROW
        BCC MS_CHECKSUM
        CLC
        LDA F_ADDR
        ADC M_ROW
        STA F_ADDR
        BCC MS_NO_PAGE
        INC F_ADDR+1
MS_NO_PAGE:
        SEC
        LDA M_LEFT
        SBC M_ROW
        STA M_LEFT
        LDA M_LEFT+1
        SBC #0
        STA M_LEFT+1
        ORA M_LEFT
        BNE MS_READ
        LDA M_CRC
        ORA M_CRC+1
        BNE MS_BAD
        INX
        INX
        INX
        INX
        CPX #16
        BCC MS_EXTENT
        STZ F_ADDR
        LDA #$AC
        STA F_ADDR+1
        LDA #8
        STA F_COUNT
        JSR MON_F_READ
        LDX #7
MS_ID:
        LDA F_BYTES,X
        CMP MS_SIGNATURE,X
        BNE MS_BAD
        DEX
        BPL MS_ID
        SEC
        BRA MS_RETURN
MS_BAD:
        CLC
MS_RETURN:
        PLA
        STA F_SELECTED
        RTS
MS_GATE:
        PHX
        STA F_RESIDENT
        JSR MON_F_SELECT
        JSR ST_ENTRY
        TAY
        PLA
        STA F_RESIDENT
        JSR MON_F_SELECT
        TYA
        RTS
MS_GATE_END:
MS_SIGNATURE: DB "ST",1,5,"PR05"
MS_EXTENTS: DB $40,$80,$C0,0,$40,$82,$C0,0,0,$AC,0,4,$50,$FA,$AA,5
MS_UNAVAILABLE_TEXT: DB "STATUS tools unavailable",13,10,0
