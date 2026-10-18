; Invoked only after monitor verifies the complete E extension. No device I/O.
; Cold/changed component: verified 512-byte RAM image. Warm: preserve capture.
SVC_ENABLED
        STZ SVC_DESC
        STZ SVC_FLAGS
        STZ SVC_DESC+4
        STZ SVC_DESC+5
        LDA SVC_ACTIVE
                        BMI service_kernel_LONG_8
                        JMP SVC_PROBE
service_kernel_LONG_8:
        LDA SVC_READY
        AND #2
        STA SVC_READY
        STZ SVC_BUSY
        STZ SVC_DRIVER_BUSY
SVC_PROBE
        LDX #3
SVC_HEADER_LOOP
        LDA $8000,X
        CMP SVC_HEADER_MAGIC,X
                        BEQ service_kernel_LONG_19
                        JMP SVC_DONE
service_kernel_LONG_19:
        DEX
                        BMI service_kernel_LONG_21
                        JMP SVC_HEADER_LOOP
service_kernel_LONG_21:
        JSR AP_CRC_INIT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        LDY #0
SVC_CRC_LOOP
        LDA (V2_PTR),Y
        JSR AP_CRC_BYTE
        INY
                        BEQ service_kernel_LONG_31
                        JMP SVC_CRC_LOOP
service_kernel_LONG_31:
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$90
                        BEQ service_kernel_LONG_35
                        JMP SVC_CRC_LOOP
service_kernel_LONG_35:
        LDA J_CRC
        ORA J_CRC+1
                        BEQ service_kernel_LONG_38
                        JMP SVC_DONE
service_kernel_LONG_38:
        LDA SVC_ACTIVE
                        BMI service_kernel_LONG_40
                        JMP SVC_COPY
service_kernel_LONG_40:
        LDA $8FFE
        CMP SVC_SEAL
                        BEQ service_kernel_LONG_43
                        JMP SVC_COPY
service_kernel_LONG_43:
        LDA $8FFF
        CMP SVC_SEAL+1
                        BNE service_kernel_LONG_46
                        JMP SVC_PUBLISH
service_kernel_LONG_46:
SVC_COPY LDX #0
SVC_COPY_LOOP
        LDA SVC_TEMPLATE,X
        STA SVC_GATE,X
        LDA SVC_TEMPLATE+$100,X
        STA SVC_GATE+$100,X
        INX
                        BEQ service_kernel_LONG_54
                        JMP SVC_COPY_LOOP
service_kernel_LONG_54:
        LDA #$FF
        STA SVC_ACTIVE
        LDA $8FFE
        STA SVC_SEAL
        LDA $8FFF
        STA SVC_SEAL+1
SVC_PUBLISH
        LDA #3
        STA SVC_FLAGS
        LDA #$65
        STA SVC_DESC+5
        LDX #3
SVC_BANNER_CHECK
        LDA $8900,X
        CMP SVC_BANNER_MAGIC,X
                        BEQ service_kernel_LONG_70
                        JMP SVC_DONE
service_kernel_LONG_70:
        DEX
                        BMI service_kernel_LONG_72
                        JMP SVC_BANNER_CHECK
service_kernel_LONG_72:
        JSR $8904
SVC_DONE
        LDA #'V'
        STA SVC_DESC+1
        LDA #1
        STA SVC_DESC+2
        LDA #$FF
        STA SVC_DESC+6
        LDA #$66
        BIT SVC_ACTIVE
                        BMI service_kernel_LONG_83
                        JMP SVC_RAM_LIMIT
service_kernel_LONG_83:
        LDA #$64
SVC_RAM_LIMIT
        STA SVC_DESC+7
        LDA #'S'
        STA SVC_DESC
        RTS

SVC_HEADER_MAGIC DB "RC",3,7
SVC_BANNER_MAGIC DB "BT",5,3

STORAGE_ASSET_FAIL:
        LDA $7D2B
        CMP #4
                        BEQ service_kernel_LONG_97
                        JMP STORAGE_CALLED
service_kernel_LONG_97:
        JMP V2_PROMPT
STORAGE_CALLED:
        CMP #3
                        BCS service_kernel_LONG_101
                        JMP STORAGE_HANDLED
service_kernel_LONG_101:
        LDA #$80
        CLC
        RTS
STORAGE_HANDLED:
        SEC
        RTS
