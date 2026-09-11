# STR8-N v1.33 Top-Update Board Test — 2026-09-10

Status: accepted on COM4 for the guarded Bank-3 top-sector update, exact
readback, software-reset entry, v1.33 identity, and HIMON warm recovery.

The canonical 4096-byte Bank-3 top image has SHA-256
`C9DA23B8ADFE78A401DD7CE5865F52B6E0F9A884BB17A6413678CEF63822BEF3`.
The RAM updater S19 has SHA-256
`7A873208316936AE77867B196DAA5ADF1A44EEB3F9770E4373F7E599C302B48A`.
The resident occupies `$F000-$FD41` (3,394 bytes), leaving 14 bytes before the
fixed 608-byte worker at `$FD50`.

The full host `make all` suite passed before board mutation. The running v1.32
image loaded `str8n-v1.33-top-update-2000.s19` through its `L` command. The
updater reported `BACKUP B1:F; TARGET B3:F`, accepted the exact `BACKUP B1F`
confirmation, verified the backup, and reported:

```text
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$17A0
```

After the exact `STR8-N 1.33` confirmation it printed:

```text
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.33 VERIFIED; RESET

RST S

STR8-N 1.33
0-2 C W S:
BOOT WARM

HIMON V 00.0910(1709)
>
```

This proves the candidate sector was programmed and read back through the
guarded RAM path, its reset vector executed, the one-shot software-reset marker
was consumed, and the normal warm HIMON handoff remained usable. The live
Bank-3 directory was preserved by the normal top updater.

This session did not repeat physical-reset classification, cold HIMON entry,
Bank 0-2 boot, directory refresh, failure recovery, or the factory WDCMONv2
migration. Those claims remain attached to their earlier exact versions and
reports. The retained raw receive transcript is
[STR8N_V1_33_TOP_UPDATE_BOARD_TRANSCRIPT_2026-09-10.txt](STR8N_V1_33_TOP_UPDATE_BOARD_TRANSCRIPT_2026-09-10.txt).
