# bf1 qualification summary

2.0bf1 generation 48 fixes native-utility/CLOCK BATCH handoffs under both monitor
slots. One pinned FT245/F30D firmware set was checked on 65C02 board 2604 and
65C816 board 2609 with emulation-mode runtime. The unchanged brief native-mode
startup detector exception is accepted; native 816 applications, ACIA and crypto
remain deferred. Native utility means the monitor utility provider, not a
native-mode 65C816 application.

The source-only build produced the 19 pinned artifacts in reference-build.json.
Packaging reuses unchanged source/build and prior offline evidence; it does not
claim a fresh firmware build or ABI suite. Initial 2604 B/A and 2609 B/A checks
passed. 2609 had 12 groups per slot and 14 emulation runtime observations.
Original A40/B35 payload restoration and two verified-transfer-boundary electrical
interruptions on 2609 passed exact cut-state/fallback/recovery, utility/CLOCK
BATCH, retained-device preservation and original application RAM restoration.
Second recovery updated two journals without erasing committed A payload.
Normal boot logged expected PF events; no manual ACK/CLEAR was issued.

No mid-erase/program, arbitrary byte timing or 2604 electrical qualification is
claimed. Only exact captured 2604/2609 migration lineages were admitted; there
is no generic stock/legacy/core/private-ABI conversion permission.

Publication is gated on the six-hour 2609 preserving soak and verified RAM
restoration. The 72-hour/300-cycle 2604 and seven-day RTC gates remain pending.
Full release qualification is false. See the
[accepted policy](STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).
