; Optional resident-bank E carrier. No reset-time dependency on this image.
                        MODULE V2_MANAGER_ROM
                        XDEF MG_ROM_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "manager-build.inc"
                        CODE
MG_ROM_DESCRIPTOR:      DB "EM",$01,$01
                        DW MG_CORE_CRC,MG_RUNTIME_ID
MG_ROM_INIT_ENTRY:      JMP MG_BOOT
MG_ROM_DISPATCH_ENTRY:  JMP STR8MGR_DISPATCH
MG_ROM_LOOKUP_ENTRY:    JMP STR8MGR_LOOKUP
; Verify the exact F binding before using generated private host services.
; FFD0-FFDF is mutable configuration and deliberately excluded.
MG_BOOT:                LDA #$FF
                        STA V2_BUF_PTR
                        STA V2_BUF_PTR+1
                        STZ V2_PTR
                        LDA #$F0
                        STA V2_PTR+1
                        LDA #$D0
                        STA V2_FLASH_PTR
                        LDA #$FF
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA #$E0
                        STA V2_PTR
                        STZ V2_FLASH_PTR
                        STZ V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA V2_BUF_PTR
                        CMP #<MG_CORE_CRC
                        BNE MG_BOOT_FAIL
                        LDA V2_BUF_PTR+1
                        CMP #>MG_CORE_CRC
                        BNE MG_BOOT_FAIL
                        LDA MG_READY
                        CMP #$01
                        BNE MG_BOOT_COPY
                        LDA MG_IMAGE_ID
                        CMP #<MG_RUNTIME_ID
                        BNE MG_BOOT_COPY
                        LDA MG_IMAGE_ID+1
                        CMP #>MG_RUNTIME_ID
                        BNE MG_BOOT_COPY
                        JSR CF_LOAD
                        SEC
                        RTS
MG_BOOT_FAIL:           STZ MG_NAMED_COUNT
                        STZ MG_DYNAMIC_COUNT
                        STZ MG_READY
                        STZ MG_COUNT
                        CLC
                        RTS
MG_BOOT_COPY:           STZ MG_NAMED_COUNT
                        STZ MG_DYNAMIC_COUNT
                        STZ MG_READY
                        STZ MG_COUNT
                        LDA #$FF
                        STA V2_BUF_PTR
                        STA V2_BUF_PTR+1
                        LDA #<MG_IMAGE
                        STA V2_PTR
                        LDA #>MG_IMAGE
                        STA V2_PTR+1
                        LDA #<(MG_IMAGE+MG_SIZE)
                        STA V2_FLASH_PTR
                        LDA #>(MG_IMAGE+MG_SIZE)
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA #$00
                        STA V2_PTR
                        LDA #>RTS_ROM_START
                        STA V2_PTR+1
                        LDA #<RTS_ROM_START
                        STA V2_PTR
                        LDA #<(RTS_ROM_START+RTS_SIZE)
                        STA V2_FLASH_PTR
                        LDA #>(RTS_ROM_START+RTS_SIZE)
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA #<CF_ROM_START
                        STA V2_PTR
                        LDA #>CF_ROM_START
                        STA V2_PTR+1
                        LDA #<CF_ROM_END
                        STA V2_FLASH_PTR
                        LDA #>CF_ROM_END
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA #<MG_SERVICE_LOOKUP_ROM
                        STA V2_PTR
                        LDA #>MG_SERVICE_LOOKUP_ROM
                        STA V2_PTR+1
                        LDA #<MG_SERVICE_ROM_END
                        STA V2_FLASH_PTR
                        LDA #>MG_SERVICE_ROM_END
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA #<AL_ROM_START
                        STA V2_PTR
                        LDA #>AL_ROM_START
                        STA V2_PTR+1
                        LDA #<AL_ROM_END
                        STA V2_FLASH_PTR
                        LDA #>AL_ROM_END
                        STA V2_FLASH_PTR+1
                        JSR MG_CRC_RANGE
                        LDA V2_BUF_PTR
                        CMP #<MG_RUNTIME_ID
                        BNE MG_BOOT_FAIL
                        LDA V2_BUF_PTR+1
                        CMP #>MG_RUNTIME_ID
                        BNE MG_BOOT_FAIL
                        INCLUDE "manager-copy.inc"
                        JSR STR8MGR_INIT
                        JSR RTS_INIT
                        BCS MG_BOOT_INITIALIZED
                        JMP MG_BOOT_FAIL
MG_BOOT_INITIALIZED:
                        LDA #<MG_RUNTIME_ID
                        STA MG_IMAGE_ID
                        LDA #>MG_RUNTIME_ID
                        STA MG_IMAGE_ID+1
                        LDA #$01
                        STA MG_READY
                        JSR AL_APPLY_ENTRY
                        SEC
                        RTS

; CRC-16/CCITT-FALSE, seeded in BUF_PTR. PTR=start, FLASH_PTR=exclusive end.
MG_CRC_RANGE:           LDA V2_PTR
                        CMP V2_FLASH_PTR
                        BNE MG_CRC_BYTE
                        LDA V2_PTR+1
                        CMP V2_FLASH_PTR+1
                        BEQ MG_CRC_DONE
MG_CRC_BYTE:            LDA (V2_PTR)
                        EOR V2_BUF_PTR+1
                        STA V2_BUF_PTR+1
                        LDX #$08
MG_CRC_BIT:             ASL V2_BUF_PTR
                        ROL V2_BUF_PTR+1
                        BCC MG_CRC_NEXT_BIT
                        LDA V2_BUF_PTR
                        EOR #$21
                        STA V2_BUF_PTR
                        LDA V2_BUF_PTR+1
                        EOR #$10
                        STA V2_BUF_PTR+1
MG_CRC_NEXT_BIT:        DEX
                        BNE MG_CRC_BIT
                        INC V2_PTR
                        BNE MG_CRC_RANGE
                        INC V2_PTR+1
                        BRA MG_CRC_RANGE
MG_CRC_DONE:            RTS
MG_IMAGE                EQU MG_STORAGE_START
MG_ROM_END:
                        ENDMOD
                        END
