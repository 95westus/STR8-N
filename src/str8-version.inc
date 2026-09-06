; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.30 reclaims resident space; cold-start and quiet-start are retained.
MSG_ID:
                        IF              STR8_IN65_VERSION_130
                        DB              $0D,$0A,"STR8-N 1.30"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
