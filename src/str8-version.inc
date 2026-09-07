; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.32 adds the one-shot hardware/software reset-source indication.
MSG_ID:
                        IF              STR8_IN65_VERSION_132
                        DB              $0D,$0A,"STR8-N 1.32"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
