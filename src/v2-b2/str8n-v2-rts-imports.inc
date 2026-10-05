; Ordinary pinned import bindings, not an indexed fast-slot ABI.
; Mutable provider entries/state live in declared manager/module RAM.
RTS_BIND_INDEX          EQU $7500
RTS_BIND_PATCH          EQU $7501
RTS_POLICY              EQU $7503
RTS_OLD_BANK            EQU $7507
RTS_FILTER              EQU $7508
RTS_BANK                EQU $7509
RTS_FOUND               EQU $750A
RTS_MATCH               EQU $750B
RTS_MATCH_BANK          EQU $750D
RTS_LAST_SECTOR         EQU $750E
RTS_NEED                EQU $750F
RTS_RUN                 EQU $7511
RTS_BINDINGS            EQU $7520

RTS_INIT:               STZ RTS_BIND_INDEX
RTS_BIND_NEXT:          LDX RTS_BIND_INDEX
                        LDA RTS_IMPORTS+2,X
                        STA RTS_BIND_PATCH
                        LDA RTS_IMPORTS+3,X
                        STA RTS_BIND_PATCH+1
                        LDA RTS_IMPORTS,X
                        PHA
                        LDA RTS_IMPORTS+1,X
                        TAX
                        PLA
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC RTS_INIT_FAIL
                        STA V2_PTR
                        STX V2_PTR+1
                        LDA RTS_BIND_PATCH
                        STA V2_ADDR
                        LDA RTS_BIND_PATCH+1
                        STA V2_ADDR+1
                        LDY #$00
                        LDA V2_PTR
                        STA (V2_ADDR),Y
                        INY
                        LDA V2_PTR+1
                        STA (V2_ADDR),Y
                        LDA RTS_BIND_INDEX
                        CLC
                        ADC #$04
                        STA RTS_BIND_INDEX
                        CMP #RTS_IMPORT_COUNT*4
                        BNE RTS_BIND_NEXT
                        JSR RTS_CONFIG_LOCATE
                        LDA #'K'
                        LDX #<CF_COMMAND
                        LDY #>CF_COMMAND
                        JSR RTS_REGISTER
                        BCC RTS_INIT_FAIL
                        LDA #'S'
                        LDX #<SR_COMMAND_SAVE
                        LDY #>SR_COMMAND_SAVE
                        JSR RTS_REGISTER
                        BCC RTS_INIT_FAIL
                        LDA #'R'
                        LDX #<SR_COMMAND_RESTORE
                        LDY #>SR_COMMAND_RESTORE
                        JSR RTS_REGISTER
                        BCC RTS_INIT_FAIL
                        LDA #'T'
                        LDX #<SR_COMMAND_TABLE
                        LDY #>SR_COMMAND_TABLE
                        JSR RTS_REGISTER
RTS_INIT_FAIL:          RTS

V2_PUTC:                JMP (RTS_BINDINGS)
V2_HEX_OUT:             JMP (RTS_BINDINGS+2)
V2_NEWLINE:             JMP (RTS_BINDINGS+4)
V2_CHECK_CANCEL:        JMP (RTS_BINDINGS+6)
V2_HEX_WORD:            JMP (RTS_BINDINGS+8)
V2_HEX_BYTE:            JMP (RTS_BINDINGS+10)
V2_SKIP_SPACES:         JMP (RTS_BINDINGS+12)
V2W_READ:               JMP (RTS_BINDINGS+14)
V2W_SNAPSHOT:           JMP (RTS_BINDINGS+16)
V2W_MUTATE:             JMP (RTS_BINDINGS+18)
RTS_REGISTER:           JMP (RTS_BINDINGS+20)
RTS_CONFIG_LOCATE:      JMP (RTS_BINDINGS+22)
RTS_IMPORT_COUNT        EQU $0C
RTS_IMPORTS:            DW RTS_IMPORT_0,RTS_BINDINGS
                        DW RTS_IMPORT_1,RTS_BINDINGS+2
                        DW RTS_IMPORT_2,RTS_BINDINGS+4
                        DW RTS_IMPORT_3,RTS_BINDINGS+6
                        DW RTS_IMPORT_4,RTS_BINDINGS+8
                        DW RTS_IMPORT_5,RTS_BINDINGS+10
                        DW RTS_IMPORT_6,RTS_BINDINGS+12
                        DW RTS_IMPORT_7,RTS_BINDINGS+14
                        DW RTS_IMPORT_8,RTS_BINDINGS+16
                        DW RTS_IMPORT_9,RTS_BINDINGS+18
                        DW RTS_IMPORT_10,RTS_BINDINGS+20
                        DW RTS_IMPORT_11,RTS_BINDINGS+22
RTS_IMPORT_0:           DB "CONSOLE.PUTC",$00
RTS_IMPORT_1:           DB "CONSOLE.HEXOUT",$00
RTS_IMPORT_2:           DB "CONSOLE.NEWLINE",$00
RTS_IMPORT_3:           DB "CONSOLE.CANCEL",$00
RTS_IMPORT_4:           DB "PARSE.HEXWORD",$00
RTS_IMPORT_5:           DB "PARSE.HEXBYTE",$00
RTS_IMPORT_6:           DB "PARSE.SPACES",$00
RTS_IMPORT_7:           DB "FLASH.READ",$00
RTS_IMPORT_8:           DB "FLASH.SNAPSHOT",$00
RTS_IMPORT_9:           DB "FLASH.MUTATE",$00
RTS_IMPORT_10:          DB "COMMAND.REGISTER",$00
RTS_IMPORT_11:          DB "CONFIG.LOCATE",$00
