; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.29 promotes the STR8-iN/65 cold-start and EDU quiet-start path.
MSG_ID:
                        IF              STR8_IN65_VERSION_129
                        DB              $0D,$0A,"STR8-N 1.29"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
