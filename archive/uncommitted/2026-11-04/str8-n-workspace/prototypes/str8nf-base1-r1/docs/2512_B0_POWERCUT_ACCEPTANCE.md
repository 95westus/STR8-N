# 2512 B0 write, boot and incomplete-image power-loss acceptance

Passed October 28, 2026 local time (October 29 UTC), 65C02 / FT245 / COM4.
The owner assigned B0 on 2512, authorized power cuts, identified USB power
and a T48 III/Xgpro recovery programmer, and performed the physical reset
and disconnection. 2205 and all other boards were untouched. Existing kit
ZIPs/assets were verified unchanged. F was never rebuilt or written.

The [sanitized receipt](../validation/2512-b0-powercut-acceptance.json) binds
actual captures, serial logs, helpers and original owner escrow. Full private
evidence: `C:\SRC\STR8-N\output\qualification\2512-closeout-20261028-r1\b0-write-powercut`.

## Normal operations

The matching OPAQUE tool programmed the commented public-ABI
[B0:9000 example](../examples/base1-b0-9000.asm), then independently read it
back byte-for-byte. Both host and device identical-image paths succeeded
without an erase or new journal record. Only B0:9 was used.

CONFIG `B 0 9000` saved the entry; `C 0` saved the default. B0 was already
enabled, so an OFF-to-ON transition was not tested. Recovery `0` directly
booted the image, then physical RESET timed out into the same saved default.
Both runs reported CPU 02 and calculated 1235. Q used the public RAM reset
ABI to return through F, where the host selected S/recovery.

## Restoring an incompatible legacy default

CONFIG `C B` correctly refused to reselect the incompatible retained b15 MON.
The sequence stopped. Independent readback proved no journal append occurred;
original RAM/ZP were restored before continuing. The refusal remains in logs.

A test-only escrow restorer checks every byte of the original retained D300
snapshot and admits only the two expected latest-page/sequence pairs. It
restores that original policy, retaining current wear counts, through a sealed
append to a verified blank page. It performs no erase and never executes MON.
Normal CONFIG/F validation is unchanged. This helper is not a public command
or a claim that old MON is compatible. One policy append replaced two planned
setting commands; nine new records were needed instead of the initial ten.

## Real USB power loss

After saving and independently checking temporary default S, a B0:9-only RAM
fixture used the ordinary durable wear reservation and erase path. It wrote
2048 A5 bytes, verified A5 in 9000-97FF and erased FF in 9800-9FFF, selected B3,
and halted with the chip idle. The intended second half was 5A.

The receiver observed USB absence for 18.61 seconds. Reconnection produced
the exact STR8N-F 0.3.0 g00000001 / BASE1 / PR05 startup and REC>. Independent
full-bank reads confirmed the exact incomplete image, committed reservation,
earlier records and untouched F. Normal OPAQUE restored the original erased
sector with another reservation; the escrow helper restored original policy.

This qualifies an incomplete opaque transaction across real power loss at a
chip-idle checkpoint. Flash-pulse brownout, torn SNBT, interrupted F, factory
migration, 65C816 and ACIA remain untested. No CPU/flash simulation was run.

## Final preservation checkpoint

| Item | Before | After |
| --- | --- | --- |
| Sequence / valid records | 952 / 20 | 961 / 29; all earlier bytes retained |
| Added pages | none | D400-DCFF; DD/DE free, DF reserved |
| B0:9 erase reservations | 5 | 9 |
| C / D / F counts | 47 / 27 / 22 | unchanged |
| Default / enable mask / entries | B / 0F / all 8000 | restored exactly |
| B0-B2, B3 owner images, frozen F | original | byte-for-byte original |
| Owner RAM 0200-66FF / ZP 00-DF | original escrow | restored and read back |

Owner RAM authority is the previously double-captured and repeatedly verified
pre-helper escrow, not a fresh original-prefix read before raw L. Final REC>,
COM4 released, no pending restoration. Old MON execution remains unqualified;
catch S on future resets when recovery is intended.

WDC migration is separate. The owner chose the current chip after the
[B3 review](2512_WDC_B3_SCOPE_REVIEW.md); this receipt does not claim migration
or first-journal provisioning has run.
