; Common native overlays. Copy this sealed 1K image from B3:8C00 to7000.
; A=0 CLOCK,1 FLASH,2 BANK MAINT,3 SRAM,4 WORK. CRC admission required.
        MODULE NATIVE_LOADER
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
NL_START:
        DB "NL",1,5,"PR05"
        JMP NL_ENTER
        DB "NB",1,2 ; sealed storage-BATCH capability required
NL_ENTER:
        SEI
        CLD
        CMP #5
        BCS NL_FAIL
        STA NL_KIND
        STA $5B02 ; return context:0=CLOCK,1=FLASH
        LDX #$FF
        TXS
        LDX #0
        LDA NL_KIND
        CMP #2
        BEQ NL_MAINT_SAVE
NL_SAVE:
        LDA $6A00,X
        STA $5D00,X
        LDA $0000,X
        STA $5C00,X
        INX
        BNE NL_SAVE
        BRA NL_SHARED_RETURN
NL_MAINT_SAVE:
        LDA $6A00,X
        STA $6500,X
        LDA $0000,X
        STA $6400,X
        INX
        BNE NL_MAINT_SAVE
        BRA NL_SELECT_APP
NL_SHARED_RETURN:
        ; Validate shared history/return code while B3 is mapped. The return
        ; entry is linked at5E00 and stored in the sealed history code region.
        STZ V2_PTR
        LDA #$90
        STA V2_PTR+1
        LDX #12
        JSR NL_CRC_PAGES
        BNE NL_FAIL
        STZ V2_PTR
        LDA #$89
        STA V2_PTR+1
        LDX #1
        JSR NL_CRC_PAGES
        BNE NL_FAIL
        LDX #0
NL_RETURN_COPY:
        LDA $9A00,X
        STA $5E00,X
        LDA $9B00,X
        STA $5F00,X
        INX
        BNE NL_RETURN_COPY
NL_SELECT_APP:
        LDX NL_KIND
        LDA NL_SOURCE_BANK,X
        JSR V2W_SELECT
        LDX NL_KIND
        LDA NL_SOURCE_PAGE,X
        STA V2_PTR+1
        STA NL_PAGE
        STZ V2_PTR
        LDA NL_SECTOR_PAGES,X
        TAX
        JSR NL_CRC_PAGES
        BNE NL_RESTORE_FAIL
        STZ V2_PTR
        LDA NL_PAGE
        STA V2_PTR+1
        LDY #7
NL_HEADER:
        CPY #3
        BEQ NL_KIND_HEADER
        LDA (V2_PTR),Y
        CMP NL_MAGIC,Y
        BNE NL_RESTORE_FAIL
        BRA NL_HEADER_NEXT
NL_KIND_HEADER:
        LDA (V2_PTR),Y
        LDX NL_KIND
        CMP NL_IMAGE_KIND,X
        BNE NL_RESTORE_FAIL
NL_HEADER_NEXT:
        DEY
        BPL NL_HEADER
        LDA $7DF9
        CMP #$B7
        BNE NL_BATCH_READY
        LDA NL_KIND
        CMP #3
        BCC NL_BATCH_READY
        LDY #25
NL_BATCH_STORAGE:
        LDA NL_STORAGE_BATCH-22,Y
        CMP (V2_PTR),Y
        BNE NL_RESTORE_FAIL
        DEY
        CPY #21
        BNE NL_BATCH_STORAGE
NL_BATCH_READY:
        LDY #8
        LDA (V2_PTR),Y
        STA NL_LEFT
        INY
        LDA (V2_PTR),Y
        STA NL_LEFT+1
        BEQ NL_RESTORE_FAIL
        LDX NL_KIND
        CMP NL_MAX_HIGH,X
        BCC NL_LENGTH_OK
        BNE NL_RESTORE_FAIL
        LDA NL_LEFT
        CMP #$DF
        BCS NL_RESTORE_FAIL
NL_LENGTH_OK:
        LDY #10
        LDA (V2_PTR),Y
        BNE NL_RESTORE_FAIL
        INY
        LDA (V2_PTR),Y
        CMP #$20
        BNE NL_RESTORE_FAIL
        ; Exact-byte copy; never read across the allocated app slot.
        LDA #32
        STA V2_PTR
        STZ V2_BUF_PTR
        LDA #$20
        STA V2_BUF_PTR+1
NL_COPY:
        LDA (V2_PTR)
        STA (V2_BUF_PTR)
        INC V2_PTR
        BNE NL_COPY_DST
        INC V2_PTR+1
NL_COPY_DST:
        INC V2_BUF_PTR
        BNE NL_COPY_LEFT
        INC V2_BUF_PTR+1
NL_COPY_LEFT:
        LDA NL_LEFT
        BNE NL_COPY_LOW
        DEC NL_LEFT+1
NL_COPY_LOW:
        DEC NL_LEFT
        LDA NL_LEFT
        ORA NL_LEFT+1
        BNE NL_COPY
        LDA #3
        JSR V2W_SELECT
        LDA NL_KIND
        BNE NL_GO
        ; CLOCK exclusively borrows the b35 gateway/history scratch layout.
        LDX #0
NL_GATE_COPY:
        LDA $8A00,X
        STA $6500,X
        LDA $8B00,X
        STA $6600,X
        INX
        BNE NL_GATE_COPY
        STZ V2_PTR
        LDA #$65
        STA V2_PTR+1
        LDX #2
        JSR NL_CRC_PAGES
        BNE NL_RESTORE_FAIL
        STZ V2_PTR
        LDA #$90
        STA V2_PTR+1
        LDX #12
        JSR NL_CRC_PAGES
        BNE NL_RESTORE_FAIL
        LDX #0
NL_ZERO:
        STZ $6B00,X
        STZ $6C00,X
        STZ $6D00,X
        INX
        BNE NL_ZERO
        LDX #0
NL_ZERO_GATE_STATE:
        STZ $6660,X
        INX
        CPX #$A0
        BCC NL_ZERO_GATE_STATE
        LDA #$AD
        STA $66B0
        LDA #$8D
        STA $66B4
        LDA #$60
        STA $66B3
        STA $66B7
        ; Keep6500 gateway code; only its private state starts6660.
        LDX #7
NL_DISCOVERY:
        LDA NL_SV,X
        STA $7D04,X
        LDA NL_PJ,X
        STA $7D19,X
        DEX
        BPL NL_DISCOVERY
        STZ $7D22
        LDA #1
        STA $7D2A
NL_GO:
        JMP $2000
NL_RESTORE_FAIL:
        ; Private queue error is ignored when inactive, and reset by capture.
        ; Set both possible live/escrow locations before any return route.
        LDA #2
        STA $6AF5
        STA $5DF5
        LDA #3
        JSR V2W_SELECT
        LDX #<NL_ERROR
        LDY #>NL_ERROR
        JSR BOOT_PRINT
        LDA NL_KIND
        CMP #2
        BEQ NL_MAINT_FAILED
        JMP $5E00
NL_MAINT_FAILED:
        ; MAINT has not executed, so its special return image is unavailable.
        ; Restore the caller context and use the trusted Foundation recovery.
        LDX #0
NL_MAINT_RESTORE:
        LDA $6400,X
        STA $0000,X
        LDA $6500,X
        STA $6A00,X
        INX
        CPX #$E0
        BCC NL_MAINT_RESTORE
        BRA NL_FAIL
NL_FAIL:
        STZ $7DF9
        JMP BOOT_RECOVERY
NL_CRC_PAGES:
        ; ROM F is absent while B2 is mapped: every CRC instruction stays RAM.
        LDA #$FF
        STA J_CRC
        STA J_CRC+1
        LDY #0
NL_CRC_BYTE:
        LDA (V2_PTR),Y
        EOR J_CRC+1
        STA J_CRC+1
        PHX
        LDX #8
NL_CRC_BIT:
        ASL J_CRC
        ROL J_CRC+1
        BCC NL_CRC_NEXT_BIT
        LDA J_CRC
        EOR #$21
        STA J_CRC
        LDA J_CRC+1
        EOR #$10
        STA J_CRC+1
NL_CRC_NEXT_BIT:
        DEX
        BNE NL_CRC_BIT
        PLX
        INY
        BNE NL_CRC_BYTE
        INC V2_PTR+1
        DEX
        BNE NL_CRC_BYTE
        LDA J_CRC
        ORA J_CRC+1
        RTS
NL_KIND: DB 0
NL_PAGE: DB 0
NL_LEFT: DB 0,0
NL_STORAGE_BATCH: DB "BQ",1,1
NL_MAGIC: DB "RP",1,0,"PR05"
NL_SOURCE_BANK: DB 2,2,1,1,1
NL_SOURCE_PAGE: DB $B0,$E0,$80,$B0,$B0
NL_SECTOR_PAGES: DB 48,32,48,48,48
NL_MAX_HIGH: DB $2F,$1F,$2F,$2F,$2F
NL_IMAGE_KIND: DB 0,1,2,3,3
NL_SV: DB "SV",1,1,0,$65,$FF,$64
NL_PJ: DB "PJ",1,1,4,$90,0,$6B
NL_ERROR: DB "REFUSED: native",13,10,0
NL_END:
        ENDMOD
        END
