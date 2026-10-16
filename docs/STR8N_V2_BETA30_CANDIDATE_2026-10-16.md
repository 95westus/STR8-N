# Beta30 candidate: native utility aliases

Beta30 adds exact bare-name aliases for MAINT, SRAM, WORK and EDU at the
monitor prompt and in BATCH segments dispatched by the monitor. Existing
R-prefixed launches remain supported. This is an offline candidate; no
board port was opened and nothing was flashed for this build.

Examples:

```text
MAINT
SRAM
WORK
EDU
BATCH SRAM;G CLK
BATCH SRAM;G CLK;STATUS;Q
BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q
```

The aliases expand to the existing `R name` command before dispatch. Input
still uses the monitor's normal case conversion. Leading/trailing spaces
are accepted for bare aliases; names must match exactly and take no extra
arguments. For example, MAINTX and EDU OFF do not become utility launches.
For explicit bank selection or other R syntax, retain the R prefix.

Aliases apply when the current interpreter is the monitor. Once a utility
is running, its existing commands retain their meaning. Q returns to the
monitor, after which another alias can run. BATCH completion stays in the
current interpreter; a final Q is needed to return from CLOCK. Stop-on-error,
Esc cancellation and real confirmation prompts retain beta29 behavior.

`BATCH SRAM;G CLK;STATUS;Q` requires a valid SRAM directory containing a
batch-aware CLK program. The included CLOCK 1.9 binary is unchanged. Saved
SRAM records, board name and display offset are not modified by this build.

## Usage

| Item | Beta30 |
| --- | ---: |
| Native utility flash reserved | 22,528 bytes |
| Utility code/help and seal used | 22,012 bytes |
| Utility flash remaining | 516 bytes |
| Increase over beta29 | 138 bytes |
| Additional RAM | 0 bytes |
| Existing BATCH protected RAM | 156 bytes |
| Monitor body per slot | 3,967 / 3,968 bytes |
| CLOCK 1.9 RAM | 11,224 bytes, 2000–4BD7 |

Utility entry addresses, WORK's compatibility stub, shared B3:E, fixed B3:F,
CLOCK and its batch ABI remain unchanged. The provider release tag is
updated consistently in the monitor, native bundle and status loader.

## Validation and package scope

The CPU-model tests cover all four bare launches, case and whitespace,
exact-token rejection, mixed bare/R-prefixed batches, all-four-utility
handoffs, SRAM-to-CLOCK execution, error stopping, Esc, confirmation
isolation, complete sector staging, protected RAM and fallback operation.
A second independent build compares 27 files byte for byte. The final
`beta30-qualification.json` pins the tested build and test receipts.

Package: `BUILD/v2-beta30-candidate`.

The candidate retains beta29's B-slot batch binding and A28 reference
fallback arrangement for offline tests. Its reference bank images are
explicitly marked unsuitable for installation. They do not represent the
board's current SRAM layout, CLOCK location, board name, offset or wear
counts. No deployment plan or board-specific installer was generated.
A future authorized installation must use fresh board backups and preserve
the user's current data and configuration.
