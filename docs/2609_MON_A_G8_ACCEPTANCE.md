# 2609 MON A g8: passed and retained

October 30, 2026. **W65C816SXB / 65C816 emulation / FT245, COM8.**
[Scope review](2609_MON_A_G8_SCOPE_REVIEW.md),
[public receipt](../monitors/validation/2609-mon-a-g8.json),
[current inventory](2609_CURRENT_INVENTORY.md).

## Installed A and tested behavior

MON A is now PR05 **0.1.0-dev g00000008**, matching the functional build of
the already-qualified MON B. A was installed permanently using the prebuilt
g8 image; no firmware rebuild or CPU simulation was performed. The old PR04
generation 8000000F sector and all original banks are archived in verified
private host backups; old A is no longer resident on chip.

Live A checks passed for identity/CPU16, Dump/Modify, refusal of force writes
to F/C/D, M1, W, APPS and TIME. Board-flash CLOCK read/return and MAINT LOAD
of WB2 g5 passed. PROGRAM Table, bounded BATCH and AUTO Store preview with
NO cancellation passed without a record write. Both CLOCK and the workbench
returned through the active-monitor contract to **MON A**, verified by V.

The first host check expected CLOCK Q to repeat the monitor banner; it
actually returns directly to the prompt. The driver restored and verified
owner RAM, then resumed with an explicit V identity check after Q. This was
a host assertion correction; no firmware rebuild or additional erase occurred.

With the receiver armed, one physical CPU RESET displayed the frozen
Foundation identity and selected A once. Cold A g8/CPU16 startup passed;
native Dump verified owner RAM/ZP unchanged by startup. Saved default remained
**S/recovery**, bank mask 00, all entries 8000. This did not change default
selection to A. At REC>, enter `A` or `B` to choose a monitor; Q returns to REC>.

## Exact writes and preservation

Exactly **one B3:A erase** and one native wear reservation **D300/seq1034**.
A's tracked count changed **51 to 52**. All 19 original raw journal records
remain at their original positions; the final journal has **20 valid records**.
C/D/E/F counts remain **78/48/45/31**. There were zero F writes, C/D erases,
B/E/tool replacements or boot-setting writes, and no power cut. Golden F is
the original frozen 4096-byte N-F 0.3.0 BASE1/PR05 image.

Complete before and after banks were independently captured twice and matched
the exact reviewed postimages. WDC B0, B1/B2, B3:8/9, MON B and services E are
unchanged. Fresh native owner RAM0200-66FF and ZP00-DF double escrow matched
the current owner-authorized RAM reference. Trial data and helpers were then
removed by exact restoration, readback and native Dump comparison. Final
context REC>, COM8 released, no pending restoration. No SRAM/WORKSPACE record,
clock SET, trim or PF acknowledgement was issued. Other boards were untouched.

## RTC continuity and remaining work

RTC admission validates the new preserving receipt and D300 record. Live
read-only RTC/NTP requalification and its audit passed. The existing sampler
bytes, profile, RAM authority, schedule, historical points and baselines are
retained. The adapter's admission changed; the RTC instrument did not.

A and B provide identical commands for now. This pass does not claim native
816 execution, a 2609 WDC launcher, resident ASM/DBG or complete b35 parity.
Source changes stay local; frozen F and published downloads are unchanged.
Private captures remain under `output/qualification/2609-MON-A-g8-*` in the
parent project. Public evidence contains hashes/results, not owner/vendor ROMs.
