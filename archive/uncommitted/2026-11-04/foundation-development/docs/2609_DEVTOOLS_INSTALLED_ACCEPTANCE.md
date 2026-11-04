# 2609 ASM/DBG installed acceptance

**Passed November 2, 2026: 16 recorded checkpoints on2609/65C816 emulation.**
The owner approved the [six-erase scope](2609_DEVTOOLS_FLASH_SCOPE.md), including
host retention of the original WDC bank and the reviewed D-journal rotation.

From REC>, enter `B`, then use `APPS`, `R ASM` or `R DBG` at B3>.
`APP ASM`/`APP DBG` also work. DBG asks for a RAM start address0200–3FFF;
`Q` cancels that prompt, `X` exits stopped debugging and program HOLD returns
to MON. ASM uses `QUIT`. These are RAM-staged interactive tools, not BATCH
returning apps. The assembler stages output at0200; use ORG0200 for direct
execution there, or deliberately place exported output at another origin.

## Installed and verified

| Region | Result |
| --- | --- |
| B0:A/B | ASM and source helper, CPU16 AP/02 envelope |
| B0:C/D | DBG g2, CPU16 envelope, exact SF/1 provider at D800–DFFF |
| B3:E | R ASM/R DBG aliases with the existing full utility profile |
| B3:C/D | Reviewed native D rotation; sequence1095,17 valid records |
| B3:F | Golden4096-byte Foundation0.3.0/g1 BASE1/PR05, unchanged |

The AP/02 targets changed CPU byte15 from02 to16 and recomputed header CRCs;
all executable/body bytes and payload CRCs remained exact. No firmware was
rebuilt. CPU16 identifies the processor, not native-mode execution. This
acceptance uses the common8-bit subset in emulation mode, alongside the
[13-group RAM qualification](DEVTOOLS_2609_EMULATION_RAM_ACCEPTANCE.md).

All installed workflows passed:

- APPS discovery, APP ASM, R/APP DBG and start cancellation.
- R ASM with EQU/labels, ASM/LST/SYMS/DUMP/S19, physical output readback,
  execution and HOLD return.
- Real DBG BRK framing, S/N/JSR/RTS, breakpoint hit, BC and HOLD cleanup.
- X publication of stopped ZP edits; HOLD preservation of live ZP while
  removing breakpoint patches and restoring the public hooks.
- Atomic invalid-call/stack refusal and representative CPU-reassigned/mode
  opcode refusals without execution.
- Public PUTC N step-over, built-in service query and real user callback.
- SF/1 read-only missing-name scan and subsequent PROGRAM overlay reload.
- Existing R CLOCK, R MAINT/BANK MAINT help, R FLASH and SRAM workbench launches.

Independent bank readbacks after programming and after the functional tests
matched the exact reviewed target hashes. The 16 checkpoints include the
five image replacements and preservation checks as well as those workflows.

## Erases, history and owner preservation

Exactly six erases and six journal appends were used: five image sectors plus
one B3:D rotation. All27 old records remain archived on the host; all11 old C
records remain exact on chip. The16 old D records were replaced as approved.
Final sequence1095,17 valid records; B3:C/D/E/F counts80/50/50/31 (decimal).
B0:A–D counts each advanced2→3. Prior-wear flags and other counts carried forward.

Saved B/g10, bank mask00, entries8000, MON A/B, RTC/board metadata, B1/B2,
B0:8/9/E/F and F remained exact. There were no SPI-data/WORKSPACE or RTC-setting
writes, resets, power cuts, retries or extra erases. Other boards and published
downloads stayed untouched. RTC collection finished first and retained priority.

Fresh owner RAM0200–66FF, ZP00–DF, full6B00–77FF cache and original BRK/HOLD
hooks were restored and verified. Final state REC>, COM8 released, RTC eligible.

The original WDC bank is verified in the private scope archive as
`B0-WDC-original.bin` (32KiB), SHA-256
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.
It is retained on the host; the current B0 is no longer a complete original
WDC image. Signature/vector remnants do not establish a qualified WDC fallback.

## Remaining boundary

Positive AS/1 PROGRAM and SF/1 FLASH source-write tests were excluded. The
read-only source backends passed, but no erased source sector exists in the
current B0:8–D arena. No extra B0:9 erase was performed. Persistent fixtures
need a separate reviewed allowance. Native16-bit assembly/debugging and a
complete source-only rebuild are not claimed. C is not a sandbox: user code
must keep IRQ masked and return through HOLD.

Workspace receipts:

- `output/qualification/2609-devtools-flash-scope-20261102-r2/plan.json`
- `output/qualification/2609-devtools-installed-20261102-r1/approval.json`
- `output/qualification/2609-devtools-installed-20261102-r1/report.json`
- `output/qualification/2609-devtools-installed-20261102-r1/completion.json`

Private before/after banks, owner escrow and traces remain outside the release.
