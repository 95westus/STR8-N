# R-YORS Integration Boundary

STR8-N owns its resident source, embedded worker, payload tools, protected 4K
layout, directory rules, and public ABI. R-YORS consumes verified artifacts;
it must not maintain a second live STR8-N source tree.

## Normal two-folder workspace

```text
parent/
  R-YORS/
  STR8-N/
```

`STR8N_HOME` may point at a differently located STR8-N checkout:

```text
make -C SRC str8n-external-check
make all STR8N_HOME="C:/path/to/STR8-N"
```

A release build must match the R-YORS content lock and use a clean STR8-N
worktree. The lock binds the top-sector and public-contract hashes; docs-only
STR8-N commits do not require lock churn.

## Published STR8-N artifacts

```text
BUILD/v1.21/bin/str8n-v1.21-bank3-f000-ffff.bin
BUILD/v1.21/s19/str8n-v1.21-f000.s19
BUILD/v1.21/s19/str8n-v1.21-worker-0200.s19
BUILD/v1.21/s19/str8n-v1.21-bank-maint-2000.s19
BUILD/v1.21/s19/str8n-v1.21-console-abi-test-2000.s19
BUILD/v1.21/s19/str8n-v1.21-top-update-2000.s19
BUILD/v1.21/s19/str8n-v1.21-directory-refresh-2000.s19
BUILD/v1.21/include/str8n-public.inc
BUILD/str8n-manifest.json
```

The manifest publishes the top-sector and worker layout, hashes, public ABI,
record service version/capabilities, and hashes for every maintained RAM tool.
Bank Maintenance loads at `$2000-$362A`, keeps its private worker at
`$3400-$362A`, and offers map, copy+directory, adopt, erase, and AP operations.
The directory-refresh image preserves a verified copy in Bank 1 sector F
before clearing Bank 3 `$FFB0-$FFF9`. The
R-YORS lock binds the core top-sector/public-contract content needed by its build.
R-YORS verifies the locked values, resident ABI gates, fixed service
addresses, vectors, and protected layout before constructing Bank 3.

```mermaid
flowchart LR
    S[STR8-N source] --> B[verified 4K top BIN]
    S --> W[worker evidence]
    S --> T[versioned RAM tools]
    B --> M[STR8-N manifest]
    W --> M
    T --> M
    M --> LOCK[R-YORS lock check]
    B --> BANK3[R-YORS Bank-3 image]
    RY[R-YORS ASM + HIMON] --> BANK3
```

## Bank-3 ownership

```text
$8000-$BFFF  ASM-F2, built by R-YORS
$C000-$EFFF  HIMON, built by R-YORS
$F000-$FFFF  STR8-N, verified external 4096-byte BIN
```

R-YORS code binds only to interfaces listed in the
[Technical Guide](TECHNICAL_GUIDE.md#public-interface). Its Banked-AP helper
runs at `$0300` after the STR8-N selector prefix at `$0200-$0228`; it shares
the larger `$0200-$0453` worker tray rather than coexisting with the complete
mutation worker. The R-YORS build must reject overlap with the selector prefix
if that contract moves.

`$F003` initializes the raw console and `$F006` reports resident ABI version
and capabilities. Record parsing is `$F009` ABI V2. Bank select is `$F010`,
with its return-capable RAM entry at `$0203`. Worker mode 6 is not an
interface.

## R-YORS files consumed by STR8-N tools

The reverse dependency is limited to the optional full-bank image builder:

```text
R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19
                         28K dense payload, $8000-$EFFF, S9 $C000
STR8-N BUILD/v1.21/bin/str8n-v1.21-bank3-f000-ffff.bin
                          4K current top, $F000-$FFFF
                                      |
                                      v
STR8-N BUILD/v1.21/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
                         32K dense payload, $8000-$FFFF, S9/RESET $F000
```

Run `make ryors-full-bank`. The builder validates every byte and checksum in
the R-YORS 28K S19, appends the current STR8-N BIN, verifies RESET, and emits
a new dense S19. It deliberately does not reuse a stale STR8-N top sector from
an older combined R-YORS binary.

The `8-F` output is for Banks 0-2. Bank 3 sector F remains externally
programmed and protected from `I`.

## RAM-loader boundary

STR8-N `L` is an operator recovery command, not a public callable ABI. It
loads S1 data only in `$2000-$7AFF` and immediately executes an in-range S9.
The supplied bank-maintenance S19 uses that path and is independent of HIMON.

HIMON bare `L` is a separate R-YORS feature. It uses a HIMON-private S0/S1/S9
parser, applies HIMON's own RAM destination policy, and reports S9 without
executing it. HIMON does not call STR8-N `$F009`; `L G` and `L F` are
rejected.

## Hardware acceptance

On 2026-08-13 the separated build installed the exact R-YORS 28K Bank-3
`8-E` payload through STR8-N 1.2. One initial transfer failed before any
sector-progress dot; an immediate retry programmed all seven sectors and
committed `OK`. Physical RESET then cold-booted HIMON `00.0813(0552)`, entered
and exited ASM-F2 `00.0813(0552)`, and a final RESET/live-`S` selection
returned to STR8-N. Sector F was not rewritten. The exact append-only terminal
evidence is retained in sibling R-YORS at
`DOC/GUIDES/LOGS/HARDWARE_TEST_LOG.md`.

The continuation loaded the standalone `$2000-$362A` Bank Maintenance image
through HIMON bare `L`, started it with explicit `G 2000`, copied all eight
Bank-3 sectors to Bank 0 behind the exact `COPY 30` guard, and enrolled
`D0 FF COPY1 FFFF FCFFFFFF`. STR8-N's own `L` then loaded and directly ran the
maintenance image; its map showed the Bank-0 copy and D0 enrollment persisted.
A final RESET still cold-booted HIMON. The complete transcript and bounded
claims are retained in
[R_YORS_OWNERSHIP_CUTOVER_HARDWARE_PROOF_2026-08-13.md](R_YORS_OWNERSHIP_CUTOVER_HARDWARE_PROOF_2026-08-13.md).
