# 2512 Foundation saved-default WDC launcher trial

Prepared October 30, 2026 after the owner continued the proposed launcher,
temporary B0 default, physical RESET and full restoration sequence. F stays
golden. This is a Foundation opaque-image boot test, not WDC factory migration.

## Exact writes and order

| Step | Mutation | Journal append |
| --- | --- | --- |
| Install | Erase/program B0:8000 with the verified project launcher | C800 / 1038, B0:8 count 8→9 |
| Select | CONFIG `C 0` saves the temporary B0 default | C900 / 1039 |
| Boot | One owner-operated physical RESET; no chooser key; WDC identity/readback | No write |
| Return | WDC uploads/readback-checks a RAM return to public B3:F004 RESET; receiver selects S | No write |
| Restore policy | CONFIG `C B` restores B with the original MON generation 00000008 | CA00 / 1040 |
| Restore image | Erase/program B0:8000 back to the original FLASH image | CB00 / 1041, B0:8 count 9→10 |

**Two erases total, both B0:8. Four C/D appends; zero F writes, C/D erases,
MON A/B/E rewrites or power cuts.** B0 is already enabled at 8000, so no bank
enable/entry write is needed. All 24 original records remain at their original
addresses. The reserved CF00 intent page is not consumed. Final record count
28, sequence 1041. C/D/E/F counts remain 53/33/28/24 and B0:9 remains 14.
These are conservative tracked attempts, not lifetime totals.

The original B default is restored and independently verified **before** the
second B0 erase. Original FLASH bytes, bank enables/entries, unknown-history
mask and other boot fields must be restored/preserved. New wear records remain;
restoration must not roll counters back.

## Launcher and return

The [project launcher source](../apps/examples/wdc-b0-launch.asm) assembled once:
133 code/data bytes, padded to one 4096-byte opaque sector at B0:8000. No F or
existing RAM component was rebuilt, and no CPU simulation ran. It checks the
pinned SXB2 identity, serial vectors and debugger-entry fingerprint, initializes
FT245, prints `WDC B0 / BASE1 DEFAULT BOOT` and enters vendor Main at F8A6.

The owner-supplied WDC B0:F sector must already match SHA-256
`ce5415f4e5032e44a19a2ab801ca9090fd81434355421d1913fca86a62f5a44b`.
The launcher contains project code and compatibility fingerprints, not a vendor
firmware image. Its Main address is private to that pinned 65C02 ROM.
F818 reset, the CS/lamp sweep, EDU VIA DDRB write and application timeout are
bypassed. No vendor flash/erase or execute-application command is admitted.

A cold opaque boot has no active MON slot. Therefore the RAM return uses public
**RESET**, not HOLD. The receiver catches the Foundation chooser with S and
returns to recovery; it does not let the temporary B0 default loop again.

Launcher sector SHA-256:
`94e3451a25bcb1cf5337d91345144b1d3ca38474ba48e2ef136391bfd646ab26`.

## Fresh admission and reset evidence

Before any write, capture native owner RAM 0200–66FF and ZP 00–DF twice, and
independently read all four banks twice against the latest preserving checkpoint.
Durably save the originals. Compare every mutation's exact sector and complete
bank postimages. Verify the temporary default and restore owner RAM before
arming the physical RESET receiver.

Ask the owner to press only 2512 RESET once, keep USB power connected, press no
chooser key and let the countdown finish. The host sends no bytes during this
physical-startup capture. Require the frozen F identity, full 6→0 countdown,
launcher banner, exact WDC identity and independent visible-B0 reads. A saved
serial-log interval proves that the host sent no chooser key.

After restoring policy and FLASH, double-read all final banks and verify every
original journal record. Restore/read back owner RAM/ZP through BASE1 and
native Dump. Finish at MON B / B3>, COM4 released. The shared lease yields to
RTC collection before this critical unit; clock, trim, power-fail flags, SPI
PROGRAM/WORKSPACE data, sampling profile and baselines stay unchanged.

Any failure stops without automatic flash retry. Keep power, backups and phase
logs. Unknown WDC protocol state needs an armed golden-F recovery receiver;
do not send recovery text blindly. Other boards, release downloads and remote
Git state remain outside the trial.

Success qualifies physical RESET through Foundation's saved-default B0 launcher
for this pinned 65C02 ROM. It does not qualify hardware bank-selector boot
directly into vendor F818, another vendor version/CPU or NFM2 factory migration.

Private plan:
`C:\SRC\STR8-N\output\qualification\2512-WDC-default-boot-scope-20261030-r1\plan.json`

Plan SHA-256:
`281edb36ae09cbe76806a055630f4131990da20dd4563c3b6eeb5757a6f25a40`.
