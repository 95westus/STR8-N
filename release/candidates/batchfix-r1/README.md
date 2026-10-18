# Separate offline BATCH candidate: batchfix-r1

Experimental identity: **batchfix-r1**, monitor display **2.0bf1**, generation
**48**, CLOCK **1.11**. This is not a published beta36 or a replacement for the
sealed beta35 generation-47 payloads. All device installation, native/electrical
acceptance, release qualification and publication remain unpermitted.

The owner authorized an offline-only candidate for STR8N-007: native/CLOCK
BATCH handoff under both monitor slots. This candidate does not change beta35's
approved B-target-only scope, supply broader migration converters or authorize
hardware acceptance. ACIA and crypto remain deferred.

## Design

The new monitor accepts the sealed **UX/3/42** utility provider and publishes
RAM capability marker `$BA` only after matching that profile and verifying its
full CRC. Its RAM BATCH gate checks the new marker. The storage/status XIP
dispatcher validates the same provider profile. Older UX/2/42 and new UX/3/42
providers are not silently treated as interchangeable by the new monitor.

Native utility line/error/cancel/application guards share a predicate that
accepts active monitor pages A0/B0, the new capability marker and the expected
RAM-gate entry opcodes. CLOCK 1.11 has the same bounded predicate. The legacy
`$B9` contract is accepted only with active B, preserving its prior restriction.
The marker describes a checked runtime interface, not permission to execute
an arbitrary corrupted or forged RAM image. Unsupported combinations fall
back to ordinary interactive readers instead of calling an unchecked gate.

Private entry addresses remain stable: deliberate NOP padding preserves
the BATCH engine at `$D0EA` and the native-reader addresses. Both monitor
images still fit their 4 KiB slots; each body is 3967 bytes. CLOCK's current
body is 12258 bytes within its 12264-byte stored-record capacity. The fixed
E/F recovery payloads, RAM worker/vector code and assembler remain unchanged.

The old engine also excluded CLOCK from launch admission. This candidate adds
only exact `R CLOCK` / `R 1 CLOCK` forms (with whitespace), retaining the
`BT/1/1` registered-application header check. Wrong banks, extended names,
arguments and arbitrary applications remain refused. A separate linked
predicate suite checks accepted forms and each malformed application-header
byte; this is not a general BATCH program-launch facility.

## Build and evidence

```powershell
python release/candidates/batchfix-r1/build.py --out C:\tmp\batchfix-build
```

Use a new short output directory and separately installed WDC02AS/WDCLN.
The builder performs 27 fresh links, including both A/B monitor images, and
produces 19 candidate artifacts. It reads assembly/data source, not existing
binary firmware. All outputs outside the explicit change list must match the
frozen beta35 baseline; new outputs are pinned in the build report. These are
candidate comparison artifacts, not an installation plan or a sealed release.

`derivation.json` records the five changed source files. `source-provenance.json`
pins all 97 candidate sources. The base derivation retains historical provenance;
the candidate hashes identify these new bytes. `release.json` names the baseline
build hash separately from the candidate identity. Owner-local state/evidence
will be recorded in `output/qualification/batchfix-r1-current.json`.

## Qualification boundaries

Initial offline result: **25 scenario checks plus 26 linked admission checks
passed**. The continuation explicitly reuses 18 completed assertions from the
retained prior run and freshly executes the seven remaining mixed/fallback
cases. The prior full-run failure remains recorded: its harness wrongly assumed
that an older A monitor clears an unused marker byte; the corrected assertion
requires disabled capability without changing firmware or fixture inputs.
Two independent 27-link source builds reproduce all 19 artifacts byte exactly.
Hashes and the validated build are pinned under the separate owner-local
candidate evidence directory; beta35's payloads, scoped kit and baseline match.

The offline model suite covers both-slot native/CLOCK BATCH handoff, query
return, command errors, Escape cancellation, unsupported ASM refusal, direct
slot/version/gate predicates, old/new provider combinations and invalid monitor
fallback. Every successful scenario must preserve all fake persistent devices.
Serial construction is explicitly forbidden by the harness. Initial failed
model runs and the profile-consumer diagnosis are retained separately.

Further migration/installation transactions, electrical power interruption,
full physical readback, native CPU acceptance and long-term behavior are
separate future gates. No candidate bytes are sent to the live boards. The
2512 soak/NIST campaign continues, other boards remain off, and clocks, trims,
configuration and persistent data remain unchanged.
