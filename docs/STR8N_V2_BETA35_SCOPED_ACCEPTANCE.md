> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 B-target scope and acceptance plan

Owner decision: scope beta35 to the proven B-target routes; defer broader
upgrades to a separately identified candidate. This approves the qualification
scope, not a live installation, reset, power interruption or publication.
The generation-47 payloads and all prior review ZIPs remain sealed.

## Included scope

The FT245/F30D B-target maintenance path must admit only registered source and
destination profiles with exact target E/F, validated monitors, a verified full
backup and current bank preimages. The linked evidence covers four archived
B34 fixtures plus specifically derived reverse-journal, activation-only and
no-op states. It is not a blanket qualification of every beta34/F30D image.

Retain validated A while replacing B through the staged RAM transaction.
The archived route retains B28 in A and replaces B34 in B; it does not retain
the previously active B34 as an inactive-slot-only upgrade. A live plan must
identify actual running/fallback monitor, versions, generations and explicit
preference handoff. Do not assume it from a board label or remembered version.

Machine-readable policy: [beta35-route-scope.json](../release/beta35-prerelease/beta35-route-scope.json).
All source, profile, destination, journal-capacity, sequence/count and stale
preimage refusals remain mandatory. User data and mutable service records are
not package padding. Scope approval waives no preservation or recovery check.

## Exclusions and the BATCH defect

A35 and active-B inactive-slot upgrades needing A35, stock WDC, beta1/a24c1,
published beta4 core conversion and incompatible private-ABI profiles are
deferred. Unknown/corrupt sources and arbitrary damaged-source recovery refuse.
ACIA and crypto remain deferred.

STR8N-007 remains an open defect in the excluded A35 experiment. Native utility
line/error/cancel hooks and CLOCK's validator require BOOT_ACTIVE `$7D30` to
equal `$B0`, in addition to the BATCH gate signature. Under A35 they use normal
interactive readers, so the batch queue is not consumed. The B-target control
passes; ordinary A CLOCK queries do not prove A BATCH integration.

A separate candidate can replace slot-specific assumptions with validated
active-monitor/BATCH capability checks. Preserve signature, ABI/version and
old-monitor fallback guards; update native/CLOCK line, error, cancel and
application admission paths together. Test both slots, mixed older fallbacks,
success/error/cancellation, corrupt/uncommitted gates, recovery and full
persistent-state preservation. This is a fix plan, not an implemented fix.

## Evidence reused

The archived-fixture, transaction, journal variants, restoration, interrupted
recovery, boot and bounded flash-fault receipts remain valid for unchanged
inputs. The 23-check manual/ABI audit and exact ten-byte ASM example also remain
unchanged. Scope documentation and package admission/exclusion checks are new;
no historical model execution is relabeled as fresh hardware or fresh CPU work.

The reservation-enabled composed RAM installer is model-only. Do not substitute
the frozen historical template or call it the new accepted installer. Physical
acceptance must bind the exact helper, wrapper, installer, plan and transfers,
in addition to the frozen firmware payloads.

## Physical acceptance, after explicit campaign release

No test board is selected or powered on by this plan. The owner must first
identify a board available for testing, report power return where applicable,
authorize destructive qualification and settle preservation of that board's
drift interval. Capture the post-return RTC sample before any change. 2512's
live soak and the other boards' powered-off campaign remain protected now.

1. Archive repeated full flash, EEPROM, external SRAM, settings, RTC controls,
   trims, identity and power-event evidence. Prove stable preimages and verified
   backups; reject any source outside the scoped catalog/profile. Preserve all
   existing failure/recovery evidence.
2. Rehearse the exact proposed image offline against those fresh bytes. Verify
   source admission, A fallback, startup/EDU values, all unowned bytes and the
   complete expected final image. No source fixture substitutions.
3. Qualify the reservation-enabled forward transaction. Confirm reservation
   durability before each additional erase, selected-monitor validity and full
   readback, with conservative count maxima retained after interruptions.
4. Exercise controlled interruption boundaries around reservation, journal
   staging, erase/program, payload/monitor commits and final activation.
   Electrical timing/partial-byte behavior cannot be inferred from model cuts.
   A late failure may follow a valid target commit: inspect actual durable
   state before deciding recovery; do not automatically rerun or roll back.
5. Qualify receipt-bound wear-aware restoration and interruption during that
   restoration. Restore original payload/settings/user bytes outside new C/D
   records while retaining new sequences and every attempted erase count.
   Do not restore old backup counters. Finish with full persistent readback.
6. Run B-target utility/CLOCK BATCH success/error/cancel, ASM, fixed-F fallback,
   and supported CPU/console acceptance. Native 816 acceptance is distinct
   from the W65C02 instruction model and emulation ABI claims.

Each case needs an exact input/installer/output identity, expected outcome,
observed full readback, attempted erase accounting and explicit pass/fail.
An unexpected difference stops that case; preserve evidence and require review
before recovery. A successful message is not full readback proof.

## Remaining release gates

Physical/native/electrical acceptance, protected long-term soak/drift evidence,
and explicit release/installation authorization remain open. No acceptance
duration or powered-off rate is invented. No SET/TRIM/OFFSET, ACK/CLEAR, board
reset, flash/retained-storage write or serial access is authorized by this
offline plan. The 2512 soak/NIST schedules stay active and the other boards
stay off. The scope decision removes the broader-route decision gate only.
