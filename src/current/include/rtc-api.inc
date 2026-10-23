; Flash RTC provider; mutable state is RAM. Call through the RAM gateway.
; 65C02 / 816 E=1, DBR=PBR=D=0. Not reentrant; no IRQ/NMI calls.
; A=status, C=1 success; X/Y/N/Z/V unspecified; I and D restored.
; No bank selection or monitor ABI modification. Exclusive VIA1/I2C ownership.
RTC_SIGNATURE EQU $8000       ; "RC",1,4 (four entry points)
RTC_READ      EQU $8004       ; Valid decoded calendar, else error + raw/status
RTC_STATUS    EQU $8007       ; Raw/status, success even if clock invalid/stopped
RTC_SET       EQU $800A       ; Explicit SET request; refuses enabled alarms
RTC_ACK_POWER EQU $800D       ; Explicit acknowledgment; captures outage first
RTC_RESULT    EQU $66C0       ; status byte
RTC_FLAGS     EQU $66C1       ; bits below, independent of error
RTC_TIME      EQU $66C2       ; 8 bytes: year LE16,month,date,weekday,hour,min,sec
RTC_RAW       EQU $66CB       ; 9 bytes: registers 00-08
RTC_OUTAGE    EQU $66D4       ; 8 bytes: registers 18-1F (latest hardware read)
RTC_EVIDENCE  EQU $66DC       ; 1 if captured outage below is available
RTC_CAPTURE   EQU $66F0       ; 8 bytes retained across service calls until reload
RTC_REQUEST   EQU $66E0       ; year LE16,month,date,weekday,hour,minute,second
RTC_KEY       EQU $66E9       ; SET: $53,$54; ACK: $50,$41; consumed on invocation
RTC_OK        EQU 0
RTC_BUS_BUSY  EQU 1
RTC_NACK      EQU 2
RTC_TIMEOUT   EQU 3
RTC_BAD_TIME  EQU 4
RTC_ALARM_ON  EQU 5
RTC_DENIED    EQU 6
RTC_UNSTABLE  EQU 7
RTC_IN_USE    EQU 8
RTC_F_START   EQU $01
RTC_F_RUNNING EQU $02
RTC_F_CALENDAR EQU $04
RTC_F_POWERFAIL EQU $08
RTC_F_BACKUP_ENABLED EQU $10
RTC_F_CONTINUITY_UNKNOWN EQU $20 ; Always set; no battery-health certification
