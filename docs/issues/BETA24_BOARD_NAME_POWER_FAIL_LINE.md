# Issue: beta24 board name joins the power-fail status line

ID: STR8N-006

Status: **Closed**

Opened: 2026-10-14

Resume condition: none

## Impact

Beta24 generation 33 prints a retained board name immediately after the RTC
power-fail status text, without a separating newline. The label is retained
and readable, but is not a distinct boot line. This leaves the named power-on
formatting qualification open.

## Reproduction and evidence

Physical 2604 (COM5, A10MQGVHA) and 2609 (COM8, A10MPQXCA), beta24 generation
33 / MAINT 2.0, EDU ON. Assign `LAB-2604` or `LAB-2609`, then remove main-board
power for about ten seconds and restore it with the backup batteries installed.
The owner confirmed this power cycle. Queued receive-only USB output contained:

```text
2604: RTCC: PF logging failed.Board: LAB-2604
2609: RTCC: PF logged, ACKBoard: LAB-2609
```

Expected: `Board: LAB-2604` / `Board: LAB-2609` on its own line. Both boards
then printed their compact local clock line and reached B3. The initial boot
header was not captured; the power-fail portion, board labels and ready prompts
were captured. Complete installed flash comparisons separately identify the
tested beta24 image.

Owner-local evidence is
`output/qualification/beta24-tests-2026-10-14/retry1/{2604,2609}/power/boot.txt`
and `capture.jsonl`. See [qualification results](../STR8N_V2_BETA24_QUALIFICATION_2026-10-14.md).

## Findings

Ordinary named J3 startup passed on both A/B monitor slots. The defect was
observed on both successful outage logging (2609) and the preserved foreign
EEPROM logging-error path (2604). NAME set, rename, clear and record readback
already passed; this observation is a display formatting defect.

The local-display builder inserts `BN_SHOW` before the existing local clock
renderer. `BN_SHOW` prints its label and trailing newline but has no leading
newline. A missing boundary between the power-fail text and this inserted
display is the likely cause; the cold-entry formatting contract needs a
targeted model check before changing firmware.

## Next action

Add power-fail-success and logging-failure model fixtures with a retained name,
then repair the cold-boot line boundary without adding output for unnamed
boards or ordinary monitor returns. Qualify a separate candidate before
updating either board.

## Close criteria

Both power-fail paths print the name on its own line in model and physical
boot captures. Normal named/unnamed startup, EDU ON/OFF and quiet-return tests
continue to pass. Flash, RTC, EEPROM, identity and SRAM preservation checks
pass, with all intended name/configuration appends accounted.

## Resolution

Closed October 14, 2026. The cold-entry local helper reads the retained name,
omits all extra output when it is unset, and emits CRLF before a nonempty label.
Ordinary returns still bypass this path. The sealed helper remains 1792 bytes;
code grows from 1749 to 1760 bytes. Fixed recovery, monitor slots, MAINT,
CLOCK and service binaries are unchanged.

Fixed asset SHA256:
`d6ffa85417799b9060eba3d65058f6432f914f3ac8e9fbb0da326733332a6281`.
Candidate: `BUILD/v2-board-name-fix006`, beta24 generation 33.

The new regression fails on the original named logging-success case and passes
on the fixed named/unnamed logging-success and foreign-layout cases. NAME,
compact-boot and timezone suites pass, including 20 NAME and 13 timezone
interrupted-write checkpoints. Both backup-bound two-sector installers pass
exact-image rehearsal, stale-source refusal and corrupt-transfer refusal.

Physical power-on captures on 2604 and 2609 show the label on its own line
after logging failure and logged/ACK text respectively. Full 128 KiB SRAM
retention, exact final flash, named EDU OFF/ON, final B/A startup, RTC settings
and original-name restoration passed. The update rewrote only B2:E and B3:C
wear metadata. See [fix deployment and retest](../STR8N_V2_FIX006_RETEST_2026-10-14.md).
