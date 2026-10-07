; 816-only RAM fixture: capture G entry E/P/DBR/PBR/D/S before RTC calls.
; Load at $2400 only after monitor CPU query confirms $16. Output $2500-$2507.
; Temporarily enters native mode to observe E, then restores canonical E=1,
; D=DBR=0 before HOLD. No RTC, VIA, flash, or interrupt-vector access.
        CHIP 65816
        MODULE RTC_816_STATE
        XDEF START
        XDEF PROBE_END
STATE EQU $2500
        CODE
        LONGA OFF
        LONGI OFF
START   PHP
        SEI
        SEP #$30
        CLD
        ; Normalize DBR before storing, while preserving its incoming value.
        PHB
        LDA #0
        PHA
        PLB
        PLA
        STA STATE+2
        PHK
        PLA
        STA STATE+3
        PHD
        PLA
        STA STATE+4
        PLA
        STA STATE+5
        PLA
        STA STATE+1
        CLC
        XCE
        LDA #0
        ADC #0
        STA STATE
        SEC
        XCE
        TSC
        STA STATE+6
        XBA
        STA STATE+7
        ; TCD always transfers full C; clear both accumulator halves in E=1.
        LDA #0
        XBA
        LDA #0
        TCD
        ; JML guarantees the bank-zero RAM HOLD target.
        JML $007E67
PROBE_END
        ENDMOD
        END
