; Versioned integrated beta5 clock API. Discover SV and RG before calling.
; Foreground 65C02 / 816 emulation, D=DBR=PBR=0. Reserve $6500-$66FF.
; A=status, C=success; I/decimal/PCR/stack preserved; X/Y/N/Z/V unspecified.
RTC_DISCOVERY EQU $7D04       ; "SV",1,flags,gateway LE16,last program RAM LE16
RTC_SIGNATURE EQU $6500       ; "RG",1,4
RTC_READ EQU $6504
RTC_STATUS EQU $6507
RTC_SET EQU $650A
RTC_ACK_POWER EQU $650D
RTC_RESULT EQU $66C0
RTC_FLAGS EQU $66C1
RTC_TIME EQU $66C2            ; year LE16,month,day,weekday,hour,minute,second
RTC_RAW EQU $66CB             ; registers 00-08
RTC_OUTAGE EQU $66D4          ; registers 18-1F; minute precision, no year
RTC_EVIDENCE EQU $66DC
RTC_REQUEST EQU $66E0
RTC_KEY EQU $66E9             ; SET $53,$54; ACK $50,$41; consumed on invocation
RTC_CAPTURE EQU $66F0         ; retained outage in RAM, lost on RESET/replacement
RTC_F_START EQU $01
RTC_F_RUNNING EQU $02
RTC_F_CALENDAR EQU $04
RTC_F_POWERFAIL EQU $08
RTC_F_BACKUP_ENABLED EQU $10
RTC_F_CONTINUITY_UNKNOWN EQU $20
