# STR8-N v2-alpha10 interaction milestone

Alpha10 makes the selected flash bank visible at every command prompt and
strengthens confirmation for edits that can compromise a boot or recovery
path. The normal prompt is `Bn> `, where `n` is the current B-command
selection. The help display lists each command's argument form on short lines.

`F` continues to show the selected bank, every `old>new` byte, and whether the
operation will program directly or erase and rewrite a sector. An edit of any
sector F, or any address in Bank 3, now requires two distinct confirmations:
an exact `Y`, followed by the exact selected bank such as `B3`. The second
prompt warns `May not boot/function`. A different bank, malformed input, or
Ctrl-C cancels without starting a flash mutation.

A resident sector-F edit still completes, verifies, and reports entirely from
RAM. It then displays `press Y to soft reset`. Pressing `Y` initializes the CPU
stack/flags and jumps from RAM to the fixed `$F004` public RESET entry. This is
a software restart and does not assert the board's electrical RESET signal.
Other input leaves the RAM prompt waiting. If the edited reset entry or monitor
is invalid, the attempted restart may fail, as warned before mutation.

The image begins with signature bytes `SN 02 00` at `$F000-$F003`. Sixteen
consecutive three-byte public JMP entries follow at `$F004-$F033`; the final
four are reserved and currently lead to a shared safe `RTS` stub. Hardware
RESET and S9 point to `$F004`.

The linked build contains 3,584 resident bytes, including a 501-byte RAM
worker and 56 bytes of RAM interrupt entry code. It leaves 480 erased bytes
before the hardware vector area. All five host suites pass their 33 test
groups, including exact prompt output, risky-confirmation rejection, all-bank
self-edit holds, and a harmless self-edit followed by a successful software
restart. Physical-board qualification is recorded separately.
