                        MODULE  V2_MANAGER
                        XDEF    MG_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        CODE
MG_DESCRIPTOR:          DB      "EM",$01,$01
                        DW      MG_END-MG_DESCRIPTOR
                        DB      MG_CAPACITY,$00
MG_INIT_ENTRY:          JMP     MG_INIT
MG_DISPATCH_ENTRY:      JMP     MG_DISPATCH
MG_LOOKUP_ENTRY:        JMP     MG_LOOKUP
MG_NAMED_ENTRY:         JMP     MG_NAMED_DISPATCH_ROM
MG_INIT:                STZ     MG_NAMED_COUNT
                        STZ     MG_DYNAMIC_COUNT
                        STZ     MG_COUNT
                        STZ     MG_READY
                        SEC
                        RTS

; Single-letter commands are exact tokens, not arbitrary prefix matches.
MG_DISPATCH:            LDA     V2_LINE+1
                        BEQ     MG_DISPATCH_TOKEN
                        CMP     #' '
                        BNE     MG_UNHANDLED
MG_DISPATCH_TOKEN:      LDX     #$00
MG_COMMAND_NEXT:        CPX     MG_COUNT
                        BEQ     MG_UNHANDLED
                        LDA     MG_TABLE,X
                        CMP     V2_LINE
                        BEQ     MG_COMMAND_FOUND
                        INX
                        INX
                        INX
                        BRA     MG_COMMAND_NEXT
MG_COMMAND_FOUND:       LDA     MG_TABLE+1,X
                        STA     MG_CALL
                        LDA     MG_TABLE+2,X
                        STA     MG_CALL+1
                        JMP     (MG_CALL)
MG_UNHANDLED:           LDA     #$00
                        RTS

; Discovered COMMAND.REGISTER service: A=key, X/Y=target low/high.
; Targets must be in reserved overlay/manager RAM or resident B-E ROM; pinned.
; C=1,A=0 success; C=0,A=1 invalid, 2 duplicate, 3 full. No partial insertion.
MG_REGISTER:            CMP     #'A'
                        BCC     MG_REGISTER_BAD
                        CMP     #'Z'+1
                        BCS     MG_REGISTER_BAD
                        CPY     #$B0
                        BCC     MG_REGISTER_RAM
                        CPY     #$F0
                        BCC     MG_REGISTER_TARGET
                        BRA     MG_REGISTER_BAD
MG_REGISTER_RAM:
                        CPY     #$58
                        BCC     MG_REGISTER_BAD
                        CPY     #$60
                        BCC     MG_REGISTER_TARGET
                        CPY     #$71
                        BCC     MG_REGISTER_BAD
                        CPY     #$79
                        BCS     MG_REGISTER_BAD
MG_REGISTER_TARGET:     STX     V2_BUF_PTR
                        STY     V2_BUF_PTR+1
                        JSR     $ED06
                        BCS     MG_REGISTER_DUP
                        LDX     #$00
MG_REGISTER_SCAN:       CPX     MG_COUNT
                        BEQ     MG_REGISTER_INSERT
                        CMP     MG_TABLE,X
                        BEQ     MG_REGISTER_DUP
                        INX
                        INX
                        INX
                        BRA     MG_REGISTER_SCAN
MG_REGISTER_INSERT:     CPX     #MG_CAPACITY*3
                        BCS     MG_REGISTER_FULL
                        STA     MG_TABLE,X
                        LDA     V2_BUF_PTR
                        STA     MG_TABLE+1,X
                        LDA     V2_BUF_PTR+1
                        STA     MG_TABLE+2,X
                        INX
                        INX
                        INX
                        STX     MG_COUNT
                        LDA     #$00
                        SEC
                        RTS
MG_REGISTER_BAD:        LDA     #$01
                        BRA     MG_REGISTER_FAIL
MG_REGISTER_DUP:        LDA     #$02
                        BRA     MG_REGISTER_FAIL
MG_REGISTER_FULL:       LDA     #$03
MG_REGISTER_FAIL:       CLC
                        RTS

MG_LOOKUP:              JMP     MG_SERVICE_LOOKUP_ROM
                        INCLUDE "manager-host-services.inc"
MG_END:
                        ENDMOD
                        END
