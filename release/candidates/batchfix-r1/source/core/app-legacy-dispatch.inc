AP_LEGACY_SR:         LDA #4
                       JMP $EF09

AP_LEGACY_MAP:         LDX #$01
                        JSR V2_SKIP_SPACES
                        BEQ AP_LEG_LONG_5
                        JMP app_legacy_dispatch_LONG_5
AP_LEG_LONG_5:
                        JMP V2_MAP_DEFAULT
app_legacy_dispatch_LONG_5:
                        LDA V2_LINE,X
                        SEC
                        SBC #'1'
                        CMP #$03
                        BCS AP_LEG_LONG_12
                        JMP app_legacy_dispatch_LONG_10
AP_LEG_LONG_12:
                        JMP AP_MAP_EDIT
app_legacy_dispatch_LONG_10:
                        INC A
                        PHA
                        INX
                        JSR V2_SKIP_SPACES
                        BEQ AP_LEG_LONG_19
                        JMP app_legacy_dispatch_LONG_15
AP_LEG_LONG_19:
                        JMP V2_MAP_MODE_OK
app_legacy_dispatch_LONG_15:
                        PLA
                        JMP AP_MAP_EDIT
V2_MAP_MODE_OK:         PLA
                        JMP V2_MAP_GO
V2_MAP_DEFAULT:         LDA #$02
V2_MAP_GO:              STA $7DFD
                        LDA #$4D
                        STA $7DFC
                        LDX #$07
V2_MAP_LINE:            LDA V2_MAP_COMMAND,X
                        STA V2_LINE,X
                        DEX
                        BPL AP_LEG_LONG_34
                        JMP app_legacy_dispatch_LONG_28
AP_LEG_LONG_34:
                        JMP V2_MAP_LINE
app_legacy_dispatch_LONG_28:
                        JMP AP_LEGACY_SR

V2_MAP_COMMAND:         DB "R MAINT",0

