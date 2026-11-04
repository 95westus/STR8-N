# 2512 programmer-installed F: C/D provisioning scope review

The owner approved this exact scope and the
[2512 public provisioning trial passed](2512_PROGRAMMER_F_CD_ACCEPTANCE.md).
The tables below retain the reviewed four-erase and on-chip journal replacement
budget. F stayed golden; images, boot settings and owner RAM were preserved.
No power cuts occurred, and 2205 and the release kit remained excluded.
The original preparation/approval and exact packets remain in private evidence.

## Why a fixture is required

The current 2512 journal is valid: latest C300 sequence 996, 20 committed
records, original B/0F/all8000 policy, decimal counts C=50, D=30, F=24.
The unchanged public `nf_provision_live.py` correctly treats it as a no-op.
Reinitializing valid history is refused; this trial will not relax that rule.

An actual first-journal test therefore requires a separately reviewed lab
fixture with non-SNBT C/D while keeping the already installed F unchanged.
This reproduces the state after F-only programmer installation. It does not
exercise an external programmer or flash F again.

**History consequence:** the existing 20 raw journal records will be archived
on the host and replaced on chip. The final chip will have three new records;
the old 20 will not be restored to their original addresses. Their latest
tracked counts, original boot policy, application configuration and pinned
generation will carry forward without rollback. This differs from the
preceding C/D recovery trial, which reinstated its original three rows.

## Exact write budget

| Region | Reviewed action |
| --- | --- |
| B3:F000-FFFF | Zero erase/program operations; exact frozen BASE1 remains golden |
| B3:C000-CFFF | Append C400 reservation; one fixture erase; one public provisioning erase; append final policy at C100 |
| B3:D000-DFFF | One fixture erase and one public provisioning erase |
| B0-B2 and B3:8/9/A/B/E | No writes; independent full-bank preservation checks |
| RAM 0200-66FF / ZP 00-DF | Borrowed by RAM tools, restored to original escrow and independently read back |

Total: **four sector erases, two each in C and D; zero F writes/erases;
zero power cuts**. Four prompted physical RESETs keep USB power connected.
No chip removal, whole-chip erase or automatic reset is included.
Any mismatch stops for inspection; no extra erase, blind replay or automatic
rollback is authorized by this budget.

F remains STR8N-F 0.3.0 g00000001 / BASE1 / PR05, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

## Execution sequence after approval

1. Run the unchanged public path on the current valid journal, with execution
   requested but no first-provisioning declaration. Observe physical RESET,
   exact BASE1 identity and REC>. Prove a no-op, unchanged flash and verified
   original RAM/ZP restoration. Admit the reviewed baseline through fresh
   independent double complete-bank reads before any fixture write.
2. Archive the original full flash and all 20 original journal records.
   A separate source-bound NFC1 RAM lab commits C400/997 with temporary S
   default and the two fixture erase reservations: C=51, D=31, F=24. The lab
   checks its sealed image/plan, all four source banks and BF/B5 chip before Y,
   then rechecks source/self before mutation.
3. NFC1 prepares D then C, one erase each, with no SNBT records in either.
   Each fixture sector is FF except its first page's byte FF, which is 00.
   F and all owner images stay unchanged. Physical RESET reaches golden
   recovery; independently read all four banks twice and match the exact
   fixture. Retain the committed reservation evidence on the host.
4. Run the unchanged public `nf_provision_live.py` first-journal entry with
   `--provision-cd --execute --allow-unqualified` and source-bound history
   import. It must observe its own physical RESET, freshly capture all banks
   twice, derive its own plan, and admit exactly the reviewed D/C operation
   list and expected hashes before sending its single Y. No prepared public
   plan is replayed and no F operation is permitted.
5. Public NFM1 erases/programs/verifies D then C, commits last, and creates
   D000/998 and C000/999. Counts become C=52, D=32, F=24; prior lifetime remains
   unknown. The new policy is S/recovery, disabled banks, entries all 8000.
   Its final physical RESET, independent all-bank readback and original
   RAM/ZP restoration must pass through the public entry itself.
6. The separate NFC1 append-only mode restores the exact original boot
   policy/configuration/pinned generation at C100/1000, retaining current
   counters. Its sealed frame and complete source-bank guards bind this
   particular restoration; it never executes the incompatible legacy MON.
   This mode has no erase, uses only C100, verifies final banks and returns
   directly to matching golden F at REC>.
7. Independently read all four final banks twice, restore/read back original
   RAM/ZP, return to REC>, release COM4 and audit the actual captures/logs.

The reset count is one for the initial no-op, one after fixture setup, and two
inside the actual public provisioning entry. No further reset is required
after restoring original B; legacy MON execution remains unqualified.

## Required final result

| Item | Before | Required final |
| --- | --- | --- |
| Latest sequence | C300/996 | C100/1000 (000003E8 hex) |
| Committed records on chip | 20 | 3: D000/998, C000/999, C100/1000 |
| Original raw journal | On chip | Complete private host archive, including all 20 original rows |
| C / D / F tracked counts | 50 / 30 / 24 | 52 / 32 / 24 |
| Other 29 counts / unknown mask | Original | Unchanged / FFFFFFFF |
| Default / mask / entries | B / 0F / all 8000 | Exact original values |
| Application config / pinned generation | Original | Exact original bytes |
| Owner images and F | Original | Byte-for-byte unchanged |
| Owner RAM / ZP | Original pre-helper escrow | Restored and independently read back |
| Final context | REC> | REC>, COM4 released, no restoration pending |

Original escrow is the actual independent capture-a/capture-b MON inventory
from the preceding closeout, before the first RAM helper. Those bytes were
restored/read back in the completed C/D recovery trial. This review does not
claim a new original-prefix capture after raw L; stop if intervening owner
execution makes that provenance inapplicable.

## Prepared artifacts and limits

Private byte-exact reference sectors, sealed fixture/policy packets, history
import and escrow are under:
`C:\SRC\STR8-N\output\qualification\2512-programmer-F-provisioning-20261028-r1\review-r2`.
Original escrow is in the sibling `owner-escrow` directory.

One necessary RAM-only NFC1 build serves both fixture and append-only modes:
template SHA-256
`24d984119fde4cf53abe4a788ea821b72317f0ab24de331af95a90739e764172`.
No F build, reproduction build, CPU/flash simulation or release-kit update ran.
An initial host preparation assertion used the wrong classifier label; it
stopped without hardware access, was corrected, and needed no RAM rebuild.
The first incomplete preparation remains separate from the completed review.

Automatic approval review initially rejected creation of the executable
COM4 trial driver before exact scope approval. The owner then explicitly
approved the four-erase/journal-replacement trial. The driver was created,
inspected and sealed afterward, and bound the public fresh plan before Y.
The reviewed 2512 happy-path hardware gate is now closed; broader limits below
remain. No hardware action preceded approval.

This happy-path trial addresses the separate programmer-installed-F entry on
2512/65C02/FT245. It does not qualify every occupied vendor layout, 65C816,
other adapters, interrupted provisioning, or external programmer operation.
Damaged/conflicting/recognized existing history remains refused by the public
classifier. Kit integration/publication remains separate work.
