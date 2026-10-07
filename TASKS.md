# STR8-IN/65 Task List

This is the working backlog for the standalone STR8-N / STR8-IN/65 W65C02
project. Check an item only when its artifact hashes, host checks, board
transcript, and final flash readback agree. Keep owner-local WDCMONv2 images
out of published release artifacts.

Defects and hardware investigations are indexed in the
[repo issue tracker](ISSUES.md).

## Optional EDU clock direction recorded 2026-10-06

See [the MCP79411 design direction](docs/STR8N_V2_RTC_DIRECTION.md) for the
consolidated scope. The optional RAM prototype is followed by the integrated
local beta5 candidate. See [phase 1 acceptance](docs/STR8N_V2_RTC_PHASE1_2026-10-06.md)
and [phase 2 acceptance](docs/STR8N_V2_RTC_PHASE2_2026-10-06.md).

- [x] Build an optional RAM service and separate client with discovery, bounded
  clock status/read, explicit SET/ACK, owned RAM, and provisional application ABI.
  Linked-code host checks and 02SXB boards 2512 (COM4, no EDU) and 2205 (COM3,
  EDU) passed their scoped tests. Both complete flash backups matched repeats
  and final readbacks; no flash was changed. 2205's RTC was explicitly set to UTC.
- [x] After the user-reported main-power outage on 2205, verify retained advancing
  time, a newly latched outage, read-only evidence preservation, and explicit ACK
  retaining its RAM capture. Same-minute outage fields do not establish duration;
  this does not certify remaining battery life. See the phase 1 follow-up record.
- [x] Qualify reported total power loss with main power and CR2032 removed on
  2205: stopped/default-like time was rejected without automatic initialization;
  explicit UTC setting restored a running clock and backup enable. Outage
  evidence was lost. Final four-bank flash readbacks matched the original backup.
- [x] Qualify the same optional RTC images on W65C816SXB 2609, COM8, EDU fitted:
  measured E=1/D=DBR=PBR=0, stopped-clock rejection, explicit UTC SET with bounded
  advancement checks, ACK without a latched event, and calls in all four overlays.
  All four complete backups, repeats, and final readbacks matched; no flash changed.
  RTC native calls remain outside this scoped acceptance. See the phase 1
  follow-up record.
- [x] After the user-reported main-power cycle on 2609, verify retained advancing
  time, a newly latched outage, read-only preservation, and explicit ACK retaining
  its RAM capture. Battery removal on 2609 is deliberately skipped by user direction;
  expected behavior is assumed from 2205, not recorded as tested on 2609.
- [x] Define and implement protected service lifetime and versioned discovery:
  verified optional software reserves RAM $6500-$66FF from RESET; the first
  clock or I2C request initializes it. HOLD revalidates code while preserving
  initialized outage capture. Existing public tables remain unchanged; kernel
  discovery is at $7D04. M/L/G and RST/MAINT honor ownership. Final ABI freeze
  remains separate from this versioned candidate.
- [x] Integrate the resident-flash RTC/I2C extension in local beta5 generation 14:
  1760 provider bytes plus a 512-byte gateway template in B3 sector 8. MAINT 1.6
  relocated to B1 sectors 8/9; B3 sector 9 is free. Exact backup-bound migrations,
  physical RESET, first requests, both A/B slots, all caller banks, MAINT/guards,
  and repeated final four-bank readbacks passed on 2512, 2205 and 2609. B0/B2
  preserved; beta4 F unchanged on 2205/2609. See the phase 2 acceptance record.
- [x] Publish the shared I2C transaction ABI with caller-owned buffers,
  read/write/repeated-START, whole-operation ownership, bounded errors and
  partial progress, separate discovery, and managed clock-write policy. Models
  qualify a second device with RTC absent. Hardware checks qualify public MCP
  reads on both SXB CPU types and bounded no-EDU failure on 2512. A physical
  second peripheral remains untested. SRAM/EEPROM drivers remain deferred.
  See [the versioned candidate ABI](tools/v2-rtc/I2C_API.md).
- [x] Synchronize installed RTCs on 2205 and 2609 to a fresh external UTC
  reference and save final sync times, pre-write outage evidence, advancing
  readbacks and initial offset intervals. See
  [the drift baseline](docs/STR8N_V2_RTC_UTC_BASELINE_2026-10-06.md).
- [ ] Measure drift with read-only checks against those baselines after about
  48 hours and a week; retain raw evidence and report uncertainty in seconds/day
  and ppm. No clock SET or trim changes during the measurement interval.
- [x] Take the requested early drift check on 2026-10-07 before changing power-fail
  handling: after about 69 minutes, 2205's offset-change interval is -0.825 to
  +1.164 seconds and 2609's is -0.869 to +0.899 seconds. Both include zero;
  no measurable drift is established at this precision. Original baselines remain
  intact. Longer checks are still pending.
- [x] Repeat the requested drift measurement after about 8.5 hours on 2026-10-07:
  2205's change is -0.021 to +1.775 seconds and 2609's -0.267 to +1.478 seconds.
  Both include zero; a fastward trend is suggested but no precise nonzero rate
  is established. No SET/trim/ACK or baseline replacement occurred. See
  [the drift record](docs/STR8N_V2_RTC_DRIFT_2026-10-07.md).
- [x] Complete beta7/CLOCK 1.1 live qualification: explicit confirmed ACK,
  latch verification and retained capture, decoded outage times and marker on
  boot, stopped/invalid-field safety, and atomic CLOCK record update. Models
  pass; all three updates, physical power-cycle restart, both slots, saved
  CLOCK/MAINT and exact four-bank readbacks passed. Both EDU events were archived
  and acknowledged once through CLOCK; retained RAM capture and advancing time,
  backup enable and control/trim verified. Original drift baselines remain intact.
  2609's reported four-red-LED transient did not reproduce as a persistent boot
  failure; UART, both slots and flash verified, LED port/control read 00/34. See
  [the power-fail update](docs/STR8N_V2_RTC_POWERFAIL_2026-10-07.md).
- [x] In CLOCK 1.2, replace the ambiguous ACK confirmation sentence
  with the user's exact wording: "ACK clears the power-fail flag and outage
  timestamps. UTC time keeps running unchanged." Save and verify the evidence in
  EEPROM before ACK and keep exact YES confirmation. ACK rearms the next outage;
  while the latch remains set, later outages do not replace its recorded times.
- [x] Finish beta8/CLOCK 1.2 EEPROM journal acceptance. All three installations,
  physical RESET, both slots, CLOCK history/show/cancellation paths and exact
  four-bank readbacks passed. 2205's authorized replacement of its backed-up
  legacy EEPROM data passed; 2609 boot saved its latched outage automatically.
  Both live flags are clear, UTC advances, and factory/protection bytes match.
  A new main-power outage on each EDU board was saved and acknowledged on boot;
  both prior entries survived. All three power-cycle checks, MAINT 1.7 sector-9
  refusal, complete final flash comparisons and evidence audit passed. Original
  UTC drift baselines and control/trim remain unchanged.
  See [the journal design and commands](docs/STR8N_V2_RTC_JOURNAL_2026-10-07.md).
- [x] Qualify and install the owner's shorter RTCC messages when flashing is
  authorized. The beta9 candidate is built and model-tested separately; `R CLOCK` remains and
  there is no `R RTCC` alias. Verified save/ACK progress selects the exact three
  messages. No boards are accessed or flashed for this preparation. See
  [the unflashed candidate and time access](docs/STR8N_V2_RTCC_MESSAGES_2026-10-07.md).
  The later beta10 TIME candidate includes these messages; a separate beta9
  installation is unnecessary.
- [x] Physically qualify/install the beta10 TIME work through integrated beta12 when
  flashing is authorized. A ten-byte monitor hook reuses the formatter; total
  monitor growth is twenty bytes. The runnable read-only example is 304 bytes.
  TIME/argument parsing, all four example banks, absent/stopped/invalid clock
  paths, kernel, boot banner and journal model checks passed without data writes.
  User programs read time only; CLOCK and boot own SET/power-fail administration.
  See [TIME and the example](docs/STR8N_V2_TIME_COMMAND_2026-10-07.md).
- [x] Physically qualify/install the beta11 EUI work through beta12/CLOCK 1.4.
  The full factory EUI-48 is shown at boot, CLOCK entry and STATUS, and via the
  read-only CLOCK EUI command. Identity reads do not require valid RTC time and
  never modify factory identity, outage records or UTC. This candidate includes
  the earlier shorter RTCC messages and TIME command; separate beta9/beta10
  installation is unnecessary. See [the EUI candidate](docs/STR8N_V2_RTCC_EUI_2026-10-07.md).
  EUI/TIME/kernel/banner/journal checks and CLOCK calendar, confirmation,
  SET-preservation and history checks passed locally. No boards were accessed.
- [x] Physically qualify/install beta12 and CLOCK 1.4 when flashing is authorized.
  Keep the existing date/time format; RTCC failure prefixes are consistent.
  Remembered EUI records use the spare tail of existing B3 sector 9, with a
  separately sealed code prefix and per-record CRC/commit. Boot only compares;
  CLOCK ACCEPT EUI requires YES, rejects stale identity and avoids matching writes.
  No extra sector or user RAM reservation is used. Full storage refuses writes.
  Upgrade preparation must preserve the identity tail with the supplied merge.
  This candidate includes the earlier pending RTC/CLOCK changes, so separate
  beta9/beta10/beta11 installation is unnecessary. See
  [the binding and message changes](docs/STR8N_V2_RTCC_BINDING_2026-10-07.md).
  Local checks passed: all 17 replacement-write interruption points, timeout,
  stale confirmation, full storage, tail preservation, binding/boot states,
  CLOCK administration/history, read-only TIME and kernel/banner regressions.
  No board access or flashing occurred.
  Follow-up: the owner authorized all three flashes. Eight-sector installers
  completed device verification on 2512/2205/2609; full/repeated backups and
  RTC/EEPROM archives passed. Restarted monitors were observed and all three
  live checks passed: both slots, TIME, read-only example, CLOCK identity/history,
  confirmed initial EUI acceptance on each EDU, no-EDU refusal, maintenance guard
  and exact final banks. Both EEPROM histories, B0/B1/F and drift baselines were
  retained unchanged. The final evidence audit passed.
  See [hardware installation](docs/STR8N_V2_RTCC_BINDING_HARDWARE_2026-10-07.md).
- [x] Perform the requested post-beta12 read-only UTC/drift comparison after
  about 13.5 hours. 2205 is +0.915 to +1.629 s from UTC, with baseline change
  +0.296 to +2.040 s. 2609 is +0.013 to +0.730 s from UTC, with change -0.242 to
  +1.234 s. Reference retries/final checks passed; no SET/trim/ACK was issued.
  See [the comparison](docs/STR8N_V2_RTC_DRIFT_POST_BETA12_2026-10-07.md).
- [x] Perform beta12/CLOCK 1.4 on-board regression on 2512, 2205 and 2609.
  Both slots, RAM ABI, physical BRK/VIA1 IRQ/NMI, loader/RAM/RESTORE, managed
  RTC/I2C, CLOCK/EUI/history and ownership guards passed. 2609 also passed native
  BRK/NMI and confirmed return to emulation. Complete before/after/post-NMI
  images, EEPROM/factory/identity data, control/trim and UTC baselines matched.
  No clock, trim, ACK or firmware mutation was issued. See
  [the physical regression](docs/STR8N_V2_BETA12_BOARD_REGRESSION_2026-10-07.md).
- [x] Build CLOCK 1.0 using the integrated clock API: UTC display, status/raw
  outage evidence, validated SET with exact YES, cancel/overflow handling, and
  safe optional-device failures. Host tests cover 437 calendar/weekday cases and
  confirmed SET; live checks preserve the drift run by canceling SET. Saved to
  erased B2 sector 8 on 2512, 2205 and 2609. `R CLOCK`, byte-exact RESTORE,
  VIA/capture preservation and final four-bank readbacks passed. All other
  flash bytes remain unchanged. See [CLOCK 1.0](docs/STR8N_V2_CLOCK_1_0_2026-10-06.md).
- [ ] Later, add compatible versioned saved-record timestamps; SAVE must work
  when usable time is unavailable.
- [x] Finish beta6 UTC/status banner hardware acceptance. Formatter is optional
  and verified in B3 sector 8; healthy/stopped/invalid/unavailable paths, stale
  pointers and kernel regressions pass host checks. All three updates, physical
  restart, both slots, CLOCK/MAINT return, guards and exact final four-bank
  readbacks passed. The user-confirmed power cycles on both EDU boards retained
  running time and latched new outage events; evidence remains unacknowledged.
  Original drift baselines are unchanged; the sampling client now copies
  its result before HOLD so a banner READ cannot replace the timed sample. See
  [the banner record](docs/STR8N_V2_RTC_BANNER_2026-10-06.md).
- [ ] Deferred by owner direction (2026-10-07): MCP79411 Alarm 0 and Alarm 1.
  No current alarm commands, ownership, polling/ACK or MFP/VIA interrupt work.
  Revisit only in a later explicitly authorized phase.
- MCP79411 SRAM remains deferred. Beta8 allocates all 128 ordinary EEPROM
  bytes to four 32-byte power-fail journal slots; the factory identity and
  protection register are preserved. No general EEPROM write API or other
  settings allocation is implemented. Essential state stays in board flash
  and works without an EDU.

## Current alpha and next EDU alpha (agreed 2026-09-30)

- All future board upgrades must preserve compatibility with static-bank
  `maint.a` and `.s19` artifacts, with S/R optional. This is a compatibility
  requirement; a complete ABI freeze awaits an inventory of entry addresses,
  registers/flags, calling conventions, RAM layouts, bank and CPU-mode
  assumptions, error returns, and optional-device discovery. Preserve existing
  contracts while that inventory is completed; do not silently break callers.
- [x] Finish scoped alpha24 host and W65C816SXB board regression without the
  EDU daughterboard. Host regression passed `make v2-a24-check` on 2026-09-30.
  Board 2609's B3:E/F passed exact readback, physical RESET, and cold power
  cycles before and after E installation. Native and emulation interrupt probes,
  cross-bank RAM ABI, and a bounded B1 S/R save/restore passed. EDU-attached
  device qualification belongs to the next alpha. See the
  [a24 prerequisite record](docs/STR8N_V2_A24_FT245_ONLY.md).
- [x] Qualify the WDCMONv2-to-STR8N-v2 alpha24 migration on board 2609,
  the W65C816SXB.
  Bind the migration artifacts to the current candidate before the board run;
  older alpha21/alpha22 migration evidence does not qualify alpha24 or the 816.
  [Board 2609 inventory](docs/STR8N_V2_2609_INVENTORY_2026-09-30.md) found the
  shipped native EDU demo and then returned `SXB6`, HW 3.00, WDCMON 2.00 on a
  successful binary board-info probe. The bridge now checks `SXB?`, retries an
  early incomplete reply, and requires physical board-type confirmation before
  RAM loading. WDC identity suffixes
  vary across boards or revisions, so record each exact tag and physical model.
  The alpha24 WDCMONv2 migration kit (retired guide)
  now builds and passes offline checks. On board 2609, the 816-entry RAM installer
  verified byte-exact, identified flash `BF/B5`, and copied original B3 to an
  erased B0 with whole-bank exact verification. In a separate run, it installed
  alpha24 B3:F; physical RESET booted `STR8-N 2.0a24 B3 65C816`, and a complete
  `D F000 FFFF` readback matched the pinned F BIN byte for byte. B2 was
  untouched. A later USB power disconnect/reconnect booted alpha24 at `B3>`.
  The [board-specific E report](docs/STR8N_V2_A24_816_E_INSTALL_2026-09-30.md)
  records exact preimage gating, E installation, and complete E/F readback.
  Native BRK/NMI and emulation BRK/IRQ/NMI probes passed on board 2609. A
  bounded B1 S/R save/restore passed; two complete read-only B2 inventory
  passes matched byte-for-byte. An unattended
  post-E run confirmed CPU/console state, the ROM and S/R descriptors, a
  four-bank RAM ABI probe (`PASS`), and read-only static-maintenance sector
  mapping (B0/B2/B3 occupied, B1 erased before the S/R test). The `.a` carrier
  decodes to the same 703-byte machine image as the board-tested `.s19`;
  a live ASM-F2 assembly session was not available on this board. See the
  board inventory.
- [ ] Next alpha: EDU board testing. Bank 3 holds the 816SXB version; Bank 2
  holds W65C02SXB with SPI/I2C/RTC updates. Both need EDU presence detection
  without LEDs or buzzer. Start with read-only RTC device/register probing,
  then separately verify valid date/time and a running clock before using
  date/time as a presence signal. With EDU absent, the stock menus still
  reported RTC `$6F` as `OK`, while date/time remained zero even after B2
  reported `Time set!`. This is a useful absent-board negative control; startup
  `OK` alone cannot establish presence. Leave crypto untouched. Handle
  absent/unresponsive hardware without hanging core operation; report
  inconclusive detection rather than assuming presence.
- [ ] Measure persistent RTC service placement against the current beta4 layout.
  Beta4 already uses `$E000` for launcher and RST services; the earlier optional
  E-sector placement proposal is superseded by the
  [RTC direction](docs/STR8N_V2_RTC_DIRECTION.md). Preserve core boot and
  static-bank maintenance with RTC support absent.
- For the EDU test, validate date/time setting with the board's shipped EDU
  firmware before STR8-N relies on RTC time. The observed B2 W65C02SXB guest
  uses bit-banged I2C/SPI via W65C22; the B0 W65C816SXB guest runs in native
  CPU mode. Future STR8N clock setting requires explicit authorization. The
  2026-10-06 RTC direction brings power-fail status into the first clock service;
  alarms remain later work. RTC SRAM and parallel/SPI SRAM allocations remain
  deferred; beta8 uses ordinary EEPROM for the outage journal described above.
  MCP79411 ordinary EEPROM is 128 bytes, with a separate 8-byte
  protected region; SRAM is 64 bytes. Desired hard state must survive loss of
  both main and battery power and remain available without an EDU.
- [ ] With the EDU board fitted, repeat bounded RTC, SPI SRAM, and 816 extended
  RAM checks. The absent-board menu failures (SPI SRAM B2 `$10` and B0 `$96`,
  zero RTC date/time, and B0 Bank 0-to-8 block move) do not qualify the devices.
- Alpha is a maturity label, independent of API/ABI, feature, or code freezes.
  Make further EDU and memory-allocation decisions at the next-alpha test.

## Deferred v2 hardware issue

- [x] Package the unchanged alpha21 image as a scoped
  STR8-N 2.0 RC1 (retired release decision), with exact artifact and
  board top-sector hash verification. The remaining hardware qualifications
  are disclosed in the RC decision.

- [ ] [W65C51N ACIA receive on boards 2205 and 2512](docs/issues/ACIA_RX_2512_2205.md):
  resume only with meter, logic probe, or scope measurements of the receive
  signal, clock, handshake, supply, and ground. The backup-console
  qualification gate remains open.

## Proposed v2 component storage and interfaces

- [ ] Add an optional target-controlled RTERM status field and set/clear API;
  see the [target status proposal](docs/RTERM_TARGET_STATUS_PROPOSAL.md).
  Bank display is one producer use case, with no STR8-N dependency in RTERM.
  Requires coordinated target API and RTERM protocol/display work.

- [ ] Document RTERM host-terminal font selection and plan optional graphical
  font/preset support; see the [appearance proposal](docs/RTERM_APPEARANCE_PROPOSAL.md).
  Local preferences include 3270-style, amber, and line-printer appearances.

- [ ] Continue the [fixed-address component/storage design](docs/STR8N_V2_COMPONENT_STORAGE_PROPOSAL.md):
  explicit-bank save, AUTO placement, original-address restore, HAL device
  access, and DEBUG's IRQX dependency. Discussion only; no implementation yet.

## Next v2 layer: public R-YORS integration

Keep this work on `v2`; the v1.34/v1.35 release line stays separate. The
[interface map and ordered proof](docs/STR8N_V2_RYORS_NEXT_LAYER.md) records
the public HIMON/ASM-F2 `00.0915(2324)` boundaries.

- [ ] Adapt HIMON `STR8` return to detect v2 and enter `$F004` after selecting
  the resident bank; retain the existing v1 route for v1 boards.
- [ ] Give HIMON `L` a v2-compatible, HIMON-owned parser or a clear refusal;
  the v1 `SR` record service is absent from v2.
- [ ] Validate RAM-only HIMON/ASM-F2/AP paths before any AP flash install or
  bank-policy changes. Do not reuse v1 directory/WORK/backup assumptions.
- [ ] Record public-release host checks, then authorize and capture a separate
  W65C02SXB board run before claiming integrated v2 compatibility.

## v1.34 release

The current source is a 120-byte size reduction from the accepted v1.33
binary. Its host results and exact image identity are recorded in
[the size-change report](docs/STR8N_V1_34_SIZE_OPTIMIZATION.md).

- [x] Retain [v1.34 COM4 evidence](docs/STR8N_V1_34_BOARD_TEST_2026-09-15.md)
  for guarded update/readback, physical/software reset, console/BRK,
  HIMON C/W and timeout, ASM-F2 entry/return, RAM loading, and J3.
- [x] Retain [follow-up evidence](docs/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md)
  for power-cycle startup, physical NMI, VIA1 timer IRQ, optimized-worker
  program/verify/erase/verify on B2:9, invalid-write rejection, and red/green LEDs.
- [x] Repeat the [complete v1.34 factory migration](docs/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md):
  erased-B0 preservation, exact canonical top plus D0, J0/selector 0,
  physical-reset return, and byte-exact four-bank readback.
- [ ] Complete the remaining hardware gates: Bank 1-2 guest boots, resident
  installation, transient LED timing, and injected failure/recovery paths.
- [x] Package the unchanged v1.34 canonical firmware with the exact existing
  board evidence and an explicit statement that the broader matrix is incomplete.
- [x] Split the STR8-N distribution from HIMON/ASM applications and games;
  retain the project-written migration kit and Bank Maintenance `.a`.
- [ ] Commit reviewed release documentation, regenerate from committed source,
  verify the final archives and manual links, and create the release tag.

## Preceding v1.33 release status

The preceding v1.33 release completed the checks below. Its complete factory
migration remains qualified by the accepted
v1.32 hardware run plus v1.33 host checks; repeat that whole path on hardware
before describing the v1.33 migration itself as board-accepted.

- [x] Promote the immediate reset banner and reset-source indication as
  canonical STR8-N v1.33.
- [x] Bring README, maps, operator/technical guides, migration boundaries,
  manifests, filenames, and public contracts into agreement with v1.33.
- [x] From committed source, rebuild and verify the v1.33 release ZIP,
  migration ZIP, S19 set, Bank Maintenance images, and SHA-256 receipts.
- [x] Run the migration-package allowlist and extracted-package self-verifier;
  owner-local WDCMONv2 bytes, bank archives, raw captures, and R-YORS payloads
  are absent from that focused migration kit.
- [x] Accept the guarded v1.33 top-sector update, exact readback, reset-source
  behavior, and HIMON warm recovery on hardware.
- [ ] Repeat the complete factory WDCMONv2-to-STR8-N migration on hardware with
  the exact v1.33 artifacts. The corresponding v1.32 path remains the accepted
  hardware evidence.
- [x] Tag the reviewed commit and publish the verified v1.33 release package
  and its SHA-256 receipt.

## LED status service

The ownership and bit-pattern contract is specified in
[LED_STATUS_PROPOSAL.md](docs/LED_STATUS_PROPOSAL.md). Keep the public raw
console ABI free of LED side effects so user applications retain Port A.

- [x] Implement only the minimal `$01`, `$41`, `$F0`, and `$00` slice first.
- [x] Measure the linked resident and worker: 3,331-byte resident, 608-byte
  worker, 77-byte erased margin; `make all` passes.
- [x] Confirm LED order/polarity, flash-mutation coverage, worker-return
  restoration, handoff release, and application ownership on hardware.
- [x] Add the measured PWE# input-wait distinction: `$21` without a configured
  FTDI host and `$43` with one. The current resident is 3,343 bytes, the worker
  remains 608 bytes, and the erased margin is 65 bytes; host checks and the
  focused board test pass.
- [x] Complete board proof for the separately measured STR8-N RX/TX activity
  slice. The host-qualified implementation adds 25 resident bytes, leaves the
  worker unchanged, and preserves 40 erased bytes with a 32-byte layout floor.
  Public character I/O and public record parsing remain LED-neutral; HIMON and
  ASM activity belongs in their own later slices. Guarded installation and
  focused `$07`/`$0B` observations passed on COM4 on 2026-09-06.
- [x] Carry the shared vocabulary into HIMON and ASM as separate, measured
  changes without claiming their states from STR8-N after handoff. R-YORS
  commits `40d6a10` and `fda8401` added and refined the HIMON-owned service
  wrappers; the focused linked-byte check and full ASM host suite pass, and
  COM4 accepted HIMON and ASM-F2 wait/RX/TX states plus physical-reset recovery
  on 2026-09-10.

## Optional board project: Stock SXB3 to a usable multi-bank system

Goal: preserve the factory system twice, install a clean STR8 system in Bank
3, and put one independently bootable example in Bank 1. This is an end-to-end
board deployment project, not a gate on the standalone v1.34 release.

### 1. Freeze the build identity

- [x] Use the canonical product/banner name `STR8-N v1.34` for this pass.
- [x] Use v1.34 consistently in banners,
  filenames, manifests, directory descriptions, transcripts, and hashes.
- [ ] Rebuild and record the exact migration-kit, Bank-3 payload, and example
  payload hashes before touching hardware.

### 2. Clone the original SXB3 flash device

- [ ] Read the complete 128K factory flash twice with an external programmer.
- [ ] Require both reads to be byte-identical and record their SHA-256.
- [ ] Program a compatible spare flash device with that exact 128K image.
- [ ] Read the spare back and require a byte-for-byte match to the saved image.
- [ ] Boot the spare in the SXB3 and capture the stock WDCMONv2 identity.
- [ ] Label and retain the original device as the untouched recovery master;
  use the verified spare for the remaining work.

Acceptance: two recoverable physical devices exist, the saved 128K image and
both readbacks agree, and the cloned device boots stock WDCMONv2.

### 3. Preserve WDCMONv2 in Bank 0 using the RAM migration path

- [ ] Follow
  [WDCMONV2_MIGRATION_BOARD_TEST.md](docs/WDCMONV2_MIGRATION_BOARD_TEST.md)
  Phase A without combining it with a destructive phase.
- [ ] Load the read-only archive application into RAM through WDCMONv2, verify
  RAM readback, inventory all four banks, and export Banks 0 and 3.
- [ ] Extract and retain the owner-local Bank-0 and Bank-3 BIN, S19, receipt,
  FNV, SHA-256, raw terminal capture, and host event log.
- [ ] Require Bank 0 to be erased or already byte-identical to Bank 3. If it is
  used and different, stop; do not overwrite it under this task.
- [ ] Run the documented refusal gates before authorizing a flash write.
- [ ] Load the guarded seed installer into RAM, copy Bank 3 to Bank 0, and
  require per-sector verify, whole-bank FNV agreement, and a complete
  byte-for-byte comparison.
- [ ] After STR8 is installed, launch Bank 0 and use the binary `$0C` identity
  exchange to prove the preserved WDCMONv2 actually runs there. A matching
  flash copy alone is not execution proof.

Acceptance: Bank 0 is an exact preserved copy of factory Bank 3, `J0` reaches
a working WDCMONv2 guest, and physical RESET still returns to Bank 3.

### 4. Install a clean STR8 system in Bank 3

- [ ] Install and verify the chosen STR8 top sector in Bank 3 from the RAM
  seed installer; do not reset, press NMI, or remove power during the active
  Bank-3 sector-F write.
- [ ] Prove physical RESET enters the selected `STR8-N v1.xx` or `STR8-IN/65`
  build.
- [ ] Install the matching HIMON/ASM-F2 payload into Bank 3 sectors `8-E` with
  the resident `I` path and commit the new Bank-3 directory row last.
- [ ] Start from an otherwise clean directory/configuration state. Do not
  silently assign WORK, backup, VTOC, automatic FNV/AP search, or other bank
  roles; make each later assignment an explicit, separately verified action.
- [ ] Prove cold and warm HIMON entry, return through `STR8`, and another cold
  start.
- [ ] Re-prove the Bank-0 WDCMONv2 guest after the Bank-3 install.

Acceptance: Bank 3 owns RESET and boots the named/versioned STR8 build; its
directory contains only deliberately committed records; Bank 0 remains the
working stock-monitor recovery guest.

### 5. Create and install the Bank-1 example

- [ ] Use ASM-F2 source (`.a`) and the existing W65C02 style for a minimal
  Bank-1 `HELLO WORLD` guest unless one richer period-appropriate candidate
  below is deliberately selected instead.
- [ ] Keep the baseline example unsealed at the ASM-F2/AP layer: after `END`,
  leave `SEAL>` without using `SEAL`, `PACKAGE`, or AP `INSTALL`. Persist it as
  a validated STR8 guest S19 instead. This does not remove the STR8 directory
  row's required identity/seal byte; the two mechanisms are separate.
- [ ] Make the baseline a fixed-vector guest with explicit NMI, RESET, and
  IRQ/BRK targets in the image.
- [ ] If a patchable-vector variant is wanted, make it a separate artifact:
  keep the hardware vectors fixed on small trampolines, place the replaceable
  targets in RAM, and add reset/default/invalid-target tests.
- [ ] Make the guest self-contained: initialize the required console state,
  print a visible identity/version line, and provide a defined halt, loop, or
  return behavior.
- [ ] Supply valid NMI, RESET, and IRQ/BRK vectors for the Bank-1 launch
  contract even when the chosen policy makes their targets minimal.
- [ ] Build a dense, validated Bank-1 S19 whose selected range, S9, RESET
  vector, padding, checksums, and manifest hash satisfy
  BANK_0_2_GUEST_S19.md (retired guide).
- [ ] Install it with `I`, commit its Bank-1 directory row, and prove both `J1`
  and the reset selector reach it.
- [ ] Press physical RESET and prove recovery to Bank 3, then re-prove `J0`
  WDCMONv2 and the Bank-3 STR8/HIMON path.

Richer candidate pool (select one only after the minimal Bank-1 path is
understood):

- [ ] Period-appropriate command adventure with at least `GO NORTH`.
- [ ] Conway's Game of Life, preferably by adapting the existing R-YORS app.
- [ ] ELIZA.
- [ ] A small, legally redistributable 6502 BASIC port, with Ben Eater's
  WOZMON/BASIC work evaluated as a lead rather than assumed to be drop-in.
- [ ] fig-FORTH or another provenance-checked 6502.org-era system.

For imported software, record provenance, license/redistribution terms,
original memory and I/O assumptions, porting changes, size, vectors, and the
exact source-to-artifact reproduction command.

Acceptance: Bank 1 has one reproducible, independently bootable example with
the unsealed-ASM/fixed-vector baseline contract (plus a separately identified
patchable variant, if built), retained source, build evidence, install
transcript, and cold-boot proof.

### 6. Final preservation evidence

- [ ] Read the complete 128K flash after all installs.
- [ ] Compare every bank with its intended artifact or preserved pre-image;
  unexplained bytes are a failure.
- [ ] Retain pre/post images, hashes, manifests, commands, board/flash part
  identification, transcripts, and recovery notes together.
- [ ] Update the relevant operator and board-test documents with appended
  hardware evidence; do not rewrite earlier hardware-proven transcripts.

Task 1 is complete only when the external clone, Bank-0 WDCMONv2, clean
Bank-3 STR8 system, Bank-1 example, and final full-device readback have all
passed independently.
