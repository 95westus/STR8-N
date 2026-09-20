# STR8-N v2 development

Development branch: `v2`. The starting firmware is commit `6d1af3d`,
preserved by tag `v1.35`. This document describes intended changes;
the firmware still implements v1.35 behavior.

## Core boundary

STR8-N v2 has no directory, enrollment, or journaling functionality or policy.
Boot selects a bank and hands off through its RESET vector, subject to bank
and vector validity checks. There are no directory records or journal states
to consult, maintain, or expose through an optional component or interface.

Retain console and recovery RAM loading, bank selection and boot handoff,
and a basic flash installer. Retain S19 checksums, address bounds,
protected-top enforcement, and bounded flash completion polling.
Do not remove additional verification merely to meet a size estimate.

Remove directory descriptions, enrollment, persistent transaction state, and
journal-based interrupted-installation recovery from v2. Remove their tooling
and packaging dependencies from the v2 product. Preserve v1 implementations
in the v1.35 baseline; existing v1 directory tools are not v2 interfaces.

## Implementation sequence

1. Establish a v2 build identity and validation path without overwriting
   the v1.35 baseline artifacts.
2. Remove directory gating from guest boot, retaining bank and RESET-vector
   validity checks. Verify that boot does not read or depend on the former
   directory storage, regardless of its contents.
3. Simplify resident installation to bank/range selection and payload writing;
   remove metadata prompts, directory writes, and journal recovery machinery.
   Define Bank 3 S9 entry handling independently of directory metadata.
4. Remove unused worker modes, directory storage reservations, and helpers;
   relink and measure actual ROM savings. Audit public ABI and RAM contracts.
5. Update host checks, operator documentation, image composition, and packaging
   for the new behavior. Exercise malformed input, protected-range rejection,
   flash failures, and successful load/install/handoff paths.
6. Validate on hardware before declaring v2 release-ready. Direct boot does
   not establish that a payload survived an interrupted installation.

## Documentation artifacts

Track book editorial sources and generators in the main repository.
Ignore generated `output/` and temporary `tmp/` files. PDF and HTML snapshots
are committed separately in the ignored `local-books/` Git repository,
which has no remote. The current book describes v1.35, not the planned v2.
