# Common ABI calls as BRK functions

The present candidate implements only `$80-$84`: debugger query, user register,
user unregister, register trace and bounded text output. The table below is a
proposal for a later ABI revision, not implemented or allocated by this board
test package. They are not added by corrected-candidate release staging.

| Proposed ID | Existing RAM ABI | Proposed BRK contract |
| --- | --- | --- |
| `$85` | PUTC `$7E6D` | Output A; preserve saved A/X/Y/P |
| `$86` | GETC `$7E70` | Blocking input; return byte in A, preserve X/Y; Ctrl-C is `$03` |
| `$87` | RAW_POLL `$7E73` | C=1 and A=byte when available; C=0 when empty; preserve X/Y |
| `$88` | CHECK_CANCEL `$7E76` | C=1 when cancellation is pending; preserve A/X/Y |
| `$89` | RX_RESET `$7E79` | Clear receive queue, overflow and cancellation state; preserve registers/flags |
| `$8A` | HEX_OUT `$7E7C` | Print A as two hex digits; preserve registers/flags |
| `$8B` | NEWLINE `$7E7F` | Output CR/LF; preserve registers/flags |
| `$8C` | HEX_NIBBLE `$7E82` | Convert ASCII in A: C=1,A=0..15; C=0 invalid; preserve X/Y |
| `$8D` | CAPS_QUERY `$7E85` | A=format, X=capabilities, Y=descriptor length, C=1 |
| `$8E` | BOARD_QUERY `$7E88` | A=format, X=CPU ID, Y=board/console flags, C=1 |

The return policy for other status bits must be specified before implementation;
wrappers must copy results into the saved context rather than restoring the
input carry over a service's result. GETC's cancellation behavior should remain
consistent with rc1. A console initialization service could follow if drivers
need it; it resets hardware/queue state, so it is less useful as an everyday
application function.

`BRK xx` is two bytes, compared with three for `JSR address`. It enters through
the current bank's hardware vector, saves the application context and changes
to the service bank. In this implementation that includes zero-page and stack
snapshots, so the one-byte saving has a substantial execution cost. Keep JSR
available for tight character loops. `$84` already offers a useful bulk operation:
A/X is the RAM text pointer and Y the byte count, preserving registers/flags.

Use `$80-$9F` for fixed firmware functions, `$A0-$BF` for the four dynamic system
slots and `$C0-$FE` for sixteen user slots. A fixed service consumes firmware
space without consuming a dynamic registration. `$FC/$FD/$FF` also have private,
origin-checked firmware uses in this candidate. In application RAM, `$FC/$FD`
still follow user registration rules; do not allocate fixed services over them.
`$FF` is outside the user registration range.
An unrecognized signature stops in the debugger. Do not write code assuming
these proposed IDs already perform I/O.

RESET/HOLD, flash writes/erases, bank-selection policy, line editing and provider
loaders should retain their current explicit entry points for this first version.
HOLD has special cleanup semantics, and loaders/flash staging share debugger
workspace. RTC/storage wrappers need a separate ownership and return contract.
All proposals here are for 65C02 and 65C816 E=1 applications; native calls and
native debugging remain outside scope.
