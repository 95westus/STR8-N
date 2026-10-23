; Offline, version-paired source editor extension. Linked in B1:9000.
; AS/1 capsule: "AS", version=1, header bytes=8, payload length LE16,
; payload CRC-16/CCITT LE16, canonical packed ASM source records.
 MODULE SOURCE_STORE
 XDEF NS_END
 INCLUDE "asm-equ.inc"
 INCLUDE "storage-equ.inc"
 INCLUDE "worker-equ.inc"
 INCLUDE "state.inc"
 CODE
 DB "NS",1,1
 DW NS_DISPATCH,NS_END
NS_INIT:
 STZ RESULT_VALID
 STZ NS_DIRTY
 STZ NS_ACTIVE
 RTS
NS_EDIT:
 STZ RESULT_VALID
 LDA #1
 STA NS_DIRTY
 RTS
; Replaces SHELL_WORD's JSR READ_TOKEN with the same-size call.
; Ordinary commands return to the original parser; handled commands discard
; this one return address and return directly to SHELL.
NS_DISPATCH:
 JSR READ_TOKEN
 LDA TOKEN
 CMP #'S'
                        BEQ BM_LONG_29
                        JMP NS_TRY_LOAD
BM_LONG_29:
 LDY #0
NS_MATCH_SAVE:
 LDA TOKEN,Y
 CMP NS_SAVE_WORD,Y
                        BEQ BM_LONG_34
                        JMP NS_NOT_COMMAND
BM_LONG_34:
 INY
 CPY #5
                        BEQ BM_LONG_37
                        JMP NS_MATCH_SAVE
BM_LONG_37:
 LDA #1
                        JMP NS_PARSE
NS_TRY_LOAD:
 CMP #'L'
                        BEQ BM_LONG_42
                        JMP NS_NOT_COMMAND
BM_LONG_42:
 LDY #0
NS_MATCH_LOAD:
 LDA TOKEN,Y
 CMP NS_LOAD_WORD,Y
                        BEQ BM_LONG_47
                        JMP NS_NOT_COMMAND
BM_LONG_47:
 INY
 CPY #5
                        BEQ BM_LONG_50
                        JMP NS_MATCH_LOAD
BM_LONG_50:
 LDA #2
NS_PARSE:
 STA NS_OPERATION
 JSR READ_TOKEN
 STZ NS_PROVIDER
 LDY #0
NS_MATCH_PROVIDER:
 LDA TOKEN,Y
 CMP NS_SRAM_WORD,Y
                        BEQ BM_LONG_60
                        JMP NS_TRY_FLASH
BM_LONG_60:
 INY
 CPY #5
                        BEQ BM_LONG_63
                        JMP NS_MATCH_PROVIDER
BM_LONG_63:
                        JMP NS_PROVIDER_DONE
NS_TRY_FLASH:
 LDY #0
NS_MATCH_FLASH:
 LDA TOKEN,Y
 CMP NS_FLASH_WORD,Y
                        BEQ BM_LONG_70
                        JMP NS_SYNTAX
BM_LONG_70:
 INY
 CPY #6
                        BEQ BM_LONG_73
                        JMP NS_MATCH_FLASH
BM_LONG_73:
 INC NS_PROVIDER
NS_PROVIDER_DONE:
 LDY #31
 LDA #0
NS_CLEAR_REQUEST:
 STA NS_REQUEST,Y
 DEY
                        BMI BM_LONG_81
                        JMP NS_CLEAR_REQUEST
BM_LONG_81:
 JSR SPACES
 LDY #0
NS_NAME_LOOP:
 LDA LINE,X
                        BNE BM_LONG_86
                        JMP NS_NAME_DONE
BM_LONG_86:
 CMP #' '
                        BNE BM_LONG_88
                        JMP NS_NAME_DONE
BM_LONG_88:
 CPY #16
                        BCC BM_LONG_90
                        JMP NS_SYNTAX
BM_LONG_90:
 CMP #'a'
                        BCS BM_LONG_92
                        JMP NS_NAME_UPPER
BM_LONG_92:
 CMP #'z'+1
                        BCC BM_LONG_94
                        JMP NS_NAME_UPPER
BM_LONG_94:
 AND #$DF
NS_NAME_UPPER:
 CMP #'_'
                        BNE BM_LONG_98
                        JMP NS_NAME_OK
BM_LONG_98:
 CMP #'-'
                        BNE BM_LONG_100
                        JMP NS_NAME_OK
BM_LONG_100:
 CMP #'0'
                        BCS BM_LONG_102
                        JMP NS_SYNTAX
BM_LONG_102:
 CMP #'9'+1
                        BCS BM_LONG_104
                        JMP NS_NAME_OK
BM_LONG_104:
 CMP #'A'
                        BCS BM_LONG_106
                        JMP NS_SYNTAX
BM_LONG_106:
 CMP #'Z'+1
                        BCC BM_LONG_108
                        JMP NS_SYNTAX
BM_LONG_108:
NS_NAME_OK:
 STA NS_REQUEST+8,Y
 INX
 INY
                        JMP NS_NAME_LOOP
NS_NAME_DONE:
 CPY #0
                        BNE BM_LONG_116
                        JMP NS_SYNTAX
BM_LONG_116:
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_119
                        JMP NS_SYNTAX
BM_LONG_119:
 LDA NS_OPERATION
 CMP #1
                        BNE BM_LONG_122
                        JMP NS_SAVE
BM_LONG_122:
 JMP NS_LOAD
NS_NOT_COMMAND:
 RTS
NS_SYNTAX:
 LDX #<NS_SYNTAX_TEXT
 LDY #>NS_SYNTAX_TEXT
 JMP NS_MESSAGE
NS_BAD:
 LDX #<NS_BAD_TEXT
 LDY #>NS_BAD_TEXT
 JMP NS_MESSAGE
NS_CANCEL:
 LDX #<NS_CANCEL_TEXT
 LDY #>NS_CANCEL_TEXT
 JMP NS_MESSAGE
NS_STORAGE_ERROR:
 PHA
 LDX #<NS_STORAGE_TEXT
 LDY #>NS_STORAGE_TEXT
 JSR PRINT
 PLA
 JSR STR8V2_RAM_HEX_OUT
 JSR STR8V2_RAM_NEWLINE
 JMP NS_SHELL
NS_MESSAGE:
 JSR PRINT
NS_SHELL:
 PLA
 PLA
 JMP SHELL
NS_SAVE:
 ; Refuse corrupt source-end state before copying any bytes.
 LDA SRC_END+1
 CMP #>SOURCE_START
                        BCS BM_LONG_157
                        JMP NS_BAD
BM_LONG_157:
 CMP #>SOURCE_END
                        BCS BM_LONG_159
                        JMP NS_SAVE_BOUNDS
BM_LONG_159:
                        BEQ BM_LONG_160
                        JMP NS_BAD
BM_LONG_160:
 LDA SRC_END
                        BEQ BM_LONG_162
                        JMP NS_BAD
BM_LONG_162:
NS_SAVE_BOUNDS:
 STZ RESULT_VALID
 SEC
 LDA SRC_END
 SBC #<SOURCE_START
 STA NS_LENGTH
 LDA SRC_END+1
 SBC #>SOURCE_START
 STA NS_LENGTH+1
 LDA #<SOURCE_START
 STA PTR
 LDA #>SOURCE_START
 STA PTR+1
 LDA #8
 STA TEMP
 LDA #2
 STA TEMP+1
 JSR NS_COPY_LENGTH
 LDY #5
NS_WRITE_HEADER:
 LDA NS_HEADER,Y
 STA $0200,Y
 DEY
                        BMI BM_LONG_186
                        JMP NS_WRITE_HEADER
BM_LONG_186:
 LDA NS_LENGTH
 STA $0204
 LDA NS_LENGTH+1
 STA $0205
 LDA #1
 STA NS_NORMALIZE
 JSR NS_VALIDATE
                        BCC BM_LONG_194
                        JMP NS_BAD
BM_LONG_194:
 JSR NS_CHECKSUM
 LDA NS_CRC
 STA $0206
 LDA NS_CRC+1
 STA $0207
 LDA #1
 STA NS_REQUEST
 ; Every saved source is a restore-only image at the scratch window.
 LDA #2
 STA NS_REQUEST+3
 SEC
 LDA NS_DOCEND
 SBC #1
 STA NS_REQUEST+4
 LDA NS_DOCEND+1
 SBC #0
 STA NS_REQUEST+5
 JSR NS_CALL_STORAGE
                        BCS BM_LONG_213
                        JMP NS_STORAGE_ERROR
BM_LONG_213:
 STZ NS_DIRTY
 LDX #<NS_SAVED_TEXT
 LDY #>NS_SAVED_TEXT
 JMP NS_MESSAGE
NS_LOAD:
 LDA NS_DIRTY
                        BNE BM_LONG_220
                        JMP NS_LOAD_BEGIN
BM_LONG_220:
 LDX #<NS_CONFIRM_TEXT
 LDY #>NS_CONFIRM_TEXT
 JSR PRINT
 JSR READ_LINE
 LDA ERROR
                        BEQ BM_LONG_226
                        JMP NS_CANCEL
BM_LONG_226:
 LDX #0
 JSR READ_TOKEN
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_231
                        JMP NS_CANCEL
BM_LONG_231:
 LDY #0
NS_CONFIRM_LOOP:
 LDA TOKEN,Y
 CMP NS_YES_WORD,Y
                        BEQ BM_LONG_236
                        JMP NS_CANCEL
BM_LONG_236:
 INY
 CPY #4
                        BEQ BM_LONG_239
                        JMP NS_CONFIRM_LOOP
BM_LONG_239:
NS_LOAD_BEGIN:
 STZ RESULT_VALID
 LDA #2
 STA NS_REQUEST
 JSR NS_CALL_STORAGE
                        BCS BM_LONG_245
                        JMP NS_STORAGE_ERROR
BM_LONG_245:
 LDY #3
NS_CHECK_HEADER:
 LDA $0200,Y
 CMP NS_HEADER,Y
                        BEQ BM_LONG_250
                        JMP NS_BAD
BM_LONG_250:
 DEY
                        BMI BM_LONG_252
                        JMP NS_CHECK_HEADER
BM_LONG_252:
 LDA $0204
 STA NS_LENGTH
 LDA $0205
 STA NS_LENGTH+1
 ; Directory length is also checked by the storage-side guard.
 CLC
 LDA NS_LENGTH
 ADC #8
 STA ENDPTR
 LDA NS_LENGTH+1
 ADC #0
 STA ENDPTR+1
 LDA ENDPTR
 CMP NS_STORED_LENGTH
                        BEQ BM_LONG_267
                        JMP NS_BAD
BM_LONG_267:
 LDA ENDPTR+1
 CMP NS_STORED_LENGTH+1
                        BEQ BM_LONG_270
                        JMP NS_BAD
BM_LONG_270:
 STZ NS_NORMALIZE
 JSR NS_VALIDATE
                        BCC BM_LONG_273
                        JMP NS_BAD
BM_LONG_273:
 JSR NS_CHECKSUM
 LDA NS_CRC
 CMP $0206
                        BEQ BM_LONG_277
                        JMP NS_BAD
BM_LONG_277:
 LDA NS_CRC+1
 CMP $0207
                        BEQ BM_LONG_280
                        JMP NS_BAD
BM_LONG_280:
 ; Source changes only after complete transfer, validation and CRC.
 LDA #8
 STA PTR
 LDA #2
 STA PTR+1
 LDA #<SOURCE_START
 STA TEMP
 LDA #>SOURCE_START
 STA TEMP+1
 JSR NS_COPY_LENGTH
 CLC
 LDA NS_LENGTH
 ADC #<SOURCE_START
 STA SRC_END
 LDA NS_LENGTH+1
 ADC #>SOURCE_START
 STA SRC_END+1
 STZ NS_DIRTY
 STZ PASTE_MODE
 STZ SKIP_LF
 STZ SCOPE_VALID
 LDX #<NS_LOADED_TEXT
 LDY #>NS_LOADED_TEXT
 JMP NS_MESSAGE
NS_COPY_LENGTH:
 LDA NS_LENGTH
 STA ENDPTR
 LDA NS_LENGTH+1
 STA ENDPTR+1
NS_COPY_LOOP:
 LDA ENDPTR
 ORA ENDPTR+1
                        BNE BM_LONG_313
                        JMP NS_COPY_DONE
BM_LONG_313:
 LDA (PTR)
 STA (TEMP)
 INC PTR
                        BEQ BM_LONG_317
                        JMP NS_COPY_DEST
BM_LONG_317:
 INC PTR+1
NS_COPY_DEST:
 INC TEMP
                        BEQ BM_LONG_321
                        JMP NS_COPY_COUNT
BM_LONG_321:
 INC TEMP+1
NS_COPY_COUNT:
 LDA ENDPTR
                        BEQ BM_LONG_325
                        JMP NS_COPY_DEC
BM_LONG_325:
 DEC ENDPTR+1
NS_COPY_DEC:
 DEC ENDPTR
                        JMP NS_COPY_LOOP
NS_COPY_DONE:
 RTS
; Validate the canonical packed source in scratch. No live source writes.
NS_VALIDATE:
 LDA NS_LENGTH+1
 CMP #$1C
                        BCS BM_LONG_336
                        JMP NS_LENGTH_OK
BM_LONG_336:
                        BEQ BM_LONG_337
                        JMP NS_INVALID
BM_LONG_337:
 LDA NS_LENGTH
                        BEQ BM_LONG_339
                        JMP NS_INVALID
BM_LONG_339:
NS_LENGTH_OK:
 CLC
 LDA NS_LENGTH
 ADC #8
 STA NS_DOCEND
 LDA NS_LENGTH+1
 ADC #2
 STA NS_DOCEND+1
 LDA #8
 STA PTR
 LDA #2
 STA PTR+1
 STZ NS_PREVIOUS
 STZ NS_PREVIOUS+1
NS_RECORD_LOOP:
 LDA PTR+1
 CMP NS_DOCEND+1
                        BEQ BM_LONG_357
                        JMP NS_RECORD
BM_LONG_357:
 LDA PTR
 CMP NS_DOCEND
                        BNE BM_LONG_360
                        JMP NS_VALID
BM_LONG_360:
NS_RECORD:
 CLC
 LDA PTR
 ADC #4
 STA NEXT
 LDA PTR+1
 ADC #0
 STA NEXT+1
 JSR NS_NEXT_BOUND
                        BCC BM_LONG_370
                        JMP NS_INVALID
BM_LONG_370:
 LDY #1
 LDA (PTR),Y
 CMP NS_PREVIOUS+1
                        BCS BM_LONG_374
                        JMP NS_INVALID
BM_LONG_374:
                        BEQ BM_LONG_375
                        JMP NS_LINE_ORDERED
BM_LONG_375:
 DEY
 LDA (PTR),Y
 CMP NS_PREVIOUS
                        BCS BM_LONG_379
                        JMP NS_INVALID
BM_LONG_379:
                        BNE BM_LONG_380
                        JMP NS_INVALID
BM_LONG_380:
NS_LINE_ORDERED:
 LDY #0
 LDA (PTR),Y
 STA NS_PREVIOUS
 INY
 LDA (PTR),Y
 STA NS_PREVIOUS+1
 INY
 LDA (PTR),Y
                        BNE BM_LONG_390
                        JMP NS_INVALID
BM_LONG_390:
 CMP #LINE_MAX+1
                        BCC BM_LONG_392
                        JMP NS_INVALID
BM_LONG_392:
 STA NS_TEXT_LENGTH
 CLC
 ADC NEXT
 STA NEXT
                        BCS BM_LONG_397
                        JMP NS_RECORD_END
BM_LONG_397:
 INC NEXT+1
NS_RECORD_END:
 JSR NS_NEXT_BOUND
                        BCC BM_LONG_401
                        JMP NS_INVALID
BM_LONG_401:
 INY
 LDA NS_NORMALIZE
                        BEQ BM_LONG_404
                        JMP NS_CLEAR_CACHE
BM_LONG_404:
 LDA (PTR),Y
                        BEQ BM_LONG_406
                        JMP NS_INVALID
BM_LONG_406:
NS_CLEAR_CACHE:
 LDA #0
 STA (PTR),Y
 INY
NS_VALIDATE_TEXT:
 LDA (PTR),Y
 CMP #$20
                        BCS BM_LONG_414
                        JMP NS_INVALID
BM_LONG_414:
 CMP #$7F
                        BCC BM_LONG_416
                        JMP NS_INVALID
BM_LONG_416:
 INY
 DEC NS_TEXT_LENGTH
                        BEQ BM_LONG_419
                        JMP NS_VALIDATE_TEXT
BM_LONG_419:
 LDA NEXT
 STA PTR
 LDA NEXT+1
 STA PTR+1
 JMP NS_RECORD_LOOP
NS_VALID:
 CLC
 RTS
NS_INVALID:
 SEC
 RTS
NS_NEXT_BOUND:
 LDA NEXT+1
 CMP NS_DOCEND+1
                        BCS BM_LONG_434
                        JMP NS_VALID
BM_LONG_434:
                        BEQ BM_LONG_435
                        JMP NS_INVALID
BM_LONG_435:
 LDA NEXT
 CMP NS_DOCEND
                        BCS BM_LONG_438
                        JMP NS_VALID
BM_LONG_438:
                        BNE BM_LONG_439
                        JMP NS_VALID
BM_LONG_439:
                        JMP NS_INVALID
NS_CHECKSUM:
 LDA #$FF
 STA NS_CRC
 STA NS_CRC+1
 LDA #8
 STA PTR
 LDA #2
 STA PTR+1
 LDA NS_LENGTH
 STA ENDPTR
 LDA NS_LENGTH+1
 STA ENDPTR+1
NS_CRC_LOOP:
 LDA ENDPTR
 ORA ENDPTR+1
                        BNE BM_LONG_456
                        JMP NS_COPY_DONE
BM_LONG_456:
 LDA (PTR)
 JSR NS_CRC_BYTE
 INC PTR
                        BEQ BM_LONG_460
                        JMP NS_CRC_COUNT
BM_LONG_460:
 INC PTR+1
NS_CRC_COUNT:
 LDA ENDPTR
                        BEQ BM_LONG_464
                        JMP NS_CRC_DEC
BM_LONG_464:
 DEC ENDPTR+1
NS_CRC_DEC:
 DEC ENDPTR
                        JMP NS_CRC_LOOP
NS_CRC_BYTE:
 EOR NS_CRC+1
 STA NS_CRC+1
 LDX #8
NS_CRC_BIT:
 ASL NS_CRC
 ROL NS_CRC+1
                        BCS BM_LONG_476
                        JMP NS_CRC_NEXT
BM_LONG_476:
 LDA NS_CRC
 EOR #$21
 STA NS_CRC
 LDA NS_CRC+1
 EOR #$10
 STA NS_CRC+1
NS_CRC_NEXT:
 DEX
                        BEQ BM_LONG_485
                        JMP NS_CRC_BIT
BM_LONG_485:
 RTS
NS_CALL_STORAGE:
 LDA NS_PROVIDER
                        BEQ BM_LONG_489
                        JMP NF_ENTRY
BM_LONG_489:
 LDX #NS_GATE_END-NS_GATE_IMAGE-1
NS_INSTALL_GATE:
 LDA NS_GATE_IMAGE,X
 STA NS_GATE,X
 DEX
                        BMI BM_LONG_495
                        JMP NS_INSTALL_GATE
BM_LONG_495:
 JSR NS_GATE
 RTS
; This exact position-independent stub runs in ASM state RAM while the flash
; bank changes. All firmware addresses are generated from the matched build.
NS_GATE_IMAGE:
 LDA #2
 JSR NS_SELECT
 JSR NS_STORAGE
 PHP
 PHA
 LDA #1
 JSR NS_SELECT
 PLA
 PLP
 RTS
NS_GATE_END:
NS_HEADER: DB "AS",1,8,0,0
NS_SAVE_WORD: DB "SAVE",0
NS_LOAD_WORD: DB "LOAD",0
NS_SRAM_WORD: DB "SRAM",0
NS_FLASH_WORD: DB "FLASH",0
NS_YES_WORD: DB "YES",0
NS_SAVED_TEXT: DB "Source saved; reassemble output.",13,10,0
NS_LOADED_TEXT: DB "Source loaded; reassemble output.",13,10,0
NS_BAD_TEXT: DB "Invalid source image.",13,10,0
NS_STORAGE_TEXT: DB "Source storage: ",0
NS_CANCEL_TEXT: DB "Load cancelled.",13,10,0
NS_SYNTAX_TEXT: DB "Use SAVE/LOAD SRAM|FLASH name.",13,10,0
NS_CONFIRM_TEXT: DB "Discard unsaved edits? Type YES: ",0
 INCLUDE "flash.inc"
NS_END:
