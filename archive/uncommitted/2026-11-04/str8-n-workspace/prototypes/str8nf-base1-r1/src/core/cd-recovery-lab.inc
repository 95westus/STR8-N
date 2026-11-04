; JCR1, 2512 source-bound C/D interruption qualification and inspected repair.
; This lab tool is not a general repair command. F stays golden and read-only.
; Immutable image 0200-4FFF; fixed rendered metadata/frames 4000-43FF.
; All mutable lab state is borrowed owner RAM 6100-611F; JE_FRAME is 6700.
JR_META EQU $4000
JR_FRAME EQU $4100
JR_PREIMAGE EQU $4200
JR_SOURCE EQU $4300
JR_SELF_HASH EQU $4FFC
JR_HASH EQU $6100
JR_TERM EQU $6104
JR_STOP_LO EQU $6108
JR_STOP_HI EQU $6109
JR_BANK EQU $610A
JR_COUNT EQU $610B
JR_PAGE EQU $610C
JR_MATCH EQU $610D
JR_SEQ EQU $6110
JR_EXPECT EQU $E8

JR_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        STZ DC_BINARY
        STZ V2_NMI_HOLD
        JSR JR_SELF
        BCC JR_REFUSE
        ; Never call ROM through an unexpected F mapping.
        STZ V2_PTR
        LDA #$F0
        STA V2_PTR+1
        STZ JR_STOP_LO
        STZ JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<JR_F_HASH
        STA JR_EXPECT
        LDA #>JR_F_HASH
        STA JR_EXPECT+1
        JSR JR_COMPARE
        BCC JR_SILENT_HALT
        JSR JR_HEADER
        BCC JR_REFUSE
        JSR JR_GUARD_ALL
        BCC JR_REFUSE
        JSR JR_IDENTIFY
        BCC JR_REFUSE
        JSR JE_READ
        BCC JR_REFUSE
        LDA J_BEST+1
        CMP JR_META+12
        BNE JR_REFUSE
        LDX #0
JR_CHECK_SOURCE:
        LDA JE_FRAME,X
        CMP JR_SOURCE,X
        BNE JR_REFUSE
        INX
        BNE JR_CHECK_SOURCE
        JSR JR_ADMIT
        BCC JR_REFUSE
        LDX #<JR_READY
        LDY #>JR_READY
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC JR_REFUSE
        LDA V2_LINE
        CMP #'Y'
        BNE JR_REFUSE
        LDA V2_LINE+1
        BNE JR_REFUSE
        JSR JR_SELF
        BCC JR_FATAL
        JSR JR_GUARD_ALL
        BCC JR_FATAL
        LDA JR_META+5
        CMP #5
        BEQ JR_ACK
        CMP #4
        BEQ JR_ROTATE
        CMP #6
        BEQ JR_FILL
        LDA JR_META+7
        STA JE_DEST
        JSR JE_WRITE
        BCC JR_FATAL
        JMP JR_COMPLETE
JR_ROTATE:
        ; Native JE_SPACE must commit the intent, erase and verify its peer.
        ; The instrumented post-erase hook halts before a new peer record.
        JSR JE_SPACE
        JMP JR_FATAL
JR_FILL:
        LDA JR_META+8
        STA JR_COUNT
        LDA JR_META+7
        STA JR_PAGE
JR_FILL_NEXT:
        JSR JE_SPACE
        BCC JR_FATAL
        LDA JE_DEST
        CMP JR_PAGE
        BNE JR_FATAL
        JSR JE_SEAL
        BCC JR_FATAL
        JSR JE_WRITE
        BCC JR_FATAL
        LDA JE_DEST
        STA J_BEST+1
        INC JR_PAGE
        DEC JR_COUNT
        BNE JR_FILL_NEXT
JR_COMPLETE:
        JSR JR_POST
        BCC JR_FATAL
        LDX #<JR_OK
        LDY #>JR_OK
        JMP JR_RETURN
JR_ACK:
        JSR JR_POST
        BCC JR_FATAL
        LDX #<JR_ACK_TEXT
        LDY #>JR_ACK_TEXT
JR_RETURN:
        LDA #1
        STA V2_LED
        JSR BOOT_PRINT
        JMP BOOT_RECOVERY
JR_REFUSE:
        LDX #<JR_REFUSED
        LDY #>JR_REFUSED
        JMP JR_RETURN
JR_FATAL:
        LDX #<JR_FAILED
        LDY #>JR_FAILED
        JSR BOOT_PRINT
JR_SILENT_HALT:
        JMP JR_SILENT_HALT

JR_HEADER:
        LDX #3
JR_MAGIC_LOOP:
        LDA JR_META,X
        CMP JR_MAGIC,X
        BNE JR_BAD
        DEX
        BPL JR_MAGIC_LOOP
        LDA JR_META+4
        CMP #1
        BNE JR_BAD
        LDA JR_META+5
        BEQ JR_BAD
        CMP #8
        BCS JR_BAD
        CMP #4
        BEQ JR_HEADER_ROTATE
        CMP #1
        BEQ JR_HEADER_APPEND
        LDA JR_META+6
        BNE JR_BAD
        BRA JR_HEADER_COUNT
JR_HEADER_ROTATE:
        LDA JR_META+6
        CMP #4
        BNE JR_BAD
        BRA JR_HEADER_COUNT
JR_HEADER_APPEND:
        LDA JR_META+6
        CMP #4
        BCS JR_BAD
JR_HEADER_COUNT:
        LDA JR_META+5
        CMP #6
        BEQ JR_HEADER_FILL
        LDA JR_META+8
        BNE JR_BAD
        BRA JR_HEADER_PAGE
JR_HEADER_FILL:
        LDA JR_META+8
        BEQ JR_BAD
        CMP #13
        BCS JR_BAD
JR_HEADER_PAGE:
        LDA JR_META+7
        CMP #$C0
        BCC JR_BAD
        CMP #$E0
        BCS JR_BAD
        SEC
        RTS
JR_BAD:
        CLC
        RTS

JR_ADMIT:
        LDA JR_META+5
        CMP #4
        BEQ JR_ADMIT_ROTATE
        CMP #6
        BEQ JR_ADMIT_FILL
        STZ V2_PTR
        LDA JR_META+7
        STA V2_PTR+1
        LDY #0
JR_PREIMAGE_LOOP:
        LDA (V2_PTR),Y
        CMP JR_PREIMAGE,Y
        BNE JR_BAD
        INY
        BNE JR_PREIMAGE_LOOP
        JSR JR_FRAME_VALID
        BCC JR_BAD
        LDA JR_META+5
        CMP #3
        BEQ JR_HISTORY
        CMP #5
        BEQ JR_ADMIT_ACK
        JSR JR_NEXT_PAGE
        BCC JR_BAD
        JSR JR_RELATION
        BCC JR_BAD
        LDA JR_META+5
        CMP #2
        BEQ JR_ADMIT_RESUME
        LDA JR_META+7
        JSR JE_PAGE_BLANK
        BCC JR_BAD
        BRA JR_ADMIT_WRITE
JR_ADMIT_RESUME:
        ; Only exact desired bytes or erased bytes may be completed in place.
        LDX #0
JR_RESUME_LOOP:
        LDA JR_PREIMAGE,X
        CMP #$FF
        BEQ JR_RESUME_NEXT
        CMP JR_FRAME,X
        BNE JR_BAD
JR_RESUME_NEXT:
        INX
        BNE JR_RESUME_LOOP
        LDA JR_PREIMAGE+$FF
        CMP #$FF
        BNE JR_BAD
JR_ADMIT_WRITE:
        LDA #$FF
        STA JE_FRAME+$FF
        SEC
        RTS
JR_ADMIT_ACK:
        LDA JR_META+7
        CMP J_BEST+1
        BNE JR_BAD
        LDX #0
JR_ACK_LOOP:
        LDA JR_FRAME,X
        CMP JR_SOURCE,X
        BNE JR_BAD
        INX
        BNE JR_ACK_LOOP
        SEC
        RTS
JR_HISTORY:
        ; Restore only one of the original three source-bound snapshots.
        LDA JR_META+7
        LDX #0
        CMP #$C0
        BEQ JR_HISTORY_HASH
        LDX #4
        CMP #$C1
        BEQ JR_HISTORY_HASH
        LDX #8
        CMP #$D0
        BNE JR_BAD
JR_HISTORY_HASH:
        STX JR_MATCH
        STZ V2_PTR
        LDA #$41
        STA V2_PTR+1
        STZ JR_STOP_LO
        LDA #$42
        STA JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<JR_ORIGINAL_HASHES
        CLC
        ADC JR_MATCH
        STA JR_EXPECT
        LDA #>JR_ORIGINAL_HASHES
        ADC #0
        STA JR_EXPECT+1
        JSR JR_COMPARE
        BCC JR_BAD
        LDA JR_META+7
        JSR JE_PAGE_BLANK
        BCC JR_BAD
        JMP JR_ADMIT_WRITE
JR_ADMIT_FILL:
        JSR JR_NEXT_PAGE
        BCC JR_BAD
        LDA JR_META+7
        STA JR_PAGE
        LDA JR_META+8
        STA JR_COUNT
JR_FILL_BLANK:
        LDA JR_PAGE
        AND #$0F
        CMP #$0F
        BCS JR_BAD
        LDA JR_PAGE
        JSR JE_PAGE_BLANK
        BCC JR_BAD
        INC JR_PAGE
        DEC JR_COUNT
        BNE JR_FILL_BLANK
        SEC
        RTS
JR_ADMIT_ROTATE:
        LDA J_BEST+1
        AND #$0F
        CMP #$0E
        BNE JR_BAD
        LDA J_BEST+1
        AND #$F0
        EOR #$10
        CMP JR_META+7
        BNE JR_BAD
        JSR JE_SECTOR_BLANK
        BCS JR_BAD
        LDA J_BEST+1
        INC A
        JSR JE_PAGE_BLANK
        BCC JR_BAD
        SEC
        RTS
JR_NEXT_PAGE:
        LDA JR_META+5
        CMP #7
        BEQ JR_PEER_RECORD
        LDA J_BEST+1
        INC A
        CMP JR_META+7
        BNE JR_BAD
        AND #$0F
        BEQ JR_BAD
        CMP #$0F
        BCS JR_BAD
        SEC
        RTS
JR_PEER_RECORD:
        ; After peer erase, preserve original old rows before publishing the
        ; next newest snapshot. Their hashes are fixed at the initial escrow.
        LDA JR_FRAME+7
        CMP #'S'
        BNE JR_BAD
        LDA J_BEST+1
        CMP #$CF
        BEQ JR_PEER_D
        CMP #$DF
        BNE JR_BAD
        LDA JR_META+7
        CMP #$C2
        BNE JR_BAD
        LDA #$C0
        JSR JR_OLD_REGION
        BCC JR_BAD
        LDA #$C1
        JMP JR_OLD_REGION
JR_PEER_D:
        LDA JR_META+7
        CMP #$D1
        BNE JR_BAD
        LDA #$D0
JR_OLD_REGION:
        STA JR_PAGE
        LDX #0
        CMP #$C0
        BEQ JR_OLD_HASH
        LDX #4
        CMP #$C1
        BEQ JR_OLD_HASH
        LDX #8
        CMP #$D0
        BNE JR_BAD
JR_OLD_HASH:
        STX JR_MATCH
        STZ V2_PTR
        STZ JR_STOP_LO
        LDA JR_PAGE
        STA V2_PTR+1
        INC A
        STA JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<JR_ORIGINAL_HASHES
        CLC
        ADC JR_MATCH
        STA JR_EXPECT
        LDA #>JR_ORIGINAL_HASHES
        ADC #0
        STA JR_EXPECT+1
        JMP JR_COMPARE

JR_FRAME_VALID:
        LDX #0
JR_FRAME_COPY:
        LDA JR_FRAME,X
        STA JE_FRAME,X
        INX
        BNE JR_FRAME_COPY
        LDX #5
JR_FRAME_MAGIC:
        LDA JR_FRAME,X
        CMP JR_RECORD_MAGIC,X
        BNE JR_BAD
        DEX
        BPL JR_FRAME_MAGIC
        LDA JR_FRAME+$FE
        CMP #$FF
        BNE JR_BAD
        LDA JR_FRAME+$FF
        BNE JR_BAD
        JSR BOOT_CHECK_FIELDS
        BCC JR_BAD
        JSR J_CRC_INIT
        LDY #0
JR_FRAME_HEADER_CRC:
        LDA JR_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #30
        BNE JR_FRAME_HEADER_CRC
        LDA J_CRC
        CMP JR_FRAME+30
        BNE JR_BAD
        LDA J_CRC+1
        CMP JR_FRAME+31
        BNE JR_BAD
        JSR J_CRC_INIT
        LDY #0
JR_FRAME_BODY_CRC:
        LDA JR_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #$FC
        BNE JR_FRAME_BODY_CRC
        LDA J_CRC
        CMP JR_FRAME+$FC
        BNE JR_BAD
        LDA J_CRC+1
        CMP JR_FRAME+$FD
        BNE JR_BAD
        SEC
        RTS
JR_RELATION:
        LDX #3
JR_SEQ_COPY:
        LDA JR_SOURCE+8,X
        STA JR_SEQ,X
        DEX
        BPL JR_SEQ_COPY
        LDX #0
JR_SEQ_INC:
        INC JR_SEQ,X
        BNE JR_SEQ_READY
        INX
        CPX #4
        BNE JR_SEQ_INC
        JMP JR_BAD
JR_SEQ_READY:
        LDX #3
JR_SEQ_COMPARE:
        LDA JR_SEQ,X
        CMP JR_FRAME+8,X
        BNE JR_BAD
        DEX
        BPL JR_SEQ_COMPARE
        LDX #12
JR_POLICY_HEADER:
        LDA JR_SOURCE,X
        CMP JR_FRAME,X
        BNE JR_BAD
        INX
        CPX #30
        BNE JR_POLICY_HEADER
        LDX #32
JR_BODY_COMPARE:
        LDA JR_SOURCE,X
        CMP JR_FRAME,X
        BNE JR_BAD
        INX
        CPX #$FC
        BNE JR_BODY_COMPARE
        LDA JR_FRAME+7
        CMP #'S'
        BEQ JR_RELATION_OK
        CMP #'B'
        BNE JR_BAD
        ; B is only escrow restoration; never execute the old MON.
        STZ V2_PTR
        LDA #$C1
        STA V2_PTR+1
        STZ JR_STOP_LO
        LDA #$C2
        STA JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<(JR_ORIGINAL_HASHES+4)
        STA JR_EXPECT
        LDA #>(JR_ORIGINAL_HASHES+4)
        STA JR_EXPECT+1
        JSR JR_COMPARE
        BCC JR_BAD
JR_RELATION_OK:
        SEC
        RTS

; Hooks are inserted only into this lab build's private writer copy.
JR_AFTER_BYTE:
        LDA JR_META+6
        CMP #1
        BNE JR_HOOK_RETURN
        LDA J_INDEX
        CMP #$80
        BEQ JR_CUT
JR_HOOK_RETURN:
        RTS
JR_BEFORE_COMMIT:
        LDA JR_META+6
        CMP #2
        BEQ JR_CUT
        RTS
JR_AFTER_COMMIT:
        LDA JR_META+6
        CMP #3
        BEQ JR_CUT
        RTS
JR_PEER_ERASED:
        LDA JR_META+5
        CMP #4
        BNE JR_HOOK_RETURN
        LDA JR_META+6
        CMP #4
        BNE JR_HOOK_RETURN
JR_CUT:
        JSR JR_POST
        BCC JR_FATAL
        LDA #1
        STA V2_LED
        LDX #<JR_CUT_READY
        LDY #>JR_CUT_READY
        JSR BOOT_PRINT
        JMP JR_SILENT_HALT

JR_SELF:
        STZ V2_PTR
        LDA #2
        STA V2_PTR+1
        LDA #$FC
        STA JR_STOP_LO
        LDA #$4F
        STA JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<JR_SELF_HASH
        STA JR_EXPECT
        LDA #>JR_SELF_HASH
        STA JR_EXPECT+1
        JMP JR_COMPARE
JR_POST:
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STZ JR_STOP_LO
        STZ JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA #<(JR_META+32)
        STA JR_EXPECT
        LDA #>(JR_META+32)
        STA JR_EXPECT+1
        JMP JR_COMPARE
JR_GUARD_ALL:
        STZ JR_BANK
JR_GUARD_BANK:
        LDA JR_BANK
        JSR V2W_SELECT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STZ JR_STOP_LO
        STZ JR_STOP_HI
        JSR JR_HASH_RANGE
        LDA JR_BANK
        ASL A
        ASL A
        CLC
        ADC #<(JR_META+16)
        STA JR_EXPECT
        LDA #>(JR_META+16)
        STA JR_EXPECT+1
        JSR JR_COMPARE
        BCC JR_GUARD_FAILED
        INC JR_BANK
        LDA JR_BANK
        CMP #4
        BNE JR_GUARD_BANK
        LDA #3
        JSR V2W_SELECT
        SEC
        RTS
JR_GUARD_FAILED:
        LDA #3
        JSR V2W_SELECT
        CLC
        RTS
JR_COMPARE:
        LDY #0
JR_COMPARE_BYTE:
        LDA (JR_EXPECT),Y
        CMP JR_HASH,Y
        BNE JR_BAD
        INY
        CPY #4
        BNE JR_COMPARE_BYTE
        SEC
        RTS
JR_IDENTIFY:
        ; Entire command/ID/read-array sequence executes in RAM.
        LDA #$AA
        STA $D555
        LDA #$55
        STA $AAAA
        LDA #$90
        STA $D555
        LDA $8000
        STA $6118
        LDA $8001
        STA $6119
        LDA #$F0
        STA $8000
        LDA $6118
        CMP #$BF
        BNE JR_BAD
        LDA $6119
        CMP #$B5
        BNE JR_BAD
        SEC
        RTS

JR_MAGIC: DB "JCR1"
JR_RECORD_MAGIC: DB "SNBT",1,32
JR_READY: DB "JCR1 self/source/F/record guards verified; Y then Enter> ",0
JR_OK: DB "OK: JCR1 journal operation verified",13,10,0
JR_ACK_TEXT: DB "OK: already committed; no write",13,10,0
JR_REFUSED: DB "REFUSED: JCR1 source/frame/operation",13,10,0
JR_FAILED: DB "FAILED: JCR1; keep power and inspect",13,10,0
JR_CUT_READY: DB "POWER CUT READY: JCR1 exact checkpoint verified; CHIP IDLE; F GOLDEN",13,10,0
        INCLUDE "jr-pins.inc"
        INCLUDE "jr-fnv.inc"
