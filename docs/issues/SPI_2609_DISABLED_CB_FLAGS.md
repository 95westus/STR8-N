# STR8N-003: disabled VIA CB flags block SPI after RESET

Status: **Closed**, 2026-10-09, with beta22 generation 31. Board 2609,
W65C816SXB with EDU; originally observed on beta15/beta17. This is
separate from the closed wrong-RESET-button observation STR8N-002.

During beta17 installation, the resident preserving SRAM reader refused with
status $01. Read-only VIA snapshots before and after the reset/IRQ qualification
showed IFR=$1A, IER=$80, PCR=$00, ACR=$00, DDRB=$00. CB flag bits $18 are
pending, but their interrupts are disabled; the port is idle and select pins
are inputs. The conservative SPI preflight rejects these flags. A/B cold boots
therefore display `SSRAM: Unavailable` even with EDU fitted.

The separately guarded qualification helper verified disabled CB interrupts,
compatible PCR mode and undriven selects before reading ORB once. This cleared
the CB flags (IFR became $02) and restored normal SRAM access. Both complete
131,072-byte SRAM comparisons passed afterward. This acknowledges VIA flags;
it is unrelated to CLOCK ACK or RTC power-fail evidence.

Evidence is owner-local under
`output/qualification/storage-beta17-2026-10-08/2609`: `via-prior`, `via-setup`,
`via-final`, `via-final-setup`, and the refused/successful SRAM read logs. Raw
evidence stays ignored. The installed acceptance report explicitly marks
unattended SPI startup on this board as unqualified.

Reproduce with physical S2/RESB or the public cold RESET and inspect the boot
SSRAM line/VIA snapshot. Close only after a reviewed driver/reset policy passes
repeated physical and software cold RESET on 2609, ordinary 65C02 regression,
active-owner/interrupt refusal cases, and full SRAM/RTC/EEPROM preservation.
The beta17 installation did not change the conservative driver policy.

## October 9 beta21 reproduction and startup candidate

Board 2609 was upgraded to the audited beta21 / CLOCK 1.6 local-time display
image. All four installed banks matched the prepared final images after physical
S2/RESB RESET. CLOCK TRIM remained -14; RTC outage history and EUI were unchanged.
The startup limitation remains present in beta21.

A RAM-only comparison after another physical RESET reproduced the complete
failure and recovery with a verified READ request: IFR=$1A, IER=$80, PCR=$00,
ACR=$00, DDRB=$00; the resident SRAM READ returned $01. The candidate guard
acknowledged only the disabled CB flags, leaving IFR=$02. The same READ then
returned $00 with all 64 bytes delivered and DDRB still $00. No firmware or
SRAM data writes occurred. Owner-local evidence:
`output/qualification/spi-startup-2609-2026-10-09/guard-cold-2`.
The earlier overlong-request attempt and corrected warm comparison are retained
separately; they are not evidence for the cold-start comparison.

An isolated, **unflashed** beta22 candidate in `BUILD/v2-spi-startup` adds a
cold-boot-only preflight to the sealed status asset, after checking the resident
SRAM service signature and before the first allocation read. It refuses enabled
CB interrupts, nondefault CB modes, shift/latch owners, driven SPI pins and both
resident busy owners. Only idle disabled CB flags may be acknowledged; all
other flags remain pending. TIME and EDU queries do not acknowledge these
flags, and the resident SPI API remains conservative. The status code occupies
2551 of 2558 available bytes. Executed tests against the exact linked guard
passed 44 caller-status/owner cases plus both busy-owner cases.

The candidate cold-boot integration model also passed recovery of the observed
idle flags, refusal of enabled CB interrupts, unchanged SRAM/RTC/EEPROM/flash,
and explicit EDU/TIME query non-acknowledgment. The full local-time/CLOCK model
passed. Two complete 131,072-byte board SRAM readbacks matched before any
candidate installation (SHA256
`0e769960d5e945c1b3cab9c5d496105db91a2f14c6b0d70ff558534c19757bac`).
Quiet A/B monitor returns and the public RTC/service lifecycle regressions
also passed, with report artifact hashes bound to this candidate. CLOCK 1.6
and the local-display asset remain byte-identical to beta21. The owner-local
`investigation-summary.json` records the completed checks and remaining work.

Before installation, status remained **Open**. Repeated physical/software reset qualification,
ordinary 65C02 board regression and complete post-install preservation checks
were required before accepting this as the permanent fix. Beta22 was not installed at that stage.

## Monitor request length comparison

On October 9, harmless RAM display commands on USB-identified 2205/COM3 and
2609/COM8 both accepted 40 characters and rejected 41 and 54 with `Long line`.
The spaced 16-byte M request is 54 characters; an eight-byte M request is 30.
The overflow is a shared monitor limit, not an 816-specific SRAM failure.
Owner-local evidence is
`output/qualification/monitor-line-limit-20261009T182555Z/report.json`.

The shared host `Link.write_ram` now stages eight bytes per command, stops on
monitor rejection, and verifies the complete readback. SPI qualification writers
use it. The corrected transport was verified on both boards by restaging 16
unchanged scratch bytes; no firmware or stored device data was written. Host
failure tests cover rejected commands, readback mismatch and RAM boundaries.
This fixes the test-request transport; it does not increase the firmware's
interactive line limit or close the separate SPI startup issue.

## Beta22 resolution and hardware qualification

The user authorized beta22 flashing on 2512, 2205 and 2609, excluding the new
2604. One unified generation-31 build was installed with backup-bound exact-image
installer rehearsals. All three uploads verified, and post-RESET readback matched
every expected flash byte. Saved EDU settings and records were preserved.

Receive-only captures (TX=0, DTR/RTS inactive) recorded **two physical main-board
resets on each board**. 2609 used S2/RESB. Both EDU boards reported
`SSRAM: Allocation uninitialized`, reflecting their retained metadata; neither
reported `SSRAM: Unavailable`. No formatting or manual CB acknowledgment was
used. Three A/B/A software cold boots also passed on each board. Actual SRAM
READ calls after the second physical reset succeeded from caller banks 0–3 on
both 2205 and 2609. Read-only VIA snapshots then showed IFR=$02, IER=$80,
PCR=$00, ACR=$00, DDRB=$00 without acknowledging flags in the snapshot helper.
2512 retained EDU OFF and omitted all device blocks.

Complete 128 KiB SRAM comparisons matched the repeated pre-flash backups on
both EDU boards. EEPROM user/factory inventory, RTC outage history and EUI were
unchanged; normal trims remained -18 on 2205 and -14 on 2609. UTC was never set.
Quiet M1 returns and explicit TIME weekday/local/trim output passed. Enabled
IRQ, shift/latch, pin-owner and busy-owner refusals passed 46 executed cases
against the exact linked candidate code; these hostile ownership states were
not deliberately introduced on hardware.

Owner-local evidence and hashes are recorded in
`output/qualification/beta22-all-2026-10-09/qualification-summary.json`, with
per-board `qualification.json`, `installed-check`, `repeat-check`, `repeat-via`,
device inventories and SRAM comparisons. Physical captures are in
`physical-boot` and `physical-boot-repeat`. STR8N-003 is closed for the qualified
65C02 and 816-emulation configurations. Native 816 mode and board 2604 are
outside this qualification.
