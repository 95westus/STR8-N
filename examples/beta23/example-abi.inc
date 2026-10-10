; Shared 65C02 helpers. Included after application code/data.
; Caller enters with SEI/CLD; 816 users must already be in the qualified E=1 profile.
PUTC EQU $7E6D
HEX EQU $7E7C
NL EQU $7E7F
HOLD EQU $7E67
TEXT EQU $D0
EX_CHECK_RA:
        LDX #3
EX_RA_LOOP:
        LDA $7E60,X
        CMP EX_RA_EXPECTED,X
        BNE EX_NOT_FOUND
        DEX
        BPL EX_RA_LOOP
        SEC
        RTS
; A = required SV capability. Never inspect service RAM before this succeeds.
EX_CHECK_SV:
        STA EX_CAP
        LDX #7
EX_SV_LOOP:
        LDA $7D04,X
        CPX #3
        BNE EX_SV_BYTE
        AND EX_CAP
        CMP EX_CAP
        BNE EX_NOT_FOUND
        BRA EX_SV_NEXT
EX_SV_BYTE:
        CMP EX_SV_EXPECTED,X
        BNE EX_NOT_FOUND
EX_SV_NEXT:
        DEX
        BPL EX_SV_LOOP
        SEC
        RTS
EX_NOT_FOUND:
        LDA #$80
        CLC
        RTS
; No console/HOLD call through an unverified RAM ABI. Physical RESET recovers.
EX_NO_ABI:
        BRA EX_NO_ABI
; X/Y = zero-terminated string address; uses D0-D1 and Y.
EX_PRINT:
        STX TEXT
        STY TEXT+1
        LDY #0
EX_PRINT_LOOP:
        LDA (TEXT),Y
        BEQ EX_PRINT_DONE
        JSR PUTC
        INY
        BRA EX_PRINT_LOOP
EX_PRINT_DONE:
        RTS
EX_RA_EXPECTED DB "RA",1,13
EX_SV_EXPECTED DB "SV",1,0,0,$65,$FF,$64
EX_CAP DB 0
