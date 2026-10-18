; RAM-only 4 KiB flash-sector reader. No flash command writes.
; $3000 = bank 0..3, $3001 = sector page $80,$90,...,$F0.
; $3002 = status (0 success, 9 invalid), $3003 = completed pages.
; $3004/$3005 = bank PCR before selection / after restoration.
; Copies to $2000-$2FFF, preserves the complete bank PCR and CPU flags.
        MODULE SOAK_SECTOR_READ
        XDEF START
        XDEF APP_END
        CODE
START:  PHP
        SEI
        CLD
        STZ $3003
        LDA #9
        STA $3002
        LDA $3000
        CMP #4
        BCS DONE
        LDA $3001
        CMP #$80
        BCC DONE
        AND #$0F
        BNE DONE
        LDA $7FEC
        STA $3004
        STA OLD_PCR
        AND #$11
        LDX $3000
        ORA BANK_BITS,X
        STA $7FEC
        LDA $3001
        STA READ_BYTE+2
        LDA #$20
        STA WRITE_BYTE+2
        LDY #0
READ_BYTE:
        LDA $8000,Y
WRITE_BYTE:
        STA $2000,Y
        INY
        BNE READ_BYTE
        INC READ_BYTE+2
        INC WRITE_BYTE+2
        INC $3003
        LDA $3003
        CMP #16
        BNE READ_BYTE
        LDA OLD_PCR
        STA $7FEC
        STZ $3002
        LDA $7FEC
        STA $3005
DONE:   PLP
        JMP $7E67
OLD_PCR DB 0
BANK_BITS DB $CC,$CE,$EC,$EE
APP_END:
        ENDMOD
        END
