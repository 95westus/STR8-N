; Immutable E code; static directory in pinned manager RAM, dynamic records
; at 7600. Caller has initialized the manager and mapped its resident bank.
                        MODULE V2_SERVICES
                        XDEF SERVICE_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "service-directory.inc"
                        CODE
SERVICE_LOOKUP_ENTRY:   JMP SERVICE_LOOKUP
SERVICE_REGISTER_ENTRY: JMP SERVICE_REGISTER
SERVICE_LOOKUP:         STA V2_ADDR
                        STX V2_ADDR+1
                        STY MG_VERSION
                        STZ V2_LAST
                        STZ V2_COUNT
                        LDA #<MG_STATIC_TABLE
                        STA V2_FLASH_PTR
                        LDA #>MG_STATIC_TABLE
                        STA V2_FLASH_PTR+1
                        LDA #MG_STATIC_BYTES
                        STA V2_DIGIT_LIMIT
LOOKUP_BEGIN:           STZ MG_INDEX
LOOKUP_NEXT:            LDA MG_INDEX
                        CMP V2_DIGIT_LIMIT
                        BCS LOOKUP_END_TABLE
                        LDY #$00
                        LDA (V2_FLASH_PTR),Y
                        STA V2_PTR
                        INY
                        LDA (V2_FLASH_PTR),Y
                        STA V2_PTR+1
                        LDY #$00
LOOKUP_CHAR:            LDA (V2_PTR),Y
                        CMP (V2_ADDR),Y
                        BNE LOOKUP_SKIP
                        CMP #$00
                        BEQ LOOKUP_NAME
                        INY
                        CPY #$20
                        BNE LOOKUP_CHAR
LOOKUP_SKIP:            LDA V2_FLASH_PTR
                        CLC
                        ADC #$06
                        STA V2_FLASH_PTR
                        BCC LOOKUP_INDEX
                        INC V2_FLASH_PTR+1
LOOKUP_INDEX:           LDA MG_INDEX
                        CLC
                        ADC #$06
                        STA MG_INDEX
                        BRA LOOKUP_NEXT
LOOKUP_NAME:            LDY #$02
                        LDA (V2_FLASH_PTR),Y
                        CMP MG_VERSION
                        BEQ LOOKUP_FOUND
                        INC V2_LAST
                        BRA LOOKUP_SKIP
LOOKUP_FOUND:           LDY #$05
                        LDA (V2_FLASH_PTR),Y
                        PHA
                        DEY
                        LDA (V2_FLASH_PTR),Y
                        PHA
                        DEY
                        LDA (V2_FLASH_PTR),Y
                        TAY
                        PLA
                        PLX
                        SEC
                        RTS
LOOKUP_END_TABLE:       LDA V2_COUNT
                        BNE LOOKUP_MISSING
                        INC V2_COUNT
                        LDA MG_DYNAMIC_COUNT
                        CMP #MG_DYNAMIC_CAPACITY*6+1
                        BCS SERVICE_BAD
                        STA V2_DIGIT_LIMIT
                        LDA #<MG_DYNAMIC_TABLE
                        STA V2_FLASH_PTR
                        LDA #>MG_DYNAMIC_TABLE
                        STA V2_FLASH_PTR+1
                        BRA LOOKUP_BEGIN
LOOKUP_MISSING:         LDA V2_LAST
                        BNE SERVICE_DUPLICATE
SERVICE_BAD:            LDA #$01
                        BRA SERVICE_FAIL
SERVICE_DUPLICATE:      LDA #$02
                        BRA SERVICE_FAIL
SERVICE_FULL:           LDA #$03
SERVICE_FAIL:           CLC
                        RTS

SERVICE_REGISTER:      CPY #$00
                        BNE SERVICE_BAD
                        STA V2_BUF_PTR
                        STX V2_BUF_PTR+1
                        LDA MG_READY
                        CMP #$01
                        BNE SERVICE_BAD
                        LDA V2_BUF_PTR
; The temporary six-byte descriptor must fit wholly within non-I/O memory.
                        CPX #$02
                        BCC SERVICE_BAD
                        CPX #$79
                        BCS DESCRIPTOR_ROM
                        CPX #$78
                        BNE DESCRIPTOR_OK
                        CMP #$FB
                        BCC DESCRIPTOR_OK
                        BRA SERVICE_BAD
DESCRIPTOR_ROM:
                        CPX #$80
                        BCC SERVICE_BAD
                        CPX #$FF
                        BNE DESCRIPTOR_OK
                        CMP #$FB
                        BCS SERVICE_BAD
DESCRIPTOR_OK:          LDY #$02
                        LDA (V2_BUF_PTR),Y
                        BEQ SERVICE_BAD
                        INY
                        LDA (V2_BUF_PTR),Y
                        CMP #$02
                        BCS SERVICE_BAD
                        INY
                        LDA (V2_BUF_PTR),Y
                        PHA
                        INY
                        LDA (V2_BUF_PTR),Y
                        TAX
                        PLA
                        JSR PINNED_POINTER
                        BCC SERVICE_BAD
                        LDY #$00
                        LDA (V2_BUF_PTR),Y
                        STA V2_ADDR
                        INY
                        LDA (V2_BUF_PTR),Y
                        STA V2_ADDR+1
                        TAX
                        LDA V2_ADDR
                        JSR PINNED_POINTER
                        BCC SERVICE_BAD
                        LDY #$00
NAME_BYTE:              LDA (V2_ADDR),Y
                        BEQ NAME_END
                        CMP #$21
                        BCC SERVICE_BAD
                        CMP #$7F
                        BCS SERVICE_BAD
                        INY
                        CPY #$20
                        BCS SERVICE_BAD
                        BRA NAME_BYTE
NAME_END:               CPY #$00
                        BEQ SERVICE_BAD
; Validate the terminator address too; no wrap or boundary-crossing names.
                        TYA
                        CLC
                        ADC V2_ADDR
                        PHA
                        LDA V2_ADDR+1
                        ADC #$00
                        TAX
                        PLA
                        BCS SERVICE_BAD
                        JSR PINNED_POINTER
                        BCC SERVICE_BAD
                        LDA MG_DYNAMIC_COUNT
                        CMP #MG_DYNAMIC_CAPACITY*6+1
                        BCS SERVICE_BAD
COUNT_VALIDATE:         CMP #$00
                        BEQ COUNT_VALID
                        SEC
                        SBC #$06
                        BCC SERVICE_BAD
                        BRA COUNT_VALIDATE
COUNT_VALID:
                        LDY #$02
                        LDA (V2_BUF_PTR),Y
                        TAY
                        LDA V2_ADDR
                        LDX V2_ADDR+1
                        JSR SERVICE_LOOKUP
                        BCS SERVICE_DUPLICATE
; A=2 means this name exists with another version, which is allowed.
                        LDX MG_DYNAMIC_COUNT
                        CPX #MG_DYNAMIC_CAPACITY*6
                        BCS SERVICE_FULL
                        LDY #$00
COPY_RECORD:            LDA (V2_BUF_PTR),Y
                        STA MG_DYNAMIC_TABLE,X
                        INX
                        INY
                        CPY #$06
                        BNE COPY_RECORD
                        STX MG_DYNAMIC_COUNT
                        LDA #$00
                        SEC
                        RTS
; Name/target: overlay RAM, reserved module RAM, or resident B..F ROM.
; Public RAM console facade is deliberately reached through static lookup.
PINNED_POINTER:        CPX #$B0
                        BCS PINNED_OK
                        CPX #$58
                        BCC PINNED_BAD
                        CPX #$60
                        BCC PINNED_OK
                        CPX #$71
                        BCC PINNED_BAD
                        CPX #$79
                        BCS PINNED_BAD
PINNED_OK:              SEC
                        RTS
PINNED_BAD:             CLC
                        RTS
SERVICE_END:
                        ENDMOD
                        END
