; Optional B2:8000 entry. A768-byte prefix includes a512-byte RAM loader.
        MODULE SERVICE_BUNDLE
        INCLUDE "workbench-interface.inc"
        INCLUDE "service-interface.inc"
        CODE
SBB_START:
        JMP SBB_BOOT
        DB "WF",3,WB_PAGES,"PR05"
        DB "SERVICE_GENERATION_BYTES"
SBB_BOOT:
        SEI
        CLD
        LDX #$FF
        TXS
        LDX #0
SBB_SAVE:
        LDA $6A00,X
        STA $6700,X
        INX
        BNE SBB_SAVE
        LDX #0
SBB_COPY:
        LDA $8100,X
        STA SB_LOAD_RAM,X
        LDA $8200,X
        STA SB_LOAD_RAM+256,X
        INX
        BNE SBB_COPY
        LDA #1
        STA $68F1
        LDA #>SB_MODULE_SOURCE
        JMP SB_LOAD_RAM
SBB_END:
        ENDMOD
        END
