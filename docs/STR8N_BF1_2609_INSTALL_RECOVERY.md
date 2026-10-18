> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# 2609 bf1 return capture and offline route qualification

The owner reported 2609 powered on October 17, 2026 and authorized its return
RTC snapshot, preserving backups and offline bf1 migration/recovery qualification.
2604 retains its bf1 soak; 2512 remains RTC-only. 2205 stays off. Native 816,
ACIA and crypto are deferred. No bf1 installation on 2609 is part of this work.

## Return snapshot

Reference: October 17 at **14:30:16.817 CDT**, against NIST. RTC minus NIST is
**+0.128253 s**, with acquisition bounds **[-0.342331, +0.598837] s**.
Over 16.154577 hours from the original baseline, the change is **-0.088084 s**,
bounded by **[-0.882260, +0.706092] s**. The endpoint rate bounds are
**[-15.170444, +12.141242] ppm**; zero remains consistent. This interval mixes
power states around switching and is not a pure powered-off drift rate or an
outage-duration estimate. No clock or trim correction is justified by it.

Trim -14 and control 128 match the immutable original four-board baseline.
Final NTP consistency passed: -0.012256 s against a 0.177336 s tolerance.
The snapshot's temporary RAM was restored exactly.

Evidence: `output/qualification/rtc-campaign-snapshot-2026-10-17-192923Z/summary.json`.
The new three-board graphs and uncertainty report are under
`output/qualification/rtc-powered-campaign-analysis-2026-10-17-1937Z/`.

## Backup and restoration evidence

The USB-identified COM8 capture preserved two matching full flash reads
(131,072 bytes each), two matching 137-byte EEPROM inventories including factory
identity, and two matching full retained SRAM reads (131,072 bytes each).
Fresh EUI matches the registered baseline. All 25,344 application RAM bytes
were archived and restored exactly.

The capture harness initially selected an executable-application loader that
refused restoration starting at $0200 before transferring restoration data.
That failed source/report and a diagnostic remain archived. A separate exact
saved-image validator and S-record restoration completed with full readback;
`restore-needed.json` is false. The future capture harness is corrected; the
backup was not repeated or its failed attempt hidden. The serial audit accepts
only monitor queries/bank selection, ordinary RAM transfers, and the two pinned
read-only probes. It found no persistent write, reset, clock/trim/settings change
or power-event ACK/CLEAR.

Evidence: `output/qualification/2609-return-backup-2026-10-17-1931Z/`.

## Exact route being modeled

The current monitor reports **2.0b35 B, generation 47**, on **65C816**, with
valid original A28/generation 40 fallback and registered F30D core. Exact source
code fingerprints, both monitor CRCs, target occupied ranges and E/F match the
existing compatible profile. Candidate bf1 is generation 48, CLOCK 1.11,
UX/3/42. Candidate source and payload bytes are unchanged.

1. Install coherent bf1 B/shared components while retaining original A40.
2. After verified B48, install bf1 A while retaining bf1 B48.
3. Original-payload restoration first restores A40 while retaining bf1 B48,
   then B35/shared assets while retaining A40 and the original startup settings.

Every transaction validates exact bank preimages and its immutable fallback,
reserves erase attempts before erase, and commits headers and activation last.
Restoration carries forward newer journal sequences and conservative wear
counts; it never replays old backup counters. The retained monitor is a console
fallback; mixed shared components do not promise working native applications.

These are separate 2609 entry points: `tools/plan_bf1_2609_route.py` and
`tools/verify_bf1_2609_route.py`. Serial constructors are forbidden during the
instruction models. The model processor is W65C02 with 2609's retained bytes
and baseline trim/control. A future bf1 hardware check on 2609 must separately
establish 65C816 emulation-mode compatibility. Native 816 remains deferred.

Read `output/qualification/bf1-2609-route-current.json` for the completed result;
an in-progress or failed run is not a pass. Physical electrical interruption,
original-payload restoration and hardware acceptance remain unqualified.
This new board-specific record does not silently broaden the sealed bf1 review
kit's earlier 2604-only route policy. Installation/release permission stays false.

Three-hour RTC collection now covers 2512, 2604 and 2609. The supervisor follows
the designated 2604 soak and checks all three samples. All sampling respects
per-board operation/restoration guards. Only 2205 remains powered off.

## Completed model checkpoint

All **28 fresh board-specific checks** passed in
`output/qualification/bf1-2609-route-2026-10-17-r1/report.json`. They cover exact
source/destination admission, five linked helper-validator subcases grouped in
one check, complete B/A installations, both-slot native/CLOCK BATCH, two-stage
original-payload restoration and restored B35 boot, four stale-bank refusals,
two corrupt-transfer refusals, four representative B cuts with boot and
recovery, and altered recovery-preimage refusal. All 28 checks are fresh;
unchanged source/helper build proofs are explicitly reused. The earlier 2604
A/restoration cut coverage is not relabeled as fresh 2609 coverage.

The checkpoint binds the final backup and RAM recovery audit, original RTC
baseline, model/source hashes, protected review ZIPs, three-board drift report,
active RTC schedules and independently verified 2604 soak process. No bf1 image
was sent to 2609. Future installation and 65C816 emulation-mode hardware checks
require their own owner authorization and evidence. Native 816 remains deferred.

## Owner-authorized installation and shared CPU hardware checkpoint

The subsequent owner authorization approved B-first/A-second installation on
2609 and initial 65C816 emulation-mode checks using the same bf1 firmware as
2604. The owner explicitly accepted the unchanged F30D startup CPU detection,
which briefly enters native mode before returning to emulation mode. Native
816 applications and native-mode service testing remain deferred.

Both transactions verified, and the owner confirmed a physical RESET after
each transaction. Both slots passed 12 hardware check groups, including
utility/CLOCK BATCH success, failure and cancellation, ASM/RAM execution, LED
restoration, full flash comparisons, EEPROM/power-record preservation and
full 128 KiB retained SRAM preservation. Original application RAM restoration
was verified after each slot's checks. Fourteen runtime observations across
the two slots found E=1, DBR/PBR/direct page zero, I=1 and D=0.

`output/qualification/bf1-2609-hardware-current.json` points to the acceptance
receipt. Its audit compares the actual final firmware ranges from 2609 and
the earlier 2604 65C02 hardware readbacks with the pinned bf1 payloads,
including both monitor slots. All 19 candidate artifacts remain unchanged.
Board-specific mutable bytes are preserved individually; whole flash banks
are not claimed to be identical across boards.

2609 now runs bf1 A with the verified bf1 B monitor retained for recovery.
Its operation guard is idle and periodic RTC sampling may resume. It has no
workload soak assigned. The 2604 soak continues; 2512 remains RTC-only, and
RTC collection covers all three powered boards. 2205 remains off. Clocks,
trims, configuration and the original four-board RTC baseline are unchanged.
ACIA and crypto remain deferred.

This separate pilot receipt supersedes the earlier no-installation status
for this explicitly authorized 2609 operation. It preserves the earlier
offline model receipts and sealed review ZIPs. Electrical interruption and
original-payload restoration acceptance, long-term accumulation and explicit
candidate/release acceptance remain outstanding. General release,
installation and publication permissions remain false.


## Bounded physical follow-up and accepted soak policy

The later owner-operated session completed original A40/B35 payload restoration
and two verified-transfer-boundary power interruptions: A40 fallback followed by
bf1 B recovery, then bf1 B fallback after A48 commit with journal-only A activation
recovery. Full flash readbacks matched modeled states; retained SRAM, expected
PF EEPROM events, E=1 runtime, utility/CLOCK BATCH and pre-interruption application
RAM restoration passed. The second recovery did not erase A payload again.
These results do not qualify mid-erase/program or arbitrary byte timing, nor
2604 electrical behavior. Prior model receipts remain historical evidence.

2609 now runs one owner-authorized six-hour preserving soak before returning to
RTC-only collection. The [accepted policy](STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md)
defines automated checks and the separately scoped GitHub prerelease. General
release qualification and generic installation permission remain false.
