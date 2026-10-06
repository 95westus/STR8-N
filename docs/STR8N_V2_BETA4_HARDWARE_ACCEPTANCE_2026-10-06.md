# Beta4 migration hardware acceptance - October 6, 2026

The beta4 migration firmware was exercised on the physical W65C02SXB on
COM3 and W65C816SXB on COM8. Both ended at `B3>` running STR8-N 2.0b4,
with two validated generation-13 monitor slots and the matching fixed core.
The 816 monitor and maintenance utility ran in emulation mode.

## Backup and preservation

Before any write, all four complete 32 KiB banks of each board were read
twice independently. Every repeated read matched. The bank images, serial
logs, plans and receipts remain private under
`BUILD/beta4-board-acceptance-20261006`. No bank readback or stock firmware
is included in the release or proposed commit.

The final B0, B1 and B2 of each board match their initial backups byte for
byte. The initial migrations preserved B3 `$8000-$9FFF`; the requested
MAINT follow-up then replaced those two storage sectors with the saved
utility. Both stages matched their respective complete expected images.

## COM3: retained B0 to B3, then WDC migration

The owner requested recreation of the retained stock baseline by copying
B0 into B3. A guarded RAM restore was built for the measured B0 hash and
rehearsed against the fresh backups. The linked image contained no B0-erase
routine. Its physical run copied/verified sectors 8-E, wrote F last, then
compared B0 and B3 exactly and verified B0 again. The owner pressed RESET.

The retained image starts a normal program unless the debugger connects
during startup. Idle sync and a delayed RESET/Enter attempt did not connect;
neither loaded RAM nor wrote flash. The established read-only armed RESET
probe reached `SXB2`, hardware 3.00, WDCMON 2.00. The portable beta4 host
then queried identity, read the complete source twice, loaded/read back the
RAM installer, and completed all six transfers in order D, C, A, B, E, F.
The installer reported `MIGRATION VERIFIED; PRESS PHYSICAL RESET`.

The release's portable startup probe now arms read-only sync/identity
requests with the port open while the owner presses RESET. Its regression
checks cover startup text, duplicate sync handling and incomplete INFO
replies. The actual armed-session opening in this test used the established
Windows probe; the remaining portable host/installer operations were
physically exercised. No vendor monitor source or firmware was embedded.

After the owner confirmed physical RESET, the monitor responded as beta4.
The complete four-bank readback matched the prepared result. A and B were
also selected through software RESET and each passed a fresh B3 readback.
The default is A. The stock route provisions disabled autostart, B3 `$F007`
and delay `$0A`. Its counters start from the stock provisioning baseline;
the original beta4 settings/counts from before restoration remain in the
private pre-test backup.

Final COM3 B3 SHA256:
`a127a91d2c16aa0060b7cae960c058da794ce9fb405cf82aa8b09be566ca7aea`.
Preserved COM3 B0 SHA256:
`2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8`.

## COM8: a24c1/beta1 to beta4

The source matched the known a24c1/beta1 F image outside its configuration
pocket. CPU state reported `$16`, and the physical RESET capture identified
`STR8-N 2.0b4 B3 65C816`. The portable host verified the source and complete
RAM installer before execution. Transfers C, A, B, E, F completed; D was
already erased and was not rewritten. F was written last.

The complete four-bank readback matched the expected result. The settings
`C 00 03 F007 40` were retained. The owner pressed physical RESET, then both
A and B were separately booted in software and checked against the full B3
image. The default is A.

Final COM8 B3 SHA256:
`8a995debc48fdebcbb52a6f18a2b2adfbde900e50370da5d34ed884d1bab1a28`.
Preserved COM8 B0 SHA256:
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.

## Loadable maintenance and limits

On both boards the packaged BANK MAINT 1.5 S19 was loaded through `L` and
read back completely. `G 2000`, help, range/grid/wear maps and `Q` worked.
A final B3 readback proved those RAM-only checks changed no flash. The
utility's 7,508 program bytes remain unchanged.

The owner subsequently requested MAINT saved on both boards and installed
by the release. Fresh all-bank backups were independently repeated before
the storage update. A guarded MAINT-only installer replaced B3 sectors 8/9,
recorded both erase attempts in the existing journal, verified its pending
record and then committed the completion marker. Monitor slots, E, F,
configuration, preference and B0-B2 were unchanged. Exact final readback,
TABLE, `R MAINT` after A/B software resets, `Q`, and monitor M/M1/M3 passed
on both physical boards. The installed record is:

```text
B3:8000 2000-3D53 1D54 C MAINT
```

Current B3 SHA256 after this follow-up: COM3
`1b4a2d70a95a25fabd7cfddd68225d91557c4d524b017a08b32cd536021f47de`;
COM8 `3aba0a711f39471c4c6776a254af19e78b79cd672dbbaf8963f6185f7db4985d`.
The release's updated eight-sector migration plan automatically includes
the same generated MAINT record. Its full-plan and pending-record failure
checks are executed in the linked model; the MAINT-only storage writes and
subsequent use were physically checked as described above.

These checks establish the listed migration, RESET, slot and maintenance
cases. They do not establish physical power-cut recovery, native-mode 816
program execution, interrupts under load, or every supported legacy source
on both CPU families. Raw a24 and other source-layout cases remain covered
by the offline checks. No staging, commit, push or publication was performed.
