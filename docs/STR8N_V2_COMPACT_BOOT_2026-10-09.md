# Compact local boot display candidate

The user selected one local-time line at boot:

```text
RTCC: Fri 2026-10-09 15:11:04 (-05:00)
```

The isolated beta23 generation-32 candidate is in `BUILD/v2-compact-boot`.
It omits automatic boot UTC duplication, the short trim suffix and the EUI
line. Weekday, local date/time and the saved signed UTC offset remain visible.
UTC snapshots and hardware time are unchanged; the offset is display-only.
No saved offset defaults to +00:00. EDU OFF continues to omit device blocks.

The candidate's R EDU pending-mode status now explicitly prints
`RESET required: ON` or `OFF`, after the active EDU line. The existing
`Saved; RESET required.` save notice remains. Models verify persistence through
ordinary return, activation at cold RESET, notice clearance and canceled changes.
Immediate CLOCK OFFSET/SET/TRIM changes do not require a reset.

EUI remains visible in R EDU, CLOCK startup and CLOCK EUI. Explicit TIME retains
UTC/local output and configured trim correction. CLOCK 1.6 is byte-identical to
beta22. Boot outage/evidence processing and the qualified disabled-CB SPI guard
remain intact; private helper references relink with the changed formatter.
This is still one C02/816-emulation firmware with optional EDU.

The display regression checks the exact chosen line, default UTC offset,
fractional-offset date rollover, detailed TIME/EDU/CLOCK output, EUI visibility,
EDU OFF and storage/register preservation. Quiet-return, RTC kernel, SPI API,
journal, startup integration and the 46 guard cases bind to the final candidate.
The SPI model fixture now initializes VIA IER to its actual reset read value
$80 instead of generic RAM filler; beta22 default startup passed that corrected
fixture as a cross-check.

The build and model receipt audit is
`BUILD/v2-compact-boot/compact-boot-candidate-check.json`; the model preview is
`compact-boot-preview.txt`. No boards have been flashed with this candidate.
Current installed firmware remains beta22. The [phase 1 freeze and fresh
backup-bound rehearsals](STR8N_V2_BETA23_PHASE1_2026-10-09.md) passed on all
three board images. Post-flash hardware checks remain required for a future
authorized update.
