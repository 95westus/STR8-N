# DBG g2 installed acceptance on 2512

**Passed on November 2, 2026, on 2512/65C02.** The owner approved the
[reviewed two-erase scope](2512_DBG_G2_FLASH_SCOPE.md). The existing
RAM-qualified build was reused without rebuilding F, MON or ASM.

DBG g2 is installed at B0:C/D. At REC>, enter `B` for the saved MON B,
then `R DBG` at `B3>`. Enter a user RAM start address ($0200–$3FFF), or
`Q` to cancel. `X` exits a stopped debugger; a running program returns
through HOLD. `APP DBG` and the APPS catalogue also work.

Thirteen recorded checkpoints passed, including fresh scope admission,
both sector replacements, independent bank/journal readback and these
installed workflows:

- APPS discovery, R/APP launch and start-prompt cancellation.
- X publication of stopped logical ZP edits; HOLD preservation of live ZP
  while removing patches and restoring public hooks.
- Bare BC, BC *, trailing-argument refusal and duplicate step-patch cleanup.
- Rejected JSR without changing the logical stack, memory bounds and
  refusal of an indirect pointer into I/O.
- Public PUTC step-over with N and return through HOLD.
- Built-in query, callback registration and execution of a real user callback.
- Unchanged ASM and SF/1 provider admission after DBG.

Exactly two erases were used, at B0:C/D, with two wear reservations at
B3:CA00/seq1200 and CB00/seq1201. All 26 preexisting journal records remain
exact at their original addresses; the final journal has 28 valid records.
B0:C/D counts each advanced 2→3. B3:C/D/E/F remain 58/38/39/24.

All four banks match the reviewed target hashes. Golden F, MON A/B g10,
default B and its generation, ASM, the exact B0:D800–DFFF SF/1 provider,
board metadata, unrelated images and reclaimed sectors are preserved.
There were no C/D erases, SPI-data or RTC-setting writes, resets, power cuts
or automatic retries. No other board was accessed. RTC collection retained
priority through the shared lease/window; its schedule was unchanged.

Fresh owner RAM $0200–$66FF, ZP $00–$DF and the full $6B00–$77FF provider
cache were restored and verified. Public hooks were restored. Final state:
REC>, COM4 released. Candidate3 and published downloads are unchanged.

The earlier [17-group RAM suite](DBG_BROAD_2512_RAM.md) remains the broader
65C02 core evidence. Free-running C is not a sandbox: user code must keep
IRQ masked and return through HOLD. Native816 developer qualification and
extracted developer-kit acceptance remain open; this follow-on increment
is not added to the published release by this board trial.

Workspace evidence:

- `BUILD/dbg-base1-g2-r1/manifest.json`
- `output/qualification/2512-DBG-g2-install-scope-20261102-r1/plan.json`
- `output/qualification/2512-DBG-g2-installed-20261102-r1/approval.json`
- `output/qualification/2512-DBG-g2-installed-20261102-r1/report.json`
- `output/qualification/2512-DBG-g2-installed-20261102-r1/completion.json`

Private captures include the fresh owner escrow, before/after bank images
and serial trace. They are not release payloads.
