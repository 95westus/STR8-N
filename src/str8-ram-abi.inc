; ----------------------------------------------------------------------------
; str8-ram-abi.inc
; STR8-N v1.2 shared RAM ownership contract.
; Keep this file synchronized with the R-YORS STR8 include and release manifest.
; ----------------------------------------------------------------------------

STR8_RAM_ABI_VERSION        EQU             $12

STR8_HIGH_TOOL_BASE         EQU             $7C00
STR8_HIGH_TOOL_END          EQU             $7DBF
HIM_AP_LINK_WORK_BASE       EQU             $7DC0
HIM_AP_LINK_WORK_END        EQU             $7DC7

STR8_STATE_BASE             EQU             $7DE9
STR8_STATE_END              EQU             $7DFF
STR8_MARK_SECTOR_HI         EQU             $7DE9
STR8_MARK_ADDR_LO           EQU             $7DEA
STR8_MARK_ADDR_HI           EQU             $7DEB
STR8_COPY_SRC_BANK          EQU             $7DEE
STR8_COPY_DST_BANK          EQU             $7DEF
STR8_COPY_MODE              EQU             $7DF0
STR8_BOOT_KEY_ENABLE        EQU             $7DF1
STR8_INPUT_SKIP_LF          EQU             $7DF1
STR8_JUMP_BANK              EQU             $7DF2
STR8_JUMP_VEC_LO            EQU             $7DF3
STR8_JUMP_VEC_HI            EQU             $7DF4
STR8_JUMP_STATUS            EQU             $7DF5
STR8_STAGE_BUF_HI           EQU             $7DF6
STR8_UPD_MASK               EQU             $7DF7
STR8_UPD_DATA_LEN           EQU             $7DF9
STR8_UPD_DST_LO             EQU             $7DFB
STR8_UPD_DST_HI             EQU             $7DFC
STR8_BANK_JUMP_SIG0         EQU             $7DFD
STR8_BANK_JUMP_SIG1         EQU             $7DFE
STR8_BANK_LAST_JUMP         EQU             $7DFF

ASM_TARGET_END_EXCLUSIVE    EQU             $7D00
ASM_TARGET_LAST             EQU             $7CFF
