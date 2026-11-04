; RAM bootstrap client for the VX1 public E descriptor. No private F/MON call.
; Raw L entry displays VERSION and resets F. Callable query JMP is at $0203.
; QUERY has the provider's register/buffer contract and restores the exact PCR.
        MODULE VERSION_CAPS_CLIENT
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "version-caps-public.inc"
QPTR EQU $D0
QCRC EQU $D2
        CODE
VQ_START: JMP VQ_TOOL
VQ_QUERY: JMP VQ_DO_QUERY
VQ_TOOL:
        SEI
        CLD
        LDA #VX_INFO_SIZE
        STA $6000
        LDA #0
        LDX #0
        LDY #$60
        JSR VQ_QUERY
        BCC VQ_TOOL_BAD
        LDX #7
VQ_TOOL_WORD:
        LDA VQ_VERSION,X
        STA STR8V2_LINE,X
        DEX
        BPL VQ_TOOL_WORD
        LDA #0
        JSR VX_COMMAND_ENTRY
        JMP STR8V2_RAM_RESET
VQ_TOOL_BAD:
        LDX #0
VQ_TOOL_PRINT:
        LDA VQ_ERROR,X
        BEQ VQ_TOOL_EXIT
        JSR STR8V2_RAM_PUTC
        INX
        BRA VQ_TOOL_PRINT
VQ_TOOL_EXIT:
        JMP STR8V2_RAM_RESET
VQ_DO_QUERY:
        STA $67E4
        STX $67E5
        STY $67E6
        LDX #15
VQ_SAVE:
        LDA $D0,X
        PHA
        DEX
        BPL VQ_SAVE
        LDA $7FEC
        STA $67F8
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
VQ_HEADER:
        LDA VX_BASE,X
        CMP VQ_MAGIC,X
        BNE VQ_ABSENT
        DEX
        BPL VQ_HEADER
        LDA VX_BASE+16
        BNE VQ_ABSENT
        LDA VX_BASE+17
        CMP #$10
        BNE VQ_ABSENT
        LDA VX_BASE+31
        BNE VQ_ABSENT
        LDA VX_BASE+15
        CMP #VX_INFO_SIZE
        BNE VQ_ABSENT
        LDA VX_BASE+13
        CMP #1
        BNE VQ_ABSENT
        LDA VX_BASE+14
        CMP #1
        BNE VQ_ABSENT
        LDX #4
VQ_ENTRY:
        LDA VX_BASE,X
        CMP #$4C
        BNE VQ_ABSENT
        LDA VX_BASE+2,X
        CMP #$E0
        BCC VQ_ABSENT
        CMP #$F0
        BCS VQ_ABSENT
        CMP #$E0
        BNE VQ_ENTRY_LAST
        LDA VX_BASE+1,X
        CMP #$40
        BCC VQ_ABSENT
        BRA VQ_ENTRY_OK
VQ_ENTRY_LAST:
        CMP #$EF
        BNE VQ_ENTRY_OK
        LDA VX_BASE+1,X
        CMP #$C0
        BCS VQ_ABSENT
VQ_ENTRY_OK:
        INX
        INX
        INX
        CPX #10
        BNE VQ_ENTRY
        STZ QPTR
        LDA #$E0
        STA QPTR+1
        LDA #$FF
        STA QCRC
        STA QCRC+1
VQ_CRC_BYTE:
        LDA (QPTR)
        EOR QCRC+1
        STA QCRC+1
        LDX #8
VQ_CRC_BIT:
        ASL QCRC
        ROL QCRC+1
        BCC VQ_CRC_NEXT
        LDA QCRC
        EOR #$21
        STA QCRC
        LDA QCRC+1
        EOR #$10
        STA QCRC+1
VQ_CRC_NEXT:
        DEX
        BNE VQ_CRC_BIT
        INC QPTR
        BNE VQ_CRC_BYTE
        INC QPTR+1
        LDA QPTR+1
        CMP #$F0
        BNE VQ_CRC_BYTE
        LDA QCRC
        ORA QCRC+1
        BNE VQ_ABSENT
        LDA $67E4
        LDX $67E5
        LDY $67E6
        JSR VX_QUERY_ENTRY
        BRA VQ_RETURN
VQ_ABSENT:
        LDA #$80
        CLC
VQ_RETURN:
        STA $67F9
        PHP
        PLA
        STA $67FA
        LDA $67F8
        STA $7FEC
        LDX #0
VQ_RESTORE:
        PLA
        STA $D0,X
        INX
        CPX #16
        BNE VQ_RESTORE
        LDA $67FA
        PHA
        PLP
        LDX $67E5
        LDY $67E6
        LDA $67F9
        RTS
VQ_MAGIC: DB "VX",1,64
VQ_VERSION: DB "VERSION",0
VQ_ERROR: DB "VX1 unavailable",13,10,0
VQ_END:
        ENDS
        END
