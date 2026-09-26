# STR8-N 2.0a21 RC1 - W65C816SXB/EDU qualification record

Print one copy per physical SXB. Keep this signed record with the raw terminal
capture, event log, readback result, and any owner-local flash backup.

## Scope and authorship

STR8-N is intended to run on a WDC W65C02SXB or W65C816SXB **with or without
its matching EDU daughterboard**. The SXB supplies the processor, flash, RAM,
and USB FT245 console; the EDU is optional expansion hardware. The 2.0a21 RC1
firmware has physical evidence on W65C02SXB. W65C816SXB execution and
W65C816EDU behavior are being evaluated by this first-board record; leave
their result blank until observed.

Owner's project intent: "This was written with AI, guided by what I think is
a way to better manage an SXB/EDU board." The owner directs the concept and
hardware acceptance; AI assisted with implementation, checks, and documents.
Mark what was actually observed. A signature accepts only the checked result.

This record covers the FT245 host-connected, stable-power operating scope.
It makes no ACIA receive, interruption-recovery, W65C816 native-mode, or
guest display/sound claim. The stock WDCMONv2-to-alpha21 RAM migration has
host checks but no prior W65C816SXB board run.

## A. Record identity before power or flash

Date / time / timezone: _________________________________________________
Operator: _________________________  Witness (optional): ________________
SXB board ID / serial / revision: ________________________________________
CPU marking: _______________________  Flash part marking: ________________
EDU board ID / revision: _________________________________________________
EDU for first core run: [ ] absent  [ ] present (explain): _______________
Host / OS: _________________________  USB adapter / COM port: ____________
RC1 ZIP filename: _______________________________________________________
RC1 ZIP SHA-256 measured: ________________________________________________
Top BIN SHA-256 expected: 3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49
Top BIN SHA-256 measured: ________________________________________________
External full-flash backup: [ ] made  [ ] unavailable  [ ] not chosen
Private backup ID / path / hash: __________________________________________

For every checkpoint mark P (pass), F (fail), or NA (not applicable). A blank
is untested. Stop at a failed gate; record the reason before taking action.

## B. Read-only stock-board gate

Follow `GETTING-STARTED-816.md`, section 2. Probe the SXB before loading the
installer. `SXB3` is an expected tag to verify, not a measured fact here.

[ ] P [ ] F [ ] NA  Data USB host and board power stable; COM port visible.
[ ] P [ ] F [ ] NA  Stock monitor responds to read-only board-info probe.
[ ] P [ ] F [ ] NA  Reported tag is `SXB3`; HW and monitor versions recorded.
[ ] P [ ] F [ ] NA  Flash marking agrees with SST39SF010A; ID later `BF/B5`.
Reported tag / HW / WDCMON: _______________________________________________
Probe command time / evidence file: ______________________________________
Mismatch or unusual stock state: _________________________________________

GATE B - proceed to RAM load only if the identity and monitor are understood:
[ ] Proceed  [ ] Hold  [ ] Reject     Initials / time: __________________

<!-- PAGE BREAK -->

## C. Guarded RAM migration and flash gate

Follow `GETTING-STARTED-816.md`, section 3. The installer copies the entire
original Bank 3 to erased Bank 0 and verifies it before modifying Bank 3 F.
A used, different Bank 0 or unexpected flash ID is a stop condition.

[ ] P [ ] F [ ] NA  Launcher accepted expected board identity.
[ ] P [ ] F [ ] NA  Installer RAM load/readback was byte-exact at `$2000`.
[ ] P [ ] F [ ] NA  Flash ID printed `BF/B5`.
[ ] P [ ] F [ ] NA  Bank 0 was erased or already byte-identical to Bank 3.
[ ] P [ ] F [ ] NA  `COPY B3 TO B0` was entered only at the copy prompt.
[ ] P [ ] F [ ] NA  Complete Bank 3 to Bank 0 copy and exact verify passed.
Bank 0 policy / original Bank 3 FNV1A: ___________________________________
Copy/verify result and timestamp: ________________________________________

GATE C - inspect the verified Bank 0 preservation before alpha21 flash:
[ ] Proceed  [ ] Hold  [ ] Reject     Initials / time: __________________

[ ] P [ ] F [ ] NA  Ctrl+U sent packaged 4096-byte alpha21 top BIN once.
[ ] P [ ] F [ ] NA  Installer reported `STR8-N TOP RECEIVED` and hash accepted.
[ ] P [ ] F [ ] NA  `INSTALL STR8-N 2.0A21` entered at exact prompt (uppercase `A`).
[ ] P [ ] F [ ] NA  B3:F program and verification completed.
[ ] P [ ] F [ ] NA  `MIGRATION VERIFIED; PRESS PHYSICAL RESET` appeared.
Installer result / timestamp: _____________________________________________
If failure, RAM recovery choice and result: _______________________________
No reset/power loss during active write: [ ] confirmed  [ ] exception noted
Exception notes: _________________________________________________________

GATE D - physical RESET only after verified completion:
[ ] Proceed  [ ] Hold  [ ] Reject     Initials / time: __________________

## D. First alpha21 boot, SXB alone

Follow `GETTING-STARTED-816.md`, section 4. Allow about 6.58 seconds for
alpha21's reset wait; keep the FT245 host connected.

[ ] P [ ] F [ ] NA  Physical RESET produced `STR8-N 2.0a21 B3 65C816`.
[ ] P [ ] F [ ] NA  ABI line printed `65C02 | 816E | 816N-VEC`.
[ ] P [ ] F [ ] NA  `B3>` prompt reached or hold was canceled with `S`.
[ ] P [ ] F [ ] NA  `D F000 F003` returned `53 4E 02 00`.
[ ] P [ ] F [ ] NA  `D 7D01 7D02` returned `16 00` (816, FT245).
[ ] P [ ] F [ ] NA  `D F000 FFFF` captured all 4096 bytes.
[ ] P [ ] F [ ] NA  Packaged verifier reported byte-exact Bank 3 F PASS.
Banner / prompt / console notes: _________________________________________
Readback capture path / SHA-256: __________________________________________
Readback verifier result / time: __________________________________________

<!-- PAGE BREAK -->

## E. Optional EDU attachment and repeat check

If no EDU is fitted, mark this section NA and sign the SXB-alone disposition.
Power off only after the core run is idle. Align EDU J1-J4 without shifted
pins; leave external modules disconnected for this first check.

EDU fitted for this run: [ ] yes  [ ] no (all E checkpoints NA)
[ ] P [ ] F [ ] NA  Power was off during EDU attachment; connectors inspected.
[ ] P [ ] F [ ] NA  USB reconnect produced complete alpha21 `B3 65C816` banner.
[ ] P [ ] F [ ] NA  `B3>` prompt and `B` command worked with EDU attached.
[ ] P [ ] F [ ] NA  `D F000 F003` and `D 7D01 7D02` matched core results.
[ ] P [ ] F [ ] NA  No unintended reset, hang, or console loss was observed.
LED / buzzer / power observations (descriptive; no EDU claim yet): _________
___________________________________________________________________________
EDU capture path / time: __________________________________________________

## F. Qualifications and disposition

Mark the scope of **this** run. A checked observation is evidence for this
board only; it does not turn the still-open tests into a general guarantee.

[ ] SXB alone: initial install, boot, CPU/console ID, and exact top readback pass.
[ ] SXB with EDU: repeat boot and core read-only checks pass.
[ ] Held: no final acceptance because of a failed or missing gate.
[ ] Rejected: investigate/recover board before further use.

Open items (check to acknowledge, not to mark passed):
[ ] W65C816 native BRK/NMI RAM probe not run in this checklist.
[ ] ACIA receive/fallback remains unqualified.
[ ] EDU visual behavior and guest LED/sound behavior remain separate work.
[ ] No interruption-recovery or automatic rollback claim.

Evidence set ID / storage path: ___________________________________________
Deviations, failures, repairs, retests, and linked issue IDs: _____________
___________________________________________________________________________
___________________________________________________________________________

Operator decision: [ ] Accept scoped RC1 on this board  [ ] Hold  [ ] Reject
Operator signature: ______________________________  Date / time: __________
Reviewer / witness signature (optional): __________  Date / time: __________

Firmware identity is frozen `STR8-N 2.0a21`; this is a board qualification
record. No WDCMONv2 firmware or owner-local stock image belongs in the public
release package or a published copy of this completed form.

<!-- PAGE BREAK -->

## G. QCC - Questions, Comments, Concerns (optional)

Name and email are optional. Provide them only if you want a reply. This page
can be typed in the PDF or completed by hand. Leave any field blank if it does
not apply. Keep private stock firmware and owner-local flash backups out of
any returned copy.

Name: _____________________________________________________________________
Email address: ____________________________________________________________
Preferred reply method / contact note: ____________________________________
Send completed records or questions to: 95west.us@gmail.com

Questions:
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________

Comments:
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________

Concerns or unexpected behavior:
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________

May the project contact you about this record? [ ] yes  [ ] no
Feedback date / timezone: _________________________________________________
