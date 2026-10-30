; UI/1 is a private MON/tool interface, not an addition to Foundation's ABI.
; Descriptor and vectors are inside the MI payload CRC. Foreground B3 only;
; E=1, D=DBR=PBR=0, SEI/CLD. All calls clobber system scratch E0-FF.
MU_DESCRIPTOR EQU $48
MU_VECTOR_BASE EQU $20
MU_VERSION EQU 0
MU_TIME EQU 1
MU_RETURN EQU 2
MU_SAMPLE EQU 3
MU_DISPLAY EQU 4
MU_BYPASS EQU 5
MU_VECTOR_COUNT EQU 6
MU_ACTIVE EQU $7D30
MU_BANK EQU $6A00
; Session EDU selection survives shared-tool reload and quiet native returns.
MU_EDU EQU $6A20
