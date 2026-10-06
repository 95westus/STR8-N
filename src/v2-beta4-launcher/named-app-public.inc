; Named flash application image header, format 1, 16 bytes, little endian.
; Host ABI 1: 65C02 / 816 emulation, D=DBR=PBR=0, IRQ masked, decimal clear.
; Call STR8-N's public RAM services; normal exit is JMP STR8V2_RAM_HOLD.
; Workspace is exclusive, not an allocation or a memory-protection mechanism.
APP_HEADER_SIZE        EQU $10
APP_FORMAT             EQU $01
APP_HOST_ABI           EQU $01
APP_LENGTH_OFFSET      EQU $04
APP_ENTRY_OFFSET       EQU $06
APP_RAM_FIRST_OFFSET   EQU $08
APP_RAM_LAST_OFFSET    EQU $0A
APP_ZP_FIRST_OFFSET    EQU $0C
APP_ZP_LAST_OFFSET     EQU $0D
APP_HEADER_CRC_OFFSET  EQU $0E
; Header: "AP", format, host ABI, image length, entry, RAM first/last,
; ZP first/last, CRC16/CCITT-FALSE of the preceding 14 bytes.
; Image length includes the header. RAM 0000/0000 and ZP FF/FF mean none.
