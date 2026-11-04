# Onboard ASM REPORT candidate

`REPORT` runs on the board's CPU, inside a paired RAM build of BASE1 ASM.
The terminal only receives text; no PC listing generator is involved.

The report contains:

- Five-digit decimal source line numbers, logical addresses and object bytes.
- Aligned continuation rows for longer data declarations.
- Symbol values and qualified local names, in assembler table order.
- Cross-references marked `D` for definition and `R` for expression reference.
  References come from the assembler's semantic symbol lookup, including
  forward references and scoped locals. Comments and quoted text are excluded.
  Repeated references on one source line are combined; long lists wrap after
  eight entries. Symbols with only a definition are visible as unused entries.
- Assembly origin and object byte count.

Build with `python tools/build_asm_report.py`; verify with
`python tools/test_asm_report.py`. WDC02AS/WDCLN and the project's existing
65C02/65C816 model dependencies are required. Neither command opens a port.
The tests exercise the actual assembled 65C02 instructions, bootstrap, command
dispatch/stack balance, local scopes, constant expressions, cancellation, and
source/object preservation in both CPU models. Only the serial ABI is stubbed.

The resulting RAM payload is `BUILD/asm-report/ASM-REPORT-RAM.bin`, entry
`$0200`. It includes the paired assembler and source editor; `report.bin` is
not a standalone application. The bootstrap moves the companion to
`$6800-$6CFF` before entering ASM. Sample output is saved beside it as
`65c02-sample-report.txt` and `65c816-e-sample-report.txt`.

In this candidate's ASM session, enter/paste the desired source, then:

```text
ASM
REPORT
```

The result appears at the serial terminal and returns to `ASM>`. Use terminal
text capture to retain it. `QUIT` returns to the monitor. The small checksum
fixture is `examples/source-cycle/report-demo.asm`; its result is 55 bytes at
`$0200-$0236`, with `$34,$00` at `$1800-$1801` after execution.

This is a CPU-model-qualified RAM prototype, not an installed flash release.
Live use requires the existing qualified RAM loader and full RAM/ZP/cache
escrow, including `$6800-$77FF`; the attempted live trial deferred to RTC
collection without opening a port. Do not send this binary as terminal text
or load it over an owner's application. Source SAVE/LOAD operations are not
supported by this prototype because the companion borrows provider cache.
It retains BASE1's 102-symbol capacity. It does not change F, MON or flash.

Reporting reassembles the source once for the listing and once per symbol
for cross-references, trading CPU time for bounded RAM use. Ctrl-C cancels.
No report date is invented, and no clock or stored settings are changed.
