; Temporary RAM-only ABI/mode observation, identical helper on either CPU.
; The 816 branch SEC/XCE can only force E=1; it never enters native mode.
        MODULE CPU_MODE
        XDEF START,PROBE_END
        CODE
START:  PHP
        PLA
        STA $2446
        SEI
        CLD
        LDA $7D01
        STA $2440
        CMP #$16
        BEQ CPU816
        LDA #$FF
        STA $2441
        STZ $2442
        STZ $2443
        STZ $2444
        STZ $2445
        BRA QUERY
CPU816: SEC
        DB $FB,$EA       ; XCE; NOP. C receives prior E, new E is 1.
        PHP
        PLA
        AND #1
        STA $2441
        DB $8B           ; PHB, valid in 816 emulation mode
        PLA
        STA $2442
        DB $4B           ; PHK
        PLA
        STA $2443
        DB $0B           ; PHD: two bytes even in emulation mode
        PLA
        STA $2444
        PLA
        STA $2445
QUERY:  JSR $7E85
        STA $2447
        STX $2448
        STY $2449
        JSR $7E88
        STA $244A
        STX $244B
        STY $244C
        LDA #$A5
        STA $244D
        JMP $7E67
PROBE_END:
        END
