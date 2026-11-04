; A RAM program that updates its own data and calls public console services.
PUTC = $7E6D
HEX = $7E7C
HOLD = $7E67
ORG $0200
start: INC count
LDA count
JSR HEX
LDA #13
JSR PUTC
LDA #10
JSR PUTC
JMP HOLD
count: BYTE 0
