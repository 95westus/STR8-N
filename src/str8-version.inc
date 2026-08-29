; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.28 promotes the board-proven STR8-iN/65 cold-start sequence.
MSG_ID:
                        IF              STR8_IN65_VERSION_128
                        DB              $0D,$0A,"STR8-N 1.28"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
