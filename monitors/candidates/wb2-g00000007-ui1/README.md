# WB2 g7: shared VERSION/TIME and quiet Q

Uses the active MON's CRC-admitted UI/1 instead of a duplicate RTC reader.
VERSION/V work in the workbench and CLOCK; TIME shares the monitor's RTC
implementation/cache. MAINT retains the selected bank; Q quietly returns
without clearing the cached sample. WG/generation marks the current module.
STORE/TABLE/RESTORE and short aliases are retained; BATCH adds VERSION/V/TIME
to its existing returning-command subset.

Built, not execution-qualified or installed. One failed WDC label-expression
attempt required one corrective build. The validated loader was reused.
224 free code bytes; state/CRC bounds unchanged. Full CLOCK SET/CONFIG and
b35 parity remain required. F and published downloads remain unchanged.
