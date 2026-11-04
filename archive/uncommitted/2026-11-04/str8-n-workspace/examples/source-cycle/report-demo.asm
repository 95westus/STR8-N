; Small RAM-only checksum application for listing/symbol/debugger reports.
BASE = $0200
HOLD = $7E67
RESULT = $1800
COUNT = $08
BIAS = $10
EXPECTED = $34
ORG BASE
start: SEI
CLD
JSR sum
STA RESULT
JSR check
STA RESULT+1
JMP HOLD
sum: LDX #COUNT
LDA #BIAS
.loop: CLC
ADC table-1,X
DEX
BNE .loop
RTS
check: CMP #EXPECTED
BNE .bad
LDA #$00
BRA .done
.bad: LDA #$FF
.done: RTS
table: BYTE $01,$02,$03,$04,$05,$06,$07,$08
tag: TEXT "REPORT"
BYTE $00
unused = $1234
END
