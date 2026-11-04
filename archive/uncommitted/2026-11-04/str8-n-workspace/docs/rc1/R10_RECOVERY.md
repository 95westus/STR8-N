# RC1 r10 recovery console

Historical generation-51 result for 2512. The corrected current-RC1 approach
for 2604/2609, preserving their later features and adding the hexadecimal boot
header, is [RC1 g0034](R10_G0034.md).

Firmware build: `rc1-r10-recovery1`, monitor generation **51 / `$00000033`**,
bootstrap contract `$52313031`. The public version remains `2.0rc1`; `VERSION`
prints the distinct build identity. Distribution r10 changes firmware and must
not be described as byte-identical to v1g r9.

The isolated build is based on the qualified v1g firmware, not the later
development monitor or assembler. It incorporates the fixed-F space/status
corrections needed for this console change. Frozen releases and `src/current`
are unchanged. The shared CRC entry points remain `$FAB4/$FABD`, since existing
RC1 runtime components call them directly. MAINT's bootstrap marker reads and
VERSION's private boot symbols are relinked for the new contract.

## Console behavior

At `REC>`, `A`/`B` validates and launches a monitor, `W` reads wear without a
flash write, and `U A`/`U B` updates a slot under the existing safety rules.
Entered text is echoed in its original case. Command/confirmation text accepts
CR, LF or CRLF; a trailing command LF no longer cancels confirmation. The full
confirmation line must be a single `Y` (case-insensitive), otherwise the update
is cancelled. Overlong commands are drained and refused.

Finish the terminal line ending before sending binary, and wait for
`SEND 4096 BIN` before transmitting exactly 4096 raw bytes. A bounded settling
window consumes the confirmation's optional LF before that prompt; the raw
receiver then preserves every byte, including initial `$00/$03/$0A/$0D/$FF`.
An arbitrarily delayed LF sent after the binary-ready prompt is binary data.

Refusals identify syntax, active-slot protection, preferred-slot protection,
cancelled confirmation, invalid image/ABI/CRC, stale/equal generation,
journal/wear refusal, flash timeout, or flash verification failure. The journal
service reports a common accounting refusal when its own underlying operation
fails; this does not claim a more specific cause than the service exposes.

## Qualification and installation

`tools/build_rc1_r10.py` creates a separate output from the hash-pinned v1g
build. Two fresh links produced byte-identical firmware. The final output is
`BUILD/rc1-r10-j`; failed development attempts remain separate evidence.

- 158 recovery-console CPU checks pass on 65C02 and 65C816 E=1, including both
  upload destinations, CR/LF/CRLF and mixed endings, echo, read-only W,
  cancellation, binary framing, image/generation/protection refusals, successful
  accounted and blank-journal recovery, exhausted wear, timeout and verify faults.
- Full debugger/boot regression passes: 21 check groups on 65C02 and 24 on
  65C816 E=1, both monitor slots, 512 decoder cases per CPU and 177 direct
  instruction comparisons on 816. Application RAM remains unchanged in boot.
- The exact 2512 BF1 preimage matches every declared firmware sector and the
  immutable RTC-code admission slice. The preserving transaction has 14 sector
  transfers/erases, with durable wear reservation. Six linked-installer CPU
  rehearsals pass: successful install, stale-source refusal and corrupt-transfer
  refusal on each CPU. Full target readback and erase-accounting oracles pass.

Private evidence is under `output/qualification/rc1-r10-2512-*`. It contains
owner RAM/flash escrows and must not be published in the release archive.
The installer halts after device verification and requests physical RESET.
The later `J3` → `S` recovery test uses a software restart and must be recorded
separately, without a physical reset during that test.

## 2512 hardware result — 2026-10-23

**PASS:** BF1 generation 48 → RC1 r10 generation 51. All 14 transfers completed
and the linked installer verified the transaction. The owner pressed physical
RESET for installer exit. The captured boot reports both slots VALID, saved
default B, EDU ON, RAM `$0200-$64FF`, and a successful wear check (maximum 591).
`VERSION` identifies `Build: rc1-r10-recovery1`. All four flash banks match the
capture-bound target; B0, RTC/TZ flash and owner configuration fields match their
preimages. All 25,344 original application RAM bytes were restored and reread
twice. This is a bounded install/boot/recovery qualification, not a new soak.

**PASS:** 11 subsequent live recovery checks, with **no physical reset during
the test**. `J3` → startup `S` reaches fixed-F recovery. Lowercase input is
echoed; CR, LF and CRLF commands report active-slot refusal correctly; each
line-ending mode accepts the command and echoes/cancels `N` confirmation;
malformed `U` gives syntax guidance; `W` matches all 32 expected wear counts.
Recovery launches A, and another `J3` boots saved default B. Both are generation
51. Final full flash matches the installed target and two full RAM reads match
the restored original. Accepted-Y binary transition and destructive upload
faults were tested on CPU models; live confirmations were cancelled to avoid
unnecessary slot erases or leaving the board in raw upload mode.

Evidence:

- [Install and preservation report](../../output/qualification/rc1-r10-2512-install-20261023/install/flash-report.json)
- [Captured physical boot](../../output/qualification/rc1-r10-2512-install-20261023/install/boot-after-installer.txt)
- [Live recovery report](../../output/qualification/rc1-r10-2512-recovery-20261023/recovery/recovery-report.json)
- [Captured software recovery entry](../../output/qualification/rc1-r10-2512-recovery-20261023/recovery/J3-S-software-entry.txt)
- [Final default-B software boot and VERSION](../../output/qualification/rc1-r10-2512-recovery-20261023/recovery/J3-default-B-boot.txt)

## 2604 / 2609 assessment

Recommendation: **hold their update pending a preserving build and source-aware
qualification for their installed development code**. Both operation markers
record generation-50 development monitor/ASM extensions and fixed-F size/status/
flow changes; 2609 explicitly records profile `fixed-f-flow-size`, hash
`c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e`.
This r10 intentionally starts from released v1g, so copying its full target over
those builds could remove their later features. The 2512 planner admits only
the exact BF1 source and is not a 2604/2609 updater. Their markers show no pending
restore/reset; fresh readbacks and per-board plans would still be required.
No 2604/2609 serial ports were opened or firmware changed by this work.
Native applications/debugging and electrical power-loss atomicity are excluded.
