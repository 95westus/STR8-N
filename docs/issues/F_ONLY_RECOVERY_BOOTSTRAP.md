> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Issue: F-only recovery cannot bootstrap monitor A/B without a wear journal

ID: STR8N-005

Status: **Closed**

Opened: 2026-10-11

Resume condition: none for isolated work; keep the running beta23 soak unchanged.

## Impact

Programming only B3:$F000–$FFFF reaches the fixed `REC>` prompt, but cannot
install monitor A/B through the current recovery update command. A valid
configuration/wear journal is also required. F alone therefore does not provide
a complete bootstrap from otherwise erased flash. Normal monitor commands,
including `J`, are unavailable until a valid monitor slot is installed.

## Reproduction and evidence

The beta24 generation 33 linked-model check initializes all four flash banks
to $FF, then programs only the candidate's B3 F-sector image. Cold entry
reaches `FIXED F RECOVERY` and `REC>`. `W` reports `JOURNAL INVALID`; A/B cannot
select absent monitor slots. `J3`, `J0`, `D`, `G`, and `L` return to recovery
without executing normal monitor commands.

Enter `U A`, confirm with `Y` and Enter, then send the matching raw 4096-byte
slot-A binary. The result is `REFUSED/FAILED`, with no flash mutation and the
F sector preserved. No physical board was accessed for this reproduction.

Tracked reproduction: [test_v2_f_only_recovery.py](../../tools/test_v2_f_only_recovery.py).
Generated evidence: `BUILD/v2-board-name/f-only-recovery-test-results.json`.
Beta24 retains the frozen beta23 F-sector bytes, so the new board-name feature
does not introduce this gap; the exact erased-flash reproduction was run on
the beta24 candidate.

## Findings

The fixed recovery dispatcher supports `A`, `B`, `U A|B`, and `W`; it does not
contain the normal monitor command interpreter. The binary update path forces
an erase even when its target slot is already erased. The RAM flash worker
requires successful erase-attempt accounting before erasing; absent journal
records cause that accounting to refuse. This safeguard prevents an
unaccounted erase, but leaves the F-only bootstrap path incomplete.

## Next action

Design a guarded bootstrap contract: explicitly provision a verified missing
journal, or program a fully verified erased slot without an erase, with a
defined follow-on journal-provisioning path. Decide the contract before
implementation; do not silently overwrite unknown or corrupt journal data.
Recording this issue does not implement either option or authorize changing
the running soak image.

## Close criteria

- From otherwise erased flash and F alone, reach recovery and install a valid
  slot-A or slot-B image using the documented operator path.
- Reach the normal monitor prompt and verify `J` and representative normal
  commands, with required journal state explicitly established.
- Reject invalid/incompatible images, cancellation and interrupted transfers;
  qualify power-cut recovery and final commit ordering.
- Preserve fixed F and unrelated flash, retain erase accounting, and refuse
  unknown/corrupt journal formats unless explicitly repaired.
- Retain exact artifact identities, linked-model results and separate physical
  qualification evidence without disturbing the beta23 soak.

## Resolution

Separate candidate implemented October 14; six model suites and the exact
artifact audit pass, including all 123 journal program checkpoints and 11 slot
power cuts. A repeated build produces identical binaries.
No physical boards have been accessed or flashed. The issue remains **Open**
until its physical qualification criteria are satisfied.
See [candidate report and operator path](../STR8N_V2_FIX005_2026-10-14.md).

## October 14 guarded bootstrap contract

The user resumed isolated work after STR8N-004. `BUILD/v2-fix005` is generation
36, based on the 004/local-only TIME candidate. `U A|B` retains image, ABI,
core-cookie, active/preferred-slot and generation checks before any mutation.

With no valid wear journal, the new exception requires every byte of both
C/D sectors to be `$FF`. It analyzes the entire target against the verified
4096-byte upload. Programming is permitted only when every target byte is
either erased or already equal to the upload. No erase is issued; already
equal bytes are skipped. This permits matching interrupted uploads to resume,
while foreign C/D data and differing occupied target bytes refuse. The slot
body is verified before its final commit byte is programmed.

Once a monitor runs, the operator loads the matching
`bootstrap/bootstrap-journal.s19` with `L`, runs it with `G 2000`, and confirms
`Y` then Enter. This separate RAM utility establishes the known initial
configuration/wear record, with sequence 1 and all 32 counts zero. Counts start
at this explicit provisioning; the utility does not claim historical erases.
It uses no erase operation. It refuses another core, unknown/torn formats,
nonblank C/D tails and existing wear history. An exact interrupted prefix of
its own initial record can resume by skipping equal bytes. It verifies the
entire body before publishing the commit; an already complete identical
initial record is idempotent.

With a valid journal, `U A|B` retains the ordinary erase-accounting path.
`W` still reports all 32 bank/sector counts; its redundant title is removed
and its missing-journal message is shortened to `JOURNAL INVALID` to fit F.
All J entries/CRC and the shared F application route retain their addresses.
The matched F/A/B and MAINT identity guard are rebuilt together; 004, TIME,
RTC/SPI, storage, CLOCK and display assets are retained.

## Beta25 compatible single-slot installation on 2609

Beta25 retains the proven generation-35 ABI-family token, separately pinning
exact F identity by full hash/canonical CRC32. Its F instruction bytes match
this candidate; both old beta24 A and new beta25 B are validated against the
retained ABI. The existing MAINT guard therefore remains unchanged. The user
authorized shared changes and only inactive MON B on 2609. Installation,
physical RESET, both monitor versions, F recovery, all 32 W counts, normal
commands, complete flash and retained-device comparisons pass.

The exact beta25 models also pass both F-only destinations, all 123 journal
program cut points, 11 slot cuts and guarded normal erase accounting. No
destructive F-only physical test was performed on the retained live board;
that close criterion remains pending. Board 2604 was untouched. See
[beta25 installation](../STR8N_V2_BETA25_2026-10-14.md).

## Physical acceptance completed October 14

2604 passed separate F-only A and B bootstrap, malformed/canceled uploads,
physical RESET after 1,024/4,096 upload bytes, explicit L/G journal provisioning
and idempotent retry, normal accounted updates, and J3 restart. Fixed F and
B0/B1/B2 were preserved. Original beta24 A/beta25 B and journal records were
restored, with 23 test/restoration erase attempts added to the wear ledger.
Complete SRAM, repaired EEPROM history and RTC settings compare exactly.
The 123 journal and 11 slot interruption checkpoints are linked-model results;
no physical mid-program electrical power cut is claimed.
Evidence: output/qualification/beta25-recovery-2026-10-14/2604/post-005/report.json.
See ../STR8N_V2_RECOVERY_ACCEPTANCE_2026-10-14.md.
