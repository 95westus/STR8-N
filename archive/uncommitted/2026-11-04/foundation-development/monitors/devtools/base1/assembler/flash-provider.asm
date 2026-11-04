 MODULE FLASH_SOURCE_PROVIDER
 INCLUDE "asm-equ.inc"
 INCLUDE "ns-equ.inc"
 INCLUDE "state.inc"
 INCLUDE "flash-bindings.inc"
 CODE
 DB "FS",1,8,"PR05"
 JMP NF_ENTRY
 ; Paired source helper callbacks, checked before entry.
 DW NS_CRC_BYTE,NS_YES_WORD
; B0:8000-DFFF only. Data-only SF/1 records occupy one or two complete sectors.
; Only whole erased sectors are allocated; unknown owner data is never erased.
NF_ENTRY:
 STZ NF_FOUND
 STZ NF_FREE
 STZ NF_RUN
 STZ NF_NEEDED
 LDA NS_OPERATION
 CMP #1
                        BEQ NF_LONG_9
                        JMP NF_BEGIN_SCAN
NF_LONG_9:
 CLC
 LDA NS_LENGTH
 ADC #8
 STA NF_LEFT
 LDA NS_LENGTH+1
 ADC #0
 STA NF_LEFT+1
 JSR NF_CALCULATE_SPAN
 STA NF_NEEDED
NF_BEGIN_SCAN:
 LDA #$80
 STA NF_CURRENT
NF_SCAN:
 JSR NF_READ_HEADER
 STZ NF_HEADER_VALID
 LDA NF_HEADER
 CMP #'S'
                        BEQ NF_LONG_27
                        JMP NF_UNKNOWN
NF_LONG_27:
 LDA NF_HEADER+1
 CMP #'F'
                        BEQ NF_LONG_30
                        JMP NF_UNKNOWN
NF_LONG_30:
 JSR NF_VALIDATE_HEADER
                        BCS NF_LONG_32
                        JMP NF_OWN_RECORD
NF_LONG_32:
 LDA NF_HEADER+3
 CMP #$FF
                        BEQ NF_LONG_35
                        JMP NF_CORRUPT
NF_LONG_35:
 ; A torn, uncommitted header cannot publish a source or claim erased space.
 JMP NF_UNKNOWN
NF_OWN_RECORD:
 INC NF_HEADER_VALID
 STZ NF_RUN
 LDY #15
NF_MATCH_NAME:
 LDA NF_HEADER+8,Y
 CMP NS_REQUEST+8,Y
                        BEQ NF_LONG_45
                        JMP NF_NEXT_OWN
NF_LONG_45:
 DEY
                        BMI NF_LONG_47
                        JMP NF_MATCH_NAME
NF_LONG_47:
 LDA NS_OPERATION
 CMP #1
                        BNE NF_LONG_50
                        JMP NF_DUPLICATE
NF_LONG_50:
 LDA NF_HEADER+3
 CMP #$3F
                        BEQ NF_LONG_53
                        JMP NF_NEXT_OWN
NF_LONG_53:
 LDA NF_FOUND
                        BEQ NF_LONG_55
                        JMP NF_CORRUPT
NF_LONG_55:
 LDA NF_CURRENT
 STA NF_FOUND
NF_NEXT_OWN:
 LDA NF_SPAN
 ASL A
 ASL A
 ASL A
 ASL A
 CLC
 ADC NF_CURRENT
                        JMP NF_ADVANCE
NF_UNKNOWN:
 LDA NS_OPERATION
 CMP #1
                        BEQ NF_LONG_70
                        JMP NF_NEXT
NF_LONG_70:
 LDA NF_FREE
                        BEQ NF_LONG_72
                        JMP NF_NEXT
NF_LONG_72:
 JSR NF_IS_ERASED
                        BEQ NF_LONG_74
                        JMP NF_OCCUPIED
NF_LONG_74:
 INC NF_RUN
 LDA NF_RUN
 CMP NF_NEEDED
                        BCS NF_LONG_78
                        JMP NF_NEXT
NF_LONG_78:
 LDA NF_CURRENT
 LDX NF_NEEDED
 CPX #2
                        BEQ NF_LONG_82
                        JMP NF_FREE_FOUND
NF_LONG_82:
 SEC
 SBC #$10
NF_FREE_FOUND:
 STA NF_FREE
                        JMP NF_NEXT
NF_OCCUPIED:
 STZ NF_RUN
NF_NEXT:
 CLC
 LDA NF_CURRENT
 ADC #$10
NF_ADVANCE:
 STA NF_CURRENT
 CMP #$E0
                        BCS NF_LONG_97
                        JMP NF_SCAN
NF_LONG_97:
 LDA NS_OPERATION
 CMP #1
                        BNE NF_LONG_100
                        JMP NF_SAVE
NF_LONG_100:
 LDA NF_FOUND
                        BNE NF_LONG_102
                        JMP NF_NOT_FOUND
NF_LONG_102:
 STA NF_CURRENT
 JSR NF_READ_HEADER
 JSR NF_VALIDATE_HEADER
                        BCC NF_LONG_106
                        JMP NF_CORRUPT
NF_LONG_106:
 JMP NF_LOAD
NF_DUPLICATE:
 LDA #$50
                        JMP NF_FAILURE
NF_FULL:
 LDA #$51
                        JMP NF_FAILURE
NF_CORRUPT:
 LDA #$52
                        JMP NF_FAILURE
NF_PROGRAM_ERROR:
 LDA #$53
                        JMP NF_FAILURE
NF_NOT_FOUND:
 LDA #$42
NF_FAILURE:
 CLC
                        JMP NF_EXIT
NF_SUCCESS:
 LDA #0
 SEC
NF_EXIT:
 RTS
NF_READ_HEADER:
 STZ V2_ADDR
 LDA NF_CURRENT
 STA V2_ADDR+1
 JSR NF_READ16
 LDX #15
NF_HEADER_FIRST:
 LDA V2_BYTES,X
 STA NF_HEADER,X
 DEX
                        BMI NF_LONG_146
                        JMP NF_HEADER_FIRST
NF_LONG_146:
 LDA #16
 STA V2_ADDR
 JSR NF_READ16
 LDX #15
NF_HEADER_SECOND:
 LDA V2_BYTES,X
 STA NF_HEADER+16,X
 DEX
                        BMI NF_LONG_155
                        JMP NF_HEADER_SECOND
NF_LONG_155:
 RTS
; Header metadata is authenticated before interpreting length/span/name.
NF_VALIDATE_HEADER:
 LDA NF_HEADER+3
 STA NF_MARKER
 CMP #$3F
                        BNE NF_LONG_162
                        JMP NF_MARKER_OK
NF_LONG_162:
 CMP #$FF
                        BEQ NF_LONG_164
                        JMP NF_INVALID
NF_LONG_164:
NF_MARKER_OK:
 LDA NF_HEADER+2
 CMP #1
                        BEQ NF_LONG_168
                        JMP NF_INVALID
NF_LONG_168:
 LDA NF_HEADER+7
                        BEQ NF_LONG_170
                        JMP NF_INVALID
NF_LONG_170:
 LDX #31
NF_RESERVED:
 LDA NF_HEADER,X
                        BEQ NF_LONG_174
                        JMP NF_INVALID
NF_LONG_174:
 DEX
 CPX #25
                        BEQ NF_LONG_177
                        JMP NF_RESERVED
NF_LONG_177:
 JSR NF_HEADER_CRC
 LDA NS_CRC
 CMP NF_HEADER+24
                        BEQ NF_LONG_181
                        JMP NF_INVALID
NF_LONG_181:
 LDA NS_CRC+1
 CMP NF_HEADER+25
                        BEQ NF_LONG_184
                        JMP NF_INVALID
NF_LONG_184:
 LDA NF_HEADER+4
 STA NF_LEFT
 LDA NF_HEADER+5
 STA NF_LEFT+1
 CMP #>(SOURCE_END-SOURCE_START+8)
                        BCS NF_LONG_190
                        JMP NF_MIN_LENGTH
NF_LONG_190:
                        BEQ NF_LONG_191
                        JMP NF_INVALID
NF_LONG_191:
 LDA NF_LEFT
 CMP #9
                        BCC NF_LONG_194
                        JMP NF_INVALID
NF_LONG_194:
NF_MIN_LENGTH:
 LDA NF_LEFT+1
                        BEQ NF_LONG_197
                        JMP NF_CHECK_SPAN
NF_LONG_197:
 LDA NF_LEFT
 CMP #8
                        BCS NF_LONG_200
                        JMP NF_INVALID
NF_LONG_200:
NF_CHECK_SPAN:
 JSR NF_CALCULATE_SPAN
 CMP NF_HEADER+6
                        BEQ NF_LONG_204
                        JMP NF_INVALID
NF_LONG_204:
 STA NF_SPAN
 ASL A
 ASL A
 ASL A
 ASL A
 CLC
 ADC NF_CURRENT
 CMP #$E1
                        BCC NF_LONG_213
                        JMP NF_INVALID
NF_LONG_213:
 ; Match the command's uppercase, padded name alphabet.
 STZ NF_INDEX
 LDX #0
NF_VALIDATE_NAME:
 LDA NF_HEADER+8,X
                        BNE NF_LONG_219
                        JMP NF_NAME_PAD
NF_LONG_219:
 LDY NF_INDEX
                        BEQ NF_LONG_221
                        JMP NF_INVALID
NF_LONG_221:
 CMP #'_'
                        BNE NF_LONG_223
                        JMP NF_NAME_NEXT
NF_LONG_223:
 CMP #'-'
                        BNE NF_LONG_225
                        JMP NF_NAME_NEXT
NF_LONG_225:
 CMP #'0'
                        BCS NF_LONG_227
                        JMP NF_INVALID
NF_LONG_227:
 CMP #'9'+1
                        BCS NF_LONG_229
                        JMP NF_NAME_NEXT
NF_LONG_229:
 CMP #'A'
                        BCS NF_LONG_231
                        JMP NF_INVALID
NF_LONG_231:
 CMP #'Z'+1
                        BCC NF_LONG_233
                        JMP NF_INVALID
NF_LONG_233:
                        JMP NF_NAME_NEXT
NF_NAME_PAD:
 CPX #0
                        BNE NF_LONG_237
                        JMP NF_INVALID
NF_LONG_237:
 INC NF_INDEX
NF_NAME_NEXT:
 INX
 CPX #16
                        BEQ NF_LONG_242
                        JMP NF_VALIDATE_NAME
NF_LONG_242:
 CLC
 RTS
NF_INVALID:
 SEC
 RTS
NF_CALCULATE_SPAN:
 LDA NF_LEFT+1
 CMP #$0F
                        BCS NF_LONG_251
                        JMP NF_ONE
NF_LONG_251:
                        BEQ NF_LONG_252
                        JMP NF_TWO
NF_LONG_252:
 LDA NF_LEFT
 CMP #$E1
                        BCC NF_LONG_255
                        JMP NF_TWO
NF_LONG_255:
NF_ONE:
 LDA #1
 RTS
NF_TWO:
 LDA #2
 RTS
NF_HEADER_CRC:
 LDA NF_HEADER+3
 PHA
 LDA #$FF
 STA NF_HEADER+3
 STA NS_CRC
 STA NS_CRC+1
 STZ NF_INDEX
NF_HEADER_CRC_LOOP:
 LDY NF_INDEX
 LDA NF_HEADER,Y
 JSR NS_CRC_BYTE
 INC NF_INDEX
 LDA NF_INDEX
 CMP #24
                        BEQ NF_LONG_277
                        JMP NF_HEADER_CRC_LOOP
NF_LONG_277:
 PLA
 STA NF_HEADER+3
 RTS
NF_IS_ERASED:
 STZ V2_ADDR
 LDA NF_CURRENT
 STA V2_ADDR+1
NF_ERASED_BLOCK:
 JSR NF_READ16
 LDX #15
NF_ERASED_BYTE:
 LDA V2_BYTES,X
 CMP #$FF
                        BEQ NF_LONG_291
                        JMP NF_NOT_ERASED
NF_LONG_291:
 DEX
                        BMI NF_LONG_293
                        JMP NF_ERASED_BYTE
NF_LONG_293:
 CLC
 LDA V2_ADDR
 ADC #16
 STA V2_ADDR
                        BEQ NF_LONG_298
                        JMP NF_ERASED_BLOCK
NF_LONG_298:
 INC V2_ADDR+1
 LDA V2_ADDR+1
 AND #15
                        BEQ NF_LONG_302
                        JMP NF_ERASED_BLOCK
NF_LONG_302:
 LDA #0
NF_NOT_ERASED:
 RTS
NF_SAVE:
 LDA NF_FREE
                        BNE NF_LONG_308
                        JMP NF_FULL
NF_LONG_308:
 STA NF_CURRENT
 STA NF_START
 LDA #0
 LDX #31
NF_ZERO_HEADER:
 STA NF_HEADER,X
 DEX
                        BMI NF_LONG_316
                        JMP NF_ZERO_HEADER
NF_LONG_316:
 LDA #'S'
 STA NF_HEADER
 LDA #'F'
 STA NF_HEADER+1
 LDA #1
 STA NF_HEADER+2
 LDA #$FF
 STA NF_HEADER+3
 CLC
 LDA NS_LENGTH
 ADC #8
 STA NF_LEFT
 STA NF_HEADER+4
 LDA NS_LENGTH+1
 ADC #0
 STA NF_LEFT+1
 STA NF_HEADER+5
 LDA NF_NEEDED
 STA NF_HEADER+6
 LDX #15
NF_COPY_NAME:
 LDA NS_REQUEST+8,X
 STA NF_HEADER+8,X
 DEX
                        BMI NF_LONG_341
                        JMP NF_COPY_NAME
NF_LONG_341:
 JSR NF_HEADER_CRC
 LDA NS_CRC
 STA NF_HEADER+24
 LDA NS_CRC+1
 STA NF_HEADER+25
 ; Allocation approval is required even when a sector reads all FF.
 LDX #<NF_CONFIRM_TEXT
 LDY #>NF_CONFIRM_TEXT
 JSR PRINT
 LDA NF_START
 JSR $7E7C
 LDA #0
 JSR $7E7C
 LDX #<NF_SPAN_TEXT
 LDY #>NF_SPAN_TEXT
 JSR PRINT
 LDA NF_NEEDED
 JSR $7E7C
 LDX #<NF_YES_TEXT
 LDY #>NF_YES_TEXT
 JSR PRINT
 JSR READ_LINE
 LDA ERROR
 BNE NF_CANCELLED
 LDY #0
NF_CONFIRM:
 LDA LINE,Y
 CMP NS_YES_WORD,Y
 BNE NF_CANCELLED
 INY
 CPY #4
 BCC NF_CONFIRM
 ; Recheck the selected extent after confirmation, before its first write.
 JSR NF_IS_ERASED
 BNE NF_PROGRAM_ERROR
 LDA NF_NEEDED
 CMP #2
 BNE NF_WRITE_BEGIN
 LDA NF_CURRENT
 PHA
 CLC
 ADC #$10
 STA NF_CURRENT
 JSR NF_IS_ERASED
 TAX
 PLA
 STA NF_CURRENT
 TXA
 BNE NF_PROGRAM_ERROR
NF_WRITE_BEGIN:
 STZ V2_FLASH_PTR
 LDA NF_START
 STA V2_FLASH_PTR+1
 LDA #<NF_HEADER
 STA PTR
 LDA #>NF_HEADER
 STA PTR+1
 LDA #32
 STA NF_LEFT
 STZ NF_LEFT+1
 JSR NF_WRITE_BLOCK
 BCC NF_PROGRAM_ERROR
 STZ PTR
 LDA #2
 STA PTR+1
 LDA NF_HEADER+4
 STA NF_LEFT
 LDA NF_HEADER+5
 STA NF_LEFT+1
 JSR NF_WRITE_BLOCK
 BCC NF_PROGRAM_ERROR
 ; Publish only after every header/payload byte has been read back.
 LDA #3
 STA V2_FLASH_PTR
 LDA NF_START
 STA V2_FLASH_PTR+1
 LDA #$3F
 STA V2_FLASH_DATA
 JSR NF_WRITE_BYTE
 BCC NF_PROGRAM_ERROR
 JMP NF_SUCCESS
NF_CANCELLED:
 LDA #$54
 JMP NF_FAILURE
NF_WRITE_BLOCK:
 LDA NF_LEFT
 ORA NF_LEFT+1
 BEQ NF_WRITE_DONE
 LDA (PTR)
 STA V2_FLASH_DATA
 JSR NF_WRITE_BYTE
 BCC NF_WRITE_FAILED
 INC PTR
 BNE NF_WRITE_ADDRESS
 INC PTR+1
NF_WRITE_ADDRESS:
 INC V2_FLASH_PTR
 BNE NF_WRITE_COUNT
 INC V2_FLASH_PTR+1
NF_WRITE_COUNT:
 LDA NF_LEFT
 BNE NF_WRITE_DEC
 DEC NF_LEFT+1
NF_WRITE_DEC:
 DEC NF_LEFT
 BRA NF_WRITE_BLOCK
NF_WRITE_DONE:
 SEC
 RTS
NF_WRITE_FAILED:
 CLC
 RTS
NF_WRITE_BYTE:
 ; RAM-only SST byte worker; raw entry skips the public BRK function prefix.
 ; Strict B0:8000-DFFF bounds, FF preimage and independent readback.
 LDA V2_FLASH_PTR+1
 CMP #$80
 BCC NF_WRITE_FAILED
 CMP #$E0
 BCS NF_WRITE_FAILED
 LDA #0
 JSR $7848
 LDA (V2_FLASH_PTR)
 CMP #$FF
 BNE NF_WRITE_LOCKED
 LDA V2_FLASH_DATA
 CMP #$FF
 BEQ NF_WRITE_VERIFY
 STZ $F6
 JSR $7B64
 BCC NF_WRITE_LOCKED
NF_WRITE_VERIFY:
 LDA (V2_FLASH_PTR)
 CMP V2_FLASH_DATA
 BNE NF_WRITE_LOCKED
 LDA #3
 JSR $7848
 SEC
 RTS
NF_WRITE_LOCKED:
 LDA #3
 JSR $7848
 CLC
 RTS
NF_CONFIRM_TEXT: DB "Append source B0:",0
NF_SPAN_TEXT: DB " sectors ",0
NF_YES_TEXT: DB "; type YES> ",0
NF_LOAD:
 LDA NF_LEFT
 STA NS_STORED_LENGTH
 LDA NF_LEFT+1
 STA NS_STORED_LENGTH+1
 LDA #32
 STA V2_ADDR
 LDA NF_CURRENT
 STA V2_ADDR+1
 STZ TEMP
 LDA #2
 STA TEMP+1
NF_LOAD_BLOCK:
 LDA #16
 LDX NF_LEFT+1
                        BEQ NF_LONG_422
                        JMP NF_LOAD_COUNT
NF_LONG_422:
 CMP NF_LEFT
                        BCS NF_LONG_424
                        JMP NF_LOAD_COUNT
NF_LONG_424:
 LDA NF_LEFT
NF_LOAD_COUNT:
 STA V2_COUNT
 JSR NF_READ
 LDY #0
NF_LOAD_BYTE:
 LDA V2_BYTES,Y
 STA (TEMP),Y
 INY
 CPY V2_COUNT
                        BEQ NF_LONG_435
                        JMP NF_LOAD_BYTE
NF_LONG_435:
 CLC
 LDA TEMP
 ADC V2_COUNT
 STA TEMP
                        BCS NF_LONG_440
                        JMP NF_LOAD_ADDRESS
NF_LONG_440:
 INC TEMP+1
NF_LOAD_ADDRESS:
 CLC
 LDA V2_ADDR
 ADC V2_COUNT
 STA V2_ADDR
                        BCS NF_LONG_447
                        JMP NF_LOAD_LEFT
NF_LONG_447:
 INC V2_ADDR+1
NF_LOAD_LEFT:
 SEC
 LDA NF_LEFT
 SBC V2_COUNT
 STA NF_LEFT
 LDA NF_LEFT+1
 SBC #0
 STA NF_LEFT+1
 ORA NF_LEFT
                        BEQ NF_LONG_458
                        JMP NF_LOAD_BLOCK
NF_LONG_458:
 JMP NF_SUCCESS
NF_READ16:
 LDA #16
 STA V2_COUNT
NF_READ:
 STZ V2_SELECTED
 JSR $7830
 RTS
NF_END:
 ENDMOD
 END
