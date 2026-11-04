# Immutable rc1 operator ZIP: known workflow/documentation issues

Applies to operator ZIP SHA-256
`ed9e87ef34323b0504c355bd6b35e0a5095ecd0665d6e67166bd9178c29bddb2`.
The [2609 existing-journal upgrade](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md) passed
using these unchanged product files. The findings below do not change that
scoped result or qualify the other migration routes.

1. **Original capture is a precondition.** nf_upgrade consumes independent
   original bank/RAM/ZP capture files; rc1 has no standalone automated b15
   pre-helper capture command. The terminal and resident MON D/B commands can
   obtain them. The test harness recorded/parsed that manual procedure. A
   one-command original-backup-and-upgrade workflow remains future work.
2. **Upgrade guide wording.** The archive's later “Future authorized live
   acceptance” paragraph still recommends a complete source checkout. rc1
   actually includes the needed public hosts, engine and wrapper generator;
   the test verified their use without development-checkout fallback.
3. **Operator guide layout/payload wording.** The archive's opaque paragraph
   incorrectly reserves A/B and mentions supplied BASE MONs. BASE1 reserves
   only C/D/F; B3:8/9/A/B/E are owner space. rc1 supplies F plus five RAM tools,
   with no MON payload. Existing owner images still require inventory and
   compatibility checks before use.

The 0.3.0 guides correct those paragraphs and include this errata and the
hardware receipt. The original-capture precondition remains. Runtime files
are unchanged; the final package has no additional live trial. These updates
do not alter the immutable tested rc1 archive.
Its packaging-time NOT_RUN field remains historical. New WDC first-provisioning
or programmer-F tests must use their own reviewed scope and exact artifact hash.
No deliberate power-cut testing or access to 2205/2604 is included.
