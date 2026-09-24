# RC1 ASM-F2 applications for the public R-YORS release

These two STR8-N `.a` files use the `ORG`/`DB` carrier syntax of the public
R-YORS HIMON and ASM-F2 `00.0915(2324)` release. They contain STR8-N project
bytes only; no HIMON, ASM-F2, or WDCMONv2 firmware is bundled here. Their
assembled bytes are checked against the matching S19 files in this package.

The public R-YORS release was prepared around STR8-N 1.34. Its HIMON uses
parts of `$7E60-$7E8A` as workspace; STR8-N v2 uses that range for its RAM
call table. These applications avoid that table while HIMON is active. This
does **not** qualify every HIMON/ASM-F2 command on v2, especially HIMON's
v1 STR8 record-service loader or software STR8 restart. Use the R-YORS
components on a W65C02SXB first; W65C816 and EDU operation remain separate
board qualifications.

## Read-only Bank 3 identity

`APPLICATIONS/str8n-v2-bank3-id-2000.a` assembles at `$2000-$20A6`. It runs
from RAM, selects Bank 3 long enough to read `$F000-$F003` and the RESET
vector, prints their hexadecimal bytes through the FT245, restores the prior
flash-bank selection, and returns to HIMON. It does not program flash or call
the v2 RAM ABI. On the frozen alpha21 Bank 3 top the expected line is:

```text
B3:F HEAD=534E0200 RESET=F004
```

The matching `FIRMWARE/str8n-v2-bank3-id-2000.s19` is available for a direct
RAM loader. A different header or vector is an observation to record, not
permission to continue with a flash update.

## Guarded alpha21 top updater

`APPLICATIONS/str8n-v2-alpha21-b3-top-update-2000.a` is a 12,288-byte
carrier at `$2000-$4FFF`; `$4000-$4FFF` is the exact frozen alpha21 top BIN.
Its matching `FIRMWARE/str8n-v2-alpha21-b3-top-update-2000.s19` has the same
bytes. This RC1 adjunct corrects the pre-erase cancel path to enter v2 RESET
at `$F004`; `$F000` is v2's `SN` signature and cannot be executed. HIMON can
clear v2 RAM before launching the updater, so the HOLD entry at `$F007` is
not a safe return from that session. After cancellation, allow the normal
startup hold and send `S` if you want to remain at the v2 prompt. The
firmware top BIN itself remains the frozen, board-read-back alpha21 image.

Run this updater only on an identified board with compatible STR8-N v2 in
Bank 3, an FT245 data host, stable power, and a deliberately chosen Bank 2 F
recovery destination. It overwrites Bank 2 F with a verified copy of the old
Bank 3 F before programming Bank 3 F. Review the prompts and the existing
recovery state before accepting either confirmation. The board-tested alpha21
installation used the earlier S19 success path; ASM-F2 ingestion and this
corrected cancel path have host checks but no new physical-board run.

## Loading from public HIMON/ASM-F2

With public HIMON and ASM-F2 already running, load one application at a time:

```text
>ASM NEW
send the complete selected .a file with terminal CR line endings;
require no ERR and successful END
SEAL> SEAL
require SEAL OK
SEAL> .
>G 2000
```

Do not send an `.a` file to STR8-N `L`; `L` accepts S19. Do not assemble both
files in the same session: each starts at `$2000`. The identity utility
returns to HIMON. The updater transfers control to STR8-N on cancellation
or after its verified install and reset-vector entry; it does not return to
the HIMON prompt.
