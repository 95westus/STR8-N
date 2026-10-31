; Returning PROGRAM example for STR8N-F BASE1/PR05 + MON gB / SP g2.
; Assemble at $3000; store $3000-$301F as kind PROGRAM with entry $3000.
; BATCH STORE still asks for live YES. The queue never supplies it.
;   EDU ON
;   BATCH S P AUTO 3000 301F DEMO
;   BATCH R P DEMO;V
; A real wide program can use the same prefix through $66FF.
        CODE
        ORG $3000
ENTRY:  BRA START
        DB "BT",1,2,"PR05"   ; BT/1/2 explicitly promises PR05/HOLD return
START:  LDA #'S'
        JSR $7E6D              ; public RAM PUTC
        LDA #13
        JSR $7E6D
        LDA #10
        JSR $7E6D
        JMP $7E67              ; public HOLD; rejoin an admitted BATCH
        DS 32-(*-ENTRY),$EA
        END
