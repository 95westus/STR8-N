; Compact identity; detailed build identity belongs in the host manifest.
; STR8-N v1.33 promotes the immediate-banner/reset-source image.
MSG_ID:
                        IF              STR8_IN65_VERSION_133
                        DB              $0D,$0A,"STR8-N 1.33"
                        ELSE
                        DB              $0D,$0A,"STR8-N 1.23"
                        ENDIF
