# 2512 golden-F C/D interruption recovery: passed

October 28, 2026 local time (October 29 UTC), 65C02 / FT245 / Windows.
The owner approved the [reviewed B3 scope](2512_CD_RECOVERY_SCOPE_REVIEW.md):
one erase each in C and D, six controlled USB power cycles, and no F writes.
All 19 reviewed phases completed on 2512. No other board was accessed; 2205
remained excluded. No F rebuild, CPU/flash simulation or release-kit update ran.

The [sanitized acceptance receipt](../validation/2512-cd-recovery-acceptance.json)
binds the actual captures, serial logs, source hashes and restoration evidence.
Private packets, original backups and intermediate journal snapshots remain at:
`C:\SRC\STR8-N\output\qualification\2512-cd-recovery-20261028-r1`.
The source-bound [JCR1 lab protocol](JCR1_LAB_PROTOCOL.md) describes the RAM tool.

## Observed interruption cases

Two fresh complete-bank captures admitted the exact reviewed starting state.
Temporary default S kept every power return in golden BASE1 recovery. Each cut
occurred only after the chip was verified idle at its exact checkpoint.

| Cut | Captured checkpoint | Verified recovery |
| --- | --- | --- |
| 1 | C300/967, first 128 bytes written, commit FF | C200/966 stayed selected; exact partial page completed and committed last |
| 2 | C400/968, complete payload verified, commit FF | C300/967 stayed selected; payload rechecked and commit completed without erase |
| 3 | C500/969 committed, normal acknowledgement withheld | Existing committed record recognized; no write, append or erase |
| 4 | CF00/979 intent committed with D erase reserved; D verified blank | Surviving C intent selected; original D000/963 restored, then current D100/980 published |
| 5 | D200/981, first 128 bytes written, commit FF | D100/980 stayed selected; exact partial page completed and committed last |
| 6 | DF00/994 intent committed with C erase reserved; C verified blank | Surviving D intent selected; original C000/964 and C100/965 restored, then current C200/995 published |

Native bounded same-policy fills reached the reserved rotation pages. Both
rotations committed and verified the erase reservation before erasing the
peer. Older restored rows never displaced the newer surviving intent or
rolled its counters back. Final C300/996 restored the original boot policy,
configuration and pinned generation without executing the legacy MON image.

## Final preservation and accounting

Counts are decimal tracked erase reservations, not lifetime erase totals.

| Item | Before | Verified final |
| --- | --- | --- |
| Latest sequence | C100/965 | C300/996 (000003E4 hex) |
| Committed records | 3 | 20 |
| Original records | C000/964, C100/965, D000/963 | Exact original bytes at all three original addresses |
| C / D / F counts | 49 / 29 / 24 | 50 / 30 / 24 |
| Other counters and unknown-history mask | Original | Unchanged; mask FFFFFFFF |
| Default / mask / entries | B / 0F / all 8000 | Restored exactly |
| Application configuration / pinned generation | Original | Restored exactly |
| B0-B2 and B3:8/9/A/B/E | Original | Byte-for-byte unchanged |
| B3:F | Frozen BASE1 4096 bytes | Byte-for-byte unchanged, zero erases/writes |
| Owner RAM 0200-66FF / ZP 00-DF | Original pre-helper escrow | Restored and independently read back byte-for-byte |
| Final context | REC> | REC>, COM4 released, no pending restoration |

Every phase received independent complete-bank readback; the final four banks
were read twice and matched the reviewed final bytes. The original three
records remain physically present; intermediate rotation records are archived
privately on the host. No history or counter rollback was used.

RAM authority remains the original pre-helper escrow repeatedly restored and
verified in the preceding acceptance cases. This is not a fresh read of the
original prefix after raw L has overwritten it. Final RAM SHA-256 is
`1e1e8f62ac65a68206d8936ce9ce65c871e0428b5114193c65b3ba0c2838dda4`;
ZP SHA-256 is
`30b1c0333c3e83a73c1abce7bd3e1fb200edf07207f485910d45cae46f816978`.

Frozen F remains STR8N-F 0.3.0 g00000001 / BASE1 / PR05, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
All frozen source bindings and existing release-kit asset hashes still match.
Legacy MON/FLASH execution remains unqualified; select S when recovery is
intended on later resets. The original B policy was preserved as requested.

## Transport interruption and evidence limit

After USB cycle 2, Windows enumerated the adapter before its COM4 endpoint
could open. The original driver stopped before sending the next board command.
Read-only inspection independently matched all four banks to the exact
precommit checkpoint and restored/verified owner RAM. One additional physical
RESET captured the full frozen BASE1 recovery identity; it performed no flash
write and was not an additional USB power cycle.

The exact measured cycle-2 USB-off duration was lost with that exception.
The executed check establishes at least three seconds; the operator was
instructed to wait five. Direct REC> observation and the later physical RESET
identity are retained separately. The other five measured off intervals were
87.125, 18.000, 10.343, 13.640 and 6.875 seconds, respectively.

An inspected host continuation admitted the same state through a fresh double
capture and resumed at phase 5 with the original sealed RAM packets and erase
budget. It only added bounded retries of failed endpoint opens before board
commands. No flash operation or earlier trial phase was retried. The original
failure log, read-only inspection, RESET capture and continuation are preserved.

## Qualification boundary

This closes the six named chip-idle C/D interruption cases on 2512/65C02/FT245
from golden REC>. It does not cover electrical interruption during an active
flash pulse, arbitrary corrupted/conflicting records, every layout, or other
CPUs/adapters. F itself remains assumed golden; interrupted-F recovery was not run.

JCR1 is a separate source-bound lab tool, not a general release repair command.
Its partial completion and original-row restoration require the exact reviewed
preimages and fingerprints. The production CONFIG writer and general damaged
journal classifier remain unchanged and strict. Programmer-installed-F live
provisioning still has its separate hardware acceptance gate. Existing kit
ZIPs/manifests remain their earlier package snapshot.
