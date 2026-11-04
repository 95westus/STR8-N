; OIP1: standalone whole-sector opaque installer. Linked at $2000 and run
; through F's verified RLP1 loader. No MON code or application RAM scratch.
; Header/state below are part of the escrowed tool image; $6800-$77FF is the
; existing reserved flash staging buffer. All target-side code executes in RAM.
OI_PTR EQU V2_PTR
OI_STAGE EQU $6800
INSTALLER_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        STZ DC_BINARY
        STZ V2_NMI_HOLD
INSTALLER_MENU:
        LDX #<OI_MENU_TEXT
        LDY #>OI_MENU_TEXT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC OI_COMMAND_BAD
        LDA V2_LINE+1
        BNE OI_COMMAND_BAD
        LDA V2_LINE
        CMP #'Q'
        BEQ OI_QUIT
        CMP #'I'
        BNE OI_COMMAND_BAD
        LDA DC_LAST
        CMP #1
        BEQ OI_PORT_OK
        CMP #2
        BNE OI_COMMAND_BAD
OI_PORT_OK:
        STA DC_BINARY
        ; Consume the optional LF paired with the command's CR, before the
        ; ready marker. No payload bytes may precede that marker.
        JSR V2W_BOOT_DELAY
        JSR V2W_RAW_POLL
        BCC OI_HEADER_READY
        CMP #10
        BNE OI_FRAME_BAD
OI_HEADER_READY:
        JSR V2W_RX_RESET
        LDX #<OI_SEND_HEADER
        LDY #>OI_SEND_HEADER
        JSR OI_PRINT
        BCC OI_TX_BAD
        LDY #0
OI_HEADER_BYTE:
        JSR OI_GET
        BCC OI_FRAME_BAD
        STA OI_HEADER,Y
        INY
        CPY #20
        BNE OI_HEADER_BYTE
        LDA V2_RX_BAD
        BNE OI_FRAME_BAD
        JSR OI_VALIDATE
        BCC OI_FRAME_BAD
        LDA OI_HEADER+5
        BEQ OI_READ
        LDX #<OI_SEND_PAYLOAD
        LDY #>OI_SEND_PAYLOAD
        JSR OI_PRINT
        BCC OI_TX_BAD
        STZ OI_PTR
        LDA #$68
        STA OI_PTR+1
        LDA #16
        STA OI_PAGES
        JSR OI_CRC_INIT
OI_RECEIVE:
        JSR OI_GET
        BCC OI_FRAME_BAD
        STA (OI_PTR)
        JSR OI_CRC_BYTE
        INC OI_PTR
        BNE OI_RECEIVE
        INC OI_PTR+1
        DEC OI_PAGES
        BNE OI_RECEIVE
        LDA V2_RX_BAD
        BNE OI_FRAME_BAD
        LDA OI_CRC
        CMP OI_HEADER+12
        BNE OI_FRAME_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BNE OI_FRAME_BAD
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+10
        BNE OI_PREIMAGE_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+11
        BNE OI_PREIMAGE_BAD
        ; Compare every byte before reserving wear. A verified identical
        ; target is successful without requiring journal space or an erase.
        JSR OI_COMPARE
        BCS OI_IDENTICAL
        LDA #3
        JSR V2W_SELECT
        LDA OI_HEADER+6
        ASL A
        ASL A
        ASL A
        STA J_COUNTINDEX
        LDA OI_HEADER+7
        LSR A
        LSR A
        LSR A
        LSR A
        SEC
        SBC #8
        ORA J_COUNTINDEX
        STA J_COUNTINDEX
        LDA #2
        JSR JE_ENTER
        BCC OI_JOURNAL_BAD
        ; An interruption after the durable reservation may overcount one
        ; attempt. Never erase first and try to publish the counter later.
OI_APPLY:
        JSR OI_TARGET
        LDA #1
        STA V2_NMI_HOLD
        STZ V2_FLASH_ERROR
        ; Skip the optional BRK $FC debugger tag. Arbitrary target banks need
        ; not contain interrupt vectors; only protected B3 journal calls use
        ; the normal tagged entries. IRQ is disabled throughout this tool.
        JSR V2W_ERASE_RAW+2
        BCC OI_FLASH_BAD
        JSR OI_TARGET
        LDA #16
        STA OI_PAGES
OI_ERASE_VERIFY:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE OI_FLASH_BAD
        INC V2_FLASH_PTR
        BNE OI_ERASE_VERIFY
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_ERASE_VERIFY
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
OI_PROGRAM:
        LDA (V2_BUF_PTR)
        CMP #$FF
        BEQ OI_PROGRAM_NEXT
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC OI_FLASH_BAD
OI_PROGRAM_NEXT:
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BNE OI_PROGRAM
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_PROGRAM
OI_PROGRAM_END:
        JSR OI_COMPARE
        BCC OI_FLASH_BAD
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+12
        BNE OI_FLASH_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BNE OI_FLASH_BAD
        LDX #<OI_OK_TEXT
        LDY #>OI_OK_TEXT
        JMP OI_FINISH
OI_IDENTICAL:
        LDX #<OI_SAME_TEXT
        LDY #>OI_SAME_TEXT
        JMP OI_FINISH
OI_PREIMAGE_BAD:
        LDX #<OI_PREIMAGE_TEXT
        LDY #>OI_PREIMAGE_TEXT
        JMP OI_FINISH
OI_JOURNAL_BAD:
        LDX #<OI_JOURNAL_TEXT
        LDY #>OI_JOURNAL_TEXT
        JMP OI_FINISH
OI_FLASH_BAD:
        LDX #<OI_FLASH_TEXT
        LDY #>OI_FLASH_TEXT
        JMP OI_FINISH
OI_FRAME_BAD:
        LDX #<OI_FRAME_TEXT
        LDY #>OI_FRAME_TEXT
        JMP OI_LOCK
OI_TX_BAD:
        LDX #<OI_TX_TEXT
        LDY #>OI_TX_TEXT
        JMP OI_LOCK
OI_COMMAND_BAD:
        LDX #<OI_COMMAND_TEXT
        LDY #>OI_COMMAND_TEXT
OI_FINISH:
        PHX
        LDA #3
        JSR V2W_SELECT
        PLX
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JSR BOOT_PRINT
        JMP INSTALLER_MENU

; Once framing or binary output fails, no remaining byte has a trusted text
; boundary. Reset is the only recovery. Discard raw bytes forever, including
; delayed payload tails and bytes that happen to spell Q/L/R/A/B commands.
OI_LOCK:
        PHX
        LDA #3
        JSR V2W_SELECT
        PLX
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JSR BOOT_PRINT
        LDX #<OI_LOCK_TEXT
        LDY #>OI_LOCK_TEXT
        JSR BOOT_PRINT
OI_LOCK_DRAIN:
        JSR V2W_RAW_POLL
        JMP OI_LOCK_DRAIN
OI_QUIT:
        STZ DC_BINARY
        STZ V2_NMI_HOLD
        JSR V2W_RX_RESET
        JMP BOOT_RECOVERY

; Read requests use the same protected target whitelist as writes. Exact
; 4096-byte output plus little-endian CRC follows the ready marker.
OI_READ:
        LDX #<OI_READ_TEXT
        LDY #>OI_READ_TEXT
        JSR OI_PRINT
        BCC OI_TX_BAD
        JSR OI_TARGET
        STZ OI_PTR
        LDA OI_HEADER+7
        STA OI_PTR+1
        LDA #16
        STA OI_PAGES
        JSR OI_CRC_INIT
OI_READ_BYTE:
        LDA (OI_PTR)
        PHA
        JSR OI_CRC_BYTE
        PLA
        JSR V2W_PUTC
        BCC OI_TX_BAD
        INC OI_PTR
        BNE OI_READ_BYTE
        INC OI_PTR+1
        DEC OI_PAGES
        BNE OI_READ_BYTE
        LDA OI_CRC
        JSR V2W_PUTC
        BCC OI_TX_BAD
        LDA OI_CRC+1
        JSR V2W_PUTC
        BCC OI_TX_BAD
        LDX #<OI_READ_OK_TEXT
        LDY #>OI_READ_OK_TEXT
        JMP OI_FINISH

; All callers enter with B3 selected. C=1 only for the complete canonical
; header; no caller-controlled address or length is used by transfer loops.
OI_VALIDATE:
        JSR OI_CRC_INIT
        LDY #0
OI_HEADER_CRC:
        LDA OI_HEADER,Y
        JSR OI_CRC_BYTE
        INY
        CPY #18
        BNE OI_HEADER_CRC
        LDA OI_CRC
        CMP OI_HEADER+18
        BNE OI_VALIDATE_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+19
        BNE OI_VALIDATE_BAD
        LDX #4
OI_MAGIC:
        LDA OI_HEADER,X
        CMP OI_SIGNATURE,X
        BNE OI_VALIDATE_BAD
        DEX
        BPL OI_MAGIC
        LDA OI_HEADER+5
        CMP #2
        BCS OI_VALIDATE_BAD
        LDA OI_HEADER+6
        CMP #4
        BCS OI_VALIDATE_BAD
        LDA OI_HEADER+7
        AND #15
        BNE OI_VALIDATE_BAD
        LDA OI_HEADER+7
        CMP #$80
        BCC OI_VALIDATE_BAD
        LDA OI_HEADER+6
        CMP #3
        BNE OI_RANGE_OK
        LDA OI_HEADER+7
        CMP #$80
        BEQ OI_RANGE_OK
        CMP #$90
        BEQ OI_RANGE_OK
        CMP #$E0
        BNE OI_VALIDATE_BAD
OI_RANGE_OK:
        LDA OI_HEADER+8
        BNE OI_VALIDATE_BAD
        LDA OI_HEADER+9
        CMP #$10
        BNE OI_VALIDATE_BAD
        LDA OI_HEADER+14
        ORA OI_HEADER+15
        ORA OI_HEADER+16
        ORA OI_HEADER+17
        BNE OI_VALIDATE_BAD
        LDA OI_HEADER+5
        BNE OI_VALIDATE_OK
        LDA OI_HEADER+10
        ORA OI_HEADER+11
        ORA OI_HEADER+12
        ORA OI_HEADER+13
        BNE OI_VALIDATE_BAD
OI_VALIDATE_OK:
        SEC
        RTS
OI_VALIDATE_BAD:
        CLC
        RTS

OI_TARGET:
        LDA OI_HEADER+6
        JSR V2W_SELECT
        STZ V2_FLASH_PTR
        LDA OI_HEADER+7
        STA V2_FLASH_PTR+1
        RTS
OI_TARGET_CRC:
        JSR OI_TARGET
        STZ OI_PTR
        LDA OI_HEADER+7
        STA OI_PTR+1
        LDA #16
        STA OI_PAGES
        JSR OI_CRC_INIT
OI_TARGET_CRC_BYTE:
        LDA (OI_PTR)
        JSR OI_CRC_BYTE
        INC OI_PTR
        BNE OI_TARGET_CRC_BYTE
        INC OI_PTR+1
        DEC OI_PAGES
        BNE OI_TARGET_CRC_BYTE
        RTS
OI_COMPARE:
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
OI_COMPARE_BYTE:
        LDA (V2_FLASH_PTR)
        CMP (V2_BUF_PTR)
        BNE OI_COMPARE_BAD
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BNE OI_COMPARE_BYTE
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_COMPARE_BYTE
        SEC
        RTS
OI_COMPARE_BAD:
        CLC
        RTS

; Raw receive is bounded per byte, port-exclusive, and never interprets 03,
; CR or LF. Every byte value is literal in header, payload and CRC trailers.
OI_GET:
        PHX
        PHY
        LDX #0
        LDY #0
OI_POLL:
        JSR V2W_RAW_POLL
        BCS OI_GOT
        DEX
        BNE OI_POLL
        DEY
        BNE OI_POLL
        CLC
OI_GOT:
        PLY
        PLX
        RTS

; Checked RAM printer: binary ready markers cannot silently lose FT245
; characters and then accept a transfer whose host never saw readiness.
OI_PRINT:
        STX OI_PTR
        STY OI_PTR+1
        LDY #0
OI_PRINT_BYTE:
        LDA (OI_PTR),Y
        BEQ OI_PRINT_DONE
        JSR V2W_PUTC
        BCC OI_PRINT_BAD
        INY
        BNE OI_PRINT_BYTE
        INC OI_PTR+1
        BRA OI_PRINT_BYTE
OI_PRINT_DONE:
        SEC
        RTS
OI_PRINT_BAD:
        CLC
        RTS

; Local RAM CRC is essential when arbitrary target flash overlays hide F.
; CRC16/CCITT-FALSE matches F exactly: polynomial1021, initFFFF, Y preserved.
OI_CRC_INIT:
        LDA #$FF
        STA OI_CRC
        STA OI_CRC+1
        RTS
OI_CRC_BYTE:
        EOR OI_CRC+1
        STA OI_CRC+1
        LDX #8
OI_CRC_BIT:
        ASL OI_CRC
        ROL OI_CRC+1
        BCC OI_CRC_NEXT
        LDA OI_CRC
        EOR #$21
        STA OI_CRC
        LDA OI_CRC+1
        EOR #$10
        STA OI_CRC+1
OI_CRC_NEXT:
        DEX
        BNE OI_CRC_BIT
        RTS

OI_SIGNATURE: DB "OIP1",1
OI_MENU_TEXT: DB "INSTALLER I Q> ",0
OI_SEND_HEADER: DB "SEND OIP1 HEADER",13,10,0
OI_SEND_PAYLOAD: DB "SEND 4096",13,10,0
OI_READ_TEXT: DB "READ SECTOR+CRC",13,10,0
OI_OK_TEXT: DB "OK: verified sector",13,10,0
OI_SAME_TEXT: DB "OK: identical; no erase",13,10,0
OI_READ_OK_TEXT: DB 13,10,"OK: read",13,10,0
OI_PREIMAGE_TEXT: DB "REFUSED: preimage CRC",13,10,0
OI_JOURNAL_TEXT: DB "REFUSED: durable wear reservation",13,10,0
OI_FLASH_TEXT: DB "FAILED: flash/readback; target may be torn",13,10,0
OI_FRAME_TEXT: DB "REFUSED: frame/range/CRC/timeout",13,10,0
OI_TX_TEXT: DB "REFUSED: TX blocked",13,10,0
OI_LOCK_TEXT: DB "LOCKED: RESET required",13,10,0
OI_COMMAND_TEXT: DB "REFUSED: I or Q",13,10,0
OI_HEADER: DB 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
OI_CRC: DB 0,0
OI_PAGES: DB 0
