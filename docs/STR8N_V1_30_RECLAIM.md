# STR8-N v1.30: resident space reclamation

## Scope and measured result

This is a behavior-preserving size release, not a RAM ABI or worker redesign.

| Region | v1.29 | v1.30 |
| --- | ---: | ---: |
| Resident code | 3,236 bytes | 3,172 bytes |
| Resident data | 178 bytes | 178 bytes |
| Resident total | 3,414 bytes | 3,350 bytes |
| Last resident byte | `$FD55` | `$FD15` |
| Margin before `$FD5C` worker | 6 bytes | 70 bytes |
| Stored worker | 596 bytes | 596 bytes, identical |

The 70-byte margin is `$FD16-$FD5B`, filled with `$FF`. The layout check now
requires at least 64 bytes. Directory `$FFB0-$FFEF`, configuration
`$FFF0-$FFF9`, vectors, and public entry addresses remain fixed. Resident ABI
V1/caps `$3F`, parser ABI V2/caps `$03`, worker ABI V2, and RAM ABI `$12` stay
unchanged. WORK remains B1:E and top backup B1:F.

Changes:

- Replace the 7-byte private wrapper plus 53-byte generic delay with a
  15-byte fixed-X/Y routine: 45 bytes saved. Remove `src/util-delay.asm` and
  its link/build rule; Git retains the prior source. `$7EDE-$7EDF` are no
  longer touched by STR8-N.
- Exclude the 11-byte full-byte hexadecimal prologue from the release. Its
  sole callers are historical, non-V1 RAM proof code; the nibble/high-nibble
  routines remain live. Preserve that proof-only source behind its guard.
- Remove 8 bytes computing/storing/reloading an unread sector count. The
  range parser retains start and exclusive limit; `$00A3` is no longer used.
- Retarget ten compact message calls to page `$FC` after relocation.
  Keep the banner's `MSG_BOOT_PROMPT` fall-through: the initial review's
  classification of this string as dead was incorrect. No strings removed.

The private delay accepts the existing nonzero A values `$23`, `$49`, and
`$6A`, with fixed X=`$B6`, Y=`$F8`. It returns A=X=Y=0 and carry set. Linked
branches stay within one page. At 8 MHz, excluding the caller's JSR, its
cycle count is `A * (182 * (5 * 248 + 6) + 6) + 7`: respectively 0.992155,
2.069350, and 3.004809 seconds. This is slightly shorter than the generic
loop; it is not a promise of cycle-identical timing. Quarantine/live tick
counts, key polling, and EDU initialization remain unchanged.

## Host validation

Run `make all` and `make release-package`. `make resident-reclaim-check` is
also available separately. The new binary regression checks all 26 emitted
compact message calls, the banner and page-boundary strings, exact delay
opcodes and branch pages, and 1,560 executions of the linked range parser
using a small instruction harness with console/line-input stubs. It checks
the released `$A3` byte remains untouched. Existing layout, S19 range matrix,
RAM-load, RAM ownership, updater, console probe, migration, and public-contract
checks are retained. These host checks do not substitute for board proof.

Canonical top BIN SHA-256:
`60B7FE19E42766AACFCDEF8320A35D9D5AB7C5F91F0FE3130041F2CFF4799734`

Worker S19 SHA-256 (unchanged):
`04F46E258924F07510FB113EDB00C788EBA129EAB98B25C284D6AB15C306E69C`

## Board evidence — 2026-09-05, COM4

The board initially ran v1.29 with HIMON `00.0902(1707)`. A complete HIMON
top-sector dump matched the v1.29 factory BIN outside its live directory.
The owner-local exact pre-update image is retained at
`BUILD/v1.30/local/pre-update-b3-f.bin` (SHA-256
`8DCDAA318F8499126FEDC053A9A9A301B241F5662AFEBB384A379F8EE2595FAF`).

The v1.30 RAM updater was loaded through `L`; it reported `BACKUP VERIFIED`
with old-sector sum `$2AF1`. Only then was `STR8-N 1.30` confirmed. It reported
`STR8-N 1.30 VERIFIED; RESET`, displayed the intact selector, and accepted `S`.
`C` then printed `BOOT COLD`, `RAM ZERO OK`, and the HIMON prompt.

A full post-update readback matches all 4,032 non-directory bytes of the
canonical v1.30 BIN, including the 70 erased margin bytes. The other 64 bytes
match the exact saved live directory. Configuration and vectors are unchanged.
The live top SHA-256 is
`4FF2F57FCF766F92369CD871584D2307005D7D181FAF68CC153812537DEAD90B`.
It differs from the factory BIN only because the live directory is retained.

The installer rejected B3:F without a write prompt, displayed correct
`I B3 C-E WRITE? Y:` and `I B0 F-F WRITE? Y:` previews, and accepted `N`
cancellation (the existing `BAD` response). No installer write was authorized
in these checks. `W` displayed `BOOT WARM` and returned to HIMON.

An uninterrupted selector timeout returned warm to HIMON. `J3` displayed
`J B3`, restarted v1.30, and likewise timed out to warm HIMON. Loading the
v1.30 console ABI probe through `L` passed ABI_QUERY, CONSOLE_INIT, CHAROUT,
raw lowercase `$71`, raw CR `$0D`, CHAR_READY empty/ready, CHARIN, and BRK.
The generated public contract include is byte-identical to v1.29.

After the probe's `PRESS PHYSICAL RESET`, the operator-triggered restart was
captured: `RESET`, `STR8-N 1.30`, intact selector, timeout, `BOOT WARM`, and
the HIMON prompt. No serial reset command was sent during that capture.

Owner-local raw exchanges are append-only in
`BUILD/v1.30/local/board-session.jsonl`; do not publish board flash dumps as
factory artifacts. A concise retained transcript accompanies this report.

Pending hardware evidence is tracked explicitly: cold-power acceptance is
not implied by the physical and software resets above.
Factory WDCMONv2 migration testing is explicitly deferred by the operator
until later (2026-09-05); it is not a blocker for this v1.30 size release and
is not claimed as tested. Destructive installer/recovery fault injection is
also not rerun by this size-release test; v1.29 acceptance stays historical.
