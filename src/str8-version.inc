; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.31 includes board-proven private RX/TX LED activity.
MSG_ID:
                        IF              STR8_IN65_VERSION_131
                        DB              $0D,$0A,"STR8-N 1.31"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
