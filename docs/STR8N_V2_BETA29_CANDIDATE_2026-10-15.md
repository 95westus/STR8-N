> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta29 BATCH candidate — not flashed

Offline qualification passed: both CPU-model suites and the independent
27-file rebuild comparison. Board 2512 remains on beta28.

Package: `BUILD/v2-beta29-candidate`. This is an offline candidate for board
2512's existing recovery ABI. Its reference layout installs beta29 generation
41 in slot B and retains beta28 generation 40 in slot A. Fixed B3:F, B0 and
the RTC/journal identity tail are preserved in the reference images. No
installer is generated. A later installation needs fresh board backups;
the reference images must not be written directly over a live board.

## BATCH

Enter an inline list at the monitor prompt:

```text
BATCH R SRAM;G CLK;STATUS;Q
```

The monitor runs `R SRAM`, SRAM runs `G CLK`, CLOCK runs `STATUS`, and CLOCK's
`Q` returns to the monitor. The executive then reports `BATCH done`.
`BATCH R SRAM;G CLK;Q` launches CLOCK and immediately quits it.

Each interpreter receives a complete command at its command boundary.
Commands are not injected as UART keystrokes. An error discards all remaining
commands and leaves the current interpreter available for correction. Esc
cancels commands that have not yet run. The currently executing command
keeps its existing cancellation rules; completed operations are retained.

Confirmation prompts always wait for manual input. For example,
`BATCH R MAINT;NAME TEST;YES;Q` waits at NAME's confirmation prompt; the queued
`YES` is not consumed as an answer. Esc or refusal stops the remainder.

The initial implementation supports:

- Monitor queries/help, bank selection and native utility launches. Raw
  monitor jumps, loaders, resets and raw writes are rejected in BATCH.
- MAINT, SRAM, WORK and EDU command interpreters, retaining their normal
  validation and confirmation rules.
- The included CLOCK 1.9 image, when saved as `CLK` and launched through SRAM.
  CLOCK is the currently registered RAM interpreter. Other RAM programs,
  including older CLOCK images, are refused by BATCH before execution.

BATCH is monitor-only, foreground and volatile. Its command-list limit is
34 characters, including spaces and semicolons, after `BATCH `; the complete
monitor line remains limited to 40 characters. Surrounding command spaces
are ignored. Empty commands, doubled separators and a trailing separator
reject the entire list before any command runs. There is no quoting,
nesting, saved batch-file format, loop or parameter substitution.

2512's retained SRAM has no valid saved-program directory. The candidate
does not format it or install CLK into it. Tests that need a saved CLK format
and populate a separate in-memory model only. The supplied CLOCK 1.9 is also
present as the ordinary B1 CLOCK record, with its BATTERY controls available
through interactive `R CLOCK`.

## NAME correction

MAINT 2.3 retained direct flash-bank switches in its NAME handler. Those
switches changed the instruction source while MAINT was executing in B2.
MAINT 2.4 uses logical bank reads and the RAM gateway for flash-byte writes.
NAME waits for exact YES, appends a CRC-protected record, commits last, and
verifies the result. Refusal does not write or erase anything.

## Space and recovery

| Item | Usage |
| --- | ---: |
| Native utility flash reservation | 22,528 bytes |
| Utility code, shared helpers, help and seal | 21,874 bytes |
| Remaining utility space | 654 bytes |
| Added utility flash since beta28 | 1,424 bytes |
| BATCH RAM reservation | 156 bytes in existing protected RAM |
| CLOCK 1.9 RAM image | 11,224 bytes, 2000–4BD7 |
| CLOCK flash record | 11,248 / 12,288 bytes |
| Monitor body per slot | 3,967 / 3,968 bytes |

BATCH uses 36 bytes at 7BD4–7BF7 for its text/padding, 96 at 7C90–7CEF
for its bank-safe gateway/padding, and 24 at 7EE4–7EFB for state. These avoid
the 4 KiB sector staging region, journal scratch, WORK/SRAM buffers, EDU
variables and hardware I/O. The byte-read worker continues using its
documented 16-byte buffer at 7C80–7C8F. Application RAM remains 0200–64FF
with EDU ON; the four utilities retain their beta28 variable/buffer locations.

The monitor checks the provider's release header and full CRC before
enabling BATCH on monitor entry. A damaged or older B2 provider leaves the
basic monitor usable. Full monitor help lives in B2; abbreviated recovery
help remains in the monitor. Retained beta28 A can run the new utilities and
CLOCK interactively, with batching disabled. This candidate's BATCH hooks
are bound to beta29 in slot B; it is not an installation image for another
board or slot arrangement.

## Offline evidence

The CPU-model suites cover sequential commands, prompt transitions,
stop-on-error, Esc, empty-list validation, confirmation isolation, the NAME
regression, saved CLOCK execution, unregistered-program refusal, complete
sector staging, and retained-slot operation. They forbid treating the board's
7F00–7F7F I/O area as RAM. An independent rebuild compares 27 files exactly.

Final receipts and exact usage are in `beta29-qualification.json` and
`usage.json` inside the package. They describe offline testing only; no board
was accessed or flashed for this candidate.
