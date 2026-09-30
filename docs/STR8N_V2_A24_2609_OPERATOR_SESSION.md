# Board 2609 - exact alpha24 migration session

The kit includes the two original host files from the owner's 2026-09-30
COM8 migration. `EVIDENCE/v2-a24-migration-20260930-152511.raw` contains the
bytes received from the board. The matching `.raw.events.txt` records host
actions, including transmitted lines and the Ctrl+U file transfer. The raw
file does not record host keystrokes before the board echoes them; use both
files to reconstruct what happened.

| Evidence | Exact text |
| --- | --- |
| Board prompt in raw transcript | `TYPE INSTALL STR8-N 2.0a24> ` |
| Host `TX LINE` in event log | `install str8-n 2.0a24` |
| Board echo in raw transcript | `INSTALL STR8-N 2.0A24` |
| Board result | `MIGRATION VERIFIED; PRESS PHYSICAL RESET` |

The firmware's input routine converts ASCII `a`-`z` to uppercase before it
stores and echoes the characters. Its comparison token is uppercase
`INSTALL STR8-N 2.0A24`. The operator typed the lowercase line recorded by
the host, the board echoed the normalized uppercase line, and the install
gate accepted it. The printed prompt retains lowercase `a24` because that
prompt is fixed message text. This is a case-normalizing input path, not
evidence of two install attempts.

The same raw transcript shows `STR8-N 2.0a24 B3 65C816`, the capability
banner, `B3> J0`, and the stock W65C816SXB menu. The host event log records
the pinned 4,096-byte F BIN SHA-256 and byte-exact RAM installer readback.
See the [board status record](STR8N_V2_2609_MANUAL_REMIGRATION_2026-09-30.md)
for the resulting bank layout and qualification limits.
