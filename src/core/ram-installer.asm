        MODULE RAM_OPAQUE_INSTALLER
        XDEF INSTALLER_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
; BASE1 OIP1: standalone whole-sector opaque installer at $0200 via raw L.
; B0-B2:8-F and B3:8/9/A/B/E are user targets; B3:C/D/F stay protected.
; No MON code or application RAM scratch. Raw L has no transfer CRC/length.
; Header/state below are part of the disposable tool image; $6800-$77FF is the
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
        BCS OI_LONG_1
        JMP OI_COMMAND_BAD
OI_LONG_1:
        LDA V2_LINE+1
        BEQ OI_LONG_2
        JMP OI_COMMAND_BAD
OI_LONG_2:
        LDA V2_LINE
        CMP #'Q'
        BNE OI_LONG_3
        JMP OI_QUIT
OI_LONG_3:
        CMP #'I'
        BEQ OI_LONG_4
        JMP OI_COMMAND_BAD
OI_LONG_4:
        LDA DC_LAST
        CMP #1
        BNE OI_LONG_5
        JMP OI_PORT_OK
OI_LONG_5:
        CMP #2
        BEQ OI_LONG_6
        JMP OI_COMMAND_BAD
OI_LONG_6:
OI_PORT_OK:
        STA DC_BINARY
        ; Consume the optional LF paired with the command's CR, before the
        ; ready marker. No payload bytes may precede that marker.
        JSR V2W_BOOT_DELAY
        JSR V2W_RAW_POLL
        BCS OI_LONG_7
        JMP OI_HEADER_READY
OI_LONG_7:
        CMP #10
        BEQ OI_LONG_8
        JMP OI_FRAME_BAD
OI_LONG_8:
OI_HEADER_READY:
        JSR V2W_RX_RESET
        LDX #<OI_SEND_HEADER
        LDY #>OI_SEND_HEADER
        JSR OI_PRINT
        BCS OI_LONG_9
        JMP OI_TX_BAD
OI_LONG_9:
        LDY #0
OI_HEADER_BYTE:
        JSR OI_GET
        BCS OI_LONG_10
        JMP OI_FRAME_BAD
OI_LONG_10:
        STA OI_HEADER,Y
        INY
        CPY #20
        BEQ OI_LONG_11
        JMP OI_HEADER_BYTE
OI_LONG_11:
        LDA V2_RX_BAD
        BEQ OI_LONG_12
        JMP OI_FRAME_BAD
OI_LONG_12:
        JSR OI_VALIDATE
        BCS OI_LONG_13
        JMP OI_FRAME_BAD
OI_LONG_13:
        LDA OI_HEADER+5
        BNE OI_LONG_14
        JMP OI_READ
OI_LONG_14:
        LDX #<OI_SEND_PAYLOAD
        LDY #>OI_SEND_PAYLOAD
        JSR OI_PRINT
        BCS OI_LONG_15
        JMP OI_TX_BAD
OI_LONG_15:
        STZ OI_PTR
        LDA #$68
        STA OI_PTR+1
        LDA #16
        STA OI_PAGES
        JSR OI_CRC_INIT
OI_RECEIVE:
        JSR OI_GET
        BCS OI_LONG_16
        JMP OI_FRAME_BAD
OI_LONG_16:
        STA (OI_PTR)
        JSR OI_CRC_BYTE
        INC OI_PTR
        BEQ OI_LONG_17
        JMP OI_RECEIVE
OI_LONG_17:
        INC OI_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_18
        JMP OI_RECEIVE
OI_LONG_18:
        LDA V2_RX_BAD
        BEQ OI_LONG_19
        JMP OI_FRAME_BAD
OI_LONG_19:
        LDA OI_CRC
        CMP OI_HEADER+12
        BEQ OI_LONG_20
        JMP OI_FRAME_BAD
OI_LONG_20:
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BEQ OI_LONG_21
        JMP OI_FRAME_BAD
OI_LONG_21:
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+10
        BEQ OI_LONG_22
        JMP OI_PREIMAGE_BAD
OI_LONG_22:
        LDA OI_CRC+1
        CMP OI_HEADER+11
        BEQ OI_LONG_23
        JMP OI_PREIMAGE_BAD
OI_LONG_23:
        ; Compare every byte before reserving wear. A verified identical
        ; target is successful without requiring journal space or an erase.
        JSR OI_COMPARE
        BCC OI_LONG_24
        JMP OI_IDENTICAL
OI_LONG_24:
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
        BCS OI_LONG_25
        JMP OI_JOURNAL_BAD
OI_LONG_25:
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
        BCS OI_LONG_26
        JMP OI_FLASH_BAD
OI_LONG_26:
        JSR OI_TARGET
        LDA #16
        STA OI_PAGES
OI_ERASE_VERIFY:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BEQ OI_LONG_27
        JMP OI_FLASH_BAD
OI_LONG_27:
        INC V2_FLASH_PTR
        BEQ OI_LONG_28
        JMP OI_ERASE_VERIFY
OI_LONG_28:
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_29
        JMP OI_ERASE_VERIFY
OI_LONG_29:
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
OI_PROGRAM:
        LDA (V2_BUF_PTR)
        CMP #$FF
        BNE OI_LONG_30
        JMP OI_PROGRAM_NEXT
OI_LONG_30:
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCS OI_LONG_31
        JMP OI_FLASH_BAD
OI_LONG_31:
OI_PROGRAM_NEXT:
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BEQ OI_LONG_32
        JMP OI_PROGRAM
OI_LONG_32:
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_33
        JMP OI_PROGRAM
OI_LONG_33:
OI_PROGRAM_END:
        JSR OI_COMPARE
        BCS OI_LONG_34
        JMP OI_FLASH_BAD
OI_LONG_34:
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+12
        BEQ OI_LONG_35
        JMP OI_FLASH_BAD
OI_LONG_35:
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BEQ OI_LONG_36
        JMP OI_FLASH_BAD
OI_LONG_36:
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
        BCS OI_LONG_37
        JMP OI_TX_BAD
OI_LONG_37:
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
        BCS OI_LONG_38
        JMP OI_TX_BAD
OI_LONG_38:
        INC OI_PTR
        BEQ OI_LONG_39
        JMP OI_READ_BYTE
OI_LONG_39:
        INC OI_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_40
        JMP OI_READ_BYTE
OI_LONG_40:
        LDA OI_CRC
        JSR V2W_PUTC
        BCS OI_LONG_41
        JMP OI_TX_BAD
OI_LONG_41:
        LDA OI_CRC+1
        JSR V2W_PUTC
        BCS OI_LONG_42
        JMP OI_TX_BAD
OI_LONG_42:
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
        BEQ OI_LONG_43
        JMP OI_HEADER_CRC
OI_LONG_43:
        LDA OI_CRC
        CMP OI_HEADER+18
        BEQ OI_LONG_44
        JMP OI_VALIDATE_BAD
OI_LONG_44:
        LDA OI_CRC+1
        CMP OI_HEADER+19
        BEQ OI_LONG_45
        JMP OI_VALIDATE_BAD
OI_LONG_45:
        LDX #4
OI_MAGIC:
        LDA OI_HEADER,X
        CMP OI_SIGNATURE,X
        BEQ OI_LONG_46
        JMP OI_VALIDATE_BAD
OI_LONG_46:
        DEX
        BMI OI_LONG_47
        JMP OI_MAGIC
OI_LONG_47:
        LDA OI_HEADER+5
        CMP #2
        BCC OI_LONG_48
        JMP OI_VALIDATE_BAD
OI_LONG_48:
        LDA OI_HEADER+6
        CMP #4
        BCC OI_LONG_49
        JMP OI_VALIDATE_BAD
OI_LONG_49:
        LDA OI_HEADER+7
        AND #15
        BEQ OI_LONG_50
        JMP OI_VALIDATE_BAD
OI_LONG_50:
        LDA OI_HEADER+7
        CMP #$80
        BCS OI_LONG_51
        JMP OI_VALIDATE_BAD
OI_LONG_51:
        LDA OI_HEADER+6
        CMP #3
        BEQ OI_LONG_52
        JMP OI_RANGE_OK
OI_LONG_52:
        LDA OI_HEADER+7
        ; The preceding checks established >=80 and a zero low nibble.
        ; Thus below C0 admits exactly 80/90/A0/B0; only E0 is above it.
        CMP #$C0
        BCC OI_RANGE_OK
        CMP #$E0
        BEQ OI_LONG_55
        JMP OI_VALIDATE_BAD
OI_LONG_55:
OI_RANGE_OK:
        LDA OI_HEADER+8
        BEQ OI_LONG_56
        JMP OI_VALIDATE_BAD
OI_LONG_56:
        LDA OI_HEADER+9
        CMP #$10
        BEQ OI_LONG_57
        JMP OI_VALIDATE_BAD
OI_LONG_57:
        LDA OI_HEADER+14
        ORA OI_HEADER+15
        ORA OI_HEADER+16
        ORA OI_HEADER+17
        BEQ OI_LONG_58
        JMP OI_VALIDATE_BAD
OI_LONG_58:
        LDA OI_HEADER+5
        BEQ OI_LONG_59
        JMP OI_VALIDATE_OK
OI_LONG_59:
        LDA OI_HEADER+10
        ORA OI_HEADER+11
        ORA OI_HEADER+12
        ORA OI_HEADER+13
        BEQ OI_LONG_60
        JMP OI_VALIDATE_BAD
OI_LONG_60:
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
        BEQ OI_LONG_61
        JMP OI_TARGET_CRC_BYTE
OI_LONG_61:
        INC OI_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_62
        JMP OI_TARGET_CRC_BYTE
OI_LONG_62:
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
        BEQ OI_LONG_63
        JMP OI_COMPARE_BAD
OI_LONG_63:
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BEQ OI_LONG_64
        JMP OI_COMPARE_BYTE
OI_LONG_64:
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BEQ OI_LONG_65
        JMP OI_COMPARE_BYTE
OI_LONG_65:
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
        BCC OI_LONG_66
        JMP OI_GOT
OI_LONG_66:
        DEX
        BEQ OI_LONG_67
        JMP OI_POLL
OI_LONG_67:
        DEY
        BEQ OI_LONG_68
        JMP OI_POLL
OI_LONG_68:
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
        BNE OI_LONG_69
        JMP OI_PRINT_DONE
OI_LONG_69:
        JSR V2W_PUTC
        BCS OI_LONG_70
        JMP OI_PRINT_BAD
OI_LONG_70:
        INY
        BEQ OI_LONG_71
        JMP OI_PRINT_BYTE
OI_LONG_71:
        INC OI_PTR+1
        JMP OI_PRINT_BYTE
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
        BCS OI_LONG_72
        JMP OI_CRC_NEXT
OI_LONG_72:
        LDA OI_CRC
        EOR #$21
        STA OI_CRC
        LDA OI_CRC+1
        EOR #$10
        STA OI_CRC+1
OI_CRC_NEXT:
        DEX
        BEQ OI_LONG_73
        JMP OI_CRC_BIT
OI_LONG_73:
        RTS

OI_SIGNATURE: DB "OIP1",1
OI_MENU_TEXT: DB "OPAQUE BASE1 / PR05 I Q> ",0
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

        INCLUDE "prototype-engine.inc"
INSTALLER_END:
        ENDMOD
        END
