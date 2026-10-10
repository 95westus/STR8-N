# Beta23 four-board storage and recovery qualification

The user expanded the beta23 test matrix to **2512, 2205, 2604 and 2609**.
All four currently use EDU ON and normal TRIM 0 for the separate synchronized
UTC drift campaign. This supersedes the earlier three-board exclusion of 2604
and the earlier -18/-14/-16 trim settings. Historical receipts remain intact.
No UTC SET, TRIM, ACK, identity acceptance or EEPROM edit is part of these tests.

## Evidence and scope

Owner-local evidence is in
`output/qualification/beta23-flash-recovery-2026-10-09-1929`.
Each board has fresh matching independent full flash reads, repeated complete
128 KiB SRAM reads, RTC/control/identity/history captures and repeated
EEPROM/factory inventory before mutation. The zero-trim reference is
`output/qualification/rtc-zero-trim-campaign-2026-10-09-231026Z/baseline-index.json`.
The drift campaign remains independent; no baseline or sampling schedule was changed.

2604's preinstalled firmware was compared with frozen beta23 generation 32.
Its A/B/A J3 startup, confirmed/canceled ON-OFF-ON changes, pending notice
persistence, cold activation/clearance, reclaimed RAM, RAM ABI, actual BRK/VIA1
IRQ and physical NMI tests passed. Original EDU ON was restored. Full flash
matches the modeled two configuration-journal appends; firmware bytes are unchanged.
J3 supplies the cold reset path for these tests; physical NMI checks use the button.

The flash/SRAM test runs the actual native `S 2 AUTO`, restore-only and run
commands, MAINT 1.8's verified flash-to-SRAM and SRAM-to-AUTO-flash copies,
cancellation, source retention, matching executable payloads, tables,
J3 record retention and SRAM deletion. B2:8 is required to be entirely erased
and is backed up before any test writes. No occupied destination is replaced.

The exact sequence and cleanup passed models of the frozen beta23 image.
An early model fixture assumed that MAINT preserves an application execution
counter; it was corrected to initialize that counter after leaving MAINT.
Hardware then exposed a host prompt expectation: native AUTO save leaves the
monitor at `B2>`. The first three saves succeeded, but the original harness
waited for `B3>` and its cleanup failed. Those attempts remain under
`flash-roundtrip`. The corrected `flash-roundtrip-prompt-fix` resumes only from
the exact known saved record, normalizes monitor bank selection and retains
all failed captures. This was a host-test correction; the firmware was unchanged.

Cleanup restores the original erased B2:8 using MAINT's read/fill/verified
write path. All other flash bytes must match the prior images. Its one erase
is accounted as **B2:8 +1**, with one metadata sequence advance and unchanged
saved configuration. Every SRAM block is compared with the complete repeated
backup; changed blocks are restored and reread. A final J3 clears transient
workspace session state while leaving EDU ON. Final RTC/EEPROM/history/EUI
comparisons passed on all four boards. Native AUTO/save/restore/run, both
verified MAINT copy directions, cancellation/source retention, J3 record
retention and SRAM deletion pass. Complete original flash and SRAM contents
were restored; only the one accounted B2:8 erase and corresponding wear-journal
update remain. Saved settings were preserved. 2604 also passed all-bank RTC
and SRAM reads with restored caller-bank state.

The successful four-board summary is `qualification-summary.json` in the run
directory. 2604's core/mode/interrupt reports are directly under `2604`; its
fresh post-mode flash backup, copy/restoration and device reports are under
`2604/flash-phase`. The three original boards use the successful
`flash-roundtrip-prompt-fix` reports. All four were left EDU ON, normal TRIM 0
and at monitor prompts, with serial ports released before the 19:55 sample.

## Other completed checks and remaining gates

The extended read-only hardware run from approximately 21:02 through 21:46
CDT passed **141 rounds on each board**: 564 RTC caller-bank calls, 564 changing
SRAM-address reads, 36 actual ABI/BRK/VIA1 IRQ probe pairs and 12 alternating
A/B cold starts. Every round checked bank restoration, retained data, advancing
UTC, protected services and quiet M1 return. Final complete flash/SRAM and
strict EEPROM/history/EUI/control comparisons passed. This short endurance
window is separate from the outstanding 48–72-hour soak.

Forced fixed-F recovery then passed on all four boards: cold `S` entry,
read-only `W` wear reporting, checked A and B returns, restored EDU services
and cleared transient WORK session. Final complete flash/SRAM and strict
EEPROM/history/EUI/control comparisons passed again. `fixed-recovery-check`
contains the reports; every runner closed its port by 21:49:19 CDT. All four
were left EDU ON, normal TRIM 0, original display offsets and ready monitor
prompts before the 21:55 drift checkpoint. The run's `qualification-summary.json`
binds all phases, current flash/SRAM hashes, frozen-image model reports and the
clean-checkout receipt. No UTC or trim change was part of this window.

The 20:02–21:50 test window uses
`output/qualification/beta23-final-matrix-2026-10-09-2003`.
Each of the four boards has passed all four WORK allocation sizes, claims,
owner/bounds/overlap refusal, release and J3 stale-handle rejection. Complete
original SRAM contents were restored and verified.

Attached-EDU standalone OFF tests passed on all four: S19 loading and execution
at `$6500`, the entire reclaimed 512-byte pattern, unavailable TIME/CLOCK/SRAM/
WORK paths, all-bank service refusal and preserved live PCR. Returning to ON
restored the `$64FF` limit and protected edits/execution at `$6500`. Two early
host assertions were corrected: an early missing-service refusal does not
populate the later PCR result fields, and the monitor cannot dump IO address
`$7FEC`. A RAM snapshot now checks actual PCR. Failed attempts and successful
restoration remain archived; each OFF/ON attempt's two configuration appends
are accounted. No firmware byte changed.

SRAM hardware fault tests passed payload/header CRC refusal, unpublished
record invisibility, destination preservation, no corrupt execution and
explicit verified-secondary layout repair. The original complete arrays
were restored. These controlled retained fault states complement the frozen
write-cut models; they are not a claim that every in-flight byte was physically
interrupted on hardware.

The same four cases also passed after actual cold J3 restarts on every board.
Each cold boot left the staged fault bytes unchanged: CRC-invalid payload/header
still refused, unpublished records remained invisible, and an unpublished
primary layout required explicit verified-secondary repair. The full original
array was restored and reread afterward. `storage-faults-cold` holds those
transcripts; `storage-fault-cold-model.json` binds the modeled sequence.

Actual main-board power removal at 20:43 CDT was captured receive-only, including
USB disconnect/reconnect and all four beta23 starts. Post-power verification
matched every byte of all four flash banks and the entire 128 KiB SRAM array
against pre-power snapshots. UTC advanced in agreement with elapsed host time;
normal TRIM 0, control registers, EUI and binding states were preserved. Cold
WORK session state was `01 00` before a workspace query. Retention used the
installed backup batteries; this test does not measure their remaining capacity.

2512 saved its first valid outage record, sequence 1, without binding its EUI.
2205 saved sequence 9 in slot 1 and 2609 sequence 14 in slot 2, replacing only
the expected oldest ring entries. Their other three slots and factory/status
bytes were exact. Startup performed its ordinary automatic acknowledgement.
2604 retained its foreign EEPROM layout byte-for-byte, reported logging failure
and retained the power-fail latch. No explicit ACK, CLEAR or ACCEPT was issued.
All original outage snapshots remain archived.

Hardware OFFSET tests passed `+05:45`, `-03:30`, `-12:00` and `+14:00`, immediate
TIME output, prior-day rollover and compact J3 startup persistence. Invalid
offset/date/trim commands, OFFSET cancellation (`NO` and `Y`), canceled UTC
SET/TRIM and unchanged OFFSET left settings untouched. Original offsets were
restored: 2512/2604 `+00:00`, 2205/2609 `-05:00`. Exactly five new committed TZ
records per board are accounted; existing records, identities, all firmware
and wear records are unchanged, with no erase. Full SRAM and strict post-power
EEPROM/history/EUI/control comparisons passed. No UTC SET or TRIM was confirmed.
The frozen formatter model also passes month/year/leap-day boundaries,
out-of-range/corrupt/uncommitted records and all 13 interrupted TZ-append cuts.

The earlier 19:05–19:20 window passed hardware SRAM save/table/restore/run/
delete/reclaim, all four allocation sizes, all-bank claim access, owner/bounds
refusal, overlap refusal, release and J3 stale-handle refusal on 2205/2609.
Both original complete SRAM images were restored. Additional frozen-image
models passed interrupted replacement/format/upgrade/delete/reclaim,
partial/short transfer, bus failure and counter exhaustion coverage.

`tools/reproduce_v2_beta23.py` rebuilt beta23 and its prerequisites from the
retained source snapshot with **no prebuilt firmware inputs**. All 17 compared
firmware/utility artifacts match the frozen bytes. The receipt is under
`tmp/beta23-source-reproduction-2026-10-09/BUILD/reproduction-receipt.json`.
The corrected clean-checkout workflow also passed under `tmp/b23repro`:
private snapshot commit `505bb36bc9ac9802aab083abdd723d84eeabd467`, all 540
frozen source files byte-exact, all 17 compared artifacts matching, clean before
and after. `tools/reproduce_v2_beta23_clean_checkout.py` requires a fresh short
workspace temp path, preserves bytes with `* -text` and ignores generated
distribution output. Earlier long-path WDC assembler and Git line-ending
failures remain archived. This proves the retained source snapshot; a reviewed
public RC source commit/tag and final release packaging remain separate gates.

A local validation ZIP under `BUILD/beta23-validation-bundle` passed a strict
allowlist, archive CRC and all 17 frozen hashes. It includes no board backups
or installers and is not a release package. No release approval is implied.

The applicable four-board functional, preservation and controlled recovery
checkpoint is complete within the documented scope. RC acceptance still requires
the **48–72-hour soak on 2604/2609**, final
package and operator-document verification. The soak has not started.
STR8N-001 ACIA receive on 2512/2205 remains deferred; advertise qualified USB
console behavior. Native RTC/I2C and the other documented RC exclusions remain.
