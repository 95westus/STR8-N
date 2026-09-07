# Reset-source indication

STR8-N prints a leading CR/LF and exactly one reset-source line before its
identity:

```text
RST H
RST S
```

`H` means hardware reset or an unmarked legacy entry. `S` means a cooperating
software path committed the one-shot record immediately before entering the
STR8-N reset vector. The W65C02 and board expose no reset-cause latch, so STR8-N
cannot distinguish a physical button press from arbitrary unmarked code that
jumps to `$F000` or through `$FFFC`.

## RAM record

The additive RAM ABI allocation is:

```text
$7DE7  STR8_SOFT_RESET_SIG0  'R'
$7DE8  STR8_SOFT_RESET_SIG1  'S' (commit byte)
```

A software restart must disable interrupts, clear `$7DE8`, write `R` to
`$7DE7`, write `S` to `$7DE8` last, and immediately jump through the active
Bank-3 RESET vector or to STR8-N `$F000`. STR8-N validates both bytes and clears
`$7DE8` before printing, making the record one-shot. The two-byte signature
limits accidental cold-RAM classification; it is telemetry, not a hardware
security boundary.

The guarded Top Update, Directory Refresh, Bank Maintenance return, and
WDCMONv2 migration/restore paths implement this contract. Older software that
does not write the record remains compatible and reports `RST H`.

## Layout

The resident grows from 3,368 to 3,398 bytes and ends at `$FD45`. Ten erased
bytes remain before the fixed worker at `$FD50`; the layout guard enforces an
8-byte minimum. The fixed resident entry points, IVI targets, worker, directory,
configuration pocket, and hardware vectors are unchanged.
