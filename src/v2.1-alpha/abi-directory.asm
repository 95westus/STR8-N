; Offline alpha foundation. No permanent anchor or firmware placement yet.
; 65C02-compatible foreground calls: SEI, CLD; 816 E=1, D=DBR=PBR=0.
; Lookup: A=service, X=operation (0=record), Y=minimum interface version.
; Returns A=status, C=success, X/Y=address low/high on success.
; Clobbers $D0-$D7 and unspecified flags/registers. Never probes hardware.
        MODULE ABI_DIRECTORY
        XDEF ABI_END
        CODE
ABI_HEADER:
        DB "AD",1,8,ABI_SERVICE_COUNT,0
        DW ABI_LOOKUP,ABI_RECORDS,ABI_END-ABI_HEADER
        DB 24,0,0,0
ABI_LOOKUP:
        STA $D2
        STX $D3
        STY $D4
        JSR ABI_CORE_CHECK
        BCC ABI_BAD_ABI
        LDA $D2
        BEQ ABI_BAD_REQUEST
        CMP #ABI_SERVICE_COUNT+1
        BCS ABI_BAD_REQUEST
        DEC A
        ASL A
        ASL A
        ASL A
        TAX
        STX $D7
        LDA ABI_RECORDS,X
        CMP $D4
        BCC ABI_BAD_VERSION
        LDA $D3
        BEQ ABI_RECORD_ADDRESS
        CMP ABI_RECORDS+4,X
        BEQ ABI_OPERATION_OK
        BCS ABI_BAD_REQUEST
ABI_OPERATION_OK:
        LDA ABI_RECORDS+1,X
        BEQ ABI_SIGNATURE_CHECK
        STA $D4
        JSR ABI_SV_CHECK
        BCC ABI_BAD_ABI
        LDA $7D07
        AND $D4
        CMP $D4
        BNE ABI_UNAVAILABLE
ABI_SIGNATURE_CHECK:
        LDX $D7
        LDA ABI_RECORDS+2,X
        BEQ ABI_TARGET
        DEC A
        ASL A
        STA $D4
        ASL A
        CLC
        ADC $D4
        TAX
        LDA ABI_SIGNATURES,X
        STA $D5
        LDA ABI_SIGNATURES+1,X
        STA $D6
        LDY #0
ABI_SIGNATURE_BYTE:
        LDA ABI_SIGNATURES+2,X
        CMP ($D5),Y
        BNE ABI_NOT_READY
        INX
        INY
        CPY #4
        BNE ABI_SIGNATURE_BYTE
ABI_TARGET:
        LDA $D2
        CMP #4
        BNE ABI_TARGET_ADDRESS
        LDA $D3
        CMP #2
        BNE ABI_TARGET_ADDRESS
        LDA $7D01
        CMP #$16
        BNE ABI_UNAVAILABLE
ABI_TARGET_ADDRESS:
        LDX $D7
        LDA ABI_RECORDS+6,X
        STA $D5
        LDA ABI_RECORDS+7,X
        STA $D6
        LDA $D3
        DEC A
        ASL A
        TAY
        LDA ($D5),Y
        TAX
        INY
        LDA ($D5),Y
        TAY
ABI_OK:
        LDA #0
        SEC
        RTS
ABI_RECORD_ADDRESS:
        TXA
        CLC
        ADC #<ABI_RECORDS
        TAX
        LDA #>ABI_RECORDS
        ADC #0
        TAY
        BRA ABI_OK
ABI_UNAVAILABLE:
        LDA #$80
        BRA ABI_FAILURE
ABI_BAD_ABI:
        LDA #$81
        BRA ABI_FAILURE
ABI_BAD_REQUEST:
        LDA #$82
        BRA ABI_FAILURE
ABI_BAD_VERSION:
        LDA #$83
        BRA ABI_FAILURE
ABI_NOT_READY:
        LDA #$84
ABI_FAILURE:
        CLC
        RTS

ABI_CORE_CHECK:
        LDX #3
ABI_RA_BYTE:
        LDA $7E60,X
        CMP ABI_RA_EXPECTED,X
        BNE ABI_CHECK_FAIL
        DEX
        BPL ABI_RA_BYTE
        LDA $7D01
        CMP #2
        BEQ ABI_CHECK_OK
        CMP #$16
        BEQ ABI_CHECK_OK
ABI_CHECK_FAIL:
        CLC
        RTS
ABI_CHECK_OK:
        SEC
        RTS
ABI_RA_EXPECTED: DB "RA",1,13

; Validate SV before examining any optional gateway/signature RAM.
ABI_SV_CHECK:
        LDX #2
ABI_SV_BYTE:
        LDA $7D04,X
        CMP ABI_SV_EXPECTED,X
        BNE ABI_CHECK_FAIL
        DEX
        BPL ABI_SV_BYTE
        LDA $7D07
        AND #$F0
        BNE ABI_CHECK_FAIL
        LDA $7D07
        BEQ ABI_SV_OFF
        LDA $7D08
        BNE ABI_CHECK_FAIL
        LDA $7D09
        CMP #$65
        BNE ABI_CHECK_FAIL
        LDA $7D0A
        CMP #$FF
        BNE ABI_CHECK_FAIL
        LDA $7D0B
        CMP #$64
        BEQ ABI_CHECK_OK
        BRA ABI_CHECK_FAIL
ABI_SV_OFF:
        LDA $7D08
        ORA $7D09
        BNE ABI_CHECK_FAIL
        LDA $7D0A
        CMP #$FF
        BNE ABI_CHECK_FAIL
        LDA $7D0B
        CMP #$66
        BEQ ABI_CHECK_OK
        BRA ABI_CHECK_FAIL
ABI_SV_EXPECTED: DB "SV",1

; A/X=caller-owned result buffer low/high, Y=capacity (minimum 24).
; Output bounds and module overlap are checked before any output write.
ABI_SYSTEM_QUERY:
        STA $D0
        STX $D1
        CPY #24
        BCC ABI_BAD_REQUEST
        JSR ABI_CORE_CHECK
        BCC ABI_BAD_ABI
        LDA $D1
        CMP #2
        BCC ABI_BAD_REQUEST
        CMP #$65
        BCS ABI_BAD_REQUEST
        LDA $D0
        CLC
        ADC #23
        STA $D5
        LDA $D1
        ADC #0
        STA $D6
        CMP #$65
        BCS ABI_BAD_REQUEST
        LDA $D1
        CMP #>ABI_END
        BCC ABI_OVERLAP_END
        BNE ABI_BUFFER_OK
        LDA $D0
        CMP #<ABI_END
        BCS ABI_BUFFER_OK
ABI_OVERLAP_END:
        LDA $D6
        CMP #>ABI_HEADER
        BCC ABI_BUFFER_OK
        BNE ABI_BAD_REQUEST
        LDA $D5
        CMP #<ABI_HEADER
        BCS ABI_BAD_REQUEST
ABI_BUFFER_OK:
        LDY #23
ABI_SYSTEM_COPY:
        LDA ABI_SYSTEM_TEMPLATE,Y
        STA ($D0),Y
        DEY
        BPL ABI_SYSTEM_COPY
        LDA $7D01
        LDY #2
        STA ($D0),Y
        LDX #$11
        CMP #$16
        BNE ABI_EFFECTIVE
        LDX #$17
ABI_EFFECTIVE:
        TXA
        LDY #5
        STA ($D0),Y
        LDA $7D02
        BNE ABI_SYSTEM_SERVICES
        LDA #1
        LDY #7
        STA ($D0),Y
        LDA #0
        INY
        STA ($D0),Y
ABI_SYSTEM_SERVICES:
        JSR ABI_SV_CHECK
        BCC ABI_OK
        LDY #10
        LDA $7D07
        STA ($D0),Y
        BEQ ABI_SYSTEM_LIMIT
        LDA $6664
        AND #3
        INY
        STA ($D0),Y
ABI_SYSTEM_LIMIT:
        LDA $7D0A
        LDY #20
        STA ($D0),Y
        LDA $7D0B
        INY
        STA ($D0),Y
        JMP ABI_OK
ABI_SYSTEM_TEMPLATE:
        DB 1,24,0,1,$17,0,1,0,$FF,1,0,0,ABI_SERVICE_COUNT,1,8,0
        DW ABI_LOOKUP,ABI_HEADER,0
        DB 13,0
        INCLUDE "abi-records.inc"
ABI_END:
        ENDMOD
        END
