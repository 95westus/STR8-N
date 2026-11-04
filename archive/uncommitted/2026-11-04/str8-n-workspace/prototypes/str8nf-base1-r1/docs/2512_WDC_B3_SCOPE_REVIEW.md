# 2512 WDC migration: B3 scope review

Reviewed scope, subsequently approved and completed: the user explicitly
approved the expanded six-erase current-chip trial. See the
[actual acceptance result](2512_WDC_MIGRATION_ACCEPTANCE.md). The original
review below covered the migration transaction; current-chip setup added a
second F/D/C pass. Board 2205 stayed excluded. Frozen F source/release bytes
and kit ZIPs are unchanged; the installed F was temporarily replaced with
WDC, then restored to the exact frozen BASE1 image.

## Current-chip preparation adds three erases

At the reviewed starting checkpoint after the B0 power-loss case, 2512 was
at REC> with original images, policy and RAM restored: 29 valid records,
sequence 961, C/D/F counts 47/27/22 and B0:9 count 9. DD/DE were blank and
DF reserved. The linked acceptance receipt records the later final state.

| Stage | Exact writes | Accounting / retained evidence |
| --- | --- | --- |
| Prepare WDC fixture | Append DD00 sequence 962, then erase/program B3:F, D, C | First commit reserves one erase each: C48, D28, F23; full original chip and records archived privately |
| Real WDC migration | Erase/program B3:F, D, C through the public NFM1 path | Import source-bound setup counts; reserve another each: C49, D29, F24; new D/C snapshots 963/964 |
| Restore original policy | Append C100 sequence 965, no erase | Restore original B/0F/all8000 and original configuration/pinned generation; retain current counts |

Total: **six sector erases, two each in B3:F/D/C**. B0-B2 and B3:8/9/A/B/E
remain exact originals. The original C/D records are archived as raw bytes on
the host; this chosen conversion replaces them on-chip with a new imported
journal. Final B0:9 count remains 9; all other counts remain unchanged except
the six declared C/D/F reservations. Prior lifetime stays unknown.

The temporary WDC F is from the archived actual 2512 pre-FLASH bank, also
matching the separately retained Desktop full-device candidate. F000-F7FF
are erased; the resident starts F800, reset F818. Sector SHA-256:
`ce5415f4e5032e44a19a2ab801ca9090fd81434355421d1913fca86a62f5a44b`.
The disposable C/D fixture sectors contain FF with byte 00FF committed as 00;
they contain no SNBT record. Explicit first-journal provisioning must admit
this declared non-SNBT fixture. They are not owner application images.

The RAM-only NFX1 setup engine checks all source banks, its own image/plan,
and chip BF/B5, commits the reservation before any erase, then admits only
F/D/C in that order. Its source-bound rendered SHA-256 is recorded in the
private reviewed plan. The unchanged public NFM1 engine performs the actual
WDC-to-BASE1 migration after physical vendor reset and double capture.

WDC reset initializes LED/PIA, reads CS0-3 during its lamp sequence, initializes
FT245/VIA, and uses low RAM/ZP. The selected binary reset prefix and serial-init
entry were inspected against the local source archive. The receiver must catch
the vendor debugger before its application timeout; no vendor application,
EDU menu, SPI SRAM formatter, RTC initialization or WDC flash command is sent.
This does not qualify every attached peripheral's electrical behavior.

The normal public post-migration callback first restores and verifies the RAM
captured before the WDC archiver. A separate source-bound policy helper then
restores original policy, after which independent full-bank reads and full
restoration of the earlier original 2512 RAM/ZP escrow finish the case. Old MON
is not executed. Final REC>, port released, exact frozen BASE1 F restored.

Prepared private plan and original full-chip recovery bytes:
`C:\SRC\STR8-N\output\qualification\2512-closeout-20261028-r1\wdc-current-scope`.
Execution used `--execute-reviewed-six-erases` after the explicit approval and
fresh live double-capture admission. The six-erase happy path passed.
For a future failure: keep power, stop without retry, retain
escrow/intent; use the identified T48 III/Xgpro if ROM recovery is unavailable.
No deliberate F/C/D interruption is included in this happy-path conversion.
The original chip capture is a recovery reference, not an automatic rollback
of wear history. Any programmer recovery must retain the latest durable erase
reservations and account conservatively for programmer erases before a new
journal is admitted. Do not blindly reinstall the older journal counters.

## Exact factory transaction

The implemented WDC RAM migrator expects a real WDC reset/debugger source and
an explicitly admitted first-journal conversion. With vendor F present, its
device operations are in this order:

| Operation | Board address | Standard linear 128 KiB chip offset | Effect |
| --- | --- | --- | --- |
| 1 | B3:F000-FFFF | 1F000-1FFFF | Erase and program the exact frozen 4096-byte BASE1 F; independently verify |
| 2 | B3:D000-DFFF | 1D000-1DFFF | Erase and provision first SNBT snapshot; verify before committing D0FF last |
| 3 | B3:C000-CFFF | 1C000-1CFFF | Erase and provision second SNBT snapshot; verify before committing C0FF last |

Confirm the actual chip/programmer address mapping before any programmer use.
Only these three sectors belong to this migration transaction. B0-B2 and
B3:8/9/A/B/E must remain byte-for-byte unchanged. A full-chip programmer erase
is a separate fixture-preparation operation, not an F-only upgrade.

The new journal defaults to S/recovery, mask 00 (all banks disabled), and entry
8000 for each bank. Its counts include a reservation for each planned C/D/F
erase. Prior wear is marked unknown unless an explicit source-bound history
import supplies lower bounds. Neither path establishes a lifetime erase count.
Original owner RAM 0200-66FF and ZP 00-DF must be independently restored after
the final physical reset and complete flash readback.

## Conflict with the preserved 2512 chip

2512 now has the frozen BASE1 F and an existing valid SNBT history. The normal
factory planner correctly treats this as an unchanged no-op. It refuses to
re-provision existing SNBT sectors. Temporarily putting WDC in F would not
remove that conflict: an existing-SNBT F change needs an append-reservation
upgrade path, not first-journal provisioning.

Erasing C/D to force the factory route would physically discard the retained
historical records. A host backup or imported latest counts does not preserve
those records on the installed chip. Restoring an old full-chip backup after
extra erases would also roll the recorded history backward unless the new
attempts were explicitly reconciled. No such rollback is proposed here.

Running the retained WDC bytes from B0 alone is insufficient: the current
archive procedure requires physical reset back into the vendor debugger before
the migration engine runs. Physical reset on the present chip goes to BASE1 F.
That shortcut would not qualify the promised end-to-end WDC migration.

## Recommended disposable fixture

Use 2512 with a separately identified, CPU-correct compatible spare flash chip.
Preserve the current original chip physically, with full double-read backups
and the final owner RAM escrow. Prepare the spare with the reviewed local WDC
fixture, verify a real vendor reset/debugger connection, and capture it twice.
Run the verbose RAM migration on that spare, including all three sector
operations and physical reset into the exact frozen BASE1 F. Verify all owner
flash areas and restore original RAM/ZP. Reinstall the untouched original chip
and independently verify its banks, journal and RAM before releasing the port.

The owner reports a T48 III / Xgpro recovery programmer and subsequently chose
the current chip. A spare chip was not identified. The exact fixture bytes, chip identity,
programmer mapping and complete expected postimage must be reviewable before
fixture programming. Private vendor originals must stay out of public kits.

The separate B0:9 power-cut trial uses normal durable SNBT appends and performs
no C/D erase or F write. It qualifies an incomplete opaque image across real
USB power loss at a chip-idle checkpoint; flash-pulse brownout, torn SNBT and
interrupted F migration need separate fault cases and repair procedures.
