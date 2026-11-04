# 2512 dense flash S19 and large flash STORE review

November 1, 2026. **The reviewed ten erases were approved and completed.**
Positive Store/Table/Restore and two-sector dense S19 passed; B0 and owner
RAM/ZP were restored. Installed checks then found a STATUS-padding overlap and
AUTO losing AREA during a full cache reload. See the separate
[three-erase correction review](FLASH_STATUS_CORRECTION_2512_SCOPE.md).
That correction was separately approved, installed and accepted; see
[the final acceptance](FLASH_TRANSFER_2512_ACCEPTANCE.md). The pinned original
review and failure receipts remain intact.
No further erase is covered by the completed allowance. F remains the exact golden4096-byte
STR8N-F0.3.0 g1 BASE1/PR05 image.2609/COM8 stays owner-held;2205/2604 and
published downloads remain outside this work. No power cuts or RTC-setting writes.

## Candidate behavior

Dense S19 is available inside the updated RAM FLASH utility:

```text
B3> R FLASH
FLASH/MAINT> BANK 0
FLASH/MAINT> I 9000 AFFF
Dense S19 B0:9000-AFFF; type YES> YES
SEND S19; complete ascending sectors; Ctrl-C cancels
```

Send ASCII S0/S1/S9 records. Every S1 checksum, delimiter, complete range and
ascending address is checked before staging. Only full4KiB sectors commit;
S9 requires the entire requested range and never runs an entry. A checked
record may cross a sector boundary. Errors/cancellation leave earlier complete
sectors committed; no rollback is claimed. A necessary erase gets a durable
wear reservation first. This helper refuses journal rotation instead of
silently erasing C/D. B0/B1 sectors8-D are its only accepted destinations.
The MON-level `I` shorthand is not added by this revision; use `R FLASH`.

The high-RAM record worker runs before WB borrows owner RAM:

```text
B3> STORE 0 9000 4E00 66FF WIDEFL
Flash STORE; no erase; type YES: YES
B3> TABLE 0
B3> RESTORE 0 WIDEFL L
```

S/R aliases are retained. Wide Store accepts source0200-66FF when the complete
record fits the admitted B0/B1 flash range8000-DFFF. It checks every target
byte is FF and refuses overlap with structural records, including their erased
payload bytes. It programs/verifies source bytes directly and commits SR01
last, without SPI staging or erasing. SR01 retains its existing lack of a
payload CRC. Restore validates the full header/bounds and supports load-only
through66FF; an omitted L uses the existing raw G handoff contract.

Existing native flash AUTO continues through WB's AREA/AUTO path with its
existing source bounds. This wide-Store qualification uses an explicit address;
it does not establish large flash AUTO or large returning BATCH. Interactive
raw protocols/wide Store remain excluded from BATCH. The Python terminal's
existing BIN keys are not an S19 sender.

## Why this needs a new write allowance

The fresh2512 capture shows **B0:9 is blank, B0:A is occupied**. Its prior
wear count is not evidence that it is free. A6,400-byte Store plus24-byte
header spans9000-A917, so A must be temporarily erased and later restored
from its exact archived original. B0:8's FLASH image stays untouched.

The current journal has27 valid records at sequence1120. Completing the
trial and installing four utility sectors requires one C rotation. This
replaces16 original C rows on chip; all original history and the later trial
rows must be archived on the host before rotation. Counts, boot choice,
generation binding, bank entries/mask and unknown-wear flags carry forward.
**Keeping every old record on chip is not possible within this plan.**

## Exact proposed scope:10 erases

| Operation | Sectors | Erases |
|---|---|---:|
| Prepare the occupied part of the temporary Store target | B0:A |1|
| Dense S19 positive write after Store/Table/Restore | B0:9/A |2|
| Restore both original test sectors exactly | B0:9/A |2|
| Install updated utilities and dispatcher | B1:A, B2:E/F, B3:E |4|
| Reviewed native boot/wear journal rotation | B3:C |1|

Total:10 erases,10 append-only records including the rotation intent,
**zero F writes, zero MON A/B rewrites and zero D erases**. Sequence1120→1130;
final21 valid rows,11 original rows still on chip and all27 originals archived.
Final tracked C/D/E/F counts:56/36/36/24. B0:9 changes20→22; B0:A0→3.
These are tracked attempts, not a measurement of physical health/prior wear.

B1:A adds the sealed gate at A380-A77F and record worker at A7C0-AFBF in
existing BANK MAINT padding, retaining its actual body/header and independent
whole-image CRC. B2:E/F contains FLASH with dense S19. B3:E supplies checked
pre-WB dispatch. Existing F, MON, WB/PROGRAM, STATUS, CLOCK, SRAM/WORK bodies
and all other sectors are retained. No additional sector allocation is needed.

First qualify positive Store/Table/load-only Restore and two-sector dense S19
using the exact RAM payloads. Then restore B0 exactly and install those same
qualified payloads. Independently read back each new utility sector and test
its installed routes, admission, cancellation and unchanged existing tools.
No duplicate positive erase test is added solely for a menu or route check.

Preserve/read back fresh owner RAM0200-66FF and ZP00-DF; retain board name,
offset/battery policy, boot settings, RTC time/trim/PF history and SPI SRAM.
Yield to RTC collection between safe units and release COM4 afterward.

## Preparation evidence

Candidate builds, private to this workspace:

```text
BUILD/flash-transfer-g1-r5/manifest.json
BUILD/flash-dispatch-g1-r3/manifest.json
```

FLASH body7602 bytes,556 free within its current two-sector image. High record
body1870 bytes,176 free in its2KiB sealed overlay. E body4090 bytes,4 free.
Unchanged bodies were reused; no CPU simulation or F build was performed.

The first RAM trial passed all six dense-I guards. Its Store cancellation
fixture incorrectly assumed A was blank; the worker correctly refused it.
The host then waited for the wrong prompt. The separate preservation recovery
restored/read back owner RAM/ZP and verified unchanged complete B3 without
reset or flash writes. The corrected remaining RAM trial uses a cancellation
range entirely within9 and observes both confirmation and MON refusal exits.

All11 RAM guards are now accepted, including the six earlier dense-I cases,
Store cancellation/source preservation, bank/range/end overflow, occupied and
missing targets, full-payload CRC refusal and AUTO deferral. Complete B0/B3
readbacks are byte-for-byte unchanged. Owner RAM/ZP were restored and read
back and COM4 was released. Zero flash/journal/SRAM/RTC writes and no reset
occurred. Evidence:
`output/qualification/2512-flash-transfer-RAM-20261101-r2/report.json`.

The immutable plan is pinned to that completed RAM receipt and fresh B0/B3
captures at `output/qualification/FLASH-transfer-scope-20261101-r1/plan.json`.
The immutable original review/approval and all failed host-prompt receipts remain
archived. A fresh complete-bank audit verifies the exact final ten-erase plan,
sequence1130 and21 current records. Rich STATUS is unavailable until the
separately reviewed correction is applied;2512 is at REC>, COM4 released.
Factory restoration remains a
separate operation that intentionally replaces F and is excluded here.
