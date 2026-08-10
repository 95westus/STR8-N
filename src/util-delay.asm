; -------------------------------------------------------------------------
; CALL HIERARCHY / LAYER RULES
; L0 (Driver): drv-*.asm        -> direct hardware/MMIO access only.
; L1 (HAL):    hal-*.asm        -> calls L0, no direct hardware touching.
; L2 (Backend):backend-*.asm    -> protocol/helpers, calls L1/L2-common.
; L2 (Common): util-*.asm       -> pure utility routines, no hardware access.
; L3 (Access): lock/access-policy -> capability gates, lock/unlock, privilege
;   checks.
; L4 (Sys):    sys-*.asm        -> device-neutral I/O API (SYS_*), calls
;   L3/L2.
; L5 (App):    app/*.asm        -> monitor/app entry points.
; TEST (Out-of-band): test/*.asm -> test harnesses (not part of layer ABI).
;
; ZP ALLOCATION POLICY
; - See ZP_MAP.md for reserved/scratch ownership.
; - Add/update labels in ZP_MAP.md before claiming new ZP bytes.
;
; THIS FILE: L2 COMMON UTILITIES (delay helpers).
; - Pure polling delay loops for bring-up.
; - No hardware/timer dependencies.
; -------------------------------------------------------------------------

                        MODULE          UTL_DELAY_AXY_8MHZ

                        XDEF            UTL_DELAY_AXY_8MHZ

DELAY_AXY_Y_INIT           EQU             $7EDE
DELAY_AXY_X_INIT           EQU             $7EDF

DELAY_AXY_MAX_A            EQU             $E5                    ; 229
DELAY_AXY_MAX_X            EQU             $B6                    ; 182
DELAY_AXY_MAX_Y            EQU             $F8                    ; 248

; ----------------------------------------------------------------------------
; ROUTINE: UTL_DELAY_AXY_8MHZ  [HASH:153EF005]
; TIER: APP-L5
; TAGS: UTL, APP-L5, NO-ZP, USES-FIXED-RAM, NOSTACK
; MEM : ZP: none; FIXED_RAM: DELAY_AXY_Y_INIT($7EDE), DELAY_AXY_X_INIT($7EDF).
; PURPOSE: Polling delay using nested A/X/Y software loops at 8 MHz.
; IN :
; OUT:
;   A = outer loop count
;   X = middle loop count
;   Y = inner loop count
;   C = 1 always (successful completion)
;   A/X/Y clobbered
;     C_core = A * ( X * (5*Y + 8) + 8 ) + 13
;     t_seconds = C_core / 8,000,000
;     t_ms      = C_core / 8,000
;     C_core = 52,015,989 cycles
;     t ~= 6.502 s (6.501998625 s from core model).
; EXCEPTIONS/NOTES:
; - If A=0 or X=0 or Y=0, routine returns immediately.
; - Inputs are clamped to A<=229, X<=182, Y<=248 to cap delay near 6.502 s.
; - Core loop-cycle model (after clamp, non-zero case):
; - Approximate time at 8 MHz:
; - With clamped maxima A=229, X=182, Y=248:
; ----------------------------------------------------------------------------
UTL_DELAY_AXY_8MHZ:
                        CMP             #$00
                        BEQ             ?DONE
                        CPX             #$00
                        BEQ             ?DONE
                        CPY             #$00
                        BEQ             ?DONE

                        CMP             #DELAY_AXY_MAX_A+1
                        BCC             ?A_OK
                        LDA             #DELAY_AXY_MAX_A
?A_OK:
                        CPX             #DELAY_AXY_MAX_X+1
                        BCC             ?X_OK
                        LDX             #DELAY_AXY_MAX_X
?X_OK:
                        CPY             #DELAY_AXY_MAX_Y+1
                        BCC             ?Y_OK
                        LDY             #DELAY_AXY_MAX_Y
?Y_OK:
                        STX             DELAY_AXY_X_INIT
                        STY             DELAY_AXY_Y_INIT

?OUTER:                 LDX             DELAY_AXY_X_INIT
?MIDDLE:                LDY             DELAY_AXY_Y_INIT
?INNER:                 DEY
                        BNE             ?INNER
                        DEX
                        BNE             ?MIDDLE
                        DEC             A
                        BNE             ?OUTER

?DONE:                  SEC
                        RTS

                        ENDMOD

                        END
