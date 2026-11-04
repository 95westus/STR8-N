# Beta34 candidate: ASM 0.5 RAM range and Store command

This candidate adds the requested inclusive RAM range and a monitor Store
command to successful assembly output. It is isolated on
`codex/v2-beta34-asm-summary`; beta33/ASM 0.4 and v2.1 are preserved separately.
Building and model checking access no board. A subsequent, separately
prepared installation on 2512 passed hardware qualification; see the
[live installation record](STR8N_V2_BETA34_2512_2026-10-16.md).

For the attributed Microchess example, the new output is:

```text
OK 1439 bytes, origin $0200, buffer $0200
RAM $0200-$079E
After QUIT; change bank/name as needed:
S 1 AUTO 0200 079E PROGRAM
ASM>
```

The range is inclusive: physical start + assembled length - 1. PROGRAM is
a valid default record name; change it to UCHESS or another wanted name.
The command is printed for use after QUIT at the monitor. It is not executed
by ASM. AUTO selects erased space and does not erase existing records; the
user still chooses the target bank and record name.

The physical code buffer starts at $0200. If ORG differs, ASM shows the
physical RAM range and says `ORG differs; use S19/load at origin before Store.`
It omits the runnable Store suggestion because saving the staged buffer
with its default entry would otherwise imply it runs at the logical origin.
An empty successful assembly says `RAM empty; nothing to save.` Failed
assembly prints its error and does not publish a save suggestion.

The summary uses existing scratch cells, including ENDPTR. DUMP and S19
refresh their own pointers, preserving their logical address behavior.
No new parser command, public ABI, permanent RAM reservation or storage
write is introduced.

| Item | Candidate usage |
|---|---|
| Monitor version / generation | 2.0b34 / 46 (`0000002E`) |
| Assembler | ASM 0.5, 6,508 flash bytes; +264 over ASM 0.4 |
| ASM placement | B1:E000-F96B, entry E010 |
| ASM allocation | Same two 4 KiB sectors; 1,684 bytes outside image, including vector tail |
| Code/output while ASM is open | $0200-$32FF, 12,544 bytes |
| Source / symbols / state | $3300-$4EFF / $4F00-$62FF / $6300-$64FF |
| Permanent RAM increase | Zero |
| Native utility bundle | Unchanged: 22,062 bytes, 466 spare |

Fixed recovery, the RTC/SPI services, existing B2 utility bundle and assets,
and beta28 A fallback retain beta33 bytes. Only ASM, its descriptor/seal,
the monitor version/generation and offline reference metadata change.
Reference bank images are not a preserving live installer.

Build and check from this worktree with the sealed beta33 parent present:

```text
make beta34-candidate
make beta34-check
```

Candidate binaries, usage and proof are under `BUILD/v2-beta34-candidate`.
Qualification covers 212 instruction encodings against an independent WDC
oracle, existing editor/assembler behavior, physical-range boundaries,
empty/failing/relocated results, subsequent DUMP/S19, and copying the actual
printed Store command through Table, Restore-only and Restore/run.
An independent rebuild compares the candidate artifacts and bank images.
Microchess's additional workflow is recorded under `BUILD/microchess-asm05`.

The original receipts below are CPU-model and build results. Subsequent
2512 hardware evidence is stored separately, without modifying the sealed
build. This is not a stable-release declaration; the soak remains stopped.

All listed checks passed: twelve ASM groups, integration, BATCH, Microchess's
actual printed Store command, and 28 byte-identical independent build files.
The [qualification receipt](../BUILD/v2-beta34-candidate/beta34-qualification.json)
binds these results to build SHA256
`2381688f48a5aa2f0da4c8b8f8fd21cdb2087d521861db813ad0d61c936938b1`.
