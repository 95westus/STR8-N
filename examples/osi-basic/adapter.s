; STR8-N Foundation adapter, Copyright (c) 2026 95west.us/wlp1963; MIT.
; Engine/reconstruction copyrights and terms remain in the adjacent notices.
; No private ROM calls. This runs in B0 with the initialized public RAM facade.
; 65C02 or 65C816 emulation only; IRQ masked, D/DBR/PBR zero on 816.
.segment "HEADER"
ENTRY:
    sei
    cld
    ldx #3
@abi:
    lda $7E60,x
    cmp ABI_ID,x
    bne ABI_BAD
    dex
    bpl @abi
    lda #0
    sta KEY_READY
    ldx #0
@title:
    lda TITLE,x
    beq @start
    jsr IO_PUTC
    inx
    bne @title
@start:
    jmp PR_WRITTEN_BY
ABI_BAD:
    jmp ABI_BAD

.segment "EXTRA"
KEY_READY = $0200
KEY_BYTE = $0201
IO_PUTC:
    php
    pha
    txa
    pha
    tya
    pha
    cld
    ; Recover the original A without disturbing the saved registers/flags.
    tsx
    lda $0103,x
    jsr $7E6D
    pla
    tay
    pla
    tax
    pla
    plp
    rts
IO_GETC:
    txa
    pha
    tya
    pha
    lda KEY_READY
    beq @read
    lda #0
    sta KEY_READY
    lda KEY_BYTE
    jmp @key
@read:
    jsr $7E70
@key:
    cmp #27
    beq IO_EXIT
    sta KEY_BYTE
    pla
    tay
    pla
    tax
    lda KEY_BYTE
    rts
; Return 3 for Ctrl-C, zero otherwise. Preserve pending ordinary input.
IO_CHECK:
    txa
    pha
    tya
    pha
    lda KEY_READY
    bne @none
    jsr $7E73
    bcc @none
    cmp #27
    beq IO_EXIT
    cmp #3
    beq @break
    sta KEY_BYTE
    lda #1
    sta KEY_READY
@none:
    lda #0
@break:
    sta CHECK_RESULT
    pla
    tay
    pla
    tax
    lda CHECK_RESULT
    rts
CHECK_RESULT = $0202
IO_EXIT:
    jmp $7E64
IO_UNAVAILABLE:
    jmp IQERR
ABI_ID: .byte "RA",1,$0D
TITLE:
    .byte "STR8-N example: OSI BASIC / BASE1 PR05",13,10
    .byte "BASIC (c) 1977 Microsoft; reconstruction Michael Steil and contributors",13,10
    .byte "Foundation adapter (c) 2026 95west.us/wlp1963; MIT",13,10
    .byte "ESC restarts Foundation; LOAD/SAVE devices unavailable.",13,10,0
