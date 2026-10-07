; Invoked only after monitor verifies the complete E extension. No device I/O.
; Cold/changed component: verified 512-byte RAM image. Warm: preserve capture.
SVC_INIT
        STZ SVC_DESC
        STZ SVC_FLAGS
        STZ SVC_DESC+4
        STZ SVC_DESC+5
        LDA SVC_ACTIVE
        BPL SVC_PROBE
        LDA SVC_READY
        AND #2
        STA SVC_READY
        STZ SVC_BUSY
        STZ SVC_DRIVER_BUSY
SVC_PROBE
        LDA $8000
        CMP #'R'
        BNE SVC_DONE
        LDA $8001
        CMP #'C'
        BNE SVC_DONE
        LDA $8002
        CMP #1
        BNE SVC_DONE
        LDA $8003
        CMP #5
        BNE SVC_DONE
        JSR AP_CRC_INIT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        LDY #0
SVC_CRC_LOOP
        LDA (V2_PTR),Y
        JSR AP_CRC_BYTE
        INY
        BNE SVC_CRC_LOOP
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$90
        BNE SVC_CRC_LOOP
        LDA J_CRC
        ORA J_CRC+1
        BNE SVC_DONE
        LDA SVC_ACTIVE
        BPL SVC_COPY
        LDA $8FFE
        CMP SVC_SEAL
        BNE SVC_COPY
        LDA $8FFF
        CMP SVC_SEAL+1
        BEQ SVC_PUBLISH
SVC_COPY LDX #0
SVC_COPY_LOOP
        LDA SVC_TEMPLATE,X
        STA SVC_GATE,X
        LDA SVC_TEMPLATE+$100,X
        STA SVC_GATE+$100,X
        INX
        BNE SVC_COPY_LOOP
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
SVC_DONE
        LDA #'V'
        STA SVC_DESC+1
        LDA #1
        STA SVC_DESC+2
        LDA #$FF
        STA SVC_DESC+6
        LDA #$66
        BIT SVC_ACTIVE
        BPL SVC_RAM_LIMIT
        LDA #$64
SVC_RAM_LIMIT
        STA SVC_DESC+7
        LDA #'S'
        STA SVC_DESC
        RTS
