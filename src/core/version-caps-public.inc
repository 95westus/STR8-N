; VX1 candidate bootstrap contract, B3 visible, SEI/CLD, 816 E=1 D=DBR=PBR=0.
; Existing RA/CAPS/BOARD contracts are unchanged. This is not a frozen v2.1 ABI.
VX_BASE EQU $E000
VX_QUERY_ENTRY EQU $E004
VX_COMMAND_ENTRY EQU $E007
VX_FORMAT EQU 1
VX_INFO_SIZE EQU 224
VX_FRAME EQU $6700
VX_REQUEST EQU $67E0
VX_MON_FOOTER EQU $0FC0
; QUERY: A=running page A0/B0, or 0 if unknown; X/Y=buffer low/high.
; Buffer byte 0 contains capacity >=224. Bounds: 0200..64FF, or exactly 6700.
; C=1/A=0 success; C=0/A=80 absent,81 incompatible,82 bad buffer/request.
; X/Y preserved; D0..DF preserved; 6700..67FF and stack are foreground scratch.
; Output layout is documented in docs/STR8N_B15_VERSION_CAPS_CANDIDATE.md.
