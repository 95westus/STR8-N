; The native-loader image owns a sealed helper and shared help in its padding.
; Do not execute absent/corrupt optional code. A minimal MON works without it.
M_SETTINGS_CHECK:
        LDA #MON_SETTINGS_IMAGE_PAGE
        LDX #4
        JSR M_CRC_PAGES
        LDA M_CRC
        ORA M_CRC+1
        BNE M_SETTINGS_BAD
        LDX #7
M_SETTINGS_ID:
        LDA MON_SETTINGS_BASE,X
        CMP M_SETTINGS_MAGIC,X
        BNE M_SETTINGS_BAD
        DEX
        BPL M_SETTINGS_ID
        SEC
        RTS
M_SETTINGS_BAD:
        CLC
        RTS
M_SETTINGS_MAGIC: DB "EC",1,1,"PR05"
