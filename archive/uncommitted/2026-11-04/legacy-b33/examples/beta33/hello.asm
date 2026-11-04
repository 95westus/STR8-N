; Assemble on-board at ASM>. Output is staged at RAM $0200.
; Public RAM ABI works from any flash bank; 816 callers use emulation mode.
PUTC = $7E6D
HOLD = $7E67
ORG $0200
LDA #'O'
JSR PUTC
LDA #'K'
JSR PUTC
LDA #13
JSR PUTC
LDA #10
JSR PUTC
JMP HOLD
