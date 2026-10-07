; Optional service discovery; existing public ROM/RAM tables are unchanged.
; These bytes are monitor-owned and cleared by the existing F reset path.
SVC_DESC EQU $7D04             ; "SV",1,flags,pointer LE16, application-end LE16
SVC_FLAGS EQU $7D07            ; bit0 RTC, bit1 I2C
SVC_ACTIVE EQU $7D0C           ; FF means $6500-$66FF reserved until RESET
SVC_SEAL EQU $7D0D             ; last accepted component seal, LE16
SVC_GATE EQU $6500
SVC_READY EQU $6664            ; bit0 verified code, bit1 initialized state
SVC_BUSY EQU $6660
SVC_DRIVER_BUSY EQU $6669
