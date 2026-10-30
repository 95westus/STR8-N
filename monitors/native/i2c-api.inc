; Phase 2 beta5 candidate ABI. Foreground single-master; no IRQ/NMI/native calls.
; Caller uses the RAM entry, reserves $6500-$66FF, and owns buffers $0200-$64FF.
; I/D/PCR/stack preserved; A=status, C=success; X/Y/N/Z/V unspecified.
I2C_SIGNATURE EQU $6510       ; "I2",1,1; independent of clock discovery
I2C_TRANSFER EQU $6514
I2C_REQUEST EQU $6650
I2C_ADDRESS EQU $6650         ; unshifted seven-bit address, $08-$77
I2C_FLAGS EQU $6651           ; bit0 repeated START; other bits reserved
I2C_WRITE_PTR EQU $6652       ; LE16 RAM source; ignored when count=0
I2C_WRITE_COUNT EQU $6654     ; 0..64
I2C_READ_PTR EQU $6655        ; LE16 RAM destination; ignored when count=0
I2C_READ_COUNT EQU $6657      ; 0..64; at least one direction nonzero
I2C_RESULT EQU $6658
I2C_WRITTEN EQU $6659         ; acknowledged payload bytes, excludes address
I2C_READ EQU $665A            ; completed/stored bytes
I2C_PHASE EQU $665B           ; 0 validation/idle setup,1 write address,2 write data,
                             ; 3 read address,4 read data,5 STOP
I2C_RESTART EQU 1
I2C_MAX_BYTES EQU 64
I2C_BAD_ARGUMENT EQU 9
; Other errors share RTC: busy=1, NACK=2, timeout=3, denied=6, in-use=8.
; RTC $6F public access is limited to explicit register reads within $00-$1F.
; RTC data writes use RTC_SET/ACK; $57 MCP EEPROM access remains deferred.
IO_LOAD EQU $66B0             ; private RAM LDA abs/RTS thunk
IO_STORE EQU $66B4            ; private RAM STA abs/RTS thunk
