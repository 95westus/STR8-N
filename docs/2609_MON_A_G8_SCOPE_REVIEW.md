# 2609 MON A g8: owner-choice review

**Owner approved install-and-keep; trial passed.** October 30, 2026.
See [acceptance](2609_MON_A_G8_ACCEPTANCE.md). The options below retain
the original pre-install review; only the one-erase option was executed.
Before this trial, 2609 had qualified MON B g8 and retained PR04/b15 MON A.
The candidate A is from the exact g8 build whose B image already matches
installed B byte-for-byte.
No firmware rebuild or CPU simulation is required.

## Two concrete options

| Option | Erases | Journal | Final MON A | A count |
| --- | ---: | --- | --- | --- |
| Install and keep current A | One B3:A erase | D300 / seq1034 | PR05 g00000008 | 51→52 |
| Temporary A test, then restore | Two B3:A erases | D300 / seq1034; D400 / seq1035 | Original PR04 generation 8000000F | 51→53 |

Both preserve **all 19 current raw journal records on chip**, default S,
mask 00, all entries 8000, every other setting/count, B0/WDC, B1/B2, MON B,
services E and frozen F. **Zero F writes or C/D erases.** C/D/E/F counts remain
78/48/45/31. No power cut, SRAM/WORKSPACE write, clock SET/trim/PF acknowledgement,
other-board access, push or release-download change is included.

The install-and-keep choice replaces an owner-retained on-chip image. Its exact
original A and complete original banks must remain in verified private host
backups; restoring it later would require another counted erase. The temporary
choice instead spends that second erase within this scope and restores A exactly.
This choice is required by the owner's preserve-images constraint, not by a
need to change F or clear journal history.

Original A SHA-256:
`0cbaa80b6d9d168775cb25c737271f9eb104aa760402a7ec3fd1fae0fae89c04`.

Candidate A SHA-256:
`01fe3f4d753881431aa2aeb5373779a293888d07311e0e8c118459cb1f0aafbe`.

Unchanged paired B SHA-256:
`41715a49265bdfdcc938944e78580a1e59de125081d726ad011df94aa4868c95`.

## Required live sequence after selection

1. Acquire the shared serial lease; use only COM8 / USB A10MPQXCA. Board idle,
   terminal disconnected. Verify qualified MON B/CPU16 and take fresh native
   owner RAM0200–66FF/ZP00–DF double escrow before any helper. Respect the current
   RAM reference, reconciled at 20:32 UTC; do not restore an old installer escrow.
2. Independently double-read all banks and match the reviewed current images,
   valid journal seq1033/19 records and golden F. Save durable complete originals
   and old A. Recheck ordinary journal capacity; never erase C/D for this case.
3. Use the existing guarded OPAQUE RAM writer for A only. Its native reservation
   commits before the erase. Verify the sector and all complete bank postimages.
4. Enter the newly admitted A; check identity, basic Dump/Modify, protected
   F/C/D refusal, M1/W/APPS and current flash-tool reload. Check read-only CLOCK,
   PROGRAM Table and bounded BATCH/preview-cancel paths, with Q/HOLD returning
   to the expected active MON A. No Store or new app-data write is admitted.
5. Arm the receiver before requesting a physical RESET; select A one-time at
   the chooser, leaving saved default S. Verify cold MON A identity/startup and
   preservation. Any additional reset must have an armed receiver.
6. For the temporary option, return to REC> before restoring old A with its
   second reserved erase; do not execute the restored unqualified PR04 A.
   Independently double-read all final banks. Restore/read back fresh owner
   RAM/ZP through BASE1 and native qualified MON B, then finish at REC>.
7. Advance RTC **admission only** for the exact new image/journal receipt,
   preserving the latest owner-RAM reference, sampler bytes/profile, clock
   settings, historical points and baselines. Requalify its read-only path.
   The strict current admission pins the pre-A-upgrade B3 hash and must not be
   bypassed. Release COM8 with no pending restoration.

No further writes are authorized by this review. Failed transfer/postimage
admission stops without automatic flash retry; retain the phase log and originals.

Private plans and exact postimages:
`C:\SRC\STR8-N\output\qualification\2609-MON-A-g8-scope-20261030-r1`.

Install-and-keep plan SHA-256:
`f75cb157c40deea697e0e7d42b2e712251a2e9e3e8d27a9a779a348d8f8d6363`.

Temporary-test plan SHA-256:
`3b0491b347f923add06a627bb7728db82e7af9c8076de6f5b0b9fe8005a4a90d`.
