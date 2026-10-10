# Beta23 hardware upload and qualification status

Later October 9 update: the user expanded testing to 2604. All four boards
now run EDU ON/TRIM 0 for the synchronized UTC campaign. See the
[four-board storage/recovery results](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md).
The three-board settings and exclusions below describe the earlier checkpoint.

The frozen beta23 generation-32 image has been programmed on 2512 (COM4),
2205 (COM3) and 2609 (COM8). All three installers reported
`MIGRATION VERIFIED; PRESS PHYSICAL RESET`. Physical RESET was captured on
all three boards. Exact four-bank readback, A/B/A J3 starts, compact local
boot, quiet M1, both EDU mode directions/reset notices, reclaimed RAM,
ABI/BRK/VIA IRQ, physical NMI and repeat physical RESET checks pass. 2609's
native BRK/NMI entry/frame/return and restored emulation state also pass.
Wider storage/recovery qualification and the 48–72-hour soak remain incomplete.

The exact phase 1 build and model receipt hashes were rechecked from
`output/qualification/beta23-phase1-2026-10-09/frozen/build`; no firmware
rebuild or substitution occurred. The beta23 installer receipt validation was
added to the shared host installer and passed no-port preflight on all boards.

Owner-local run evidence is under
`output/qualification/beta23-hardware-2026-10-09`:

- `hardware-manifest.json` binds the frozen build/audit, fresh backups,
  board-specific plans, emulator models, installers and host scripts.
- Each `prior` directory holds fresh matching independent four-bank reads.
- Both EDU boards have repeated matching complete 128 KiB SRAM archives and
  repeated EEPROM/factory inventory plus RTC status/history/EUI evidence.
- Each fresh installer model passed byte-exact final banks, erase ordering,
  stale-preimage refusal and corrupt-payload refusal.
- Each `upgrade/install` directory contains serial capture, the verified-upload
  result and `reset-pending.json`. `upload-status.json` records all three results.

The installer re-read all four current flash banks and matched each verified
preimage before programming. Each board received exactly the planned eight
sectors: B3:C/8/9, B2:D/C/E and B3:B/A. The installed image retains CLOCK 1.6,
saved records, saved EDU mode, offset/identity tail, fixed recovery and the
modeled wear accounting. Full-bank comparisons passed, including a byte-exact
audit of the two intended EDU configuration appends. Each original mode was
restored. Both complete post-test 128 KiB SRAM arrays match their independent
pre-upload archives. Repeated EEPROM/factory inventory, outage history, EUI,
RTC CONTROL and calibrated trim match. UTC was retained and continues advancing.
The last repeat checks read only; no test program data was written to SRAM.

No UTC SET, trim change, power-fail ACK, SRAM format or EEPROM edit was issued.
The pre-upload EDU settings are OFF on 2512 and ON on 2205/2609; calibrated
trim remains -18/-14 on the two EDU boards. Board 2604 was not flashed or reset
by this run. Its user-installed beta23/EDU RTC remains enrolled in separate
three-board [drift analysis](STR8N_V2_RTC_2604_2026-10-09.md); its broader
firmware/RC qualification remains outside this run. The deferred STR8N-001
ACIA receive limitation remains documented.

## Physical actions and following checks

The main-board RESET capture passed on all three boards with TX=0 and DTR/RTS
inactive. For 2609 RESET uses S2/RESB; physical NMI uses S1/NMIB. The halted
installer could not accept J3. Physical emulation NMI passed on all three boards.

The completed startup and mode checks cover
exact four-bank images, compact local boot, detailed TIME/CLOCK/EUI, A/B/A
J3 starts, quiet M1, SRAM startup, saved/pending reset notices in both mode
directions, cancellation, cold activation/clearance, reclaimed RAM and ABI/IRQ.
Confirmed mode tests restored each original saved EDU setting while retaining
configuration-journal append evidence. Repeat physical RESET was captured
with TX=0 on all three boards. Read-only VIA snapshots show IER=80, PCR/ACR/DDRB
zero and no manual CB acknowledgment. Both EDU boards pass RTC and SRAM reads
from caller banks 0–3. With EDU OFF, 2512 correctly refuses service discovery
before any RTC call. The first repeat-check expected active services on 2512;
that host expectation was corrected and the failed attempt retained. Its
successful report is `repeat-check-off-expectation/report.json`.

`qualification-summary.json` binds the successful scoped reports; wider
storage/workspace save/restore/run/delete, retention/interruption recovery,
48–72-hour soak and clean build/package reproduction remain pending gates.
The soak has not started. Firmware bytes still match the phase 1 candidate;
the only intentional flash changes during these checks were the two modeled
configuration appends per board, with each original saved EDU mode restored.

See the [RC plan](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md) and
[phase 1 freeze](STR8N_V2_BETA23_PHASE1_2026-10-09.md).
