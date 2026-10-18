# Remaining bf1 acceptance gates

The source, model, initial W65C02 hardware, manual/ABI and local package evidence
have separate receipts. Package verification does not establish electrical
interruption behavior or authorize installation/publication.

- Physical electrical interruption and original-payload restoration acceptance
  on the exact supported route, with preservation and full readback evidence.
- Continued preserving bf1 soak and RTC measurement accumulation; no minimum
  duration or pass threshold has been silently invented.
- Explicit acceptance of the scoped candidate and a separate release decision.

Native 816, ACIA and crypto are deferred outside this acceptance scope.
Stock/legacy/core/private-ABI converters are not qualified. The supported route
is limited to the registered 2604 lineage and its separately proven B-first/A-second
transaction; this kit cannot admit an arbitrary board or partial component set.

Keep 2604 soaking, 2512 RTC-only, and periodic snapshots on both. 2205/2609 remain
off. No resets, persistent-device changes, clock/trim changes, event clearing or
baseline replacement are part of local review. Failed workers must retain their
evidence and must not restart automatically.
