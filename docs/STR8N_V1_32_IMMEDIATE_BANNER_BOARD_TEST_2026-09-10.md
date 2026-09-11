# STR8-N v1.32 Immediate-Banner Board Test — 2026-09-10

Status: accepted on COM4 for guarded update, program verification, cooperating
restart, immediate identity display, and HIMON/ASM recovery.

The candidate Bank-3 top image has SHA-256
`A55142FC996C38BDAF3E64E1685E5EC361286D637AE757492D078282E88FC0A3`.
Its resident occupies `$F000-$FD41` (3,394 bytes), leaving 14 bytes before the
fixed worker at `$FD50`.

The RAM Top Update reported `BACKUP B1:F; TARGET B3:F`, accepted the exact
`BACKUP B1F` confirmation, verified the backup, and reported receipt sum
`$17D2`. After the exact `STR8-N 1.32` confirmation it printed:

```text
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.32 VERIFIED; RESET

RST S

STR8-N 1.32
0-2 C W S:
```

This proves that the former hidden six-second pre-banner quarantine is gone
and exactly two linefeeds separate `RST S` from the immediately printed
identity. The six-second live selector interval remains.

The follow-on R-YORS update completed through STR8-N's guarded installer. An
incorrect stale ASM-only stream was rejected after START, and STR8-N correctly
required a full Bank-3 `$8000-$EFFF` recovery rather than accepting a partial
retry. The regenerated dense recovery stream reached `COMMIT? Y`, verified,
and returned `OK`. Final live identities were:

```text
HIMON V 00.0910(1709)
ASM-F2 00.0910(1709)
```

Bank-1 MicroChess at `$9000` remained discoverable and executable. No physical
RESET button capture was made during this automated session; `RST S` and
unmarked `G F000`/`RST H` paths were observed.
