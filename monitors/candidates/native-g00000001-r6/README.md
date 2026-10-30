# Native apps g1, loader repair r6

Build-only repair: preserve X around frozen F J_CRC_BYTE, which preserves Y
but clobbers X. The r5 hardware launch stalled because its page counter was
destroyed. Only B3:8 changes; CLOCK, FLASH/MAINT, RTC/history code and MON/WB
payloads are unchanged. No F rebuild. Live repaired launch remains pending.
