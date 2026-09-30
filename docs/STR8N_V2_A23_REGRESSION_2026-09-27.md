# STR8-N 2.0a23 regression

Date: 2026-09-27. Target: W65C02SXB board 2205 on COM3 at 115200 baud.

## Candidate

2.0a23 gives the F-sector size reduction its own version and source tree under
`src/v2a23`. The resident build is 4,044 bytes, leaving 20 bytes before
vectors. The RAM worker remains 759 bytes; the RAM vector/public code remains
196 bytes. The a23 F sector differs from the installed optimized a22 F by one
version-text byte. The E extension code and the board's E sector are unchanged.

| Image | SHA-256 |
| --- | --- |
| Previous optimized a22 F | `23278c32717d8cd1a26b13d7eddc79019050f2ba21f37729e9566a2e021758cd` |
| a23 F | `24d0d9f2c7f619aece4d608b706c1a9b862b69c3bc2a411fe7dcc79fc1d36fa0` |
| Installed a23 B3:E/F | `307f0293c2179733d947d12e5e6f13d8e007eae7ed6e68f2c10c14f86e667012` |

## Host regression

`make v2-a23-check` rebuilds the historical a22 baseline, builds a23, and
runs ten linked-code suites: boot, ACIA probe, guarded migration, monitor,
S19 load, flash, configuration, interrupt probes, S/R/T, and the focused F
size/prompt cases. All passed. The board-specific F updater model also passed
exact old-image rejection, B2:F backup, installation, recovery, and mismatch
rejection. Historical `make v2-check` passed after the shared test harness was
updated for both layouts.

The modeled 10-tenth autostart window measured 8,258,653 cycles, or 1.032 s
at 8 MHz. Negative interrupt probes intentionally print FAIL/TIMEOUT as part
of their rejection tests; the suite result passed.

## Board installation and readback

The installed B3:E/F matched the previous tested optimized a22 image before
the update. B2 matched its complete earlier readback. The exact-image RAM
updater reported `BACKUP VERIFIED` with old-top sum `$26FF`, then reported
`STR8-N 2.0a23 VERIFIED; RESET`. It reached the `B3>` prompt with the a23
banner.

The complete B3:E/F readback exactly matched the a23 F and the original E:
only one byte changed in B3:E/F. The full B2 readback proved B2:F equals the
old optimized a22 F, while B2 sectors 8-E remained unchanged. Final complete
B2 SHA-256:
`2b07b9bd7431d140705a7df060490127670a2d56dc42b79a595e7f864a9ca62d`.

Board checks passed:

- `C` still reported `C 00 00 V 0A`; `?` still listed all commands.
- `T 3` listed the existing `8FF0 ... TEST` record. `R 3 8FF0` restored
  `12 34 56 78` to RAM after clearing those four bytes.
- `F E800 00` on B3 returned `Protected`.
- The RAM ABI probe printed `B0 B1 B2 B3 RAM ABI: PASS`.
- The BRK/VIA1 IRQ probe printed `V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS`.
- A wrong bank response to the F risk prompt canceled. The matching `B2`
  response reported `Done` for a no-op `F F000 53` edit.
- `J3` printed 160 startup dots and the a23 banner, then returned to `B3>`;
  `C` and `T 3` still reported the same configuration and record.

## Scope and follow-up

The model exposed an existing a22/a23 behavior: an enabled vector autostart
whose target vector is erased prints `Bad vector` through ACIA before console
selection. The model reaches the resident prompt, but an FT245-only host may
miss that message. This was not introduced by the a23 version change.

Physical RESET, cold USB reconnect, and physical NMI require separate human
interaction and are not counted as passed here until captured. W65C816 board
qualification remains outside this W65C02 session.

Build and board evidence is under
`output/qualification/board-2205-a23-2026-09-27/` and the preceding
`output/qualification/board-2205-f-size-2026-09-27/` logs.
