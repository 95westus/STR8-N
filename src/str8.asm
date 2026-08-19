; ----------------------------------------------------------------------------
; str8.asm
; STR8 recovery monitor, built in proof and flashable v1.22 layouts.
;
; Flashable command surface:
;   I  preview metadata and run the dense journaled Bank 0-3 transaction
;   L  load an S19 into $2000-$7AFF RAM and execute its S9 address
;   C  cold-entry local HIMON and request its normal RAM initialization
;   W  warm-entry local HIMON without changing banks
;   J0/J1/J2/J3  non-destructive reset-vector handoff to bank 0/1/2/3
;   invalid input is discarded without reprinting the command help
; V0 proof builds retain U instead of I for the fixed $C000-$EFFF HIMON gate.
;
; Reset prints RESET, shows unpolled attach pulses, flushes RX, prints the banner, then
; opens six live selector dots. Timeout warm-starts compatible HIMON at $C000;
; W selects the same RAM-preserving entry. A missing or incompatible marker falls
; into the STR8 menu. S enters STR8; 0-2 announce the selected bank, wait about
; 3 more seconds, then reuse the non-destructive J handoff.
;
; The RAM proof build performs destructive bank copies directly from RAM.
; The resident ROM contains one worker. $F010 copies only its selector prefix;
; I and J copy and verify the full worker before any bank-dependent operation.
; ----------------------------------------------------------------------------

                        MODULE          STR8_APP

                        XDEF            START
                        XDEF            STR8_CONSOLE_INIT_SERVICE_ENTRY
                        XDEF            STR8_ABI_QUERY_SERVICE_ENTRY
                        XDEF            STR8_RECORD_SERVICE_ENTRY
                        XDEF            STR8_RECORD_SERVICE_SIGNATURE
                        XDEF            STR8_BANK_SELECT_SERVICE_ENTRY
                        XDEF            STR8_CHARIN_SERVICE_ENTRY
                        XDEF            STR8_CHAROUT_SERVICE_ENTRY
                        XDEF            STR8_CHAR_READY_SERVICE_ENTRY
                        XDEF            STR8_BANK_SELECT_SERVICE_BODY
                        XDEF            STR8_DIR_VALIDATE_BANK_A
                        XDEF            STR8_DIR_SCAN_JOURNAL
                        IF              STR8_V1_LAYOUT
                        XDEF            STR8_DIR_WRITE_BYTES
                        XDEF            STR8_READ_LINE
                        XDEF            STR8_CMD_INSTALL_PREVIEW
                        XDEF            STR8_CMD_LOAD_RAM
                        IF              STR8_V1_INSTALLER_DRY
                        XDEF            STR8_I_RECEIVE_DENSE
                        XDEF            STR8_I_STAGE_SECTOR_READY
                        IF              STR8_V1_INSTALLER_TXN
                        XDEF            STR8_I_BEGIN_TRANSACTION
                        XDEF            STR8_I_FINISH_TRANSACTION
                        XDEF            STR8_I_RUN_SECTOR_WORKER
                        ENDIF
                        ENDIF
                        ENDIF
                        XDEF            STR8_IVY_ENTRY_NMI
                        XDEF            STR8_IVY_ENTRY_IRQ_MASTER
                        XDEF            STR8_ID_MARKER_BYTES

                        XREF            UTL_DELAY_AXY_8MHZ
                        IF              STR8_RAM_PROOF
                        XREF            FLSH_BANK_SELECT_A
                        XREF            FLSH_BANK_SELECT_3
                        XREF            FLASH_SECTOR_ERASE_RAW_XY
                        XREF            FLASH_WRITE_BYTE_RAW_AXY
                        ENDIF

                        INCLUDE         "himon-image-eq.inc"
                        INCLUDE         "str8-ram-abi.inc"
                        INCLUDE         "str8-record-eq.inc"
                        INCLUDE         "str8-jump-eq.inc"
                        INCLUDE         "str8-console-eq.inc"
                        INCLUDE         "str8-directory-eq.inc"
                        INCLUDE         "str8-worker-eq.inc"

; 2026-05-07T22:58-05:00        WLP2        Combined ROM layout moves STR8 to $F000.
; 2026-05-17T21:20-05:00        WLP2        Worker storage formerly moved to $FC00 to make room for U/HIMON update.
; 2026-05-21T23:55-05:00        WLP2        Worker now packs down from $FFEF so the free hole is contiguous.
; 2026-07-23T13:07-05:00        Codex       Size pass shares resident paths and repacks the smaller worker.
; 2026-07-23T17:27-05:00        Codex       B selects one destination; E/enrollment is removed.
; STR8 identity marker. The source phrase is private.
STR8_ID_MARKER0         EQU             $7A
STR8_ID_MARKER1         EQU             $0F
STR8_ID_MARKER2         EQU             $6A
STR8_ID_MARKER3         EQU             $5F
STR8_RESET_VECTOR       EQU             $FFFC
STR8_HIMON_START        EQU             HIMON_IMAGE_ENTRY
STR8_HIMON_RESET_SIG0   EQU             $7EE6
STR8_HIMON_RESET_SIG1   EQU             $7EE7
STR8_HIMON_RESET_SIG2   EQU             $7EE8
STR8_HIMON_RESET_SIG3   EQU             $7EE9
STR8_IVY_SIG0           EQU             $7EED
STR8_IVY_SIG1           EQU             $7EEE
STR8_IVY_SIG2           EQU             $7EEF
STR8_IVY_SIG0_VAL       EQU             'I'
STR8_IVY_SIG1_VAL       EQU             'V'
STR8_IVY_SIG2_VAL       EQU             'Y'
STR8_IVY_VEC_RESET_LO   EQU             $7EF8
STR8_IVY_VEC_RESET_HI   EQU             $7EF9
STR8_IVY_VEC_NMI_LO     EQU             $7EFA
STR8_IVY_VEC_NMI_HI     EQU             $7EFB
STR8_IVY_VEC_BRK_LO     EQU             $7EFC
STR8_IVY_VEC_BRK_HI     EQU             $7EFD
STR8_IVY_VEC_IRQ_LO     EQU             $7EFE
STR8_IVY_VEC_IRQ_HI     EQU             $7EFF
STR8_WORKER_RUN_HI      EQU             $02
STR8_WORKER_TRAY_SIZE   EQU             $0800
STR8_WORKER_TRAY_END    EQU             $09FF
STR8_WORKER_STORE_LO    EQU             <STR8_WORKER_STORE
STR8_WORKER_STORE_HI    EQU             >STR8_WORKER_STORE
STR8_WORKER_COPY_LEN_LO EQU             <STR8_WORKER_SIZE
STR8_WORKER_COPY_LEN_HI EQU             >STR8_WORKER_SIZE
STR8_SELECTOR_COPY_LEN  EQU             STR8_WORKER_SELECT_SIZE
STR8_DELAY_TICK_X       EQU             $B6
STR8_DELAY_TICK_Y       EQU             $F8
STR8_STARTUP_DOT_COUNT  EQU             $0C
STR8_STARTUP_LIVE_TICKS EQU             $06
STR8_STARTUP_DOT_A      EQU             $23    ; 0.993s at 8 MHz
STR8_BANK_BOOT_DELAY_A  EQU             $6A    ; 3.010s at 8 MHz
STR8_COPY_MODE_PROGRAM_STAGED EQU        $05
STR8_PTR_LO             EQU             $CD
STR8_PTR_HI             EQU             $CE
STR8_COPY_PTR_LO        EQU             $CF
STR8_COPY_PTR_HI        EQU             $D0
STR8_REC_WORK_REMAIN    EQU             $D1
STR8_REC_WORK_SUM       EQU             $D2
STR8_REC_WORK_COUNT     EQU             $D3
STR8_REC_WORK_TMP       EQU             $D4
STR8_REC_WORK_TYPE      EQU             $D5
STR8_LINE_LIMIT         EQU             $D1
; I owns this transient user-ZP frame for the complete recovery transaction.
; The RAM worker uses only $CD-$D6, so these bytes survive every worker call.
STR8_INSTALL_BANK       EQU             $90
STR8_INSTALL_TYPE       EQU             $91
STR8_INSTALL_DESC       EQU             $92
STR8_INSTALL_STATE      EQU             $97
STR8_INSTALL_PAIR       EQU             $98
STR8_INSTALL_ENTRY_LO   EQU             $99
STR8_INSTALL_ENTRY_HI   EQU             $9A
STR8_INSTALL_EXPECT_LO  EQU             $9B
STR8_INSTALL_EXPECT_HI  EQU             $9C
STR8_INSTALL_PHASE      EQU             $9E
STR8_INSTALL_SECTOR_HI  EQU             $9F
; $A0 is intentionally free; the record service retains its own detailed
; parse/program status while the compact installer reports a single failure.
; v1.22 selected dense range. The receiver requires this exact start and
; exclusive limit while retaining a count for summaries/tests.
STR8_INSTALL_START_HI   EQU             $A1
STR8_INSTALL_RANGE_LIMIT_HI EQU         $A2
STR8_INSTALL_SECTOR_COUNT EQU           $A3
; L reuses the resident parser and pointer helpers.  Its destination ceiling
; stays below the parser's $7B00 data buffer and the higher RTC/IVI cells.
STR8_RAM_LOAD_HAVE_DATA EQU              $A0
STR8_RAM_LOAD_MIN_HI  EQU                $20
STR8_RAM_LOAD_LIMIT_HI EQU               $7B
STR8_INSTALL_DENSE      EQU             $10
STR8_INSTALL_ENTRY      EQU             $11
STR8_INSTALL_FLASH      EQU             $12
STR8_INSTALL_TRAILING   EQU             $13
STR8_INSTALL_DIRECTORY  EQU             $14
STR8_INSTALL_WORKER     EQU             $15
; Internal only: sealed interrupted Bank-3 enrollment still needs S9 entry.
STR8_INSTALL_NEEDS_ENTRY EQU            STR8_DIR_RECORD_INVALID
; The resident directory validator and S19 record parser run serially and
; intentionally share this small zero-page work set.
STR8_DIR_BANK_WORK      EQU             $D1
STR8_DIR_OPEN_WORK      EQU             $D2
STR8_DIR_PACKED_WORK    EQU             $D3
STR8_DIR_LEFT_WORK      EQU             $D4
STR8_DIR_RESULT_PAIR    EQU             $D5
STR8_DIR_PAIR_WORK      EQU             $D6
STR8_CON_VIA_CTRL       EQU             $7FE0
STR8_CON_VIA_DATA       EQU             $7FE1
STR8_CON_VIA_DDRB       EQU             $7FE2
STR8_CON_VIA_DDRA       EQU             $7FE3
STR8_CON_PN_TXE         EQU             $01
STR8_CON_PN_RXF         EQU             $02
STR8_CON_PN_WR          EQU             $04
STR8_CON_PN_RD          EQU             $08
STR8_CON_PN_CTRL_INIT   EQU             $0C
STR8_CON_FLUSH_RX_MAX   EQU             $FF

                        CODE
; 2026-05-07T19:14-05:00        WLP2        Timeout enters HIMON warm; S/s takes STR8.
; 2026-05-14T00:00-05:00        WLP2        Timeout enters HIMON cold after half delay.
; 2026-08-02T00:00-05:00        Codex       Missing local C000 target falls into STR8.
; 2026-08-18T00:00-05:00        Codex       Timeout again enters HIMON warm and preserves RAM.
; 2026-08-19T00:00-05:00        Codex       C explicitly enters HIMON cold.
; 2026-08-19T00:00-05:00        Codex       Live selector and prompt use paired C/W entry.
START:
                        JMP             STR8_BOOT_START

; These two slots were fail-closed tombstones in the preceding v1.2 image.
; Therefore an old image returns C=0 from $F006 instead of entering arbitrary
; code, allowing callers to detect the expanded resident ABI safely.
STR8_CONSOLE_INIT_SERVICE_ENTRY:
                        JMP             STR8_CON_INIT

STR8_ABI_QUERY_SERVICE_ENTRY:
                        JMP             STR8_ABI_QUERY_BODY

STR8_RECORD_SERVICE_ENTRY:
                        JMP             STR8_RECORD_SERVICE_BODY
STR8_RECORD_SERVICE_SIGNATURE:
                        DB              STR8_REC_SIG0_VALUE,STR8_REC_SIG1_VALUE
                        DB              STR8_REC_VERSION_VALUE
                        IF              STR8_RAM_PROOF
                        DB              (STR8_REC_CAP_BUFFER+STR8_REC_CAP_CONSOLE)
                        ELSE
                        DB              STR8_REC_CAPS_V2
                        ENDIF

; Stable bank-selector front door. A RAM caller passes A=bank 0-3. The body
; copies the bank-safe trampoline to $0200 and tail-calls its fixed $0203
; entry, which returns directly to the original RAM caller in the new bank.
STR8_BANK_SELECT_SERVICE_ENTRY:
                        JMP             STR8_BANK_SELECT_SERVICE_BODY

; Stable raw console services. Physical RESET initializes the FT245R
; interface before any STR8-N command or guest handoff. External callers must
; have Bank 3 visible and must preserve that initialized interface state.
; CHARIN:  OUT A=received byte, C=1; X/Y preserved; waits for input.
STR8_CHARIN_SERVICE_ENTRY:
STR8_CON_READ_BYTE_BLOCK:
                        JSR             STR8_CON_READ_BYTE_NONBLOCK
                        BCC             STR8_CON_READ_BYTE_BLOCK
                        RTS

; CHAROUT: IN A=byte; OUT A preserved, C=1; X/Y preserved; waits for output.
STR8_CHAROUT_SERVICE_ENTRY:
STR8_CON_WRITE_BYTE_BLOCK:
                        PHA
                        STZ             STR8_CON_VIA_DDRA
                        STA             STR8_CON_VIA_DATA
                        NOP
                        NOP
                        LDA             #STR8_CON_PN_TXE
?WAIT:                  BIT             STR8_CON_VIA_CTRL
                        BNE             ?WAIT
                        LDA             #STR8_CON_PN_WR
                        TSB             STR8_CON_VIA_CTRL
                        DEC             STR8_CON_VIA_DDRA
                        NOP
                        NOP
                        LDA             #STR8_CON_PN_WR
                        TRB             STR8_CON_VIA_CTRL
                        STZ             STR8_CON_VIA_DDRA
                        PLA
                        SEC
                        RTS

; CHAR_READY is a non-consuming receiver poll. C=1 means a byte is ready;
; C=0 means empty. A/flags are clobbered except for carry; X/Y are preserved.
STR8_CHAR_READY_SERVICE_ENTRY:
                        LDA             #STR8_CON_PN_RXF
                        BIT             STR8_CON_VIA_CTRL
                        BEQ             ?READY
                        CLC
                        RTS
?READY:                 SEC
                        RTS

STR8_BOOT_START:
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        JSR             STR8_IVY_INIT
                        JSR             STR8_CON_INIT
                        IF              STR8_RAM_PROOF
                        ELSE
                        JSR             STR8_STARTUP_DELAY
                        BCC             ?HIMON
                        CMP             #'S'
                        BEQ             ?STR8_KEY
                        CMP             #'3'
                        IF              STR8_V1_LAYOUT
                        BCS             ?HIMON_KEY
                        ELSE
                        BEQ             ?HIMON_KEY
                        ENDIF
                        AND             #$03
                        JSR             STR8_BOOT_JUMP_BANK_A
                        BRA             ?STR8_TAKEOVER
?HIMON_KEY:            JMP             STR8_CMD_SELECT_HIMON
?HIMON:
                        LDX             #<MSG_CRLF
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_CRLF
                        JSR             STR8_PRINT_XY
                        ENDIF
                        JMP             STR8_ENTER_HIMON_WARM
?STR8_KEY:             JSR             STR8_CON_FLUSH_RX
                        LDX             #<MSG_BOOT_MENU
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_BOOT_MENU
                        JSR             STR8_PRINT_XY
                        ENDIF
                        BRA             STR8_ENTER_MENU_READY
?STR8_TAKEOVER:        BRA             STR8_ENTER_MENU_HELP
                        ENDIF
; Transaction startup always enters HELP or READY explicitly.
                        IF              STR8_V1_INSTALLER_TXN
                        ELSE
STR8_ENTER_MENU:
                        JSR             STR8_PRINT_SCREEN
                        BRA             STR8_ENTER_MENU_READY
                        ENDIF

STR8_ENTER_MENU_HELP:
                        LDX             #<MSG_SCREEN
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_SCREEN
                        JSR             STR8_PRINT_XY
                        ENDIF
STR8_ENTER_MENU_READY:
                        STZ             STR8_INPUT_SKIP_LF
                        JMP             STR8_CMD_LOOP

; ----------------------------------------------------------------------------
; IVI vector front door. IVI is pronounced IVY; LEAF is the later product surface.
; ----------------------------------------------------------------------------
; Hardware RESET lands in STR8. Hardware NMI and IRQ/BRK land in these STR8
; top-sector stubs, which dispatch through RAM vector cells once initialized.
STR8_IVY_INIT:
                        PHP
                        SEI
                        STZ             STR8_IVY_SIG0

                        LDA             #<START
                        STA             STR8_IVY_VEC_RESET_LO
                        LDA             #>START
                        STA             STR8_IVY_VEC_RESET_HI

                        LDX             #$04
?VECTOR:               LDA             #<STR8_IVY_DEFAULT_RTI
                        STA             STR8_IVY_VEC_NMI_LO,X
                        LDA             #>STR8_IVY_DEFAULT_RTI
                        STA             STR8_IVY_VEC_NMI_HI,X
                        DEX
                        DEX
                        BPL             ?VECTOR

                        LDA             #STR8_IVY_SIG1_VAL
                        STA             STR8_IVY_SIG1
                        LDA             #STR8_IVY_SIG2_VAL
                        STA             STR8_IVY_SIG2
                        LDA             #STR8_IVY_SIG0_VAL
                        STA             STR8_IVY_SIG0
                        PLP
                        RTS

STR8_IVY_SIG_OK:
                        LDA             STR8_IVY_SIG0
                        CMP             #STR8_IVY_SIG0_VAL
                        BNE             ?NO
                        LDA             STR8_IVY_SIG1
                        CMP             #STR8_IVY_SIG1_VAL
                        BNE             ?NO
                        LDA             STR8_IVY_SIG2
                        CMP             #STR8_IVY_SIG2_VAL
                        BNE             ?NO
                        RTS
?NO:                   CLC
                        RTS

STR8_IVY_ENTRY_NMI:
                        PHA
                        JSR             STR8_IVY_SIG_OK
                        BCC             ?RTI
                        LDA             STR8_IVY_VEC_NMI_LO
                        ORA             STR8_IVY_VEC_NMI_HI
                        BEQ             ?RTI
                        PLA
                        JMP             (STR8_IVY_VEC_NMI_LO)
?RTI:                  PLA
STR8_IVY_DEFAULT_RTI:   RTI

STR8_IVY_ENTRY_IRQ_MASTER:
                        PHA
                        PHX
                        TSX
                        LDA             $0103,X
                        AND             #$10
                        BEQ             ?IRQ
                        LDX             #$00
                        BRA             ?DISPATCH
?IRQ:                  LDX             #$02
?DISPATCH:             JSR             STR8_IVY_SIG_OK
                        BCC             ?RTI
                        LDA             STR8_IVY_VEC_BRK_LO,X
                        ORA             STR8_IVY_VEC_BRK_HI,X
                        BEQ             ?RTI
                        CPX             #$00
                        BEQ             ?BRK_JUMP
                        PLX
                        PLA
                        JMP             (STR8_IVY_VEC_IRQ_LO)
?BRK_JUMP:            PLX
                        PLA
                        JMP             (STR8_IVY_VEC_BRK_LO)
?RTI:                 PLX
                        PLA
                        RTI

STR8_ENTER_HIMON_WARM:
                        IF              STR8_V1_LAYOUT
                        JSR             STR8_LOCAL_HIMON_AVAILABLE
                        IF              STR8_V1_INSTALLER_TXN
                        BCC             STR8_ENTER_MENU_NO_BOOT
                        ELSE
                        BCC             STR8_ENTER_MENU_NO_HIMON
                        ENDIF
                        LDX             #HIMON_IMAGE_ID_SIZE-1
?SIG:                  LDA             STR8_HIMON_WARM_SIGNATURE,X
                        STA             STR8_HIMON_RESET_SIG0,X
                        DEX
                        BPL             ?SIG
                        ELSE
                        JSR             STR8_BOOT_TARGET_AVAILABLE
                        BCC             STR8_ENTER_MENU_NO_BOOT
                        LDA             #$A5
                        STA             STR8_HIMON_RESET_SIG0
                        LDA             #$5A
                        STA             STR8_HIMON_RESET_SIG1
                        LDA             #$C3
                        STA             STR8_HIMON_RESET_SIG2
                        LDA             #$3C
                        STA             STR8_HIMON_RESET_SIG3
                        ENDIF
                        JMP             STR8_HIMON_START

                        IF              STR8_V1_LAYOUT
STR8_ENTER_HIMON_COLD:
                        JSR             STR8_LOCAL_HIMON_AVAILABLE
                        BCC             STR8_ENTER_MENU_NO_BOOT
                        LDX             #HIMON_IMAGE_ID_SIZE-1
?SIG:                  STZ             STR8_HIMON_RESET_SIG0,X
                        DEX
                        BPL             ?SIG
                        JMP             STR8_HIMON_START
                        ENDIF

                        IF              STR8_V1_LAYOUT
                        ELSE
; Minimal generic HIMON/user-app availability gate retained for V0 proof
; layouts. v1.22 warm entry requires the fixed HIMON marker below.
STR8_BOOT_TARGET_AVAILABLE:
                        LDY             #$00
?BYTE:                 LDA             STR8_HIMON_START,Y
                        CMP             #$FF
                        BNE             ?YES
                        INY
                        CPY             #$10
                        BNE             ?BYTE
                        CLC
                        RTS
?YES:                  SEC
                        RTS
                        ENDIF

                        IF              STR8_V1_LAYOUT
; H is specifically HIMON warm entry, not a generic local-$C000 launch. Match
; the complete fixed image marker before writing HIMON's warm signature to RAM.
STR8_LOCAL_HIMON_AVAILABLE:
                        LDX             #HIMON_IMAGE_ID_SIZE-1
?BYTE:                 LDA             HIMON_IMAGE_ID_ADDR,X
                        CMP             STR8_HIMON_WARM_SIGNATURE,X
                        BNE             ?NO
                        DEX
                        BPL             ?BYTE
                        SEC
                        RTS
?NO:                   CLC
                        RTS

                        IF              STR8_V1_INSTALLER_TXN
                        ELSE
STR8_ENTER_MENU_NO_HIMON:
                        LDX             #<MSG_NO_TARGET
                        LDY             #>MSG_NO_HIMON
                        BRA             STR8_ENTER_MENU_NO_TARGET_PRINT
                        ENDIF
                        ENDIF

STR8_ENTER_MENU_NO_BOOT:
                        JSR             STR8_CON_FLUSH_RX
                        LDX             #<MSG_NO_TARGET
                        IF              STR8_V1_INSTALLER_TXN
STR8_ENTER_MENU_NO_TARGET_PRINT:
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_NO_TARGET
STR8_ENTER_MENU_NO_TARGET_PRINT:
                        JSR             STR8_PRINT_XY
                        ENDIF
                        JMP             STR8_ENTER_MENU_HELP

                        IF              STR8_RAM_PROOF
                        ELSE
; OUT: C=1 and A='0'/'1'/'2'/'H'/'S' when a choice was consumed.
;      C=0 if the timeout elapsed.
; Six one-second WAIT pulses quarantine USB enumeration and cannot consume a
; key. At the midpoint RX is flushed, identity and selector are printed, and
; six one-second live dots poll only 0/1/2/H/S.
STR8_STARTUP_DELAY:
                        STZ             STR8_BOOT_KEY_ENABLE
                        IF              STR8_V1_LAYOUT
                        LDX             #<MSG_RESET
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_CRLF
                        JSR             STR8_PRINT_XY
                        ENDIF
                        ENDIF
                        LDA             #STR8_STARTUP_DOT_COUNT
?TICK:
                        PHA
                        CMP             #STR8_STARTUP_LIVE_TICKS
                        BNE             ?WAIT
                        JSR             STR8_CON_FLUSH_RX
                        INC             STR8_BOOT_KEY_ENABLE
                        LDX             #<MSG_ID
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_ID
                        JSR             STR8_PRINT_XY
                        ENDIF
                        IF              STR8_V1_LAYOUT
                        ELSE
                        LDX             #<MSG_BOOT_PROMPT
                        LDY             #>MSG_BOOT_PROMPT
                        JSR             STR8_PRINT_XY
                        ENDIF
?WAIT:
                        IF              STR8_V1_LAYOUT
                        LDX             #<MSG_WAIT
                        LDA             STR8_BOOT_KEY_ENABLE
                        BEQ             ?PULSE
                        LDX             #<MSG_LIVE_DOT
?PULSE:
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_WAIT
                        JSR             STR8_PRINT_XY
                        ENDIF
                        ENDIF
                        LDA             #STR8_STARTUP_DOT_A
                        JSR             STR8_DELAY_FIXED_A
                        IF              STR8_V1_LAYOUT
                        ELSE
                        LDA             #'.'
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        ENDIF
                        JSR             STR8_BOOT_KEY_POLL_IF_ENABLED
                        BCS             ?KEY_PRESSED
                        PLA
                        DEC             A
                        BNE             ?TICK
                        CLC
                        RTS
?KEY_PRESSED:          TAX
                        PLA
                        TXA
                        SEC
                        RTS

STR8_DELAY_FIXED_A:
                        LDX             #STR8_DELAY_TICK_X
                        LDY             #STR8_DELAY_TICK_Y
                        JMP             UTL_DELAY_AXY_8MHZ

STR8_BOOT_KEY_POLL_IF_ENABLED:
                        LDA             STR8_BOOT_KEY_ENABLE
                        BNE             STR8_BOOT_KEY_POLL
                        CLC
                        RTS

; 2026-08-05T00:00-05:00        Codex       Echo only accepted live-dot keys.
STR8_BOOT_KEY_POLL:
                        JSR             STR8_CON_READ_BYTE_NONBLOCK
                        BCC             ?NO
                        JSR             STR8_TO_UPPER_A
                        CMP             #'0'
                        BCC             ?NOT_DIGIT
                        IF              STR8_V1_LAYOUT
                        CMP             #'3'
                        ELSE
                        CMP             #'4'
                        ENDIF
                        BCC             ?YES
?NOT_DIGIT:
                        IF              STR8_V1_LAYOUT
                        CMP             #'C'
                        BEQ             ?YES
                        CMP             #'W'
                        BEQ             ?YES
                        ENDIF
                        CMP             #'S'
                        BEQ             ?YES
?NO:                   CLC
                        RTS
?YES:                  JSR             STR8_CON_WRITE_BYTE_BLOCK
                        SEC
                        RTS
                        ENDIF

                        IF              STR8_V1_INSTALLER_TXN
                        ELSE
STR8_PRINT_SCREEN:
                        LDX             #<MSG_ID
                        LDY             #>MSG_ID
                        JSR             STR8_PRINT_XY
                        LDX             #<MSG_SCREEN
                        LDY             #>MSG_SCREEN
                        JMP             STR8_PRINT_XY
                        ENDIF

STR8_CMD_LOOP:
                        JSR             STR8_PRINT_PROMPT
                        IF              STR8_V1_LAYOUT
                        LDX             #$02
                        JSR             STR8_READ_LINE
                        BEQ             ?ABORT
                        LDA             STR8_REC_DATA_BUF
                        BRA             ?DISPATCH
?ABORT:                JSR             STR8_CMD_ABORT
                        BRA             STR8_CMD_LOOP
                        ELSE
                        JSR             STR8_READ_COMMAND
                        CMP             #$00
                        BNE             ?DISPATCH
                        JSR             STR8_CMD_ABORT
                        BRA             STR8_CMD_LOOP
                        ENDIF
?DISPATCH:
                        JSR             STR8_DISPATCH_A
                        BRA             STR8_CMD_LOOP

                        IF              STR8_V1_LAYOUT
; Shared release line editor.
;   IN:  X = maximum accepted printable bytes (1-252)
;   OUT: A = line length; STR8_REC_DATA_BUF is uppercase and zero-terminated
; Backspace/Delete edit the buffer and terminal. CR, LF, and CR/LF terminate;
; the deferred LF after CR is consumed by the next text read, including S19.
STR8_READ_LINE:
                        STX             STR8_LINE_LIMIT
                        LDY             #$00
?READ:                 JSR             STR8_READ_TEXT_BYTE_BLOCK
                        CMP             #$0D
                        BEQ             ?CR
                        CMP             #$0A
                        BEQ             ?DONE
                        CMP             #$08
                        BEQ             ?BACKSPACE
                        CMP             #$7F
                        BEQ             ?BACKSPACE
                        CMP             #' '
                        BCC             ?READ
                        CMP             #$7F
                        BCS             ?READ
                        JSR             STR8_TO_UPPER_A
                        CPY             STR8_LINE_LIMIT
                        BCS             ?READ
                        STA             STR8_REC_DATA_BUF,Y
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        INY
                        BRA             ?READ
?BACKSPACE:            CPY             #$00
                        BEQ             ?READ
                        DEY
                        PHY
                        LDX             #<MSG_BACKSPACE
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_BACKSPACE
                        JSR             STR8_PRINT_XY
                        ENDIF
                        PLY
                        BRA             ?READ
?CR:                   INC             STR8_INPUT_SKIP_LF
?DONE:                 LDA             #$00
                        STA             STR8_REC_DATA_BUF,Y
                        TYA
                        RTS

STR8_READ_TEXT_BYTE_BLOCK:
?READ:                 JSR             STR8_CON_READ_BYTE_BLOCK
                        PHA
                        LDA             STR8_INPUT_SKIP_LF
                        BEQ             ?KEEP
                        STZ             STR8_INPUT_SKIP_LF
                        PLA
                        CMP             #$0A
                        BEQ             ?READ
                        RTS
?KEEP:                 PLA
                        RTS
                        ELSE
; 2026-07-31T14:32-05:00        Codex       Uppercase echo; controls cancel.
; OUT: A=uppercase printable byte, or zero for Backspace/Delete/CR/LF.
;      A CRLF pair produces one zero result; the paired LF is consumed later.
STR8_READ_COMMAND:
?READ:
                        JSR             STR8_CON_READ_BYTE_BLOCK
                        LDX             STR8_INPUT_SKIP_LF
                        BEQ             ?CONTROL
                        STZ             STR8_INPUT_SKIP_LF
                        CMP             #$0A
                        BEQ             ?READ
?CONTROL:
                        CMP             #$0D
                        BEQ             ?CR
                        CMP             #$0A
                        BEQ             ?CANCEL
                        CMP             #$08
                        BEQ             ?CANCEL
                        CMP             #$7F
                        BEQ             ?CANCEL
                        JSR             STR8_TO_UPPER_A
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        RTS
?CR:                   INC             STR8_INPUT_SKIP_LF
?CANCEL:               LDA             #$00
                        RTS
                        ENDIF

; IN/OUT: A=ASCII byte; lowercase a-z becomes uppercase.
STR8_TO_UPPER_A:
                        CMP             #'a'
                        BCC             ?DONE
                        CMP             #$7B
                        BCS             ?DONE
                        AND             #$DF
?DONE:                 RTS

; ----------------------------------------------------------------------------
; Command dispatch
; ----------------------------------------------------------------------------
STR8_DISPATCH_A:
                        IF              STR8_V1_LAYOUT
                        CMP             #'C'
                        BEQ             ?HIMON
                        CMP             #'W'
                        BNE             ?NOT_SELECT
?HIMON:
                        LDX             STR8_REC_DATA_BUF+1
                        BNE             ?NOT_SELECT
                        JMP             STR8_CMD_SELECT_HIMON
                        ELSE
                        CMP             #'0'
                        BCC             ?NOT_SELECT
                        CMP             #'4'
                        BCS             ?NOT_SELECT
                        JMP             STR8_CMD_SELECT_A
                        ENDIF
?NOT_SELECT:
                        IF              STR8_V1_LAYOUT
                        CMP             #'L'
                        BNE             ?NOT_L
                        LDX             STR8_REC_DATA_BUF+1
                        BEQ             STR8_CMD_LOAD_RAM
                        RTS
?NOT_L:
                        CMP             #'I'
                        BEQ             STR8_CMD_INSTALL_PREVIEW
?NOT_I:
                        ENDIF
                        CMP             #'J'
                        BNE             ?NOT_J
                        JMP             STR8_CMD_JUMP_BANK
?NOT_J:
                        IF              STR8_V1_LAYOUT
                        ELSE
                        CMP             #'U'
                        BNE             ?NOT_U
                        JMP             STR8_CMD_UPDATE_HIMON
?NOT_U:
                        ENDIF
                        JMP             STR8_CMD_UNKNOWN

                        IF              STR8_V1_LAYOUT
; Recovery RAM loader.  Every complete S1 span must stay in $2000-$7AFF.
; A valid non-empty stream executes its in-range S9 address immediately.
STR8_CMD_LOAD_RAM:
                        LDX             #<MSG_I_SEND_S19
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        STZ             STR8_RAM_LOAD_HAVE_DATA
                        LDA             #STR8_REC_OP_PARSE
                        STA             STR8_REC_OP
                        STA             STR8_REC_FORMAT
                        STA             STR8_REC_SOURCE
?RECORD:               JSR             STR8_RECORD_SERVICE_BODY
                        BCC             ?FAIL
                        LDA             STR8_REC_KIND
                        CMP             #STR8_REC_KIND_DATA
                        BEQ             ?DATA
                        BCC             ?RECORD

; The parser publishes only METADATA, DATA, or END on success.
?END:                  LDA             STR8_RAM_LOAD_HAVE_DATA
                        BEQ             ?FAIL
                        LDA             STR8_REC_ENTRY_HI
                        SEC
                        SBC             #STR8_RAM_LOAD_MIN_HI
                        CMP             #(STR8_RAM_LOAD_LIMIT_HI-STR8_RAM_LOAD_MIN_HI)
                        BCS             ?FAIL
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        JMP             (STR8_REC_ENTRY_LO)

?DATA:                 LDA             STR8_REC_ADDR_HI
                        CMP             #STR8_RAM_LOAD_MIN_HI
                        BCC             ?FAIL
; Check the final byte, not only the first, so no record can cross into $7B00.
                        LDA             STR8_REC_DATA_LEN
                        BEQ             ?FAIL
                        DEC             A
                        CLC
                        ADC             STR8_REC_ADDR_LO
                        LDA             STR8_REC_ADDR_HI
                        ADC             #$00
                        BCS             ?FAIL
                        CMP             #STR8_RAM_LOAD_LIMIT_HI
                        BCS             ?FAIL
                        JSR             STR8_REC_LOAD_APPLY_POINTERS
                        LDY             #$00
?COPY:                 LDA             (STR8_COPY_PTR_LO),Y
                        STA             (STR8_PTR_LO),Y
                        INY
                        CPY             STR8_REC_WORK_COUNT
                        BNE             ?COPY
; Y equals the nonzero record length here, so this flag cannot wrap after
; 256 or more S1 records.
                        STY             STR8_RAM_LOAD_HAVE_DATA
                        BRA             ?RECORD
?FAIL:                 JSR             STR8_I_QUENCH_S19
                        JMP             STR8_CMD_ABORT

; I preflight for Banks 0-3 and the guarded write transaction.
STR8_CMD_INSTALL_PREVIEW:
                        LDA             STR8_REC_DATA_BUF+1
                        BEQ             ?PROMPT
                        RTS
?PROMPT:
                        LDX             #<MSG_I_BANK
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_I_BANK
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDX             #$01
                        JSR             STR8_READ_LINE
                        CMP             #$01
                        BEQ             ?BANK
                        JMP             STR8_CMD_ABORT
?BANK:
                        LDA             STR8_REC_DATA_BUF
                        CMP             #'0'
                        BCS             ?BANK_LOW_OK
                        JMP             ?BAD
?BANK_LOW_OK:
                        CMP             #'4'
                        BCC             ?BANK_VALID
                        JMP             ?BAD
?BANK_VALID:
                        AND             #$03
                        STA             STR8_INSTALL_BANK
                        JSR             STR8_I_READ_RANGE
                        BCS             ?RANGE_OK
                        JMP             ?BAD
?RANGE_OK:
                        LDA             STR8_INSTALL_BANK
                        JSR             STR8_DIR_VALIDATE_BANK_A
                        STX             STR8_INSTALL_PAIR
                        STA             STR8_INSTALL_STATE
                        BCC             ?INVALID
                        CMP             #STR8_DIR_RECORD_INCOMPLETE
                        BNE             ?CLASSIFY
; The old partial range is not stored.  Recovery therefore requires a complete
; writable-bank image so a different retry cannot hide half-programmed data.
                        LDA             STR8_INSTALL_START_HI
                        CMP             #$80
                        BNE             ?INVALID
                        LDA             STR8_INSTALL_BANK
                        CMP             #STR8_DIR_BANK3
                        BNE             ?RECOVER_32K
                        LDA             STR8_INSTALL_RANGE_LIMIT_HI
                        CMP             #$F0
                        BNE             ?INVALID
                        BRA             ?RECOVER_ROW
?RECOVER_32K:          LDA             STR8_INSTALL_RANGE_LIMIT_HI
                        BNE             ?INVALID
?RECOVER_ROW:          LDY             #STR8_DIR_SEAL
                        LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_SEAL_VALUE
                        BEQ             ?RECOVER_SEALED
; Reconstruct an interrupted first descriptor from the operator's same type
; and description.  The metadata writer accepts only erased or exact bytes.
                        LDA             #STR8_DIR_RECORD_EMPTY
                        STA             STR8_INSTALL_STATE
                        LDA             #$FF
                        STA             STR8_INSTALL_ENTRY_LO
                        STA             STR8_INSTALL_ENTRY_HI
                        JSR             STR8_I_READ_TYPE
                        BCC             ?BAD
                        JSR             STR8_I_READ_DESCRIPTION
                        BCC             ?BAD
                        JMP             STR8_I_PRINT_SUMMARY
?RECOVER_SEALED:       JSR             STR8_I_COPY_RECORD_METADATA
; A started Bank-3 enrollment with no published entry still needs the
; first-install finish path after the full recovery payload verifies.
                        LDA             STR8_INSTALL_BANK
                        CMP             #STR8_DIR_BANK3
                        BEQ             ?RECOVER_BANK3
                        JMP             STR8_I_PRINT_SUMMARY
?RECOVER_BANK3:
                        LDA             STR8_INSTALL_ENTRY_LO
                        AND             STR8_INSTALL_ENTRY_HI
                        CMP             #$FF
                        BEQ             ?RECOVER_NEEDS_ENTRY
                        JMP             STR8_I_PRINT_SUMMARY
?RECOVER_NEEDS_ENTRY:
                        LDA             #STR8_INSTALL_NEEDS_ENTRY
                        STA             STR8_INSTALL_STATE
                        JMP             STR8_I_PRINT_SUMMARY
?CLASSIFY:
                        CMP             #STR8_DIR_RECORD_EMPTY
                        BNE             ?EXISTING
                        LDA             #$FF
                        STA             STR8_INSTALL_ENTRY_LO
                        STA             STR8_INSTALL_ENTRY_HI
                        JSR             STR8_I_READ_TYPE
                        BCC             ?BAD
                        JSR             STR8_I_READ_DESCRIPTION
                        BCC             ?BAD
                        JMP             STR8_I_PRINT_SUMMARY
?EXISTING:             JSR             STR8_I_COPY_RECORD_METADATA
                        JMP             STR8_I_PRINT_SUMMARY
?INVALID:              LDX             #<MSG_I_INVALID
                        IF              STR8_V1_INSTALLER_TXN
                        JMP             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_I_INVALID
                        JMP             STR8_PRINT_XY
                        ENDIF
?BAD:                  JMP             STR8_CMD_UNKNOWN

STR8_I_READ_TYPE:
                        LDX             #<MSG_I_TYPE_PROMPT
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_I_TYPE_PROMPT
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDX             #$02
                        JSR             STR8_READ_LINE
                        CMP             #$02
                        BNE             ?FAIL
                        LDA             STR8_REC_DATA_BUF
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
                        STA             STR8_REC_WORK_TMP
                        LDA             STR8_REC_DATA_BUF+1
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
                        ORA             STR8_REC_WORK_TMP
                        STA             STR8_INSTALL_TYPE
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

; Read one sector ("C") or an inclusive sector span ("C-E"). Publish the
; 4K-aligned start high byte, exclusive limit high byte, and sector count.
; $F + 1 deliberately becomes the wrapped exclusive limit high byte $00.
STR8_I_READ_RANGE:
                        LDX             #<MSG_I_RANGE_PROMPT
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_I_RANGE_PROMPT
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDX             #$04
                        JSR             STR8_READ_LINE
                        DEC             A
                        TAX
                        BEQ             ?END_CHAR
                        CPX             #$02
                        BNE             ?FAIL
                        LDA             STR8_REC_DATA_BUF+1
                        CMP             #'-'
                        BNE             ?FAIL
?END_CHAR:             LDA             STR8_REC_DATA_BUF,X
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
?END:                  STA             STR8_REC_WORK_TMP
                        LDA             STR8_REC_DATA_BUF
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
                        CMP             #$08
                        BCC             ?FAIL
                        STA             STR8_INSTALL_START_HI
                        LDA             STR8_REC_WORK_TMP
                        CMP             STR8_INSTALL_START_HI
                        BCC             ?FAIL
                        LDX             STR8_INSTALL_BANK
                        CPX             #STR8_DIR_BANK3
                        BNE             ?VALID
                        CMP             #$0F
                        BCS             ?FAIL
?VALID:                SEC
                        SBC             STR8_INSTALL_START_HI
                        INC             A
                        STA             STR8_INSTALL_SECTOR_COUNT
                        LDA             STR8_REC_WORK_TMP
                        INC             A
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
                        STA             STR8_INSTALL_RANGE_LIMIT_HI
                        LDA             STR8_INSTALL_START_HI
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
                        STA             STR8_INSTALL_START_HI
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

STR8_I_READ_DESCRIPTION:
                        LDX             #<MSG_I_DESC_PROMPT
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_I_DESC_PROMPT
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDX             #STR8_DIR_DESCRIPTION_LEN
                        JSR             STR8_READ_LINE
                        CMP             #STR8_DIR_DESCRIPTION_LEN
                        BNE             ?FAIL
                        LDX             #(STR8_DIR_DESCRIPTION_LEN-1)
?BYTE:                 LDA             STR8_REC_DATA_BUF,X
                        JSR             STR8_DIR_DESCRIPTION_BYTE_A
                        BCC             ?FAIL
                        STA             STR8_INSTALL_DESC,X
                        DEX
                        BPL             ?BYTE
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

STR8_I_COPY_RECORD_METADATA:
                        LDY             #STR8_DIR_TYPE
                        LDA             (STR8_PTR_LO),Y
                        STA             STR8_INSTALL_TYPE
                        LDX             #$00
                        LDY             #STR8_DIR_DESCRIPTION
?DESC:                 LDA             (STR8_PTR_LO),Y
                        STA             STR8_INSTALL_DESC,X
                        INY
                        INX
                        CPX             #STR8_DIR_DESCRIPTION_LEN
                        BNE             ?DESC
                        LDY             #STR8_DIR_ENTRY_LO
                        LDA             (STR8_PTR_LO),Y
                        STA             STR8_INSTALL_ENTRY_LO
                        INY
                        LDA             (STR8_PTR_LO),Y
                        STA             STR8_INSTALL_ENTRY_HI
                        RTS

STR8_I_PRINT_SUMMARY:
                        LDX             #<MSG_I_SUMMARY
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_I_SUMMARY
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDA             STR8_INSTALL_BANK
                        JSR             STR8_WRITE_DEC_DIGIT_A
                        LDA             #' '
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        LDA             STR8_INSTALL_START_HI
                        JSR             STR8_WRITE_HEX_HIGH_NIBBLE_A
                        LDA             #'-'
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        LDA             STR8_INSTALL_RANGE_LIMIT_HI
                        SEC
                        SBC             #$10
                        JSR             STR8_WRITE_HEX_HIGH_NIBBLE_A
                        IF              STR8_V1_INSTALLER_DRY
                        LDA             STR8_INSTALL_PAIR
                        CMP             #STR8_DIR_PAIR_NONE
                        BEQ             STR8_I_NO_WRITE
                        IF              STR8_V1_INSTALLER_TXN
                        LDX             #<MSG_I_WRITE_CONFIRM
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDX             #<MSG_I_STAGE_CONFIRM
                        LDY             #>MSG_I_STAGE_CONFIRM
                        JSR             STR8_PRINT_XY
                        ENDIF
                        JSR             STR8_CONFIRM_Y
                        BCS             ?CONFIRMED
                        JMP             STR8_CMD_ABORT
?CONFIRMED:
; Prepare the worker and persistent transaction before inviting the sender.
; First enrollment writes START, immutable metadata, and seal here, so an
; ordinary terminal may stream the S19 at full speed once S19 is visible.
                        JSR             STR8_COPY_WORKER_TO_RAM
                        BCC             ?INSTALL_FAIL
                        JSR             STR8_I_BEGIN_TRANSACTION
                        BCC             ?INSTALL_FAIL
                        LDX             #<MSG_I_SEND_S19
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_I_SEND_S19
                        JSR             STR8_PRINT_XY
                        ENDIF
                        JSR             STR8_I_RECEIVE_DENSE
                        BCC             ?INSTALL_FAIL
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_I_FINISH_TRANSACTION
                        BCC             ?INSTALL_FAIL
                        LDX             #<MSG_I_INSTALL_OK
                        JMP             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDX             #<MSG_I_STAGE_OK
                        LDY             #>MSG_I_STAGE_OK
                        JSR             STR8_PRINT_XY
                        BRA             STR8_I_NO_WRITE
                        ENDIF
?INSTALL_FAIL:         LDX             #<MSG_I_FAIL
                        IF              STR8_V1_INSTALLER_TXN
                        JMP             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_I_S19_FAIL
                        JSR             STR8_PRINT_XY
                        ENDIF
STR8_I_NO_WRITE:       LDX             #<MSG_I_NO_WRITE
                        IF              STR8_V1_INSTALLER_TXN
                        JMP             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_I_NO_WRITE
                        JMP             STR8_PRINT_XY
                        ENDIF

                        IF              STR8_V1_INSTALLER_TXN
; START is the first persistent write after confirmation. Empty records then
; receive their immutable TYPE/DESCRIPTION bytes. The seal and Bank-3 entry
; remain erased until the complete payload has passed read-back verification.
STR8_I_BEGIN_TRANSACTION:
                        JSR             STR8_I_WRITE_JOURNAL_START
                        BCC             ?FAIL
                        LDA             STR8_INSTALL_STATE
                        CMP             #STR8_DIR_RECORD_EMPTY
                        BNE             ?OK
                        JSR             STR8_I_WRITE_METADATA
                        BCC             ?FAIL
; Seal the descriptor as soon as its immutable metadata is exact.  Journal
; STARTED still prevents launch until the verified payload completes.
                        LDA             #STR8_DIR_SEAL_VALUE
                        STA             STR8_REC_DATA_BUF
                        LDA             #STR8_DIR_SEAL
                        JSR             STR8_I_SET_DIR_ADDRESS_A
                        LDA             #$01
                        STA             STR8_REC_DATA_LEN
                        JSR             STR8_DIR_WRITE_BYTES
                        BCC             ?FAIL
?OK:                   SEC
                        RTS
; Both incoming write failures branch with carry clear.
?FAIL:                 RTS

; COMPLETE is always last. On a first Bank-3 install, publish the immutable
; local entry after payload verification and before completing the journal.
STR8_I_FINISH_TRANSACTION:
                        LDA             STR8_INSTALL_STATE
                        CMP             #STR8_DIR_RECORD_EMPTY
                        BEQ             ?NEEDS_ENTRY
                        CMP             #STR8_INSTALL_NEEDS_ENTRY
                        BNE             STR8_I_WRITE_JOURNAL_COMPLETE
?NEEDS_ENTRY:
                        LDA             STR8_INSTALL_BANK
                        CMP             #STR8_DIR_BANK3
                        BNE             STR8_I_WRITE_JOURNAL_COMPLETE
                        LDA             STR8_INSTALL_ENTRY_LO
                        STA             STR8_REC_DATA_BUF
                        LDA             STR8_INSTALL_ENTRY_HI
                        STA             STR8_REC_DATA_BUF+1
                        LDA             #STR8_DIR_ENTRY_LO
                        JSR             STR8_I_SET_DIR_ADDRESS_A
                        LDA             #$02
                        STA             STR8_REC_DATA_LEN
                        JSR             STR8_DIR_WRITE_BYTES
                        BCC             ?FAIL
                        BRA             STR8_I_WRITE_JOURNAL_COMPLETE
; Both directory-writer failures branch with carry clear.
?FAIL:                 RTS

STR8_I_WRITE_METADATA:
                        LDA             STR8_INSTALL_TYPE
                        STA             STR8_REC_DATA_BUF
                        LDA             #$FF
                        LDX             #STR8_DIR_ENTRY_HI
?ERASED:               STA             STR8_REC_DATA_BUF,X
                        DEX
                        BNE             ?ERASED
                        LDX             #$00
?DESC:                 LDA             STR8_INSTALL_DESC,X
                        STA             STR8_REC_DATA_BUF+STR8_DIR_DESCRIPTION,X
                        INX
                        CPX             #STR8_DIR_DESCRIPTION_LEN
                        BNE             ?DESC
; On recovery, already-programmed metadata bytes must be exact.  A different
; answer or a partially corrupted byte fails closed before any payload write.
                        LDA             #$00
                        JSR             STR8_I_SET_DIR_ADDRESS_A
                        LDY             #$00
?EXACT:                LDA             (STR8_PTR_LO),Y
                        CMP             #$FF
                        BEQ             ?EXACT_NEXT
                        CMP             STR8_REC_DATA_BUF,Y
                        BNE             ?FAIL
?EXACT_NEXT:           INY
                        CPY             #(STR8_DIR_ENTRY_HI+1)
                        BNE             ?EXACT
                        LDA             #(STR8_DIR_DESCRIPTION+STR8_DIR_DESCRIPTION_LEN)
                        STA             STR8_REC_DATA_LEN
                        JMP             STR8_DIR_WRITE_BYTES
?FAIL:                 CLC
                        RTS

STR8_I_WRITE_JOURNAL_START:
                        LDA             STR8_INSTALL_PAIR
                        ASL             A
                        TAX
                        BRA             STR8_I_WRITE_JOURNAL_MASK_A
STR8_I_WRITE_JOURNAL_COMPLETE:
                        LDA             STR8_INSTALL_PAIR
                        ASL             A
                        INC             A
                        TAX
STR8_I_WRITE_JOURNAL_MASK_A:
                        TXA
                        AND             #$07
                        TAX
                        LDA             STR8_I_JOURNAL_MASK,X
                        STA             STR8_REC_DATA_BUF
                        LDA             STR8_INSTALL_PAIR
                        LSR             A
                        LSR             A
                        CLC
                        ADC             #STR8_DIR_JOURNAL
                        JSR             STR8_I_SET_DIR_ADDRESS_A
                        LDY             #$00
                        LDA             (STR8_PTR_LO),Y
                        AND             STR8_REC_DATA_BUF
                        STA             STR8_REC_DATA_BUF
                        LDA             #$01
                        STA             STR8_REC_DATA_LEN
                        JMP             STR8_DIR_WRITE_BYTES

; IN: A=record-relative byte offset. Publish both the request address and a
; resident pointer used to derive a one-to-zero journal byte.
STR8_I_SET_DIR_ADDRESS_A:
                        PHA
                        LDA             STR8_INSTALL_BANK
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
; Bank 0-3 leaves carry clear after the fourth shift.
                        ADC             #<STR8_DIR_BASE
                        STA             STR8_REC_ADDR_LO
                        PLA
                        CLC
                        ADC             STR8_REC_ADDR_LO
                        STA             STR8_REC_ADDR_LO
                        STA             STR8_PTR_LO
                        LDA             #>STR8_DIR_BASE
                        STA             STR8_REC_ADDR_HI
                        STA             STR8_PTR_HI
                        RTS

STR8_I_JOURNAL_MASK:
                        DB              $FE,$FD,$FB,$F7,$EF,$DF,$BF,$7F
                        ENDIF

; Receive exactly the operator-selected 4K-aligned payload range. The caller
; has already copied the worker and opened the persistent transaction before
; printing S19. The selected final sector stays in RAM through S9 and COMMIT.
STR8_I_RECEIVE_DENSE:
                        STZ             STR8_INSTALL_EXPECT_LO
                        STZ             STR8_INSTALL_PHASE
                        LDA             STR8_INSTALL_START_HI
                        STA             STR8_INSTALL_EXPECT_HI
                        LDA             STR8_INSTALL_START_HI
                        STA             STR8_INSTALL_SECTOR_HI
                        LDA             #STR8_REC_OP_PARSE
                        STA             STR8_REC_OP
                        LDA             #STR8_REC_FORMAT_S19
                        STA             STR8_REC_FORMAT
                        LDA             #STR8_REC_SOURCE_CONSOLE
                        STA             STR8_REC_SOURCE
?RECORD:               JSR             STR8_RECORD_SERVICE_BODY
                        BCS             ?PARSED
                        LDA             STR8_REC_STATUS
                        JMP             STR8_I_RECEIVE_FAIL_A
?PARSED:
                        LDA             STR8_REC_KIND
                        CMP             #STR8_REC_KIND_METADATA
                        BEQ             ?METADATA
                        CMP             #STR8_REC_KIND_DATA
                        BEQ             ?DATA
                        CMP             #STR8_REC_KIND_END
                        BNE             ?BAD_KIND
                        JMP             ?END
?BAD_KIND:             BRA             ?DENSE_FAIL
?METADATA:             LDA             STR8_INSTALL_PHASE
                        BNE             ?DENSE_FAIL
?FIRST_METADATA:
                        INC             STR8_INSTALL_PHASE
                        BRA             ?RECORD
?DATA:                 LDA             STR8_INSTALL_PHASE
                        CMP             #$03
                        BCS             ?DENSE_FAIL
?NOT_FINAL:
                        LDA             STR8_REC_ADDR_LO
                        CMP             STR8_INSTALL_EXPECT_LO
                        BNE             ?DENSE_FAIL
?ADDRESS_LO:
                        LDA             STR8_REC_ADDR_HI
                        CMP             STR8_INSTALL_EXPECT_HI
                        BNE             ?DENSE_FAIL
?ADDRESS_HI:
                        LDA             STR8_REC_DATA_LEN
                        BNE             ?HAVE_DATA
?DENSE_FAIL:           JMP             STR8_I_RECEIVE_DENSE_FAIL
?HAVE_DATA:
                        LDA             STR8_INSTALL_EXPECT_LO
                        STA             STR8_PTR_LO
                        LDA             STR8_INSTALL_EXPECT_HI
                        AND             #$0F
                        CLC
                        ADC             #$0A
                        STA             STR8_PTR_HI
                        LDX             #$00
?COPY:                 LDY             #$00
                        LDA             STR8_REC_DATA_BUF,X
                        STA             (STR8_PTR_LO),Y
                        INX
                        INC             STR8_PTR_LO
                        BNE             ?EXPECTED
                        INC             STR8_PTR_HI
?EXPECTED:             INC             STR8_INSTALL_EXPECT_LO
                        BNE             ?COUNT
                        INC             STR8_INSTALL_EXPECT_HI
?COUNT:                DEC             STR8_REC_DATA_LEN
                        LDA             STR8_INSTALL_EXPECT_LO
                        BNE             ?MORE
                        LDA             STR8_INSTALL_EXPECT_HI
                        AND             #$0F
                        BNE             ?MORE
                        LDA             STR8_INSTALL_EXPECT_HI
                        CMP             STR8_INSTALL_RANGE_LIMIT_HI
                        BEQ             ?FINAL
                        JSR             STR8_I_STAGE_SECTOR_READY
                        BCS             ?SECTOR_READY
                        JMP             STR8_I_RECEIVE_FLASH_FAIL
?SECTOR_READY:
                        LDA             STR8_INSTALL_SECTOR_HI
                        CLC
                        ADC             #$10
                        STA             STR8_INSTALL_SECTOR_HI
                        STZ             STR8_PTR_LO
                        LDA             #$0A
                        STA             STR8_PTR_HI
?MORE:                 LDA             STR8_REC_DATA_LEN
                        BNE             ?COPY
; Phase 2 records that the first valid S1 has entered the sector tray. Worker
; and directory preparation were completed before S19 was printed.
                        LDA             STR8_INSTALL_PHASE
                        CMP             #$02
                        BEQ             ?NEXT_RECORD
                        LDA             #$02
                        STA             STR8_INSTALL_PHASE
?NEXT_RECORD:
                        JMP             ?RECORD
?FINAL:                LDA             STR8_REC_DATA_LEN
                        BNE             ?DENSE_FAIL
?FINAL_EXACT:
                        LDA             #$03
                        STA             STR8_INSTALL_PHASE
                        JMP             ?RECORD

?END:                  LDA             STR8_INSTALL_PHASE
                        CMP             #$03
                        BNE             ?DENSE_FAIL
?COVERAGE_OK:
                        LDA             STR8_INSTALL_BANK
                        CMP             #STR8_DIR_BANK3
                        BEQ             ?BANK3_ENTRY

; A complete Bank-0/1/2 image publishes the same entry as its RESET vector.
                        LDA             STR8_INSTALL_START_HI
                        CMP             #$80
                        BNE             ?OPTIONAL_ENTRY
                        LDA             STR8_INSTALL_RANGE_LIMIT_HI
                        BNE             ?OPTIONAL_ENTRY
                        LDA             STR8_REC_ENTRY_LO
                        CMP             $19FC
                        BNE             ?ENTRY_FAIL
                        LDA             STR8_REC_ENTRY_HI
                        CMP             $19FD
                        BNE             ?ENTRY_FAIL
                        LDA             STR8_REC_ENTRY_LO
                        AND             STR8_REC_ENTRY_HI
                        CMP             #$FF
                        BEQ             ?ENTRY_FAIL
                        BRA             ?COMMIT

?OPTIONAL_ENTRY:       LDA             STR8_REC_ENTRY_LO
                        AND             STR8_REC_ENTRY_HI
                        CMP             #$FF
                        BEQ             ?COMMIT
                        JSR             STR8_I_ENTRY_IN_RANGE
                        BCC             ?ENTRY_FAIL
                        BRA             ?COMMIT

?BANK3_ENTRY:          LDA             STR8_INSTALL_STATE
                        CMP             #STR8_DIR_RECORD_EMPTY
                        BEQ             ?NEW_BANK3_ENTRY
                        CMP             #STR8_INSTALL_NEEDS_ENTRY
                        BEQ             ?NEW_BANK3_ENTRY
; An existing immutable Bank-3 entry accepts $FFFF (no change) or an exact
; match.  It need not lie in the partial range being refreshed.
                        LDA             STR8_REC_ENTRY_LO
                        AND             STR8_REC_ENTRY_HI
                        CMP             #$FF
                        BEQ             ?COMMIT
                        LDA             STR8_REC_ENTRY_LO
                        CMP             STR8_INSTALL_ENTRY_LO
                        BNE             ?ENTRY_FAIL
                        LDA             STR8_REC_ENTRY_HI
                        CMP             STR8_INSTALL_ENTRY_HI
                        BNE             ?ENTRY_FAIL
                        BRA             ?COMMIT

?NEW_BANK3_ENTRY:      LDA             STR8_REC_ENTRY_LO
                        AND             STR8_REC_ENTRY_HI
                        CMP             #$FF
                        BEQ             ?ENTRY_FAIL
                        JSR             STR8_I_ENTRY_IN_RANGE
                        BCC             ?ENTRY_FAIL
                        LDA             STR8_REC_ENTRY_LO
                        STA             STR8_INSTALL_ENTRY_LO
                        LDA             STR8_REC_ENTRY_HI
                        STA             STR8_INSTALL_ENTRY_HI
                        BRA             ?COMMIT

?ENTRY_FAIL:           BRA             STR8_I_RECEIVE_ENTRY_FAIL

?COMMIT:               JSR             STR8_I_CONFIRM_COMMIT
                        BCC             STR8_I_RECEIVE_TRAIL_FAIL
                        JSR             STR8_I_STAGE_SECTOR_READY
                        BCC             STR8_I_RECEIVE_FLASH_FAIL
                        SEC
                        RTS

STR8_I_ENTRY_IN_RANGE:
                        LDA             STR8_REC_ENTRY_HI
                        CMP             STR8_INSTALL_START_HI
                        BCC             ?FAIL
                        LDX             STR8_INSTALL_RANGE_LIMIT_HI
                        BEQ             ?OK
                        CMP             STR8_INSTALL_RANGE_LIMIT_HI
                        BCS             ?FAIL
?OK:
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

STR8_I_CONFIRM_COMMIT:
                        LDX             #<MSG_I_COMMIT
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        JMP             STR8_CONFIRM_Y

STR8_I_RECEIVE_DENSE_FAIL:
STR8_I_RECEIVE_WORKER_FAIL:
STR8_I_RECEIVE_DIRECTORY_FAIL:
STR8_I_RECEIVE_ENTRY_FAIL:
STR8_I_RECEIVE_FLASH_FAIL:
STR8_I_RECEIVE_TRAIL_FAIL:
STR8_I_RECEIVE_FAIL_A:
                        BRA             STR8_I_QUENCH_S19

STR8_I_STAGE_SECTOR_READY:
                        IF              STR8_V1_INSTALLER_TXN
                        LDA             STR8_INSTALL_SECTOR_HI
                        STA             STR8_MARK_SECTOR_HI
                        LDA             #$0A
                        STA             STR8_STAGE_BUF_HI
                        LDA             STR8_INSTALL_BANK
                        STA             STR8_COPY_DST_BANK
                        LDA             #STR8_COPY_MODE_PROGRAM_STAGED
                        STA             STR8_COPY_MODE
                        JSR             STR8_I_RUN_SECTOR_WORKER
                        BCC             ?FAIL
                        LDA             #'.'
; The blocking writer returns only after its nonblocking write sets carry.
                        JMP             STR8_CON_WRITE_BYTE_BLOCK
; The worker failure branch already carries clear.
?FAIL:                 RTS

STR8_I_RUN_SECTOR_WORKER:
                        JMP             STR8_WORKER_RUN
                        ELSE
; The receive/staging proof deliberately cannot reach flash.
                        SEC
                        RTS
                        ENDIF

; After a fatal L/I receive error, keep the command parser closed until the
; sender reaches a validated S9 or the operator sends Ctrl-C.  Reusing the
; record parser also resynchronizes after a malformed partial line.
STR8_I_QUENCH_S19:
?RECORD:               LDA             STR8_REC_KIND
                        CMP             #STR8_REC_KIND_END
                        BEQ             ?DONE
                        LDA             STR8_REC_STATUS
                        CMP             #STR8_REC_ABORT
                        BEQ             ?DONE
                        JSR             STR8_RECORD_SERVICE_BODY
                        BRA             ?RECORD
?DONE:
                        CLC
                        RTS
                        ELSE
                        LDX             #<MSG_I_NO_WRITE
                        LDY             #>MSG_I_NO_WRITE
                        JMP             STR8_PRINT_XY
                        ENDIF
                        ENDIF

; 2026-07-28T21:19-05:00        Codex       J0-J2 hand off opaque banks from RAM.
; 2026-07-28T22:48-05:00        Codex       Echo the two-byte J command at the prompt.
; 2026-08-02T00:00-05:00        Codex       J3 returns a running STR8 copy to Bank 3.
STR8_CMD_JUMP_BANK:
                        IF              STR8_V1_LAYOUT
                        LDA             STR8_REC_DATA_BUF+1
                        BEQ             ?BAD
                        ELSE
?OPERAND:
                        JSR             STR8_READ_COMMAND
                        CMP             #$00
                        BNE             ?HAVE_OPERAND
                        JMP             STR8_CMD_ABORT
?HAVE_OPERAND:
                        CMP             #' '
                        BEQ             ?OPERAND
                        ENDIF
                        CMP             #'0'
                        BCC             ?BAD
                        CMP             #'4'
                        BCS             ?BAD
                        AND             #$03
                        JSR             STR8_JUMP_BANK_PREP_A
                        IF              STR8_V1_LAYOUT
                        BRA             STR8_JUMP_BANK_LAUNCH
                        ELSE
                        JMP             STR8_JUMP_BANK_LAUNCH
                        ENDIF
?BAD:
                        BRA             STR8_CMD_UNKNOWN

                        IF              STR8_V1_LAYOUT
                        ELSE
; Legacy V0 bare 0/1/2 reuse the proven J handoff. Bare 3 enters Bank-3 HIMON.
STR8_CMD_SELECT_A:
                        CMP             #'3'
                        BEQ             STR8_CMD_SELECT_HIMON
                        AND             #$03
                        JSR             STR8_JUMP_BANK_PREP_A
                        JMP             STR8_JUMP_BANK_LAUNCH
                        ENDIF

; C/W enter the local cold/warm target without selecting a bank. The RAM-proof
; V0 path retains its legacy explicit Bank-3 selection before entering HIMON.
STR8_CMD_SELECT_HIMON:
                        PHA
                        IF              STR8_RAM_PROOF
                        JSR             STR8_SELECT_BANK_3
                        ENDIF
                        JSR             STR8_CON_FLUSH_RX
                        LDX             #<MSG_CRLF
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_CRLF
                        JSR             STR8_PRINT_XY
                        ENDIF
                        IF              STR8_V1_LAYOUT
                        PLA
                        CMP             #'C'
                        BNE             ?WARM
                        JMP             STR8_ENTER_HIMON_COLD
?WARM:
                        ELSE
                        PLA
                        ENDIF
                        JMP             STR8_ENTER_HIMON_WARM

                        IF              STR8_V1_LAYOUT
                        ELSE
; 2026-05-17T21:20-05:00        WLP2        U is the first fixed-gate HIMON S19 update.
STR8_CMD_UPDATE_HIMON:
                        IF              STR8_RAM_PROOF
                        LDX             #<MSG_UPDATE_ROM_ONLY
                        LDY             #>MSG_UPDATE_ROM_ONLY
                        JMP             STR8_PRINT_XY
                        ELSE
                        LDX             #<MSG_UPDATE_HIMON
                        LDY             #>MSG_UPDATE_HIMON
                        JSR             STR8_PRINT_XY
                        JSR             STR8_CONFIRM_Y
                        BCC             STR8_CMD_ABORT
                        JSR             STR8_STAGE_HIMON_BLANK
                        JSR             STR8_UPD_INIT
                        LDX             #<MSG_UPDATE_SEND_S19
                        LDY             #>MSG_UPDATE_SEND_S19
                        JSR             STR8_PRINT_XY
                        JSR             STR8_READ_HIMON_S19
                        BCC             STR8_CMD_UPDATE_S19_FAIL
                        LDA             STR8_UPD_MASK
                        BEQ             STR8_CMD_UPDATE_NO_DATA
                        LDX             #<MSG_UPDATE_WRITE
                        LDY             #>MSG_UPDATE_WRITE
                        JSR             STR8_PRINT_XY
                        JSR             STR8_CONFIRM_Y
                        BCC             STR8_CMD_ABORT
                        JSR             STR8_PROGRAM_HIMON_UPDATE
                        BCC             STR8_CMD_COPY_FAIL
                        JMP             STR8_CMD_OK
                        ENDIF

STR8_CMD_UPDATE_S19_FAIL:
                        JSR             STR8_CON_FLUSH_RX
                        LDX             #<MSG_S19_FAIL
                        LDY             #>MSG_S19_FAIL
                        JMP             STR8_PRINT_XY

STR8_CMD_UPDATE_NO_DATA:
                        LDX             #<MSG_S19_NO_DATA
                        LDY             #>MSG_S19_NO_DATA
                        JMP             STR8_PRINT_XY

                        ENDIF

; Legacy U is absent from v1.2, so its success path is dead in the transaction.
                        IF              STR8_V1_INSTALLER_TXN
                        ELSE
STR8_CMD_OK:
                        IF              STR8_RAM_PROOF
                        JSR             STR8_SELECT_BANK_3
                        ENDIF
                        LDX             #<MSG_OK
                        LDY             #>MSG_OK
                        JMP             STR8_PRINT_XY
                        ENDIF

STR8_CMD_ABORT:
                        IF              STR8_RAM_PROOF
                        JSR             STR8_SELECT_BANK_3
                        ENDIF
                        IF              STR8_V1_LAYOUT
                        LDX             #<MSG_I_INVALID
                        ELSE
                        LDX             #<MSG_ABORT
                        ENDIF
                        IF              STR8_V1_INSTALLER_TXN
                        JMP             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_ABORT
                        JMP             STR8_PRINT_XY
                        ENDIF

                        IF              STR8_V1_LAYOUT
                        ELSE
STR8_CMD_COPY_FAIL:
                        IF              STR8_RAM_PROOF
                        JSR             STR8_SELECT_BANK_3
                        ENDIF
                        JMP             STR8_PRINT_COPY_FAIL
                        ENDIF

STR8_CMD_UNKNOWN:
                        RTS

                        IF              STR8_RAM_PROOF
                        ELSE
STR8_BOOT_JUMP_BANK_A:
                        JSR             STR8_JUMP_BANK_PREP_A
                        JSR             STR8_CON_FLUSH_RX
                        LDX             #<MSG_BOOT_BANK_WAIT
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_BOOT_BANK_WAIT
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDA             #STR8_BANK_BOOT_DELAY_A
                        JSR             STR8_DELAY_FIXED_A
                        IF              STR8_V1_LAYOUT
                        BRA             STR8_JUMP_BANK_LAUNCH
                        ELSE
                        JMP             STR8_JUMP_BANK_LAUNCH
                        ENDIF
                        ENDIF

STR8_JUMP_BANK_PREP_A:
                        STA             STR8_JUMP_BANK
                        STZ             STR8_JUMP_VEC_LO
                        STZ             STR8_JUMP_VEC_HI
                        STZ             STR8_JUMP_STATUS
                        LDX             #<MSG_JUMP_B
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_JUMP_B
                        JSR             STR8_PRINT_XY
                        ENDIF
                        LDA             STR8_JUMP_BANK
                        JSR             STR8_WRITE_DEC_DIGIT_A
                        LDX             #<MSG_CRLF
                        IF              STR8_V1_INSTALLER_TXN
                        JSR             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_CRLF
                        JSR             STR8_PRINT_XY
                        ENDIF
                        RTS

STR8_JUMP_BANK_LAUNCH:
                        IF              STR8_V1_INSTALLER_TXN
; Bank 3 is the deliberate local STR8 re-entry exception. Banks 0-2 may
; launch only after their directory journal reaches COMPLETE.
                        LDA             STR8_JUMP_BANK
                        CMP             #STR8_DIR_BANK3
                        BCS             ?DIRECTORY_OK
                        JSR             STR8_DIR_VALIDATE_BANK_A
                        CMP             #STR8_DIR_RECORD_COMPLETE
                        BEQ             ?DIRECTORY_OK
                        JMP             STR8_PRINT_JUMP_FAIL
?DIRECTORY_OK:
                        ENDIF
                        JSR             STR8_CON_FLUSH_RX
                        LDA             #STR8_COPY_MODE_JUMP_BANK
                        STA             STR8_COPY_MODE
                        IF              STR8_RAM_PROOF
                        JSR             STR8_JUMP_BANK_RAM
                        ELSE
                        JSR             STR8_COPY_WORKER_TO_RAM
                        BCS             ?WORKER_READY
                        JMP             STR8_PRINT_JUMP_FAIL
?WORKER_READY:
                        JSR             STR8_WORKER_RUN
                        ENDIF
                        JMP             STR8_PRINT_JUMP_FAIL

; Published $F010 bank selector.
; IN:  A=bank 0-3; caller and JSR return address must be RAM below $8000.
; OUT: C=1 and selected bank remains visible; C=0 leaves the bank unchanged.
;      A/X/Y are clobbered. The copied RAM trampoline remains at $0203.
STR8_BANK_SELECT_SERVICE_BODY:
                        CMP             #STR8_BANK_COUNT
                        IF              STR8_RAM_PROOF
                        BCS             ?BAD_BANK_RAM
                        JSR             FLSH_BANK_SELECT_A
                        SEC
                        RTS
?BAD_BANK_RAM:         CLC
                        RTS
                        ELSE
                        BCS             ?BAD_BANK
                        PHA
                        TSX
                        LDA             $0103,X
                        BMI             ?BAD_RETURN
                        JSR             STR8_COPY_SELECTOR_TO_RAM
                        BCC             ?BAD_RETURN
                        PLA
                        JMP             STR8_BANK_SELECT_RAM
?BAD_RETURN:           PLA
?BAD_BANK:             CLC
                        RTS
                        ENDIF
STR8_BANK_SELECT_SERVICE_BODY_END:

; ----------------------------------------------------------------------------
; v1.22 Bank Directory validator for I and directory-gated J.
;
; STR8_DIR_VALIDATE_BANK_A
;   IN:  A=bank 0-3, Bank 3 visible
;   OUT: A=STR8_DIR_RECORD_*; X=next/retry pair or $FF; C=1 unless INVALID
;
; STR8_DIR_SCAN_JOURNAL
;   IN:  STR8_PTR_LO/HI points at a 16-byte record
;   OUT: A=STR8_DIR_JOURNAL_*; X=next/retry pair or $FF; C=1 unless INVALID
;
; These routines never select a bank and never mutate flash. The installer
; must reject INVALID, retry INCOMPLETE at the returned pair, and begin EMPTY
; at pair zero. Launch code may accept only COMPLETE.
; ----------------------------------------------------------------------------
STR8_DIR_VALIDATE_BANK_A:
                        CLD
                        CMP             #STR8_DIR_RECORD_COUNT
                        BCC             ?BANK_OK
                        IF              STR8_V1_LAYOUT
                        JMP             STR8_DIR_RETURN_RECORD_INVALID
                        ELSE
                        JMP             STR8_DIR_RETURN_RECORD_INVALID
                        ENDIF
?BANK_OK:              STA             STR8_DIR_BANK_WORK
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
                        CLC
                        ADC             #<STR8_DIR_BASE
                        STA             STR8_PTR_LO
                        LDA             #>STR8_DIR_BASE
                        STA             STR8_PTR_HI

; An exactly all-$FF record is the only EMPTY representation.
                        LDY             #$00
?EMPTY_SCAN:           LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_EMPTY_BYTE
                        BNE             ?STRUCTURE
                        INY
                        CPY             #STR8_DIR_RECORD_SIZE
                        BNE             ?EMPTY_SCAN
                        LDA             #STR8_DIR_RECORD_EMPTY
                        LDX             #$00
                        SEC
                        RTS

; Read the one-way event strip before requiring a completed descriptor.  A
; STARTED row with no seal is a recoverable first-install construction.
?STRUCTURE:            JSR             STR8_DIR_SCAN_JOURNAL
                        BCC             STR8_DIR_RETURN_RECORD_INVALID
                        STA             STR8_DIR_OPEN_WORK
                        STX             STR8_DIR_RESULT_PAIR
                        CMP             #STR8_DIR_JOURNAL_STARTED
                        BCC             STR8_DIR_RETURN_RECORD_INVALID
                        BNE             ?VALIDATE_DESCRIPTOR
                        LDY             #STR8_DIR_SEAL
                        LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_SEAL_VALUE
                        BEQ             ?VALIDATE_DESCRIPTOR
                        LDX             STR8_DIR_RESULT_PAIR
                        LDA             #STR8_DIR_RECORD_INCOMPLETE
                        SEC
                        RTS

; RESERVED must remain erased.
?VALIDATE_DESCRIPTOR:  LDY             #STR8_DIR_RESERVED
?RESERVED:             LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_EMPTY_BYTE
                        BNE             STR8_DIR_RETURN_RECORD_INVALID
                        INY
                        CPY             #(STR8_DIR_RESERVED+STR8_DIR_RESERVED_LEN)
                        BNE             ?RESERVED

; DESCRIPTION is exactly five display-safe uppercase bytes.
                        LDY             #STR8_DIR_DESCRIPTION
?DESCRIPTION:          LDA             (STR8_PTR_LO),Y
                        JSR             STR8_DIR_DESCRIPTION_BYTE_A
                        BCC             STR8_DIR_RETURN_RECORD_INVALID
                        INY
                        CPY             #(STR8_DIR_DESCRIPTION+STR8_DIR_DESCRIPTION_LEN)
                        BNE             ?DESCRIPTION

                        LDY             #STR8_DIR_SEAL
                        LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_SEAL_VALUE
                        BNE             STR8_DIR_RETURN_RECORD_INVALID

; All banks accept erased $FFFF. Only Bank 3 also accepts $8000-$EFFF.
?ENTRY:                LDY             #STR8_DIR_ENTRY_LO
                        LDA             (STR8_PTR_LO),Y
                        INY
                        AND             (STR8_PTR_LO),Y
                        CMP             #$FF
                        BEQ             ?JOURNAL
                        LDA             STR8_DIR_BANK_WORK
                        CMP             #STR8_DIR_BANK3
                        BNE             STR8_DIR_RETURN_RECORD_INVALID
                        LDA             (STR8_PTR_LO),Y
                        CMP             #STR8_DIR_BANK3_ENTRY_MIN_HI
                        BCC             STR8_DIR_RETURN_RECORD_INVALID
                        CMP             #(STR8_DIR_BANK3_ENTRY_MAX_HI+1)
                        BCS             STR8_DIR_RETURN_RECORD_INVALID

?JOURNAL:              LDA             STR8_DIR_OPEN_WORK
                        CMP             #STR8_DIR_JOURNAL_STARTED
                        BEQ             ?RETURN_STATE
                        LDA             #STR8_DIR_RECORD_COMPLETE
?RETURN_STATE:         LDX             STR8_DIR_RESULT_PAIR
                        SEC
                        RTS

STR8_DIR_RETURN_RECORD_INVALID:
                        LDX             #STR8_DIR_PAIR_NONE
                        LDA             #STR8_DIR_RECORD_INVALID
                        CLC
                        RTS

STR8_DIR_DESCRIPTION_BYTE_A:
                        CMP             #'A'
                        BCC             ?DIGIT
                        CMP             #'Z'+1
                        BCC             ?VALID
?DIGIT:                CMP             #'0'
                        BCC             ?PUNCTUATION
                        CMP             #'9'+1
                        BCC             ?VALID
?PUNCTUATION:          CMP             #'-'
                        BEQ             ?VALID
                        CMP             #'_'
                        BEQ             ?VALID
                        CMP             #'.'
                        BEQ             ?VALID
                        CLC
                        RTS
?VALID:                SEC
                        RTS

STR8_DIR_SCAN_JOURNAL:
                        LDY             #STR8_DIR_JOURNAL
                        LDX             #$00
                        STZ             STR8_DIR_OPEN_WORK
?BYTE:                 LDA             (STR8_PTR_LO),Y
                        STA             STR8_DIR_PACKED_WORK
                        LDA             #$08
                        STA             STR8_DIR_LEFT_WORK
; Journal bits are a one-way event strip: START clears one bit and COMPLETE
; clears the next.  Cleared bits must be one uninterrupted prefix.
?BIT:                  LSR             STR8_DIR_PACKED_WORK
                        BCS             ?UNUSED
                        LDA             STR8_DIR_OPEN_WORK
                        BNE             ?INVALID
                        INX
                        BRA             ?NEXT_BIT
?UNUSED:               INC             STR8_DIR_OPEN_WORK
?NEXT_BIT:
                        DEC             STR8_DIR_LEFT_WORK
                        BNE             ?BIT
                        INY
                        CPY             #(STR8_DIR_JOURNAL+STR8_DIR_JOURNAL_LEN)
                        BNE             ?BYTE
                        TXA
                        BEQ             ?FRESH
                        CMP             #$20
                        BEQ             ?FULL
                        LSR             A
                        TAX
                        BCS             ?STARTED
                        LDA             #STR8_DIR_JOURNAL_COMPLETE
                        SEC
                        RTS
?STARTED:              LDA             #STR8_DIR_JOURNAL_STARTED
                        SEC
                        RTS
?FRESH:                LDA             #STR8_DIR_JOURNAL_FRESH
                        LDX             #$00
                        SEC
                        RTS
?FULL:
                        LDA             #STR8_DIR_JOURNAL_FULL
                        LDX             #STR8_DIR_PAIR_NONE
                        SEC
                        RTS
?INVALID:              LDA             #STR8_DIR_JOURNAL_INVALID
                        LDX             #STR8_DIR_PAIR_NONE
                        CLC
                        RTS

                        IF              STR8_V1_LAYOUT
; STR8_DIR_WRITE_BYTES
;   IN:  STR8_REC_ADDR_LO/HI = first Bank-3 directory byte
;        STR8_REC_DATA_LEN   = byte count, 1-64 within $FFB0-$FFEF
;        STR8_REC_DATA_BUF   = exact desired bytes
;   OUT: A/STR8_REC_STATUS = STR8_DIR_WRITE_*; C=1 only on exact verify
;        STR8_REC_FAIL/OBSERVED/EXPECTED identify the first byte failure
;
; This is the only directory mutation primitive. It never erases. The
; complete request is preflighted before mode $07 runs, so a later 0-to-1
; transition cannot partially program an earlier byte. The RAM worker repeats
; that whole-request preflight after selecting Bank 3.
STR8_DIR_WRITE_BYTES:
                        CLD
                        JSR             STR8_REC_CLEAR_FAILURE
                        LDA             STR8_REC_DATA_LEN
                        BEQ             ?BAD_COUNT
                        LDA             STR8_REC_ADDR_HI
                        CMP             #>STR8_DIR_BASE
                        BNE             ?BAD_RANGE
                        LDA             STR8_REC_ADDR_LO
                        CMP             #<STR8_DIR_BASE
                        BCC             ?BAD_RANGE
                        CMP             #<(STR8_DIR_END+1)
                        BCS             ?BAD_RANGE
                        CLC
                        ADC             STR8_REC_DATA_LEN
                        BCS             ?BAD_RANGE
                        CMP             #<(STR8_DIR_END+2)
                        BCS             ?BAD_RANGE

; The RAM worker repeats a complete one-to-zero preflight after selecting
; Bank 3, then reports the exact failing byte if the transition is unsafe.
                        JSR             STR8_RUN_PROGRAM_RECORD_WORKER
                        BCC             ?WORKER_FAIL

                        JSR             STR8_REC_LOAD_APPLY_POINTERS
?VERIFY:               LDY             #$00
                        LDA             (STR8_PTR_LO),Y
                        STA             STR8_REC_WORK_TMP
                        CMP             (STR8_COPY_PTR_LO),Y
                        BNE             ?VERIFY_FAIL
                        JSR             STR8_REC_ADVANCE_APPLY_POINTERS
                        DEC             STR8_REC_WORK_COUNT
                        BNE             ?VERIFY
                        LDA             #STR8_DIR_WRITE_OK
                        STA             STR8_REC_STATUS
                        SEC
                        RTS

?BAD_COUNT:            LDA             #STR8_DIR_WRITE_BAD_COUNT
                        BRA             ?FAIL
?BAD_RANGE:            LDA             STR8_REC_ADDR_LO
                        STA             STR8_REC_FAIL_LO
                        LDA             STR8_REC_ADDR_HI
                        STA             STR8_REC_FAIL_HI
                        LDA             #STR8_DIR_WRITE_BAD_RANGE
                        BRA             ?FAIL
?WORKER_FAIL:          LDA             #STR8_DIR_WRITE_WORKER
                        BRA             ?FAIL
?VERIFY_FAIL:          JSR             STR8_REC_CAPTURE_APPLY_FAILURE
                        LDA             #STR8_DIR_WRITE_VERIFY
?FAIL:                 STA             STR8_REC_STATUS
                        CLC
                        RTS
                        ENDIF

; Private mode-$07 doorway used only by the directory writer.
STR8_RUN_PROGRAM_RECORD_WORKER:
                        IF              STR8_RAM_PROOF
                        CLC
                        RTS
                        ELSE
                        LDA             #STR8_COPY_MODE_PROGRAM_RECORD
                        STA             STR8_COPY_MODE
                        JMP             STR8_WORKER_RUN
                        ENDIF

; ----------------------------------------------------------------------------
; V2 validated-record service. PARSE validates a complete S0/S1/S9 record into
; $7B00 before publishing its descriptor. Destructive dispatch is private.
; ----------------------------------------------------------------------------
STR8_RECORD_SERVICE_BODY:
                        CLD
                        LDA             STR8_REC_OP
                        CMP             #STR8_REC_OP_PARSE
                        BEQ             STR8_REC_PARSE
?BAD_OP:
                        LDA             #STR8_REC_BAD_OP
                        JMP             STR8_REC_FAIL_A

STR8_REC_PARSE:
                        JSR             STR8_REC_CLEAR_RESULT
                        LDA             STR8_REC_FORMAT
                        CMP             #STR8_REC_FORMAT_S19
                        BEQ             ?FORMAT_OK
                        LDA             #STR8_REC_BAD_FORMAT
                        JMP             STR8_REC_FAIL_A
?FORMAT_OK:
                        LDA             STR8_REC_SOURCE
                        CMP             #STR8_REC_SOURCE_CONSOLE+1
                        BCC             ?SOURCE_OK
                        LDA             #STR8_REC_BAD_SOURCE
                        JMP             STR8_REC_FAIL_A
?SOURCE_OK:
                        LDA             STR8_REC_SRC_LO
                        STA             STR8_PTR_LO
                        LDA             STR8_REC_SRC_HI
                        STA             STR8_PTR_HI
                        LDA             STR8_REC_SRC_LEN
                        STA             STR8_REC_WORK_REMAIN
                        LDA             STR8_REC_SOURCE
                        CMP             #STR8_REC_SOURCE_BUFFER
                        BNE             ?CONSOLE_START

                        ; Validate the inclusive end without rejecting a
                        ; one-byte span at $FFFF.
                        LDA             STR8_REC_WORK_REMAIN
                        BEQ             ?BUFFER_START
                        DEC             A
                        CLC
                        ADC             STR8_PTR_LO
                        BCC             ?BUFFER_START
                        LDA             STR8_PTR_HI
                        CMP             #$FF
                        BNE             ?BUFFER_START
                        LDA             #STR8_REC_BAD_SOURCE
                        JMP             STR8_REC_FAIL_A

?CONSOLE_START:
                        JSR             STR8_REC_READ_CHAR
                        BCS             ?CONSOLE_HAVE_CHAR
                        JMP             STR8_REC_FAIL_READ_START
?CONSOLE_HAVE_CHAR:
                        CMP             #$0D
                        BEQ             ?CONSOLE_START
                        CMP             #$0A
                        BEQ             ?CONSOLE_START
                        BRA             ?HAVE_START
?BUFFER_START:
                        JSR             STR8_REC_READ_CHAR
                        BCS             ?HAVE_START
                        JMP             STR8_REC_FAIL_READ_START
?HAVE_START:
                        AND             #$DF
                        CMP             #'S'
                        BEQ             ?HAVE_S
                        LDA             #STR8_REC_BAD_START
                        JMP             STR8_REC_FAIL_A
?HAVE_S:
                        JSR             STR8_REC_READ_CHAR
                        BCS             ?HAVE_TYPE
                        JMP             STR8_REC_FAIL_READ_TYPE
?HAVE_TYPE:
                        STA             STR8_REC_WORK_TYPE
                        CMP             #'9'
                        BEQ             STR8_REC_PARSE_BODY
                        CMP             #'0'
                        BCC             ?BAD_TYPE
                        CMP             #'2'
                        BCC             STR8_REC_PARSE_BODY
?BAD_TYPE:
                        LDA             #STR8_REC_BAD_TYPE
                        JMP             STR8_REC_FAIL_A

STR8_REC_PARSE_BODY:
                        STZ             STR8_REC_WORK_SUM
                        JSR             STR8_REC_READ_SUM_BYTE
                        BCC             ?HEX_FAIL
?HAVE_COUNT:
                        STA             STR8_REC_WORK_COUNT
                        CMP             #$03
                        BEQ             ?COUNT_OK
                        BCC             ?BAD_COUNT
?COUNT_MIN_OK:
                        LDA             STR8_REC_WORK_TYPE
                        CMP             #'9'
                        BNE             ?COUNT_OK
?BAD_COUNT:
                        LDA             #STR8_REC_BAD_COUNT
                        JMP             STR8_REC_FAIL_A
?COUNT_OK:
                        JSR             STR8_REC_READ_SUM_BYTE
                        BCC             ?HEX_FAIL
?HAVE_ADDR_HI:
                        STA             STR8_REC_ADDR_HI
                        JSR             STR8_REC_READ_SUM_BYTE
                        BCC             ?HEX_FAIL
?HAVE_ADDR_LO:
                        STA             STR8_REC_ADDR_LO
                        LDA             STR8_REC_WORK_COUNT
                        SEC
                        SBC             #$03
                        STA             STR8_REC_DATA_LEN
                        STA             STR8_REC_WORK_COUNT
                        LDX             #$00
                        BRA             ?DATA
?HEX_FAIL:             JMP             STR8_REC_FAIL_READ_HEX
?DATA:
                        LDA             STR8_REC_WORK_COUNT
                        BEQ             ?CHECKSUM
                        JSR             STR8_REC_READ_SUM_BYTE
                        BCC             ?HEX_FAIL
?HAVE_DATA_BYTE:
                        STA             STR8_REC_DATA_BUF,X
                        INX
                        DEC             STR8_REC_WORK_COUNT
                        BRA             ?DATA
?CHECKSUM:
                        JSR             STR8_REC_READ_SUM_BYTE
                        BCC             ?HEX_FAIL
?HAVE_CHECKSUM:
                        LDA             STR8_REC_WORK_SUM
                        CMP             #$FF
                        BEQ             ?CHECKSUM_OK
                        LDA             #STR8_REC_BAD_CHECKSUM
                        BRA             STR8_REC_FAIL_A
?CHECKSUM_OK:
                        LDA             STR8_REC_SOURCE
                        CMP             #STR8_REC_SOURCE_BUFFER
                        BNE             ?CONSOLE_END
                        LDA             STR8_REC_WORK_REMAIN
                        BEQ             ?PUBLISH
                        LDA             #STR8_REC_BAD_END
                        BRA             STR8_REC_FAIL_A
?CONSOLE_END:
                        JSR             STR8_REC_READ_CHAR
                        BCS             ?HAVE_END
                        BRA             STR8_REC_FAIL_READ_END
?HAVE_END:
                        IF              STR8_V1_INSTALLER_DRY
                        CMP             #$0D
                        BNE             ?CHECK_LF
                        INC             STR8_INPUT_SKIP_LF
                        BRA             ?PUBLISH
                        ELSE
                        CMP             #$0D
                        BEQ             ?PUBLISH
                        ENDIF
?CHECK_LF:
                        CMP             #$0A
                        BEQ             ?PUBLISH
                        LDA             #STR8_REC_BAD_END
                        BRA             STR8_REC_FAIL_A

?PUBLISH:
                        LDA             #STR8_REC_DATA_BUF_LO
                        STA             STR8_REC_DATA_LO
                        LDA             #STR8_REC_DATA_BUF_HI
                        STA             STR8_REC_DATA_HI
                        LDA             STR8_REC_WORK_TYPE
                        CMP             #'9'
                        BEQ             ?END
                        AND             #$0F
                        INC             A
                        STA             STR8_REC_KIND
                        BRA             STR8_REC_RETURN_OK
?END:
                        LDA             #STR8_REC_KIND_END
                        STA             STR8_REC_KIND
                        LDA             #STR8_REC_FLAG_ENTRY_VALID
                        STA             STR8_REC_FLAGS
                        LDA             STR8_REC_ADDR_LO
                        STA             STR8_REC_ENTRY_LO
                        LDA             STR8_REC_ADDR_HI
                        STA             STR8_REC_ENTRY_HI

STR8_REC_RETURN_OK:
                        STZ             STR8_REC_STATUS
                        LDA             #STR8_REC_OK
                        SEC
                        RTS

STR8_REC_FAIL_READ_START:
                        LDX             #STR8_REC_BAD_START
                        BRA             STR8_REC_FAIL_READ_X
STR8_REC_FAIL_READ_TYPE:
                        LDX             #STR8_REC_BAD_TYPE
                        BRA             STR8_REC_FAIL_READ_X
STR8_REC_FAIL_READ_HEX:
                        LDX             #STR8_REC_BAD_HEX
                        BRA             STR8_REC_FAIL_READ_X
STR8_REC_FAIL_READ_END:
                        LDX             #STR8_REC_BAD_END
STR8_REC_FAIL_READ_X:
                        LDA             STR8_REC_STATUS
                        CMP             #STR8_REC_ABORT
                        BNE             STR8_REC_FAIL_READ_NOT_ABORT
STR8_REC_RETURN_CURRENT_FAIL:
                        LDA             STR8_REC_STATUS
                        CLC
                        RTS
STR8_REC_FAIL_READ_NOT_ABORT:
                        TXA
STR8_REC_FAIL_A:
                        STA             STR8_REC_STATUS
                        CLC
                        RTS

; Public APPLY_LF is retired. Directory programming alone uses these pointer
; and failure-detail helpers before and after its private mode-$07 worker.
STR8_REC_LOAD_APPLY_POINTERS:
                        LDA             STR8_REC_ADDR_LO
                        STA             STR8_PTR_LO
                        LDA             STR8_REC_ADDR_HI
                        STA             STR8_PTR_HI
                        LDA             #STR8_REC_DATA_BUF_LO
                        STA             STR8_COPY_PTR_LO
                        LDA             #STR8_REC_DATA_BUF_HI
                        STA             STR8_COPY_PTR_HI
                        LDA             STR8_REC_DATA_LEN
                        STA             STR8_REC_WORK_COUNT
                        RTS

STR8_REC_ADVANCE_APPLY_POINTERS:
                        INC             STR8_PTR_LO
                        BNE             ?DATA
                        INC             STR8_PTR_HI
?DATA:
                        INC             STR8_COPY_PTR_LO
                        BNE             ?DONE
                        INC             STR8_COPY_PTR_HI
?DONE:
                        RTS

STR8_REC_CAPTURE_APPLY_FAILURE:
                        LDA             STR8_PTR_LO
                        STA             STR8_REC_FAIL_LO
                        LDA             STR8_PTR_HI
                        STA             STR8_REC_FAIL_HI
                        LDA             STR8_REC_WORK_TMP
                        STA             STR8_REC_OBSERVED
                        LDY             #$00
                        LDA             (STR8_COPY_PTR_LO),Y
                        STA             STR8_REC_EXPECTED
                        RTS

STR8_REC_CLEAR_RESULT:
                        LDX             #(STR8_REC_DATA_HI-STR8_REC_KIND)
?RESULT:               STZ             STR8_REC_KIND,X
                        DEX
                        BPL             ?RESULT
STR8_REC_CLEAR_FAILURE:
                        STZ             STR8_REC_STATUS
                        LDX             #(STR8_REC_EXPECTED-STR8_REC_FAIL_LO)
?FAILURE:              STZ             STR8_REC_FAIL_LO,X
                        DEX
                        BPL             ?FAILURE
                        RTS

STR8_REC_READ_SUM_BYTE:
                        JSR             STR8_REC_READ_HEX_BYTE
                        BCC             ?FAIL
                        PHA
                        CLC
                        ADC             STR8_REC_WORK_SUM
                        STA             STR8_REC_WORK_SUM
                        PLA
                        SEC
?FAIL:
                        RTS

STR8_REC_READ_HEX_BYTE:
                        JSR             STR8_REC_READ_CHAR
                        BCC             ?FAIL
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
                        ASL             A
                        ASL             A
                        ASL             A
                        ASL             A
                        STA             STR8_REC_WORK_TMP
                        JSR             STR8_REC_READ_CHAR
                        BCC             ?FAIL
                        JSR             STR8_REC_HEX_ASCII_TO_NIBBLE
                        BCC             ?FAIL
                        ORA             STR8_REC_WORK_TMP
?FAIL:
                        RTS

STR8_REC_HEX_ASCII_TO_NIBBLE:
                        CMP             #'0'
                        BCC             ?FAIL
                        CMP             #'9'+1
                        BCC             ?DIGIT
                        AND             #$DF
                        CMP             #'A'
                        BCC             ?FAIL
                        CMP             #'F'+1
                        BCS             ?FAIL
                        SEC
                        SBC             #('A'-10)
                        RTS
?DIGIT:
                        SEC
                        SBC             #'0'
                        RTS
?FAIL:
                        CLC
                        RTS

STR8_REC_READ_CHAR:
                        LDA             STR8_REC_SOURCE
                        CMP             #STR8_REC_SOURCE_BUFFER
                        BEQ             ?BUFFER
                        IF              STR8_V1_LAYOUT
                        JSR             STR8_READ_TEXT_BYTE_BLOCK
                        ELSE
                        JSR             STR8_CON_READ_BYTE_BLOCK
                        ENDIF
                        CMP             #$03
                        BNE             ?OK
                        LDA             #STR8_REC_ABORT
                        STA             STR8_REC_STATUS
                        CLC
                        RTS
?BUFFER:
                        LDA             STR8_REC_WORK_REMAIN
                        BEQ             ?EMPTY
                        LDY             #$00
                        LDA             (STR8_PTR_LO),Y
                        INC             STR8_PTR_LO
                        BNE             ?COUNT
                        INC             STR8_PTR_HI
?COUNT:
                        DEC             STR8_REC_WORK_REMAIN
?OK:
                        SEC
                        RTS
?EMPTY:
                        CLC
                        RTS

                        IF              STR8_RAM_PROOF
STR8_SELECT_BANK_3:
                        JSR             FLSH_BANK_SELECT_3
                        RTS
                        ENDIF

STR8_CONFIRM_Y:
                        IF              STR8_V1_LAYOUT
                        LDX             #$01
                        JSR             STR8_READ_LINE
                        CMP             #$01
                        BNE             ?NO
                        LDA             STR8_REC_DATA_BUF
                        CMP             #'Y'
                        BNE             ?NO
                        SEC
                        RTS
?NO:                   CLC
                        RTS
                        ELSE
                        JSR             STR8_READ_COMMAND
                        CMP             #'Y'
                        BEQ             ?YES
                        CLC
?YES:
                        RTS
                        ENDIF

                        IF              STR8_RAM_PROOF
                        ELSE
STR8_COPY_WORKER_TO_RAM:
                        JSR             STR8_WORKER_COPY_POINTERS
                        LDX             #STR8_WORKER_COPY_LEN_HI
?COPY_PAGE:            LDY             #$00
?COPY_BYTE:            LDA             (STR8_PTR_LO),Y
                        STA             (STR8_COPY_PTR_LO),Y
                        CMP             (STR8_COPY_PTR_LO),Y
                        BNE             ?FAIL
                        INY
                        BNE             ?COPY_BYTE
                        INC             STR8_PTR_HI
                        INC             STR8_COPY_PTR_HI
                        DEX
                        BNE             ?COPY_PAGE
?COPY_TAIL:            CPY             #STR8_WORKER_COPY_LEN_LO
                        BEQ             ?OK
                        LDA             (STR8_PTR_LO),Y
                        STA             (STR8_COPY_PTR_LO),Y
                        CMP             (STR8_COPY_PTR_LO),Y
                        BNE             ?FAIL
                        INY
                        BRA             ?COPY_TAIL
?OK:                   SEC
                        RTS
?FAIL:                 CLC
                        RTS

STR8_WORKER_COPY_POINTERS:
                        LDA             #STR8_WORKER_STORE_LO
                        STA             STR8_PTR_LO
                        LDA             #STR8_WORKER_STORE_HI
                        STA             STR8_PTR_HI
                        STZ             STR8_COPY_PTR_LO
                        LDA             #STR8_WORKER_RUN_HI
                        STA             STR8_COPY_PTR_HI
                        RTS

; $F010 copies only the selector prefix, preserving HIMON's executing $0300
; staging helper.  Each byte is read back before the next byte is copied.
STR8_COPY_SELECTOR_TO_RAM:
                        LDY             #$00
?COPY:
                        LDA             STR8_WORKER_STORE,Y
                        STA             STR8_WORKER_RUN,Y
                        CMP             STR8_WORKER_RUN,Y
                        BNE             ?SELECT_FAIL
                        INY
                        CPY             #STR8_SELECTOR_COPY_LEN
                        BNE             ?COPY
                        SEC
                        RTS
?SELECT_FAIL:          CLC
                        RTS
                        ENDIF

                        IF              STR8_RAM_PROOF
                        ELSE
                        IF              STR8_V1_LAYOUT
                        ELSE
; ----------------------------------------------------------------------------
; Fixed-gate HIMON update: receive S1/S9, stage blank C/D/E, then program C/D/E.
; ----------------------------------------------------------------------------
STR8_UPD_INIT:
                        STZ             STR8_UPD_MASK
                        RTS

STR8_STAGE_HIMON_BLANK:
                        STZ             STR8_PTR_LO
                        LDA             #$40
                        STA             STR8_PTR_HI
?PAGE:
                        LDY             #$00
                        LDA             #$FF
?BYTE:
                        STA             (STR8_PTR_LO),Y
                        INY
                        BNE             ?BYTE
                        INC             STR8_PTR_HI
                        LDA             STR8_PTR_HI
                        CMP             #$70
                        BNE             ?PAGE
                        RTS

STR8_READ_HIMON_S19:
?RECORD:
                        LDA             #STR8_REC_OP_PARSE
                        STA             STR8_REC_OP
                        LDA             #STR8_REC_FORMAT_S19
                        STA             STR8_REC_FORMAT
                        LDA             #STR8_REC_SOURCE_CONSOLE
                        STA             STR8_REC_SOURCE
                        JSR             STR8_RECORD_SERVICE_BODY
                        BCC             ?FAIL
                        LDA             STR8_REC_KIND
                        CMP             #STR8_REC_KIND_METADATA
                        BEQ             ?RECORD
                        CMP             #STR8_REC_KIND_DATA
                        BEQ             ?DATA
                        CMP             #STR8_REC_KIND_END
                        BEQ             ?TERM
                        BRA             ?FAIL
?DATA:
                        JSR             STR8_STAGE_HIMON_RECORD
                        BCC             ?FAIL
                        LDA             #'.'
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        BRA             ?RECORD
?TERM:
                        SEC
                        RTS
?FAIL:
                        CLC
                        RTS

STR8_STAGE_HIMON_RECORD:
                        LDA             STR8_REC_ADDR_LO
                        STA             STR8_UPD_DST_LO
                        LDA             STR8_REC_ADDR_HI
                        STA             STR8_UPD_DST_HI
                        LDA             STR8_REC_DATA_LEN
                        STA             STR8_UPD_DATA_LEN
                        BEQ             ?OK
                        LDA             STR8_UPD_DST_HI
                        CMP             #$C0
                        BCC             ?FAIL
                        CMP             #$F0
                        BCS             ?FAIL
                        LDA             STR8_UPD_DATA_LEN
                        DEC             A
                        CLC
                        ADC             STR8_UPD_DST_LO
                        LDA             STR8_UPD_DST_HI
                        ADC             #$00
                        CMP             #$F0
                        BCS             ?FAIL
                        LDA             #$01
                        TSB             STR8_UPD_MASK
                        LDX             #$00
?DATA:
                        LDA             STR8_UPD_DATA_LEN
                        BEQ             ?OK
                        LDA             STR8_UPD_DST_HI
                        AND             #$7F
                        STA             STR8_PTR_HI
                        LDA             STR8_UPD_DST_LO
                        STA             STR8_PTR_LO
                        LDY             #$00
                        LDA             STR8_REC_DATA_BUF,X
                        STA             (STR8_PTR_LO),Y
                        INX
                        INC             STR8_UPD_DST_LO
                        BNE             ?COUNT
                        INC             STR8_UPD_DST_HI
?COUNT:
                        DEC             STR8_UPD_DATA_LEN
                        BRA             ?DATA
?OK:
                        SEC
                        RTS
?FAIL:
                        CLC
                        RTS

STR8_PROGRAM_HIMON_UPDATE:
                        LDA             #$C0
                        LDX             #$40
                        JSR             STR8_PROGRAM_HIMON_SECTOR_AX
                        BCC             ?FAIL
                        LDA             #$D0
                        LDX             #$50
                        JSR             STR8_PROGRAM_HIMON_SECTOR_AX
                        BCC             ?FAIL
                        LDA             #$E0
                        LDX             #$60
                        JSR             STR8_PROGRAM_HIMON_SECTOR_AX
                        BCC             ?FAIL
                        SEC
                        RTS
?FAIL:
                        CLC
                        RTS

STR8_PROGRAM_HIMON_SECTOR_AX:
                        STA             STR8_MARK_SECTOR_HI
                        STX             STR8_STAGE_BUF_HI
                        LDA             #$03
                        STA             STR8_COPY_DST_BANK
                        LDA             #STR8_COPY_MODE_PROGRAM_STAGED
                        STA             STR8_COPY_MODE
                        JSR             STR8_COPY_WORKER_TO_RAM
                        JSR             STR8_WORKER_RUN
                        BCC             ?FAIL
                        LDA             #'.'
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        SEC
                        RTS
?FAIL:
                        CLC
                        RTS
                        ENDIF
                        ENDIF

                        IF              STR8_V1_LAYOUT
                        ELSE
STR8_PRINT_COPY_FAIL:
                        IF              STR8_RAM_PROOF
                        LDX             #<MSG_COPY_FAIL_AT
                        LDY             #>MSG_COPY_FAIL_AT
                        JSR             STR8_PRINT_XY
                        LDA             STR8_MARK_ADDR_HI
                        JSR             STR8_WRITE_HEX_BYTE_A
                        LDA             STR8_MARK_ADDR_LO
                        JSR             STR8_WRITE_HEX_BYTE_A
                        LDX             #<MSG_CRLF
                        LDY             #>MSG_CRLF
                        JMP             STR8_PRINT_XY
                        ELSE
                        LDX             #<MSG_COPY_FAIL
                        LDY             #>MSG_COPY_FAIL
                        JMP             STR8_PRINT_XY
                        ENDIF
                        ENDIF

STR8_PRINT_JUMP_FAIL:
                        LDX             #<MSG_JUMP_FAIL
                        IF              STR8_V1_INSTALLER_TXN
                        BRA             STR8_PRINT_TXN_PAGE1_X
                        ELSE
                        LDY             #>MSG_JUMP_FAIL
                        JMP             STR8_PRINT_XY
                        ENDIF

STR8_WRITE_DEC_DIGIT_A:
; Callers supply a validated binary digit 0-9.
                        ORA             #'0'
                        IF              STR8_RAM_PROOF
                        JMP             STR8_CON_WRITE_BYTE_BLOCK
                        ELSE
                        JMP             STR8_CON_WRITE_BYTE_BLOCK
                        ENDIF

STR8_WRITE_HEX_BYTE_A:
                        PHA
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        JSR             STR8_WRITE_HEX_NIBBLE_A
                        PLA
                        AND             #$0F
STR8_WRITE_HEX_NIBBLE_A:
                        CMP             #$0A
                        BCC             ?ASCII
; CMP leaves carry set for A-F. ADC #$06 therefore adds seven before the
; common ASCII-'0' addition, producing 'A'-'F'.
                        ADC             #$06
?ASCII:
                        ADC             #'0'
                        IF              STR8_RAM_PROOF
                        JMP             STR8_CON_WRITE_BYTE_BLOCK
                        ELSE
                        JMP             STR8_CON_WRITE_BYTE_BLOCK
                        ENDIF

                        IF              STR8_V1_LAYOUT
STR8_WRITE_HEX_HIGH_NIBBLE_A:
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        BRA             STR8_WRITE_HEX_NIBBLE_A
                        ENDIF

                        IF              STR8_RAM_PROOF
; RAM-proof equivalent of worker mode $08. All code and bank-select helpers
; remain in RAM after the visible $8000-$FFFF bank window changes.
STR8_JUMP_BANK_RAM:
                        PHP
                        SEI
                        LDA             STR8_JUMP_BANK
                        CMP             #STR8_BANK_COUNT
                        BCS             ?BAD_BANK
                        JSR             FLSH_BANK_SELECT_A
                        LDA             STR8_RESET_VECTOR
                        STA             STR8_JUMP_VEC_LO
                        LDA             STR8_RESET_VECTOR+1
                        STA             STR8_JUMP_VEC_HI
                        CMP             #$80
                        BCC             ?LOW_VECTOR
                        CMP             #$FF
                        BNE             ?GO
                        LDA             STR8_JUMP_VEC_LO
                        CMP             #$FF
                        BEQ             ?ERASED_VECTOR
?GO:
                        LDA             #STR8_JUMP_STATUS_GO
                        STA             STR8_JUMP_STATUS
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        STZ             STR8_BANK_JUMP_SIG1
                        LDA             STR8_JUMP_BANK
                        STA             STR8_BANK_LAST_JUMP
                        LDA             #STR8_BANK_JUMP_SIG0_VALUE
                        STA             STR8_BANK_JUMP_SIG0
                        LDA             #STR8_BANK_JUMP_SIG1_VALUE
                        STA             STR8_BANK_JUMP_SIG1
                        JMP             (STR8_JUMP_VEC_LO)
?BAD_BANK:
                        LDA             #STR8_JUMP_STATUS_BANK
                        BRA             ?FAIL
?LOW_VECTOR:
                        LDA             #STR8_JUMP_STATUS_LOW
                        BRA             ?FAIL
?ERASED_VECTOR:
                        LDA             #STR8_JUMP_STATUS_ERASED
?FAIL:
                        STA             STR8_JUMP_STATUS
                        JSR             FLSH_BANK_SELECT_3
                        PLP
                        CLC
                        RTS
                        ENDIF

; ----------------------------------------------------------------------------
; Tiny I/O
; ----------------------------------------------------------------------------
STR8_PRINT_PROMPT:
                        LDX             #<MSG_PROMPT
                        IF              STR8_V1_INSTALLER_TXN
                        BRA             STR8_PRINT_TXN_PAGE0_X
                        ELSE
                        LDY             #>MSG_PROMPT
                        JMP             STR8_PRINT_XY
                        ENDIF

                        IF              STR8_V1_INSTALLER_TXN
; Transaction messages span exactly two pages. Callers load X with the
; message low byte and enter the helper matching the map-checked message page.
STR8_PRINT_TXN_PAGE0_X:
                        LDY             #>MSG_ID
                        BRA             STR8_PRINT_XY
STR8_PRINT_TXN_PAGE1_X:
                        LDY             #>MSG_CRLF
                        ENDIF
STR8_PRINT_XY:
                        STX             STR8_PTR_LO
                        STY             STR8_PTR_HI
                        LDY             #$00
?LOOP:                  LDA             (STR8_PTR_LO),Y
                        BMI             ?LAST
                        JSR             STR8_CON_WRITE_BYTE_BLOCK
                        INY
                        BNE             ?LOOP
                        INC             STR8_PTR_HI
                        BRA             ?LOOP
?LAST:                  AND             #$7F
                        JMP             STR8_CON_WRITE_BYTE_BLOCK

STR8_CON_INIT:
                        LDA             #STR8_CON_PN_CTRL_INIT
                        STA             STR8_CON_VIA_CTRL
                        STA             STR8_CON_VIA_DDRB
                        STZ             STR8_CON_VIA_DDRA
                        RTS

STR8_ABI_QUERY_BODY:
                        LDA             #STR8_RESIDENT_ABI_VERSION
                        LDX             #STR8_RESIDENT_ABI_CAPS
                        SEC
                        RTS

STR8_CON_FLUSH_RX:
                        LDX             #STR8_CON_FLUSH_RX_MAX
?LOOP:                  JSR             STR8_CON_READ_BYTE_NONBLOCK
                        BCC             ?EMPTY
                        DEX
                        BNE             ?LOOP
                        CLC
                        RTS
?EMPTY:                 SEC
                        RTS

STR8_CON_READ_BYTE_NONBLOCK:
                        STZ             STR8_CON_VIA_DDRA
                        LDA             #STR8_CON_PN_RXF
                        BIT             STR8_CON_VIA_CTRL
                        BNE             ?NO_BYTE_READY
?BYTE_READY:            LDA             #STR8_CON_PN_RD
                        TRB             STR8_CON_VIA_CTRL
                        NOP
                        NOP
                        LDA             STR8_CON_VIA_DATA
                        PHA
                        LDA             #STR8_CON_PN_RD
                        TSB             STR8_CON_VIA_CTRL
                        PLA
                        SEC
                        RTS
?NO_BYTE_READY:         CLC
                        RTS

                        DATA
STR8_ID_MARKER_BYTES:   DB              STR8_ID_MARKER0,STR8_ID_MARKER1
                        DB              STR8_ID_MARKER2,STR8_ID_MARKER3

                        INCLUDE         "str8-version.inc"
; 2026-08-03T09:46Z Codex       Compact the resident ROM location into the ID.
                        IF              STR8_RAM_PROOF
                        DB              $0D,$8A
                        ELSE
                        IF              STR8_V1_LAYOUT
                        DB              $0D,$0A
MSG_BOOT_PROMPT:        DB              "0-2 C W S:",$A0
MSG_WAIT:               DB              "WAIT...",$A0
MSG_LIVE_DOT:           DB              ('.'+$80)
                        ELSE
                        DB              " $F",$0D,$8A
                        ENDIF
                        ENDIF
                        IF              STR8_RAM_PROOF
                        ELSE
MSG_BOOT_MENU:          DB              $0D,$0A
                        ENDIF
MSG_SCREEN:
                        IF              STR8_RAM_PROOF
                        DB              "RAM $0200 BUF $4000-$4FFF",$0D,$0A
                        ENDIF
MSG_HELP:
                        IF              STR8_V1_LAYOUT
                        DB              "I L C W J",$0D,$8A
                        ELSE
                        DB              "U 0-3 J0-3",$0D,$8A
                        ENDIF
MSG_PROMPT:             DB              "STR8-N",('>'+$80)
                        IF              STR8_RAM_PROOF
                        ELSE
                        IF              STR8_V1_LAYOUT
                        ELSE
MSG_BOOT_PROMPT:        DB              "0/1/2=BOOT 3=HIMON S=STR8 ",$A0
                        ENDIF
MSG_BOOT_BANK_WAIT:     DB              "3S",$0D,$8A
                        ENDIF

                        IF              STR8_V1_INSTALLER_TXN
                        ELSE
MSG_OK:                 DB              $0D,$0A,"OK",$0D,$8A
                        ENDIF
                        IF              STR8_V1_LAYOUT
                        ELSE
MSG_ABORT:              DB              $0D,$0A,"ABORT",$0D,$8A
                        ENDIF
                        IF              STR8_V1_LAYOUT
MSG_I_BANK:             DB              $0D,$0A,"B0-3:",$A0
MSG_I_RANGE_PROMPT:     DB              $0D,$0A,"RANGE:",$A0
MSG_I_TYPE_PROMPT:      DB              $0D,$0A,"TYPE:",$A0
MSG_I_DESC_PROMPT:      DB              $0D,$0A,"DESC:",$A0
MSG_I_INVALID:          DB              $0D,$0A,"BAD",$0D,$8A
MSG_I_SUMMARY:          DB              $0D,$0A,"I ",('B'+$80)
; Compact prompts finish page $FC; summaries and transaction results use $FD.
                        IF              STR8_V1_INSTALLER_TXN
MSG_I_INSTALL_OK:       DB              $0D,$0A,"OK",$0D,$8A
                        ENDIF
                        IF              STR8_V1_INSTALLER_DRY
                        IF              STR8_V1_INSTALLER_TXN
MSG_I_WRITE_CONFIRM:    DB              " WRITE? Y:",$A0
                        ELSE
MSG_I_STAGE_CONFIRM:    DB              " STAGE? Y:",$A0
                        ENDIF
MSG_I_SEND_S19:         DB              $0D,$0A,"S19",$0D,$8A
                        IF              STR8_V1_INSTALLER_TXN
MSG_I_COMMIT:           DB              "COMMIT? Y:",$A0
MSG_I_FAIL:             DB              $0D,$0A,"FAIL",$0D,$8A
                        ELSE
MSG_I_STAGE_OK:         DB              "STAGE O",('K'+$80)
MSG_I_S19_FAIL:         DB              $0D,$0A,"S19 FAI",('L'+$80)
                        ENDIF
                        ENDIF
MSG_I_NO_WRITE:         DB              " NO",$0D,$8A
                        ENDIF
                        IF              STR8_V1_LAYOUT
                        ELSE
MSG_COPY_FAIL:          DB              $0D,$0A,"COPY FAIL",$0D,$8A
MSG_UPDATE_ROM_ONLY:    DB              $0D,$0A,"U ROM ONLY",$0D,$8A
MSG_UPDATE_HIMON:       DB              $0D,$0A,"UPDATE HIMON C000-EFFF? Y:",$A0
MSG_UPDATE_SEND_S19:    DB              $0D,$0A,"SEND S19 C000-EFFF",$0D,$8A
MSG_UPDATE_WRITE:       DB              $0D,$0A,"PROGRAM C000-EFFF? Y:",$A0
MSG_S19_FAIL:           DB              $0D,$0A,"S19 FAIL",$0D,$8A
MSG_S19_NO_DATA:        DB              $0D,$0A,"NO S19 DATA",$0D,$8A
                        ENDIF
MSG_NO_TARGET:          DB              "NO",$0D,$8A
MSG_JUMP_B:             DB              $0D,$0A,"J ",('B'+$80)
MSG_JUMP_FAIL:          DB              "J FAIL",$0D,$8A
                        IF              STR8_RAM_PROOF
MSG_COPY_FAIL_AT:       DB              $0D,$0A,"COPY FAIL @ ",('$'+$80)
                        ENDIF
MSG_RESET:              DB              "RESET"
MSG_CRLF:               DB              $0D,$8A
                        IF              STR8_V1_LAYOUT
MSG_BACKSPACE:          DB              $08,$20,$88
STR8_HIMON_WARM_SIGNATURE:
                        DB              HIMON_IMAGE_SIG0_VALUE,HIMON_IMAGE_SIG1_VALUE
                        DB              HIMON_IMAGE_SIG2_VALUE,HIMON_IMAGE_SIG3_VALUE
                        ENDIF

                        END
