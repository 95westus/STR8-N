; Read-only flash catalogue. Skip admitted record extents, never hunt inside
; their payload. SR01 C means committed, not a claim about its old execution ABI.
MT_HEAD EQU $6300
MT_BANK EQU $6320
MT_PAGE EQU $6321
MT_LAST_BANK EQU $6322
MT_NEXT EQU $6323
MT_LOAD EQU $6324
MT_SIZE EQU $6326
MT_END EQU $6328
MT_KIND EQU $632A
MT_STATE EQU $632B
MT_PAGES EQU $632C
MT_CRC EQU $632D
MT_NAME EQU $6330

MM_BM_TABLE:
        JSR MM_SPACES
        BNE MT_ARGS
        STZ MT_BANK
        LDA #3
        STA MT_LAST_BANK
        BRA MT_BANK_START
MT_ARGS:
        JSR MM_RANGE
        BCC MM_BM_BAD
        JSR MM_ENDLINE
        BCC MM_BM_BAD
        LDA MM_FIRST+1
        ORA MM_LAST+1
        BNE MM_BM_BAD
        LDA MM_LAST
        CMP #4
        BCS MM_BM_BAD
        STA MT_LAST_BANK
        LDA MM_FIRST
        STA MT_BANK
MT_BANK_START:
        LDA #$80
        STA MT_PAGE
MT_ROW:
        JSR MM_CHECK_CANCEL
        LDA MT_BANK
        JSR MM_V2W_SELECT
        STZ MM_SRC
        LDA MT_PAGE
        STA MM_SRC+1
        INC A
        STA MT_NEXT
        LDY #0
MT_HEADER_READ:
        LDA (MM_SRC),Y
        STA MT_HEAD,Y
        INY
        CPY #32
        BCC MT_HEADER_READ
        LDA #3
        JSR MM_V2W_SELECT
        LDA MT_HEAD
        CMP #'S'
        BEQ MT_SR
        CMP #'R'
        BNE MT_ADVANCE
        JSR MT_NATIVE
        BCS MT_PRINT_ROW
        BRA MT_ADVANCE
MT_SR:
        JSR MT_SR_CHECK
        BCC MT_ADVANCE
MT_PRINT_ROW:
        JSR MT_SHOW
MT_ADVANCE:
        LDA MT_NEXT
        BEQ MT_BANK_DONE
        STA MT_PAGE
        BRA MT_ROW
MT_BANK_DONE:
        LDA MT_BANK
        CMP MT_LAST_BANK
        BEQ MT_DONE
        INC MT_BANK
        BRA MT_BANK_START
MT_DONE:
        LDA #3
        JSR MM_V2W_SELECT
        LDX #<MT_FOOTER
        LDY #>MT_FOOTER
        JMP MM_MESSAGE

MT_SR_CHECK:
        LDA MT_HEAD+1
        CMP #'R'
        BNE MT_NO
        LDA MT_HEAD+2
        CMP #1
        BNE MT_NO
        LDA MT_HEAD+3
        CMP #$3F
        BEQ MT_SR_STATE
        CMP #$FF
        BNE MT_NO
MT_SR_STATE:
        LDA #'?'
        LDX MT_HEAD+3
        CPX #$3F
        BNE MT_SR_FLAG
        LDA #'C'
MT_SR_FLAG:
        STA MT_STATE
        LDA MT_HEAD+4
        STA MT_LOAD
        LDA MT_HEAD+5
        STA MT_LOAD+1
        LDA MT_HEAD+6
        STA MT_SIZE
        LDA MT_HEAD+7
        STA MT_SIZE+1
        JSR MT_RAM_EXTENT
        BCC MT_NO
        LDY #0
        LDX #0
MT_SR_NAME:
        LDA MT_HEAD+8,Y
        BEQ MT_SR_ZERO
        CPX #0
        BNE MT_NO
        CMP #$21
        BCC MT_NO
        CMP #$7F
        BCS MT_NO
        BRA MT_SR_COPY
MT_SR_ZERO:
        INX
MT_SR_COPY:
        STA MT_NAME,Y
        INY
        CPY #16
        BCC MT_SR_NAME
        LDA MT_NAME
        BEQ MT_NO
        STZ MT_NAME+16
        ; Compute exclusive flash end and round to the following header page.
        CLC
        LDA MT_SIZE
        ADC #24
        TAX
        LDA MT_SIZE+1
        ADC MT_PAGE
        BCS MT_NO
        CPX #0
        BEQ MT_SR_NEXT
        INC A
MT_SR_NEXT:
        STA MT_NEXT
        SEC
        RTS
MT_NO:
        CLC
        RTS
MT_RAM_EXTENT:
        LDA MT_SIZE
        ORA MT_SIZE+1
        BEQ MT_NO
        LDA MT_LOAD+1
        CMP #2
        BCC MT_NO
        CLC
        LDA MT_LOAD
        ADC MT_SIZE
        STA MT_END
        LDA MT_LOAD+1
        ADC MT_SIZE+1
        BCS MT_NO
        STA MT_END+1
        LDA MT_END
        BNE MT_END_LOW
        DEC MT_END+1
MT_END_LOW:
        DEC MT_END
        LDA MT_END+1
        CMP #$67
        BCS MT_NO
        SEC
        RTS

MT_NATIVE:
        LDA MT_HEAD+1
        CMP #'P'
        BNE MT_NO
        LDA MT_HEAD+2
        CMP #1
        BNE MT_NO
        LDX #3
MT_NATIVE_ABI:
        LDA MT_HEAD+4,X
        CMP MT_PR05,X
        BNE MT_NO
        DEX
        BPL MT_NATIVE_ABI
        LDA MT_HEAD+3
        CMP #3
        BCS MT_NO
        STA MT_KIND
        CMP #2
        BEQ MT_MAINT_PLACE
        LDA MT_BANK
        CMP #2
        BNE MT_NO
        LDX MT_KIND
        LDA MT_PAGE
        CMP MT_TOOL_PAGES,X
        BNE MT_NO
        BRA MT_NATIVE_PLACE_OK
MT_MAINT_PLACE:
        LDA MT_BANK
        CMP #1
        BNE MT_NO
        LDA MT_PAGE
        CMP #$80
        BNE MT_NO
MT_NATIVE_PLACE_OK:
        LDA MT_HEAD+10
        ORA MT_HEAD+12
        BNE MT_NO
        LDA MT_HEAD+11
        CMP #$20
        BNE MT_NO
        CMP MT_HEAD+13
        BNE MT_NO
        LDA MT_HEAD+8
        STA MT_SIZE
        LDA MT_HEAD+9
        STA MT_SIZE+1
        LDX MT_KIND
        LDA MT_SECT_PAGES,X
        SEC
        SBC #1
        CMP MT_SIZE+1
        BCC MT_NO
        BNE MT_NATIVE_LENGTH
        LDA MT_SIZE
        CMP #$DF
        BCS MT_NO
MT_NATIVE_LENGTH:
        STZ MT_LOAD
        LDA #$20
        STA MT_LOAD+1
        JSR MT_RAM_EXTENT
        BCC MT_NO
        LDX MT_KIND
        LDA MT_SECT_PAGES,X
        STA MT_PAGES
        CLC
        ADC MT_PAGE
        STA MT_NEXT
        LDA MT_BANK
        JSR MM_V2W_SELECT
        STZ MM_SRC
        LDA MT_PAGE
        STA MM_SRC+1
        LDA #$FF
        STA MT_CRC
        STA MT_CRC+1
MT_CRC_LOOP:
        LDA (MM_SRC)
        JSR MT_CRC_BYTE
        INC MM_SRC
        BNE MT_CRC_LOOP
        INC MM_SRC+1
        DEC MT_PAGES
        BNE MT_CRC_LOOP
        LDA #3
        JSR MM_V2W_SELECT
        LDA MT_CRC
        ORA MT_CRC+1
        BNE MT_NO
        LDA #'C'
        STA MT_STATE
        LDA MT_KIND
        ASL A
        TAX
        LDA MT_NAMES,X
        STA MM_TXT
        LDA MT_NAMES+1,X
        STA MM_TXT+1
        LDY #0
MT_NATIVE_NAME:
        LDA (MM_TXT),Y
        STA MT_NAME,Y
        BEQ MT_NATIVE_OK
        INY
        BRA MT_NATIVE_NAME
MT_NATIVE_OK:
        SEC
        RTS
MT_CRC_BYTE:
        EOR MT_CRC+1
        STA MT_CRC+1
        LDX #8
MT_CRC_BIT:
        ASL MT_CRC
        ROL MT_CRC+1
        BCC MT_CRC_NEXT
        LDA MT_CRC
        EOR #$21
        STA MT_CRC
        LDA MT_CRC+1
        EOR #$10
        STA MT_CRC+1
MT_CRC_NEXT:
        DEX
        BNE MT_CRC_BIT
        RTS
MT_SHOW:
        LDA MT_BANK
        JSR MM_SPACE_NAME
        LDA #':'
        JSR MM_PUTC
        LDA MT_PAGE
        JSR MM_HEX
        LDA #0
        JSR MM_HEX
        JSR MT_SPACE
        LDA MT_LOAD+1
        JSR MM_HEX
        LDA MT_LOAD
        JSR MM_HEX
        LDA #'-'
        JSR MM_PUTC
        LDA MT_END+1
        JSR MM_HEX
        LDA MT_END
        JSR MM_HEX
        JSR MT_SPACE
        LDA MT_SIZE+1
        JSR MM_HEX
        LDA MT_SIZE
        JSR MM_HEX
        JSR MT_SPACE
        LDA MT_STATE
        JSR MM_PUTC
        JSR MT_SPACE
        LDX #<MT_NAME
        LDY #>MT_NAME
        JSR MM_PRINT
        JMP MM_NL
MT_SPACE:
        LDA #' '
        JMP MM_PUTC
MT_PR05: DB "PR05"
MT_TOOL_PAGES: DB $B0,$E0
MT_SECT_PAGES: DB 48,32,48
MT_NAMES: DW MT_CLOCK_NAME,MT_FLASH_NAME,MT_MAINT_NAME
MT_CLOCK_NAME: DB "CLOCK",0
MT_FLASH_NAME: DB "FLASH",0
MT_MAINT_NAME: DB "MAINT",0
MT_FOOTER: DB "C=committed SR01 (no payload CRC) / sealed native RP; ?=pending.",13,10,0
