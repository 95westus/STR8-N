; Optional MS/01 service dispatcher: M1/W never borrow owner RAM or probe I/O.
; Larger MAINT/CLOCK workbench is loaded only by those explicit commands.
        MODULE MON_SERVICES
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "workbench-interface.inc"
        INCLUDE "service-interface.inc"
        INCLUDE "service-layout.inc"
        INCLUDE "service-foundation.inc"
        CODE
S_START:
        DB "MS",SB_FORMAT,SB_PAGES,"PR05"
        JMP S_DISPATCH
S_DISPATCH:
        CMP #4
        BCS S_UNHANDLED
        STA S_BANK
        STX S_PTR
        STY S_PTR+1
        LDY #0
S_LINE_COPY:
        LDA (S_PTR),Y
        STA S_LINE,Y
        BEQ S_LINE_READY
        INY
        CPY #41
        BCC S_LINE_COPY
        BRA S_UNHANDLED
S_LINE_READY:
        LDX #0
        JSR S_SKIP
        CMP #'M'
        BNE S_NOT_MAP
        LDA S_LINE+1,X
        CMP #'A'
        BEQ S_NOT_MAP
        INX
        JSR S_SKIP
        BEQ S_MAP
        CMP #'1'
        BNE S_MAP_OTHER
        INX
        JSR S_END_ARGS
        BCS S_MAP
        BRA S_UNHANDLED
S_MAP_OTHER:
        CMP #'2'
        BEQ S_RANGES
        CMP #'3'
        BEQ S_MAP_WEAR
        BRA S_UNHANDLED
S_RANGES:
        INX
        JSR S_END_ARGS
        BCC S_UNHANDLED
        LDX #<S_RANGES_TEXT
        LDY #>S_RANGES_TEXT
        JMP S_MESSAGE
S_MAP_WEAR:
        INX
        JSR S_END_ARGS
        BCS S_WEAR
        BRA S_UNHANDLED
S_NOT_MAP:
        CMP #'W'
        BNE S_NAMES
        INX
        JSR S_END_ARGS
        BCS S_WEAR
        BRA S_NAMES
S_NAMES:
        LDX #<S_APPS_WORD
        LDY #>S_APPS_WORD
        JSR S_MATCH
        BCC S_MODULE_NAMES
        JSR S_END_ARGS
        BCC S_UNHANDLED
        JMP AP_LIST
S_MODULE_NAMES:
        LDX #<S_APP_WORD
        LDY #>S_APP_WORD
        JSR S_MATCH
        BCS AP_LAUNCH
        STZ S_LOADER_REQUEST
        LDX #<S_MAINT_WORD
        LDY #>S_MAINT_WORD
        JSR S_MATCH
        BCS S_MAINT_ARGS
        LDX #<S_FLASH_WORD
        LDY #>S_FLASH_WORD
        JSR S_MATCH
        BCS S_REQUEST_LOAD
        LDX #<S_CLOCK_WORD
        LDY #>S_CLOCK_WORD
        JSR S_MATCH
        BCC S_AUTO_NAMES
        BRA S_REQUEST_LOAD
S_AUTO_NAMES:
        LDA #<S_AUTO_WORDS
        STA $69F0
        LDA #>S_AUTO_WORDS
        STA $69F1
S_AUTO_NEXT:
        LDX $69F0
        LDY $69F1
        JSR S_MATCH
        BCS S_AUTO_LOAD
        LDY #0
S_AUTO_SKIP:
        LDA (S_PTR),Y
        INY
        CMP #0
        BNE S_AUTO_SKIP
        TYA
        CLC
        ADC $69F0
        STA $69F0
        BCC S_AUTO_PAGE
        INC $69F1
S_AUTO_PAGE:
        LDA $69F0
        STA S_PTR
        LDA $69F1
        STA S_PTR+1
        LDA (S_PTR)
        BNE S_AUTO_NEXT
        BRA S_MODULE
S_AUTO_LOAD:
        INC S_LOADER_REQUEST
        BRA S_MODULE
S_MAINT_ARGS:
        STX S_FORCE_END
        JSR S_SKIP
        BEQ S_REQUEST_LOAD
        LDY #0
S_FORCE_WORD:
        LDA S_LINE,X
        CMP S_LOAD_WORD,Y
        BNE S_UNHANDLED
        INX
        INY
        CPY #4
        BCC S_FORCE_WORD
        JSR S_END_ARGS
        BCC S_UNHANDLED
        ; LOAD belongs to this dispatcher; WB receives its normal MAINT.
        LDX S_FORCE_END
        STZ S_LINE,X
        LDA #2
        STA S_LOADER_REQUEST
        BRA S_MODULE
S_REQUEST_LOAD:
        JSR S_END_ARGS
        BCC S_UNHANDLED
        INC S_LOADER_REQUEST
S_MODULE:
        LDA S_LOADER_REQUEST
        CMP #2
        BEQ S_FORCE_LOAD
        JSR S_CHECK_WB
        BCS S_CALL_WB
        LDA S_LOADER_REQUEST
        BEQ S_NO_MODULE
S_FORCE_LOAD:
        LDX #<S_LOADING_TEXT
        LDY #>S_LOADING_TEXT
        JSR S_PUTS
        LDA SB_CLIENT_FLOOR
        STA S_HAVE_WB
        LDX #0
S_SAVE_MON:
        LDA $6A00,X
        STA $6700,X
        INX
        BNE S_SAVE_MON
        LDX #0
S_LOAD_COPY:
        LDA S_LOAD_IMAGE,X
        STA SB_LOAD_RAM,X
        INX
        BNE S_LOAD_COPY
        LDX #0
S_LOAD_COPY_TAIL:
        LDA S_LOAD_IMAGE+256,X
        STA SB_LOAD_RAM+256,X
        INX
        CPX #SERVICE_LOADER_TAIL
        BNE S_LOAD_COPY_TAIL
        STZ $68F1
        LDA #>SB_MODULE_SOURCE
        JSR SB_LOAD_RAM
        BCC S_LOAD_FAILED
        LDA S_HAVE_WB
        STA SB_CLIENT_FLOOR
        JSR S_CHECK_WB
        BCC S_LOAD_FAILED
S_CALL_WB:
        LDA SB_CLIENT_FLOOR
        STA WB_CLIENT_FLOOR
        LDA S_BANK
        LDX #<S_LINE
        LDY #>S_LINE
        JMP WB_COMMAND
S_NO_MODULE:
        LDX #<S_NO_MODULE_TEXT
        LDY #>S_NO_MODULE_TEXT
        BRA S_MESSAGE
S_LOAD_FAILED:
        LDX #<S_LOAD_FAILED_TEXT
        LDY #>S_LOAD_FAILED_TEXT
S_MESSAGE:
        JSR S_PUTS
S_HANDLED:
        LDA S_BANK
        SEC
        RTS
S_UNHANDLED:
        CLC
        RTS
S_SKIP:
        LDA S_LINE,X
        CMP #' '
        BNE S_SKIP_END
        INX
        BRA S_SKIP
S_SKIP_END:
        CMP #0
        RTS
S_END_ARGS:
        JSR S_SKIP
        BNE S_UNHANDLED
        SEC
        RTS
S_MATCH:
        STX S_PTR
        STY S_PTR+1
        LDX #0
        JSR S_SKIP
        LDY #0
S_MATCH_BYTE:
        LDA (S_PTR),Y
        BEQ S_MATCH_END
        CMP S_LINE,X
        BNE S_UNHANDLED
        INX
        INY
        BRA S_MATCH_BYTE
S_MATCH_END:
        LDA S_LINE,X
        BEQ S_MATCH_OK
        CMP #' '
        BNE S_UNHANDLED
S_MATCH_OK:
        SEC
        RTS
S_CHECK_WB:
        ; A valid older cache is not the current shipping tool module.
        LDX #5
S_WB_GENERATION_CHECK:
        LDA WB_ORIGIN+17,X
        CMP S_WB_GENERATION,X
        BNE S_UNHANDLED
        DEX
        BPL S_WB_GENERATION_CHECK
        LDX #7
S_WB_ID:
        LDA WB_ORIGIN,X
        CMP S_WB_MAGIC,X
        BNE S_UNHANDLED
        DEX
        BPL S_WB_ID
        STZ S_PTR
        LDA #>WB_ORIGIN
        STA S_PTR+1
        LDX #WB_PAGES
        JSR S_CRC_PAGES
        LDA S_CRC
        ORA S_CRC+1
        BNE S_UNHANDLED
        SEC
        RTS
S_CRC_INIT:
        LDA #$FF
        STA S_CRC
        STA S_CRC+1
        RTS
S_CRC_BYTE:
        PHX
        EOR S_CRC+1
        STA S_CRC+1
        LDX #8
S_CRC_BIT:
        ASL S_CRC
        ROL S_CRC+1
        BCC S_CRC_NEXT
        LDA S_CRC
        EOR #$21
        STA S_CRC
        LDA S_CRC+1
        EOR #$10
        STA S_CRC+1
S_CRC_NEXT:
        DEX
        BNE S_CRC_BIT
        PLX
        RTS
S_CRC_PAGES:
        JSR S_CRC_INIT
        LDY #0
S_CRC_PAGE_BYTE:
        LDA (S_PTR),Y
        JSR S_CRC_BYTE
        INY
        BNE S_CRC_PAGE_BYTE
        INC S_PTR+1
        DEX
        BNE S_CRC_PAGE_BYTE
        RTS
S_READ64:
        LDA S_F_SELECTED
        PHA
        LDA S_READ_BANK
        STA S_F_SELECTED
        LDA S_ADDR
        STA S_F_ADDR
        LDA S_ADDR+1
        STA S_F_ADDR+1
        LDA #64
        STA S_F_COUNT
        JSR SB_F_READ
        LDX #63
S_READ_COPY:
        LDA S_F_BYTES,X
        STA S_BUFFER,X
        DEX
        BPL S_READ_COPY
        PLA
        STA S_F_SELECTED
        RTS
S_PUTS:
        STX S_PTR
        STY S_PTR+1
        LDY #0
S_PUTS_BYTE:
        LDA (S_PTR),Y
        BEQ S_PUTS_END
        JSR STR8V2_RAM_PUTC
        INY
        BNE S_PUTS_BYTE
        INC S_PTR+1
        BRA S_PUTS_BYTE
S_PUTS_END:
        RTS
        INCLUDE "service-map.inc"
        INCLUDE "service-wear.inc"
        INCLUDE "service-apps.inc"
S_WB_MAGIC: DB "MW",WB_FORMAT,WB_PAGES,"PR05"
S_WB_GENERATION: DB "WG","WORKBENCH_GENERATION_BYTES"
S_APPS_WORD: DB "APPS",0
S_APP_WORD: DB "APP",0
S_MAINT_WORD: DB "MAINT",0
S_LOAD_WORD: DB "LOAD"
S_FLASH_WORD: DB "FLASH",0
S_CLOCK_WORD: DB "CLOCK",0
S_AUTO_WORDS: DB "S",0,"STORE",0,"T",0,"TABLE",0,"R",0,"RESTORE",0
        DB "EDU",0,"SRAM",0,"WORK",0,"BATCH",0,"BOOT",0,0
S_RANGES_TEXT: DB "B0/B1: owner images/records retained. Erased != available.",13,10
        DB "B2:8-A tool bundle; other B2 assets retained; legacy calls disabled.",13,10
        DB "B3:A/B MON; C/D boot/wear; E services; F frozen recovery.",13,10
        DB "MAINT LOAD: WB4800-66FF + PROGRAM6B00-77FF.",13,10,0
S_LOADING_TEXT: DB "Load flash WB2/PROGRAM: 4800-66FF +6B00-77FF",13,10,0
S_NO_MODULE_TEXT: DB "WB2 absent/invalid. MAINT/CLOCK load the flash bundle.",13,10,0
S_LOAD_FAILED_TEXT: DB "REFUSED: bundle/header/CRC failed; workbench not called",13,10,0
S_LOAD_IMAGE:
        INCLUDE "service-load-image.inc"
S_END:
        ENDMOD
        END
