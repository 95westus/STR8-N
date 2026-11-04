# Unified candidate4 status

November 2, 2026. Current profile: Foundation 0.3.0 g1 BASE1/PR05, MON A/B
0.1.0-dev g10, WB2 gE, PROGRAM g3, SRAM/WORK g4, CLOCK, ASM/DBG g2 and
REC-loaded full MAINT/FLASH. This is a local candidate, not a published release.

## Accepted bytes and boundaries

| Area | Recorded acceptance |
| --- | --- |
| Frozen F | Exact published 4096 bytes; unchanged throughout MON/tool cleanup |
| MON A/B and Traditional startup | Installed and physical-startup receipts on the supported CPU paths |
| Storage/BATCH/loaders | Named flash/PROGRAM, manager G/return, AUTO and large returning PROGRAM fixtures; later compact read/cancel checks |
| CLOCK | Full queries, normal SET and metadata fixtures have dated receipts; calibration/history preserved in cleanup |
| ASM/DBG | Broader 2512 RAM/installed checks; developer candidate2 extracted RAM pass; targeted 2609 emulation and installed checks; 2604 rollout |
| REC MAINT/FLASH | Actual RAM loading and operation on 2512/2604/2609; host-independent of retired utility copies |
| Compact layout | 2604/2609 match 2512, with 36 KiB in erased sectors each; CPU-specific AP/02 envelope fields retained |
| Preservation | Owner RAM/ZP/cache/hooks restored; saved boot policy, board metadata, RTC/SPI and cumulative wear retained as reviewed |
| Terminal 0.1.2 | Earlier candidate3 physical Shift-key/BIN/S19 cancellation/load pass; package includes the current console |
| Candidate4 extracted ZIP, 2512 | Ten RAM groups; extracted ASM/DBG and REC MAINT/FLASH; all terminal actions exercised, including physical Shift+F2/F3, S19/BIN cancellation and normal loads; exact owner restoration |
| Reference SPI layouts | Separately approved native SS2/64K PROGRAM +64K WORKSPACE standardization passed on2512/2609/2604; full SRAM comparisons and exact owner restoration; zero flash/journal writes |
| 2205 SPECIAL rollout | Permanent private b35 archive; approved 34-erase compact Foundation/MONg10/ASM/DBGg2 installation and final saved-B startup passed; all128KiB SPI exact, owner RAM/ZP restored, native TIME/LED RTC readmitted |

All four reference boards now have the common Foundation/MONg10/ASM/DBGg2
feature profile, with CPU-specific envelopes and board metadata preserved.
A later owner-requested 2205 native P64 resize passed, so all four reference
boards now use SS2 with 64 KiB PROGRAM / 64 KiB WORKSPACE. Both old 2205 CLK
records and all payload bytes remain exact. Its old CLK payloads are retained
data, not newly qualified legacy-ABI apps. The original three-board receipt
and SPECIAL archive stay unchanged; the four-board combined receipt is
`output/qualification/SS2-64K-four-board-complete-20261102.json`.
See [2205 rollout acceptance](2205_FOUNDATION_ROLLOUT_ACCEPTANCE.md).
This rollout did not alter the Candidate4 ZIP or published downloads.

Cleanup used 21 approved erases: nine on 2604 (including native D rotation),
twelve on 2609 with no C/D erase. All 26 old 2604 rows were host archived;
16 D rows were replaced on chip and ten C rows retained. All 17 old 2609
rows remained on chip. No F or MON rewrite occurred. These are historical
test allowances, not permission to erase a user's board.

## What this packaging step proves

The fresh ZIP contains the exact qualified components, correct CPU envelopes,
both REC BINs, Python terminal, manuals and examples. Extraction/file pins,
host sector preparation/preservation and CLI smoke checks run without serial
access. The entire published Foundation subkit remains byte-for-byte exact.
The current terminal is included separately; the root launcher selects that
console with `--kit foundation` for its unchanged Foundation presets.
Private chip/owner-memory captures and vendor WDC firmware are excluded.

## Remaining gates and limitations

Candidate4 extracted-kit RAM acceptance passed on 2512 on November 2, 2026.
The ZIP SHA256 is
`1e9d5a8e0f81036412ae7411edb80db37c9b4cd1d4eddcd2756fae26b27e77e9`.
The companion `BUILD/unified-g10-candidate4-20261102-r1/ACCEPTANCE-2512.json`
records the exact action and physical-key coverage. Ordinary actions also
used buttons; this is not a claim that every F-key was physically pressed.
Native file dialogs were prefilled by the harness. The first guided attempt
stopped at file selection; its restoration passed independently before retry.
All four flash banks, SPI metadata, owner RAM/ZP, cache and hooks were verified
exact. No persistent writes, physical resets or power cuts occurred; RTC kept
priority and no other board was accessed. Final state: REC>, COM4 released.
The tested ZIP was not rebuilt or edited; its internal pending-status text
records packaging time. This companion result supersedes that status for
2512 RAM acceptance only; it does not add a new 816 extracted-kit pass.

- Earlier candidate3/developer candidate2 passes remain evidence for their
  specific archives; broader CPU and positive-write scopes remain distinct.
- The g1-based REC MAINT does not expose the former g3 `EDU SAVE` or named X
  transfer commands. Saved EDU policy is still read at startup; session EDU
  commands and normal copy/restore/store workflows remain available.
- The assembler is a 65C02 cross-assembler. DBG's 816 scope is the common
  8-bit emulation subset; native 816 and hardware IRQ debugging are excluded.
- Physical source-write/clock administrative fixtures retain their original
  board scopes. CPU-RAM fault injection does not close real latched-event,
  changed hardware-trim or battery-condition cases.
- Factory-restoration preparation is host-only; actual factory restoration,
  source-only rebuilding of this extracted kit, and the later Host/B0/Both
  full WDC migration workflow remain separate qualifications.
- The reference boards2512/2609/2604 now use SS2 with64 KiB PROGRAM and64 KiB
  WORKSPACE. The separate standardization preserved every payload byte and
  all flash/settings/history, restored owner RAM/ZP/cache/hooks, and released
  all ports at REC>. Native upgrade ran once on2512/2609; native resize ran
  once on2604. A volatile reader-profile correction on2512 required read-only
  continuation, without replaying its upgrade. Full receipts and permanent
  private preimages are retained locally; see
  `output/qualification/SS2-64K-standardization-complete-20261102.json`.
  The installer still does not silently upgrade, resize or format another
  user's SRAM. Existing SS1 stores require a separate reviewed upgrade for
  managed WORK. The original candidate4 ZIP and published downloads are exact.

No publication, tag/ref change, board access or flashing occurs in packaging.
The published Foundation and historical candidate downloads stay unchanged.
