; STR8-N V1.1 BANK MAINTENANCE, LOAD ADDRESS $2000.
; INTERACTIVE BANK COPY/ERASE/MAP MAINTENANCE FOR STR8-N L.
;
; LOAD AND RUN:
;   STR8-N>L
;   S19
;   send BUILD/v1.1/s19/str8n-v1.1-bank-maint-2000.s19
; STR8-N L executes its S9 $2000 entry automatically. Q returns to STR8-N.
;
; C COPIES $8000-$FFFF FROM SOURCE BANK 0-3 TO AN EMPTY DESTINATION 0-2,
; THEN ENROLLS THAT DESTINATION IN THE BANK-3 DIRECTORY. COMPLETE IS LAST.
; P PUTS ONE VALIDATED AP ENVELOPE FROM $4000 INTO BANK 0 $BF00.
;   THE AP MUST BE 5-$FF BYTES AND THE COMPLETE DESTINATION MUST BE ERASED.
; E ERASES ONE 4K SECTOR OR THE ALLOWED BANK RANGE:
;   BANKS 0-2: 8-F, ALL, OR AN X-Y RANGE WITHIN 8-F.
;   BANK 3:     8-E, ALL, OR AN X-Y RANGE WITHIN 8-E.
; A IS SECTOR A. ALL IS THE COMPLETE VALID RANGE. B3 SECTOR F IS PROTECTED.
; M READS ALL BANK/SECTOR CONTENTS: E=ERASED, U=USED, A=VALID AP,
;   P=PROTECTED B3F. A REQUIRES A COMPLETE ENVELOPE AND MATCHING BODY FNV.
;   ONE AP DETAIL LINE IS PRINTED FOR EACH SECTOR MARKED A.
; M ALSO PRINTS BANK-3 DIRECTORY TYPE, DESCRIPTION, ENTRY, AND JOURNAL.
; M RESTORES ITS ENTRY BANK AFTER EACH CARRIED-WORKER STAGE CALL.
; C/E/M/P, ABORT, AND SAFE FAILURES RETURN TO THIS MENU. Q RETURNS TO STR8-N.
; BANK-3 ERASE REMAINS THE EXCEPTION AND RETURNS DIRECTLY TO STR8.
;
; THIS SOURCE CARRIES THE EXACT V1 MUTATION WORKER AT $3000-$322A AND COPIES
; IT TO $0200-$042A. IT DOES NOT REQUEST MODES $05/$06 THROUGH V1 $F003.
; THE WORKER SKIPS A PHYSICAL ERASE WHEN A STAGED $FF SECTOR IS ALREADY
; ERASED. EVERY PROGRAMMED SECTOR IS VERIFIED.
; BANK 3 ERASE PRINTS ITS LAST MESSAGE BEFORE THE FIRST ERASE, MAKES NO
; LATER HIMON CALLS, AND JUMPS DIRECTLY TO STR8 $F000 ON SUCCESS OR FAILURE.
; AT THE STR8 COUNTDOWN, SELECT S; HIMON MAY HAVE BEEN ERASED.
;
; COPY IS NOT ATOMIC. POWER LOSS CAN LEAVE A PARTIAL, NON-BOOTABLE DESTINATION.
; C REFUSES A DESTINATION WHOSE BANK-3 DIRECTORY ROW IS NOT COMPLETELY ERASED.
; A SOURCE WITH THE STR8 SERVICE SIGNATURE PRINTS !STR8 BEFORE CONFIRMATION.
; ERASE REQUIRES EXACT `ERASE BS`, `ERASE BX-Y`, OR `ERASE BALL`.
; B IS THE BANK. COPY REQUIRES EXACT `COPY XY`.
; AP PUT REQUIRES EXACT `PUT B0BF00`.
;
; RAM MAP:
;   $0200-$09FF  STR8 RAM WORKER TRAY
;   $0A00-$19FF  ONE 4K STAGED SECTOR
;   $1B00-$1B0B  RESULT/STATE
;   $1B0C        ENTRY-BANK PCR BITS FOR MAP RETURN
;   $1B0D-$1B0E  DIRECTORY PRINT INDEXES
;   $1B0F-$1B17  AP MAP COUNT/PARSER STATE
;   $1B18-$1B1D  COPY ENROLLMENT TYPE AND FIVE-CHARACTER DESCRIPTION
;   $1C00-$1CFE  INPUT BUFFER
;   $1D00-$1D3F  STAGED BANK-3 DIRECTORY
;   $1D40-$1DDA  FIRST VALID AP PER MAPPED SECTOR, 31 X 5 BYTES
;   $2000-...    THIS PROGRAM
;   $3000-$322A  EMBEDDED V1 MUTATION WORKER
; The program owns direct FT245R console input/output and does not require
; HIMON vectors or an initialized HIMON session.
;
; RESULT:
;   $1B00 STATUS: $AC OK, $E0 ABORT, $E1 STAGE FAIL,
;                 $E2 PROGRAM/VERIFY FAIL, $E6 BAD RESET VECTOR,
;                 $E7 DIRECTORY ENROLLMENT FAIL
;   $1B01 OPERATION: C, E, M, P, OR Q
;   $1B02 SOURCE/ERASE BANK
;   $1B03 DESTINATION BANK
;   $1B04 CURRENT/FAILING SECTOR HIGH BYTE
;   $1B05 COMPLETED/REMAINING SECTOR COUNT OR AP LENGTH
;   $1B06/$1B07 STR8 FAIL ADDRESS, LO/HI
;   $1B08-$1B0A ERASE SELECTION; $1B0B LENGTH, ONE OR THREE

        ORG $2000

BM_FTDI_CTRL EQU $7FE0
BM_FTDI_DATA EQU $7FE1
BM_FTDI_DDRA EQU $7FE3
BM_FTDI_TXE EQU $01
BM_FTDI_RXF EQU $02
BM_FTDI_WR EQU $04
BM_FTDI_RD EQU $08

BM_MAIN LDX #$00
?WCOPY LDA $3000,X
        STA $0200,X
        LDA $3100,X
        STA $0300,X
        INX
        BNE ?WCOPY
        LDX #$2A
?WTAIL LDA $3200,X
        STA $0400,X
        DEX
        BPL ?WTAIL
        STZ $1B00
        STZ $1B01
        STZ $1B02
        STZ $1B03
        STZ $1B04
        STZ $1B05
        STZ $1B06
        STZ $1B07
        STZ $1B08
        STZ $1B09
        STZ $1B0A
        STZ $1B0B
        STZ $1B0F
        LDA $7FEC
        AND #$EE
        STA $1B0C
        LDX #<BM_MTITLE
        LDY #>BM_MTITLE
        JSR BM_PUTS
        JSR BM_READ
        BCC BM_ABORT
        LDA $1C01
        BNE BM_MAIN
        LDA $1C00
        BEQ BM_ABORT
        CMP #'C'
        BEQ ?COPY
        CMP #'E'
        BEQ ?ERASE
        CMP #'M'
        BEQ ?MAP
        CMP #'P'
        BEQ ?PUT
        CMP #'Q'
        BNE BM_MAIN
        STA $1B01
        LDA #$AC
        STA $1B00
        JMP $F000
?MAP   JMP BM_MAP
?PUT   JMP BM_PUT
?ERASE JMP BM_ERASE
?COPY  JMP BM_COPY

BM_ABORT LDA #$E0
        STA $1B00
        LDA #'A'
        JSR BM_OUT
        LDA #'B'
        JSR BM_OUT
        LDA #'O'
        JSR BM_OUT
        LDA #'R'
        JSR BM_OUT
        LDA #'T'
        JSR BM_OUT
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        JMP BM_MAIN

; Read one uppercase, zero-terminated line into $1C00-$1CFE. CR completes,
; LF is ignored, Ctrl-C aborts, and Backspace/Delete edit the current line.
BM_READ LDY #$00
?READ   JSR BM_IN
        CMP #$03
        BEQ ?ABORT
        CMP #$0D
        BEQ ?DONE
        CMP #$0A
        BEQ ?READ
        CMP #$08
        BEQ ?BACK
        CMP #$7F
        BEQ ?BACK
        CMP #'a'
        BCC ?STORE
        CMP #'z'+1
        BCS ?STORE
        AND #$DF
?STORE  CPY #$FE
        BCS ?READ
        STA $1C00,Y
        JSR BM_OUT
        INY
        BRA ?READ
?BACK   CPY #$00
        BEQ ?READ
        DEY
        LDA #$08
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        LDA #$08
        JSR BM_OUT
        BRA ?READ
?DONE   LDA #$00
        STA $1C00,Y
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        SEC
        RTS
?ABORT  STZ $1C00
        CLC
        RTS

BM_PUTS STX $CA
        STY $CB
        LDY #$00
?BYTE   LDA ($CA),Y
        BEQ ?DONE
        JSR BM_OUT
        INY
        BNE ?BYTE
        INC $CB
        BRA ?BYTE
?DONE   RTS

; Direct FT245R console I/O. BM_OUT preserves A; both preserve Y.
BM_OUT  PHA
        STZ BM_FTDI_DDRA
        STA BM_FTDI_DATA
?READY  LDA #BM_FTDI_TXE
        BIT BM_FTDI_CTRL
        BNE ?READY
        LDA #BM_FTDI_WR
        TSB BM_FTDI_CTRL
        DEC BM_FTDI_DDRA
        NOP
        NOP
        TRB BM_FTDI_CTRL
        STZ BM_FTDI_DDRA
        PLA
        RTS

BM_IN   STZ BM_FTDI_DDRA
?READY  LDA #BM_FTDI_RXF
        BIT BM_FTDI_CTRL
        BNE ?READY
        LDA #BM_FTDI_RD
        TRB BM_FTDI_CTRL
        NOP
        NOP
        LDA BM_FTDI_DATA
        PHA
        LDA #BM_FTDI_RD
        TSB BM_FTDI_CTRL
        PLA
        RTS

; Self-contained hexadecimal output and 32-bit FNV-1a. The AP map formerly
; reached these through HIMON's RAM service table; STR8-N L must not require
; HIMON or initialized IVI/service vectors.
BM_HEX  PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR BM_NIBBLE
        PLA
        AND #$0F
BM_NIBBLE CMP #$0A
        BCC ?DIGIT
        ADC #$06
?DIGIT  ADC #'0'
        JMP BM_OUT

BM_FNV_INIT LDX #$03
?BYTE   LDA BM_FNV_BASIS,X
        STA $B0,X
        DEX
        BPL ?BYTE
        RTS
BM_FNV_BASIS DB $C5,$9D,$1C,$81

BM_FNV_UPDATE EOR $B0
        STA $B0
        LDX #$03
?COPY   LDA $B0,X
        STA $C7,X
        DEX
        BPL ?COPY
        LDX #$01
        JSR BM_FNV_SHIFT_ADD
        LDX #$03
        JSR BM_FNV_SHIFT_ADD
        LDX #$03
        JSR BM_FNV_SHIFT_ADD
        LDX #$01
        JSR BM_FNV_SHIFT_ADD
        LDA $B3
        CLC
        ADC $C8
        STA $B3
        RTS
BM_FNV_SHIFT_ADD JSR BM_FNV_SHIFT
        CLC
        LDA $B0
        ADC $C7
        STA $B0
        LDA $B1
        ADC $C8
        STA $B1
        LDA $B2
        ADC $C9
        STA $B2
        LDA $B3
        ADC $CA
        STA $B3
        RTS
BM_FNV_SHIFT ASL $C7
        ROL $C8
        ROL $C9
        ROL $CA
        DEX
        BNE BM_FNV_SHIFT
        RTS

BM_MDIR DB $0D,$0A,'D','I','R',' ','B',' ','T',' '
        DB 'D','E','S','C',' ','E','N','T','R','Y',' '
        DB 'J','O','U','R','N','A','L'
        DB $0D,$0A,0
BM_MMAP DB $0D,$0A,'B','A','N','K',' ','8',' ','9',' ','A'
        DB ' ','B',' ','C',' ','D',' ','E',' ','F',$0D,$0A
        DB $0D,$0A,0
BM_MLEGEND DB 'E','=','E','R','A','S','E','D',' '
        DB 'U','=','U','S','E','D',' ','A','=','A','P',' '
        DB 'V','A','L','I','D',' ','P','=','B','3','F',' '
        DB 'P','R','O','T'
        DB 'E','C','T','E','D'
        DB $0D,$0A,0
BM_MSRC DB 'S','O','U','R','C','E',' ','B','A','N','K',' '
        DB '0','-','3','>',' ',0
BM_MDST DB 'D','E','S','T',' ','B','A','N','K',' ','0','-','2'
        DB '>',' ',0
BM_MBANK DB 'B','A','N','K',' ','0','-','3','>',' ',0
BM_MSEC02 DB 'S','E','C','T','O','R',' ','8','-','F',','
        DB ' ','A','L','L',',',' ','O','R',' ','X','-','Y',';'
        DB ' ','B','3',' ','M','A','X',' ','E','>',' ',0
BM_MCTYPE DB 'T','Y','P','E',' ','C','O','P','Y',' ',0
BM_METYPE DB 'T','Y','P','E',' ','E','R','A','S','E',' ',0

BM_PARSE_BANK LDA $1C01
        BNE ?BAD
        LDA $1C00
        CMP #'0'
        BCC ?BAD
        CMP #'4'
        BCS ?BAD
        SEC
        SBC #'0'
        SEC
        RTS
?BAD   CLC
        RTS

BM_STAGE LDA $1B02
        STA $1FEE
        LDA $1B04
        STA $1FE9
        LDA #$0A
        STA $1FF6
        LDA #$06
        STA $1FF0
        JMP $0200

BM_PROGRAM LDA $1B03
        STA $1FEF
        LDA $1B04
        STA $1FE9
        LDA #$0A
        STA $1FF6
        LDA #$05
        STA $1FF0
        JMP $0200

BM_FILL LDA #$0A
        STA $CB
        STZ $CA
        LDX #$10
        LDA #$FF
?FPAGE LDY #$00
?FBYTE STA ($CA),Y
        INY
        BNE ?FBYTE
        INC $CB
        DEX
        BNE ?FPAGE
        RTS

; Snapshot the Bank-3 directory, restore the entry bank, then print:
; Dn TYPE DESCRIPTION ENTRY JOURNAL. Nonprintable description bytes are '.'.
BM_DIR  BRA ?BODY
?DIGIT  CLC
        ADC #'0'
        JMP BM_OUT
?NIB    CMP #$0A
        BCC ?DIGIT
        CLC
        ADC #$37
        JMP BM_OUT
?DOTCHAR LDA #'.'
        RTS
?SAFECHAR CMP #$20
        BCC ?DOTCHAR
        CMP #$7F
        BCS ?DOTCHAR
        RTS
?HEX    PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR ?NIB
        PLA
        AND #$0F
        JMP ?NIB
?BODY   PHP
        SEI
        LDA #$EE
        TRB $7FEC
        LDA #$EE
        TSB $7FEC
        LDX #$3F
?COPY   LDA $FFB0,X
        STA $1D00,X
        DEX
        BPL ?COPY
        LDA #$EE
        TRB $7FEC
        LDA $1B0C
        TSB $7FEC
        PLP
        LDX #<BM_MDIR
        LDY #>BM_MDIR
        JSR BM_PUTS
        STZ $1B0D
?ROW    LDA #'D'
        JSR BM_OUT
        LDA $1B0D
        LSR A
        LSR A
        LSR A
        LSR A
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        LDX $1B0D
        LDA $1D00,X
        JSR ?HEX
        LDA #' '
        JSR BM_OUT
        LDA $1B0D
        CLC
        ADC #$04
        STA $1B0E
?DESC   LDX $1B0E
        LDA $1D00,X
        JSR ?SAFECHAR
        JSR BM_OUT
        INC $1B0E
        LDA $1B0E
        SEC
        SBC $1B0D
        CMP #$09
        BNE ?DESC
        LDA #' '
        JSR BM_OUT
        LDX $1B0D
        LDA $1D0B,X
        JSR ?HEX
        LDX $1B0D
        LDA $1D0A,X
        JSR ?HEX
        LDA #' '
        JSR BM_OUT
        LDA $1B0D
        CLC
        ADC #$0C
        STA $1B0E
?JOURNAL LDX $1B0E
        LDA $1D00,X
        JSR ?HEX
        INC $1B0E
        LDA $1B0E
        SEC
        SBC $1B0D
        CMP #$10
        BNE ?JOURNAL
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        LDA $1B0D
        CLC
        ADC #$10
        STA $1B0D
        CMP #$40
        BEQ ?PRINTDONE
        JMP ?ROW
?PRINTDONE RTS

; AP map parser scratch:
;   $CC/$CD candidate base, $CE/$CF parse/body pointer
;   $D0/$D1 remaining, $D2 section length, $D3-$D8 temporaries
;   $1B10/$1B11 package length, $1B12/$1B13 body length
;   $1B14-$1B17 expected body FNV, $B0-$B3 computed body FNV
; Require A bytes in the current 16-bit remainder.
BM_APNEED STA $D8
        LDA $D1
        BNE ?OK
        LDA $D0
        CMP $D8
        BCS ?OK
        CLC
        RTS
?OK    SEC
        RTS

; Advance the parser by A bytes.
BM_APADV STA $D8
        JSR BM_APNEED
        BCC ?BAD
        LDA $CE
        CLC
        ADC $D8
        STA $CE
        LDA $CF
        ADC #$00
        STA $CF
        LDA $D0
        SEC
        SBC $D8
        STA $D0
        LDA $D1
        SBC #$00
        STA $D1
        SEC
        RTS
?BAD   CLC
        RTS

; Match tag A plus its one-byte payload length, then skip the tag header.
BM_APTAG STA $D7
        LDA #$02
        JSR BM_APNEED
        BCC ?BAD
        LDY #$00
        LDA ($CE),Y
        CMP $D7
        BNE ?BAD
        INY
        LDA ($CE),Y
        STA $D2
        LDA #$02
        JMP BM_APADV
?BAD   CLC
        RTS

; Validate the AP header and initialize pointer/remainder state.
BM_APHEAD BRA ?BODY
?BAD    CLC
        RTS
?BODY   LDA $CD
        CMP #$0A
        BCC ?BAD
        CMP #$1A
        BCS ?BAD
        LDA #$00
        SEC
        SBC $CC
        STA $D0
        LDA #$1A
        SBC $CD
        STA $D1
        LDA #$05
        JSR BM_APNEED
        BCC ?BAD
        LDY #$00
        LDA ($CC),Y
        CMP #'A'
        BNE ?BAD
        INY
        LDA ($CC),Y
        CMP #'P'
        BNE ?BAD
        INY
        LDA ($CC),Y
        CMP #$01
        BNE ?BAD
        INY
        LDA ($CC),Y
        STA $1B10
        INY
        LDA ($CC),Y
        STA $1B11
        LDA $1B11
        CMP $D1
        BCC ?FIT
        BNE ?BAD
        LDA $1B10
        CMP $D0
        BCC ?FIT
        BNE ?BAD
?FIT    LDA $CC
        STA $CE
        LDA $CD
        STA $CF
        LDA $1B10
        STA $D0
        LDA $1B11
        STA $D1
        LDA #$05
        JSR BM_APADV
        BCC ?BAD
        SEC
        RTS

; Validate the seal, including exclusive end = base + body length.
BM_APSEAL BRA ?BODY
?BAD    CLC
        RTS
?BODY   LDA #'S'
        JSR BM_APTAG
        BCC ?BAD
        LDA $D2
        CMP #$0B
        BNE ?BAD
        JSR BM_APNEED
        BCC ?BAD
        LDY #$00
        LDA ($CE),Y
        CMP #$01
        BNE ?BAD
        LDY #$05
        LDA ($CE),Y
        STA $1B12
        INY
        LDA ($CE),Y
        STA $1B13
        ORA $1B12
        BEQ ?BAD
        LDY #$01
        LDA ($CE),Y
        CLC
        LDY #$05
        ADC ($CE),Y
        STA $D7
        LDY #$02
        LDA ($CE),Y
        LDY #$06
        ADC ($CE),Y
        BCS ?BAD
        STA $D8
        LDY #$03
        LDA ($CE),Y
        CMP $D7
        BNE ?BAD
        LDY #$04
        LDA ($CE),Y
        CMP $D8
        BNE ?BAD
        LDY #$07
        LDA ($CE),Y
        STA $1B14
        INY
        LDA ($CE),Y
        STA $1B15
        INY
        LDA ($CE),Y
        STA $1B16
        INY
        LDA ($CE),Y
        STA $1B17
        LDA #$0B
        JSR BM_APADV
        BCC ?BAD
        SEC
        RTS

; Validate count plus five-byte relocation rows.
BM_APREL BRA ?BODY
?BAD    CLC
        RTS
?BODY   LDA #'R'
        JSR BM_APTAG
        BCC ?BAD
        LDA $D2
        BEQ ?BAD
        JSR BM_APNEED
        BCC ?BAD
        LDY #$00
        LDA ($CE),Y
        CMP #$11
        BCS ?BAD
        STA $D7
        ASL A
        ASL A
        CLC
        ADC $D7
        INC A
        CMP $D2
        BNE ?BAD
        LDA $D2
        JSR BM_APADV
        BCC ?BAD
        SEC
        RTS

; Validate an export/import record section selected by tag A.
BM_APREC BRA ?BODY
?BAD    CLC
        RTS
?BODY   JSR BM_APTAG
        BCC ?BAD
        LDA $D2
        CMP #$02
        BCC ?BAD
        JSR BM_APNEED
        BCC ?BAD
        LDY #$01
        LDA ($CE),Y
        CMP $D2
        BNE ?BAD
        LDA $D2
        JSR BM_APADV
        BCC ?BAD
        SEC
        RTS

; Validate the body tag, seal length, and exact package remainder.
BM_APBODY BRA ?BODY
?BAD    CLC
        RTS
?BODY   LDA #$03
        JSR BM_APNEED
        BCC ?BAD
        LDY #$00
        LDA ($CE),Y
        CMP #'B'
        BNE ?BAD
        INY
        LDA ($CE),Y
        CMP $1B12
        BNE ?BAD
        INY
        LDA ($CE),Y
        CMP $1B13
        BNE ?BAD
        LDA #$03
        JSR BM_APADV
        BCC ?BAD
        LDA $D0
        CMP $1B12
        BNE ?BAD
        LDA $D1
        CMP $1B13
        BNE ?BAD
        LDA $CE
        STA $D3
        LDA $CF
        STA $D4
        SEC
        RTS

; Hash the body with the local FNV service and compare the seal.
BM_APHASH BRA ?BODY
?BAD    CLC
        RTS
?BODY   JSR BM_FNV_INIT
        LDA $1B12
        STA $D5
        LDA $1B13
        STA $D6
?MORE   LDA $D5
        ORA $D6
        BEQ ?CHECK
        LDY #$00
        LDA ($D3),Y
        JSR BM_FNV_UPDATE
        INC $D3
        BNE ?COUNT
        INC $D4
?COUNT  DEC $D5
        LDA $D5
        CMP #$FF
        BNE ?MORE
        DEC $D6
        BRA ?MORE
?CHECK  LDX #$03
?HASH   LDA $B0,X
        CMP $1B14,X
        BNE ?BAD
        DEX
        BPL ?HASH
        SEC
        RTS

; Find and record the first valid AP envelope in the staged sector.
BM_APSCAN STZ $CC
        LDA #$0A
        STA $CD
        BRA ?NEXT
?ADV   INC $CC
        BNE ?NEXT
        INC $CD
        LDA $CD
        CMP #$1A
        BCC ?NEXT
        CLC
        RTS
?NEXT   LDY #$00
        LDA ($CC),Y
        CMP #'A'
        BNE ?ADV
        JSR BM_APHEAD
        BCC ?ADV
        JSR BM_APSEAL
        BCC ?ADV
        JSR BM_APREL
        BCC ?ADV
        LDA #'E'
        JSR BM_APREC
        BCC ?ADV
        LDA #'I'
        JSR BM_APREC
        BCC ?ADV
        JSR BM_APBODY
        BCC ?ADV
        JSR BM_APHASH
        BCC ?ADV
        LDA $1B0F
        ASL A
        ASL A
        CLC
        ADC $1B0F
        TAX
        LDA $1B02
        STA $1D40,X
        LDA $CC
        STA $1D41,X
        LDA $CD
        SEC
        SBC #$0A
        CLC
        ADC $1B04
        STA $1D42,X
        LDA $1B10
        STA $1D43,X
        LDA $1B11
        STA $1D44,X
        INC $1B0F
        SEC
        RTS

; Print AP Bn AAAA Lhhhh for the first valid envelope in each A sector.
BM_APLIST BRA ?BODY
?TITLE  DB $0D,$0A,'A','P',' ','E','N','V','E','L'
        DB 'O','P','E','S'
        DB $0D,$0A,0
?BODY   LDA $1B0F
        BNE ?HAVE
        RTS
?HAVE
        LDX #<?TITLE
        LDY #>?TITLE
        JSR BM_PUTS
        STZ $1B0D
        STZ $1B0E
?ROW    LDA #'A'
        JSR BM_OUT
        LDA #'P'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        LDA #'B'
        JSR BM_OUT
        LDX $1B0E
        LDA $1D40,X
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        LDX $1B0E
        LDA $1D42,X
        JSR BM_HEX
        LDX $1B0E
        LDA $1D41,X
        JSR BM_HEX
        LDA #' '
        JSR BM_OUT
        LDA #'L'
        JSR BM_OUT
        LDX $1B0E
        LDA $1D44,X
        JSR BM_HEX
        LDX $1B0E
        LDA $1D43,X
        JSR BM_HEX
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        LDA $1B0E
        CLC
        ADC #$05
        STA $1B0E
        INC $1B0D
        LDA $1B0D
        CMP $1B0F
        BNE ?ROW
        RTS

; Read-only live map: E=erased, U=used, A=valid AP, P=protected B3F.
BM_MAP  LDA #'M'
        STA $1B01
        STZ $1B0F
        LDX #<BM_MMAP
        LDY #>BM_MMAP
        JSR BM_PUTS
        STZ $1B02
?BANK   LDA #'B'
        JSR BM_OUT
        LDA $1B02
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA #$80
        STA $1B04
?SECTOR LDA #' '
        JSR BM_OUT
        LDA $1B02
        CMP #$03
        BNE ?STAGE
        LDA $1B04
        CMP #$F0
        BNE ?STAGE
        LDA #'P'
        BRA ?MARK
; The shared worker returns in Bank 3. Restore the entry bank before
; re-enabling interrupts or calling the entry bank's HIMON vectors.
?STAGE  PHP
        SEI
        JSR BM_STAGE
        BCS ?STAGEOK
        LDA #$00
        BRA ?STAGERES
?STAGEOK LDA #$01
?STAGERES PHA
        LDA #$EE
        TRB $7FEC
        LDA $1B0C
        TSB $7FEC
        PLA
        BNE ?STAGEPASS
        PLP
        JMP BM_FSTAGE
?STAGEPASS PLP
?SCAN   STZ $CA
        LDA #$0A
        STA $CB
        LDX #$10
?PAGE   LDY #$00
?BYTE   LDA ($CA),Y
        CMP #$FF
        BNE ?USED
        INY
        BNE ?BYTE
        INC $CB
        DEX
        BNE ?PAGE
        LDA #'E'
        BRA ?MARK
?USED   JSR BM_APSCAN
        BCC ?PLAIN
        LDA #'A'
        BRA ?MARK
?PLAIN  LDA #'U'
?MARK   JSR BM_OUT
        LDA $1B04
        CLC
        ADC #$10
        STA $1B04
        BNE ?SECTOR
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        INC $1B02
        LDA $1B02
        CMP #$04
        BCS ?DONE
        JMP ?BANK
?DONE   LDX #<BM_MLEGEND
        LDY #>BM_MLEGEND
        JSR BM_PUTS
        JSR BM_APLIST
        JSR BM_DIR
        JMP BM_SUCCESS

BM_COPY BRA ?BODY
?ABORT JMP BM_ABORT
?BODY  LDA #'C'
        STA $1B01
?SRC   LDX #<BM_MSRC
        LDY #>BM_MSRC
        JSR BM_PUTS
        JSR BM_READ
        BCC ?ABORT
        LDA $1C00
        BEQ ?ABORT
        JSR BM_PARSE_BANK
        BCC ?SRC
        STA $1B02
?DST   LDX #<BM_MDST
        LDY #>BM_MDST
        JSR BM_PUTS
        JSR BM_READ
        BCC ?ABORT
        LDA $1C00
        BEQ ?ABORT
        JSR BM_PARSE_BANK
        BCC ?DST
        CMP #$03
        BCS ?DST
        CMP $1B02
        BEQ ?DST
        STA $1B03
        JSR BM_COPY_DIR_EMPTY
        BCS ?DIR_EMPTY
        LDX #<BM_MCDIRUSED
        LDY #>BM_MCDIRUSED
        JSR BM_PUTS
        JMP BM_ABORT
?DIR_EMPTY

; Require a source reset vector in $8000-$FFFE before destructive copy.
        LDA #$F0
        STA $1B04
        JSR BM_STAGE
        BCS ?VECTOR
        JMP BM_FSTAGE
?VECTOR
        LDA $19FD
        CMP #$80
        BCC ?VEC
        CMP #$FF
        BNE ?CONF
        LDA $19FC
        CMP #$FF
        BNE ?CONF
?VEC   LDA #$E6
        STA $1B00
        JMP BM_FAIL

?CONF  LDA $0A0C
        CMP #'S'
        BNE ?TYPE
        LDA $0A0D
        CMP #'R'
        BNE ?TYPE
        LDA $0A0E
        CMP #$02
        BNE ?TYPE
        LDA $0A0F
        CMP #$03
        BNE ?TYPE
        LDA #'!'
        JSR BM_OUT
        LDA #'S'
        JSR BM_OUT
        LDA #'T'
        JSR BM_OUT
        LDA #'R'
        JSR BM_OUT
        LDA #'8'
        JSR BM_OUT
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
?TYPE   BRA ?PROMPT
?NO    JMP BM_ABORT
?PROMPT LDX #<BM_MCTYPE
        LDY #>BM_MCTYPE
        JSR BM_PUTS
        LDA $1B02
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA $1B03
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA #'>'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        JSR BM_READ
        BCC ?NO
        LDA $1C07
        BNE ?NO
        LDA $1C00
        CMP #'C'
        BNE ?NO
        LDA $1C01
        CMP #'O'
        BNE ?NO
        LDA $1C02
        CMP #'P'
        BNE ?NO
        LDA $1C03
        CMP #'Y'
        BNE ?NO
        LDA $1C04
        CMP #' '
        BNE ?NO
        LDA $1B02
        CLC
        ADC #'0'
        CMP $1C05
        BNE ?NO
        LDA $1B03
        CLC
        ADC #'0'
        CMP $1C06
        BNE ?NO
?YES   LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        LDA #$80
        STA $1B04
        STZ $1B05
?LOOP  JSR BM_STAGE
        BCS ?STAGED
        JMP BM_FSTAGE
?STAGED
        JSR BM_PROGRAM
        BCS ?WRITTEN
        JMP BM_FPROGRAM
?WRITTEN
        INC $1B05
        LDA #'.'
        JSR BM_OUT
        LDA $1B04
        CLC
        ADC #$10
        STA $1B04
        BNE ?LOOP
        JMP BM_COPY_ENROLL

; C only adopts an erased directory row. Existing/incomplete identities must
; be recovered through STR8-N I so their immutable metadata cannot be changed.
BM_COPY_DIR_EMPTY JSR BM_COPY_DIR_BASE
        LDY #$00
?BYTE   LDA ($CA),Y
        CMP #$FF
        BNE ?USED
        INY
        CPY #$10
        BNE ?BYTE
        SEC
        RTS
?USED   CLC
        RTS

BM_COPY_DIR_BASE LDA $1B03
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #$B0
        STA $CA
        LDA #$FF
        STA $CB
        RTS

BM_COPY_ENROLL LDX #<BM_MCTYPE2
        LDY #>BM_MCTYPE2
        JSR BM_PUTS
        JSR BM_READ
        BCS ?READ_OK
        JMP BM_COPY_ENROLL_ABORT
?READ_OK
        LDA $1C02
        BNE BM_COPY_ENROLL
        LDA $1C00
        JSR BM_HEX_NIBBLE
        BCC BM_COPY_ENROLL
        ASL A
        ASL A
        ASL A
        ASL A
        STA $1B18
        LDA $1C01
        JSR BM_HEX_NIBBLE
        BCC BM_COPY_ENROLL
        ORA $1B18
        STA $1B18
BM_COPY_DESC LDX #<BM_MCDESC
        LDY #>BM_MCDESC
        JSR BM_PUTS
        JSR BM_READ
        BCS ?READ_OK
        JMP BM_COPY_ENROLL_ABORT
?READ_OK
        LDA $1C05
        BNE BM_COPY_DESC
        LDX #$00
?BYTE   LDA $1C00,X
        JSR BM_DESC_BYTE
        BCC BM_COPY_DESC
        STA $1B19,X
        INX
        CPX #$05
        BNE ?BYTE
        LDX #<BM_MCENROLL
        LDY #>BM_MCENROLL
        JSR BM_PUTS
        JSR BM_READ
        BCC BM_COPY_ENROLL_ABORT
        LDA $1C00
        CMP #'Y'
        BNE BM_COPY_ENROLL_ABORT
        LDA $1C01
        BNE BM_COPY_ENROLL_ABORT

; START first: clear journal bit zero. The row remains unbootable until the
; final COMPLETE write clears bit one.
        LDA #$FE
        STA $7B00
        LDA #$0C
        LDX #$01
        JSR BM_COPY_DIR_WRITE
        BCC BM_COPY_ENROLL_FAIL

; Immutable descriptor for Banks 0-2: TYPE, erased reserved bytes, DESC,
; seal FE, and erased FFFF entry. Program and verify as one request.
        LDA $1B18
        STA $7B00
        LDA #$FF
        LDX #$01
?ERASED STA $7B00,X
        INX
        CPX #$04
        BNE ?ERASED
        LDX #$00
?DESC   LDA $1B19,X
        STA $7B04,X
        INX
        CPX #$05
        BNE ?DESC
        LDA #$FE
        STA $7B09
        LDA #$FF
        STA $7B0A
        STA $7B0B
        LDA #$00
        LDX #$0C
        JSR BM_COPY_DIR_WRITE
        BCC BM_COPY_ENROLL_FAIL

; COMPLETE is the last persistent action.
        LDA #$FC
        STA $7B00
        LDA #$0C
        LDX #$01
        JSR BM_COPY_DIR_WRITE
        BCC BM_COPY_ENROLL_FAIL
        JMP BM_SUCCESS

BM_COPY_ENROLL_ABORT JMP BM_ABORT
BM_COPY_ENROLL_FAIL LDA #$E7
        STA $1B00
        LDA $7EA5
        STA $1B06
        LDA $7EA6
        STA $1B07
        JMP BM_FAIL

; Program one exact Bank-3 directory request through the carried private
; mode-$07 worker, then independently verify every requested byte.
; IN: A=row-relative offset, X=length, desired bytes at $7B00.
BM_COPY_DIR_WRITE PHA
        STX $7EA0
        JSR BM_COPY_DIR_BASE
        PLA
        CLC
        ADC $CA
        STA $7E9E
        LDA #$FF
        STA $7E9F
        LDA #$07
        STA $1FF0
        JSR $0200
        BCC ?FAIL
        LDA $7E9E
        STA $CA
        LDA #$FF
        STA $CB
        LDY #$00
?VERIFY LDA ($CA),Y
        CMP $7B00,Y
        BNE ?FAIL
        INY
        CPY $7EA0
        BNE ?VERIFY
        SEC
        RTS
?FAIL   CLC
        RTS

BM_HEX_NIBBLE CMP #'0'
        BCC ?BAD
        CMP #'9'+1
        BCC ?DIGIT
        CMP #'A'
        BCC ?BAD
        CMP #'F'+1
        BCS ?BAD
        SEC
        SBC #'A'-10
        SEC
        RTS
?DIGIT SEC
        SBC #'0'
        SEC
        RTS
?BAD   CLC
        RTS

BM_DESC_BYTE CMP #'A'
        BCC ?DIGIT
        CMP #'Z'+1
        BCC ?OK
        BRA ?PUNCT
?DIGIT CMP #'0'
        BCC ?PUNCT
        CMP #'9'+1
        BCC ?OK
?PUNCT CMP #'-'
        BEQ ?OK
        CMP #'_'
        BEQ ?OK
        CMP #'.'
        BEQ ?OK
        CLC
        RTS
?OK    SEC
        RTS

BM_MCDIRUSED DB $0D,$0A,'D','I','R',' ','N','O','T',' ','E','M','P','T','Y'
        DB $0D,$0A,0
BM_MCTYPE2 DB $0D,$0A,'T','Y','P','E',' ','0','0','-','F','F','>',' ',0
BM_MCDESC DB 'D','E','S','C',' ','5',' ','C','H','A','R','S','>',' ',0
BM_MCENROLL DB 'E','N','R','O','L','L','?',' ','Y',':',' ',0

BM_ERASE LDA #'E'
        STA $1B01
BM_EBANK LDX #<BM_MBANK
        LDY #>BM_MBANK
        JSR BM_PUTS
        JSR BM_READ
        BCC BM_EABORT
        LDA $1C00
        BEQ BM_EABORT
        JSR BM_PARSE_BANK
        BCC BM_EBANK
        STA $1B02
        STA $1B03
        BRA BM_ESECTOR
BM_EABORT JMP BM_ABORT
BM_ESECTOR LDX #<BM_MSEC02
        LDY #>BM_MSEC02
        JSR BM_PUTS
        JSR BM_READ
        BCC BM_EABORT
        LDA $1C00
        BEQ BM_EABORT
        CMP #'A'
        BNE BM_ENOTALL
        LDA $1C01
        CMP #'L'
        BNE BM_ENOTALL
        LDA $1C02
        CMP #'L'
        BNE BM_ESECTOR
        LDA $1C03
        BNE BM_ESECTOR
BM_EALL LDA #$80
        STA $1B04
        LDA #$08
        STA $1B05
        LDA $1B02
        CMP #$03
        BNE BM_EASEL
        DEC $1B05
BM_EASEL LDA #'A'
        STA $1B08
        LDA #'L'
        STA $1B09
        STA $1B0A
        LDA #$03
        STA $1B0B
        JMP BM_ECONF

BM_ENOTALL LDA $1C01
        BEQ BM_ESINGLE
        CMP #'-'
        BNE BM_ESECTOR
        LDA $1C03
        BNE BM_ESECTOR
        LDA $1C00
        JSR BM_EHEX
        BCC BM_ESECTOR
        STA $1B04
        LDA $1C02
        JSR BM_EHEX
        BCC BM_ESECTOR
        CMP $1B04
        BCC BM_ESECTOR
        SEC
        SBC $1B04
        LSR A
        LSR A
        LSR A
        LSR A
        INC A
        STA $1B05
        LDA $1C00
        STA $1B08
        LDA #'-'
        STA $1B09
        LDA $1C02
        STA $1B0A
        LDA #$03
        STA $1B0B
        JMP BM_ECONF

BM_ESINGLE LDA $1C00
        JSR BM_EHEX
        BCS BM_ESOK
        JMP BM_ESECTOR
BM_ESOK
        STA $1B04
        LDA #$01
        STA $1B05
        LDA $1C00
        STA $1B08
        STZ $1B09
        STZ $1B0A
        LDA #$01
        STA $1B0B
        JMP BM_ECONF

; Convert 8, 9, A-F to a sector high byte and enforce Bank-3 max E.
BM_EHEX SEC
        SBC #'8'
        BCC BM_EBAD
        CMP #$0F
        BCS BM_EBAD
        TAX
        LDA BM_ETABLE,X
        BEQ BM_EBAD
        CMP #$F0
        BEQ BM_ECHECKF
        SEC
        RTS
BM_ECHECKF LDX $1B02
        CPX #$03
        BEQ BM_EBAD
        LDA #$F0
        SEC
        RTS
BM_EBAD CLC
        RTS
BM_ETABLE DB $80,$90,$00,$00,$00,$00,$00,$00,$00
        DB $A0,$B0,$C0,$D0,$E0,$F0

BM_ECONF LDX #<BM_METYPE
        LDY #>BM_METYPE
        JSR BM_PUTS
        LDA $1B02
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA $1B08
        JSR BM_OUT
        LDA $1B0B
        CMP #$01
        BEQ BM_ESELEND
        LDA $1B09
        JSR BM_OUT
        LDA $1B0A
        JSR BM_OUT
BM_ESELEND
        LDA #'>'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        JSR BM_READ
        BCC BM_ENO
        LDA $1C00
        CMP #'E'
        BNE BM_ENO
        LDA $1C01
        CMP #'R'
        BNE BM_ENO
        LDA $1C02
        CMP #'A'
        BNE BM_ENO
        LDA $1C03
        CMP #'S'
        BNE BM_ENO
        LDA $1C04
        CMP #'E'
        BNE BM_ENO
        LDA $1C05
        CMP #' '
        BNE BM_ENO
        LDA $1B02
        CLC
        ADC #'0'
        CMP $1C06
        BNE BM_ENO
        LDA $1B08
        CMP $1C07
        BNE BM_ENO
        LDA $1B0B
        CMP #$01
        BEQ BM_EONELEN
        LDA $1B09
        CMP $1C08
        BNE BM_ENO
        LDA $1B0A
        CMP $1C09
        BNE BM_ENO
        LDA $1C0A
        BEQ BM_EYES
        BNE BM_ENO
BM_EONELEN LDA $1C08
        BEQ BM_EYES
BM_ENO JMP BM_ABORT
BM_EYES
        JSR BM_FILL
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        LDA $1B02
        CMP #$03
        BNE BM_ELOOP
        SEI

; No HIMON calls are permitted below here while erasing Bank 3.
BM_ELOOP JSR BM_PROGRAM
        BCS BM_EWRITTEN
        JMP BM_FPROGRAM
BM_EWRITTEN
        LDA $1B02
        CMP #$03
        BEQ BM_ENODOT
        LDA #'.'
        JSR BM_OUT
BM_ENODOT LDA $1B04
        CLC
        ADC #$10
        STA $1B04
        DEC $1B05
        BNE BM_ELOOP
        LDA $1B02
        CMP #$03
        BNE BM_SUCCESS
        LDA #$AC
        STA $1B00
        JMP $F000

BM_FSTAGE LDA #$E1
        BRA BM_FAILCODE
BM_FPROGRAM LDA #$E2
        LDX $1FEA
        STX $1B06
        LDX $1FEB
        STX $1B07
BM_FAILCODE STA $1B00
        LDA $1B01
        CMP #'E'
        BNE BM_FAIL
        LDA $1B02
        CMP #$03
        BNE BM_FAIL
        JMP $F000
BM_FAIL LDA #'!'
        JSR BM_OUT
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        JMP BM_MAIN

BM_SUCCESS LDA #$AC
        STA $1B00
        LDA #' '
        JSR BM_OUT
        LDA #'O'
        JSR BM_OUT
        LDA #'K'
        JSR BM_OUT
        LDA #$0D
        JSR BM_OUT
        LDA #$0A
        JSR BM_OUT
        JMP BM_MAIN

BM_MTITLE DB $0D,$0A,'S','T','R','8','-','N',' ','1','.','1',' '
        DB 'B','A','N','K',' ','M','A','I','N','T',$0D,$0A
        DB 'B','3',' ','E','R','A','S','E',' ','R','E','T','U'
        DB 'R','N','S',' ','T','O',' ','S','T','R','8',';',' '
        DB 'S','E','L','E','C','T'
        DB ' ','S',$0D,$0A
        DB '!','S','T','R','8','=','S','O','U','R','C','E',' '
        DB 'H','A','S',' ','S','T','R','8',$0D,$0A
        DB 'C','=','C','O','P','Y','+','D','I','R',' ','E','=','E','R','A'
        DB 'S','E',' ','M','=','M','A','P','+','D','I','R'
        DB ' ','P','=','A','P',' ','B','0','B','F','0','0'
        DB ' ','Q','=','Q','U','I','T'
        DB '>',' ',0
; Fixed one-sector AP carrier put for the split-V1 promotion proof.
; First run AP $4000 $3000 in HIMON. The outer envelope and fit are checked
; again here; HIMON remains the authority for the complete AP format.
BM_PUT  BRA ?BODY
?MTARGET DB 'P','U','T',' ','A','P',' ','B','0',' ','$','B','F'
        DB '0','0',$0D,$0A
        DB 'T','Y','P','E',' ','P','U','T',' ','B','0','B','F'
        DB '0','0','>',' ',0
?EXACT  DB 'P','U','T',' ','B','0','B','F','0','0',0
?BAD    JMP BM_ABORT
?BODY   LDA #'P'
        STA $1B01
        LDA $4000
        CMP #'A'
        BNE ?BAD
        LDA $4001
        CMP #'P'
        BNE ?BAD
        LDA $4002
        CMP #$01
        BNE ?BAD
        LDA $4004
        BNE ?BAD
        LDA $4003
        CMP #$05
        BCC ?BAD
        STA $1B05
        STZ $1B02
        STZ $1B03
        LDA #$B0
        STA $1B04
        JSR BM_STAGE
        BCS ?STAGED
        JMP BM_FSTAGE
?STAGED
        LDX #$00
?ERASED LDA $1900,X
        CMP #$FF
        BEQ ?ERASEOK
        JMP BM_ABORT
?ERASEOK
        INX
        CPX $1B05
        BNE ?ERASED
        LDX #<?MTARGET
        LDY #>?MTARGET
        JSR BM_PUTS
        JSR BM_READ
        BCS ?READOK
        JMP BM_ABORT
?READOK
        LDX #$00
?CONFIRM LDA $1C00,X
        CMP ?EXACT,X
        BEQ ?MATCH
        JMP BM_ABORT
?MATCH
        INX
        CPX #$0B
        BNE ?CONFIRM
        LDX #$00
?OVERLAY LDA $4000,X
        STA $1900,X
        INX
        CPX $1B05
        BNE ?OVERLAY
        JSR BM_PROGRAM
        BCS ?PROGRAMMED
        JMP BM_FPROGRAM
?PROGRAMMED
        JMP BM_SUCCESS

; BEGIN GENERATED STR8 MUTATION WORKER
        ORG $3000
        DB $4C,$07,$02,$49,$57,$01,$FE,$08
        DB $78,$AD,$F0,$1F,$C9,$05,$F0,$0B
        DB $C9,$06,$F0,$0C,$C9,$07,$F0,$0D
        DB $28,$18,$60,$20,$38,$02,$80,$0A
        DB $20,$4B,$02,$80,$05,$20,$62,$02
        DB $80,$00,$90,$06,$20,$14,$04,$28
        DB $38,$60,$20,$14,$04,$28,$18,$60
        DB $20,$E5,$02,$90,$0C,$20,$2F,$03
        DB $90,$07,$20,$6E,$03,$90,$02,$38
        DB $60,$18,$60,$AD,$EE,$1F,$20,$16
        DB $04,$64,$CD,$AD,$E9,$1F,$85,$CE
        DB $64,$CF,$AD,$F6,$1F,$85,$D0,$4C
        DB $D2,$02,$20,$14,$04,$20,$B8,$02
        DB $AE,$A0,$7E,$F0,$31,$A0,$00,$B1
        DB $CF,$85,$D3,$B1,$D1,$25,$D3,$C5
        DB $D3,$D0,$25,$20,$C9,$02,$CA,$D0
        DB $EC,$20,$B8,$02,$AE,$A0,$7E,$A0
        DB $00,$B1,$CF,$85,$D3,$B1,$D1,$C5
        DB $D3,$F0,$05,$20,$C5,$03,$90,$08
        DB $20,$C9,$02,$CA,$D0,$E9,$38,$60
        DB $A5,$D1,$8D,$A5,$7E,$A5,$D2,$8D
        DB $A6,$7E,$A0,$00,$B1,$D1,$8D,$A7
        DB $7E,$A5,$D3,$8D,$A8,$7E,$18,$60
        DB $AD,$9E,$7E,$85,$D1,$AD,$9F,$7E
        DB $85,$D2,$64,$CF,$A9,$7B,$85,$D0
        DB $60,$E6,$D1,$D0,$02,$E6,$D2,$E6
        DB $CF,$60,$A0,$00,$B1,$CD,$91,$CF
        DB $C8,$D0,$F9,$E6,$CE,$E6,$D0,$20
        DB $A2,$03,$D0,$EE,$60,$AD,$EF,$1F
        DB $20,$16,$04,$20,$08,$03,$B0,$16
        DB $AD,$EA,$1F,$85,$D1,$AD,$EB,$1F
        DB $85,$D2,$20,$AB,$03,$90,$05,$20
        DB $08,$03,$B0,$02,$18,$60,$38,$60
        DB $64,$CD,$AD,$E9,$1F,$85,$CE,$A0
        DB $00,$B1,$CD,$C9,$FF,$D0,$0D,$C8
        DB $D0,$F7,$E6,$CE,$A5,$CE,$29,$0F
        DB $D0,$ED,$38,$60,$98,$8D,$EA,$1F
        DB $A5,$CE,$8D,$EB,$1F,$18,$60,$AD
        DB $EF,$1F,$20,$16,$04,$64,$D1,$AD
        DB $E9,$1F,$85,$D2,$64,$CF,$AD,$F6
        DB $1F,$85,$D0,$A0,$00,$B1,$CF,$C9
        DB $FF,$F0,$13,$85,$D3,$20,$C5,$03
        DB $B0,$0C,$A5,$D1,$8D,$EA,$1F,$A5
        DB $D2,$8D,$EB,$1F,$18,$60,$E6,$D1
        DB $E6,$CF,$D0,$DF,$E6,$D2,$E6,$D0
        DB $20,$A2,$03,$D0,$D6,$60,$AD,$EF
        DB $1F,$20,$16,$04,$64,$CD,$AD,$E9
        DB $1F,$85,$CE,$64,$CF,$AD,$F6,$1F
        DB $85,$D0,$A0,$00,$B1,$CD,$D1,$CF
        DB $D0,$0D,$C8,$D0,$F7,$E6,$CE,$E6
        DB $D0,$20,$A2,$03,$D0,$EC,$60,$98
        DB $8D,$EA,$1F,$A5,$CE,$8D,$EB,$1F
        DB $18,$60,$AD,$F6,$1F,$18,$69,$10
        DB $C5,$D0,$60,$20,$02,$04,$A9,$80
        DB $8D,$55,$D5,$20,$02,$04,$A9,$30
        DB $A0,$00,$91,$D1,$A9,$FF,$85,$D3
        DB $A9,$08,$4C,$E5,$03,$A0,$00,$B1
        DB $D1,$C5,$D3,$F0,$17,$25,$D3,$C5
        DB $D3,$D0,$3A,$20,$02,$04,$A9,$A0
        DB $8D,$55,$D5,$A5,$D3,$91,$D1,$A9
        DB $02,$4C,$E5,$03,$60,$64,$D4,$64
        DB $D5,$85,$D6,$A0,$00,$B1,$D1,$C5
        DB $D3,$F0,$0E,$C6,$D4,$D0,$F4,$C6
        DB $D5,$D0,$F0,$C6,$D6,$D0,$EC,$80
        DB $0C,$60,$A9,$AA,$8D,$55,$D5,$A9
        DB $55,$8D,$AA,$AA,$60,$A9,$F0,$8D
        DB $55,$D5,$18,$60,$A9,$03,$29,$03
        DB $AA,$BD,$27,$04,$48,$A9,$EE,$1C
        DB $EC,$7F,$68,$0C,$EC,$7F,$60,$CC
        DB $CE,$EC,$EE
; END GENERATED STR8 MUTATION WORKER
        END
