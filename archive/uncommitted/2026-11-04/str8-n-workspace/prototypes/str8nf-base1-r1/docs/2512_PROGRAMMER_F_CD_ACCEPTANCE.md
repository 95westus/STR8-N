# 2512 programmer-installed-F C/D provisioning acceptance: passed

October 28, 2026 local time (October 29 UTC), 65C02 / FT245 / Windows.
The owner explicitly approved the [four-erase C/D scope](2512_PROGRAMMER_F_CD_SCOPE_REVIEW.md),
including archiving and replacing the current on-chip journal. The separate
programmer-installed-F public entry passed its existing-journal no-op and
occupied non-SNBT first-journal paths. F remained golden throughout.

The [sanitized acceptance receipt](../validation/2512-programmer-f-cd-acceptance.json)
binds actual serial logs, complete-bank captures, original escrow, freshly
derived public plan, source hashes and restoration evidence. Private evidence:
`C:\SRC\STR8-N\output\qualification\2512-programmer-F-provisioning-20261028-r1`.
No other board was accessed; 2205 and the existing release kit were untouched.

## Observed hardware sequence

1. The unchanged public `nf_provision_live.run` observed a real physical RESET,
   exact frozen BASE1 identity and REC>. Two complete-bank captures matched
   the original 2512 state. With execution requested and valid SNBT present,
   it selected its no-op path, independently verified unchanged flash, then
   restored/read back original RAM/ZP. No flash write occurred in this stage.
2. Further fresh double captures admitted the exact reviewed setup source.
   The separate NFC1 RAM lab passed self/plan/all-bank/BF-B5 checks and
   committed C400/997 before either fixture erase. That record selected S and
   reserved one erase each in C/D, retaining all other settings and counts.
   NFC1 then prepared and verified D followed by C. These non-SNBT fixtures
   reproduced occupied C/D after F-only installation; F was never rewritten.
3. A physical RESET reached the same golden recovery. Independent double
   complete-bank reads matched the exact fixture. The public provisioning
   entry then observed its own physical RESET, captured all banks twice and
   derived a fresh `nf-recovery` plan with source-bound history import.
   The reviewed source/expected hashes, complete D/C transaction and counts
   were admitted before the public executor's single Y. No saved public plan
   was replayed and no public classifier rule was bypassed.
4. The unchanged public NFM1 engine passed its self/plan/source/chip checks,
   erased/programmed/verified D then C, and committed each journal record
   last. It produced D000/998 and C000/999 with S/00/all8000 policy and counts
   C=52, D=32, F=24. The public entry itself observed its final physical RESET,
   independently verified all four banks and restored/read back original RAM/ZP.
5. NFC1's separate append-only mode restored the exact original policy,
   application configuration and pinned generation at C100/1000 without an
   erase or legacy MON execution. It returned directly to matching golden
   REC>. Two independent final complete-bank reads matched the reviewed final
   bytes. Original RAM/ZP were restored and independently read back again.
   Final REC>, COM4 released, no restoration pending.

Four physical RESETs were observed. There were no power cuts, automatic
resets, flash retries, extra erases, F builds or CPU/flash simulations.
The single NFC1 RAM lab was built during preparation and reused unchanged;
the public NFM1 binary, production CONFIG and frozen F were not rebuilt.

## Final preservation and accounting

Counts are decimal tracked erase reservations, not measured lifetime totals.

| Item | Before | Verified final |
| --- | --- | --- |
| Latest sequence | C300/996 | C100/1000 (000003E8 hex) |
| Committed records on chip | 20 | 3: D000/998, C000/999, C100/1000 |
| Original 20 raw records | On chip | Complete original flash retained in private host archive |
| C / D / F counts | 50 / 30 / 24 | 52 / 32 / 24 |
| Actual sector erases | None in this trial | Two each in C/D: fixture plus public provisioning; F zero |
| Other counts / unknown-history mask | Original | Unchanged / FFFFFFFF |
| Default / mask / entries | B / 0F / all 8000 | Restored exactly |
| Application configuration / pinned generation | Original | Restored exactly |
| B0-B2 and B3:8/9/A/B/E | Original | Byte-for-byte unchanged |
| B3:F | Frozen BASE1 4096 bytes | Byte-for-byte unchanged |
| RAM 0200-66FF / ZP 00-DF | Original pre-helper escrow | Restored/read back byte-for-byte |

This approved conversion replaced C/D raw history on chip; it did not restore
the old 20 records to their previous addresses. Their latest counts carried
forward, and all four new erase reservations were retained. Original raw
history and the fixture reservation evidence remain privately archived.

F remains STR8N-F 0.3.0 g00000001 / BASE1 / PR05, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Frozen source bindings and existing release-kit asset hashes still match.
Source acceptance notes/receipts were updated; ZIPs/manifests were not rebuilt.

RAM authority is the genuine independent capture-a/capture-b MON inventory
before the first helper, subsequently restored/read back in preceding cases.
The public entry durably saved those supplied original pairs before loading
and independently verified restoration. This does not claim a fresh read of
the original prefix after recovery L overwrites it. RAM SHA-256:
`1e1e8f62ac65a68206d8936ce9ce65c871e0428b5114193c65b3ba0c2838dda4`;
ZP SHA-256:
`30b1c0333c3e83a73c1abce7bd3e1fb200edf07207f485910d45cae46f816978`.

## Qualification boundary

This closes the separate programmer-installed-F provisioning happy path on
2512/65C02/FT245 for the declared occupied non-SNBT C/D fixture, with imported
tracked counts, independent readback and owner preservation. It tests the
state following F-only installation; external programmer operation itself
was not exercised or inferred from this trial.

Other occupied layouts, CPUs and adapters remain unqualified, as do interrupted
provisioning and electrical flash-pulse failures. No power-cut test was part
of this scope. F itself remains assumed golden. Damaged, conflicting, legacy
or mixed recognized journal history remains refused; no generic force
conversion was added. The explicit `--allow-unqualified` switch remains in
the source command for broader qualification limits.

Legacy MON/FLASH execution remains unqualified. The original B policy is
restored as requested; select S on later resets when recovery is intended.
Future release-kit integration and publication remain separate work.
