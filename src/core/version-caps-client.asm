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
        BCS P_LONG_1
        JMP VQ_TOOL_BAD
P_LONG_1:
        LDX #7
VQ_TOOL_WORD:
        LDA VQ_VERSION,X
        STA STR8V2_LINE,X
        DEX
        BMI P_LONG_2
        JMP VQ_TOOL_WORD
P_LONG_2:
        LDA #0
        JSR VX_COMMAND_ENTRY
        JMP STR8V2_RAM_RESET
VQ_TOOL_BAD:
        LDX #0
VQ_TOOL_PRINT:
        LDA VQ_ERROR,X
        BNE P_LONG_3
        JMP VQ_TOOL_EXIT
P_LONG_3:
        JSR STR8V2_RAM_PUTC
        INX
        JMP VQ_TOOL_PRINT
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
        BMI P_LONG_4
        JMP VQ_SAVE
P_LONG_4:
        LDA $7FEC
        STA $67F8
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
VQ_HEADER:
        LDA VX_BASE,X
        CMP VQ_MAGIC,X
        BEQ P_LONG_5
        JMP VQ_ABSENT
P_LONG_5:
        DEX
        BMI P_LONG_6
        JMP VQ_HEADER
P_LONG_6:
        LDA VX_BASE+16
        BEQ P_LONG_7
        JMP VQ_ABSENT
P_LONG_7:
        LDA VX_BASE+17
        CMP #$10
        BEQ P_LONG_8
        JMP VQ_ABSENT
P_LONG_8:
        LDA VX_BASE+31
        BEQ P_LONG_9
        JMP VQ_ABSENT
P_LONG_9:
        LDA VX_BASE+15
        CMP #VX_INFO_SIZE
        BEQ P_LONG_10
        JMP VQ_ABSENT
P_LONG_10:
        LDA VX_BASE+13
        CMP #1
        BEQ P_LONG_11
        JMP VQ_ABSENT
P_LONG_11:
        LDA VX_BASE+14
        CMP #1
        BEQ P_LONG_12
        JMP VQ_ABSENT
P_LONG_12:
        LDX #4
VQ_ENTRY:
        LDA VX_BASE,X
        CMP #$4C
        BEQ P_LONG_13
        JMP VQ_ABSENT
P_LONG_13:
        LDA VX_BASE+2,X
        CMP #$E0
        BCS P_LONG_14
        JMP VQ_ABSENT
P_LONG_14:
        CMP #$F0
        BCC P_LONG_15
        JMP VQ_ABSENT
P_LONG_15:
        CMP #$E0
        BEQ P_LONG_16
        JMP VQ_ENTRY_LAST
P_LONG_16:
        LDA VX_BASE+1,X
        CMP #$40
        BCS P_LONG_17
        JMP VQ_ABSENT
P_LONG_17:
        JMP VQ_ENTRY_OK
VQ_ENTRY_LAST:
        CMP #$EF
        BEQ P_LONG_18
        JMP VQ_ENTRY_OK
P_LONG_18:
        LDA VX_BASE+1,X
        CMP #$C0
        BCC P_LONG_19
        JMP VQ_ABSENT
P_LONG_19:
VQ_ENTRY_OK:
        INX
        INX
        INX
        CPX #10
        BEQ P_LONG_20
        JMP VQ_ENTRY
P_LONG_20:
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
        BCS P_LONG_21
        JMP VQ_CRC_NEXT
P_LONG_21:
        LDA QCRC
        EOR #$21
        STA QCRC
        LDA QCRC+1
        EOR #$10
        STA QCRC+1
VQ_CRC_NEXT:
        DEX
        BEQ P_LONG_22
        JMP VQ_CRC_BIT
P_LONG_22:
        INC QPTR
        BEQ P_LONG_23
        JMP VQ_CRC_BYTE
P_LONG_23:
        INC QPTR+1
        LDA QPTR+1
        CMP #$F0
        BEQ P_LONG_24
        JMP VQ_CRC_BYTE
P_LONG_24:
        LDA QCRC
        ORA QCRC+1
        BEQ P_LONG_25
        JMP VQ_ABSENT
P_LONG_25:
        LDA $67E4
        LDX $67E5
        LDY $67E6
        JSR VX_QUERY_ENTRY
        JMP VQ_RETURN
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
        BEQ P_LONG_26
        JMP VQ_RESTORE
P_LONG_26:
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
