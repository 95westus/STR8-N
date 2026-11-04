# 2609 extracted rc1 existing-journal upgrade: passed

October 28, 2026 local time (October 29 UTC), W65C816SXB / 65C816 emulation /
FT245 / Windows. The owner explicitly authorized the
[reviewed B3 scope](2609_RC1_ZIP_MIGRATION_SCOPE_REVIEW.md): one C900 append,
one frozen-F sector replacement, zero C/D erases and no power cuts. Test
software opened only COM8/A10MPQXCA; 2205 and 2604 were excluded.

The immutable operator ZIP was STR8N-F-BASE1-0.3.0-rc1.zip, SHA-256
`ed9e87ef34323b0504c355bd6b35e0a5095ecd0665d6e67166bd9178c29bddb2`.
All product modules and uploaded bytes came from its fresh extraction.
The [sanitized receipt](../validation/2609-rc1-zip-upgrade-acceptance.json)
binds actual captures, plan, source hashes, serial logs and preservation.
Private evidence: `output/qualification/2609-rc1-zip-migration-20261028-r1`.

## Actual sequence

1. The first read-only capture encountered REC> and stopped after CR without
   uploading or writing. Entering the retained b15 MON B identified 65C816.
   Its complete B3 matched the reference; owner RAM/ZP matched the preceding
   verified escrow. Two fresh independent complete-bank passes and before/
   after owner-RAM reads then agreed. No legacy RAM helper was uploaded.
2. The packaged nf_upgrade prepare/inspect path produced the actual source-
   bound plan, retaining original pre-helper escrow. The harness supplied
   logging, serial coordination, terminal-text parsing and assertions; it
   supplied no replacement product component or flash implementation.
3. The first acknowledged RESET produced no COM8 output. After an additional
   reset prompt the old F chooser was observed. No upload, confirmation or
   flash operation preceded that observation. The cause of the silent attempt
   is unestablished; two startup faces were ultimately captured. This was not
   a repeated flash operation or a power-cut test.
4. The unchanged packaged NFU1 engine passed RAM/plan/all-bank/chip guards.
   Its single Y committed and verified C900/1024 before accepting F data.
   It erased/programmed/verified frozen F once and verified final device banks.
5. The next physical RESET reached STR8N-F 0.3.0 g00000001 / BASE1 / PR05 and
   REC>. The packaged completion path independently read every bank, matched
   the plan, restored original RAM/ZP and read them back byte-for-byte.
6. The extracted terminal core sent L, cancelled at SEND BIN with Ctrl-C before
   payload, then loaded the exact bundled MAP BIN through Session.start.
   MAP's read-only banner, M1 grid over B0-B3 and Q return to REC> passed.
   These exercise the F12/F5 core paths; native GUI keys/dialogs were not
   repeated on 2609. The earlier native-key evidence is scoped to 2512.
7. A further independent double complete-bank read matched the exact final
   images. Original RAM/ZP were restored and read back again. Original volatile
   console selection C3 was restored without saving a journal setting.
   Final REC>, COM8 released, no owner-RAM restoration pending.

## Final accounting and preservation

Counts below are decimal conservative erase-attempt reservations.

| Item | Before | Verified final |
| --- | --- | --- |
| F | Known b15 | Exact frozen 4096-byte BASE1, zero builds |
| Latest sequence | C800/1023 | C900/1024 (00000400 hex) |
| Valid records | 10 | 11; every old row exact at its original address |
| C / D / F counts | 78 / 47 / 30 | 78 / 47 / 31 |
| C/D erases | None | Zero |
| Other counts / unknown mask | Original | Unchanged / FFFFFFFF |
| Default / mask / entries | S / 00 / all8000 | Exact original values |
| Application config / pinned legacy MON generation | Original | Exact original bytes |
| B0-B2 and B3:8/9/A/B/E | Original | Byte-for-byte unchanged |
| RAM 0200-66FF / ZP00-DF | Fresh pre-helper escrow | Restored/read back exactly |

Only B3:C900-C9FF and B3:F000-FFFF differ from the original flash capture.
The complete old journal remains on chip and in private backups. There was no
counter rollback, journal conversion, owner-image write, automatic retry,
power cut, assembler invocation, CPU model or external programmer operation.

Original RAM SHA-256:
`078bb916a4a4abdd22f1a415cc7620b68235122f5f57d65b166006b2c3dcc200`.
Original owner ZP SHA-256:
`491723ca60957a41126493da11f2b20d2b8ecbc7a304903186ee34ffa5e1d6e4`.
Stack/system scratch outside those specified owner ranges is not claimed as
restored application memory. No owner application was resumed or executed.

F remains version 0.3.0 g00000001 / BASE1 / PR05, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
The operator ZIP and its 92 manifest-bound files remain unchanged. Its inner
NOT_RUN field is the packaging-time snapshot; this external receipt records
the later test without changing the archive or its hash.

## Boundary and rc1 findings

This closes the extracted rc1 **existing-SNBT upgrade** on 2609/65C816 emulation/
FT245, including terminal core checks and owner preservation. It is not a WDC
first-provisioning run, programmer-F journal conversion, native application
mode or ACIA pass. Legacy MON/FLASH bytes remain preserved but their execution
under BASE1 stays unqualified. Normal recovery keeps the installed F golden.

rc1 requires operator-provided original captures for this route. This test
automated the bundled terminal/resident MON procedure; it does not establish
a one-command b15 backup-and-upgrade interface. The archive also contains stale
source-only upgrade wording and an older opaque-layout paragraph. See
[rc1 errata](RC1_KNOWN_ISSUES.md). Corrections are source-only for a future
candidate; the tested ZIP is not edited or silently repackaged.
