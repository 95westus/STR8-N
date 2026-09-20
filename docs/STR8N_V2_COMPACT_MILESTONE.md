# STR8-N v2-alpha6 size pass

Historical milestone. The current [alpha7 pass](STR8N_V2_LEAN_MILESTONE.md)
further shares code and relaxes three nonessential checks.

Reduces the complete alpha5 monitor by **206 bytes**, from **3882 to 3676**.
There are now **388 bytes free** before the hardware vectors at $FFE0.
The command set, safety checks, flash protections, configuration format,
autostart/hold behavior, and application RAM boundaries are retained.
No convenience commands were added. Hardware qualification remains pending.

## Where the savings came from

| Top-sector component | Alpha5 | Alpha6 | Change |
| --- | ---: | ---: | ---: |
| Resident executable code | 2907 | 2796 | -111 |
| Text pool | 447 | 322 | -125 |
| Command dispatch tables | 0 | 30 | +30 |
| Stored RAM worker | 472 | 472 | 0 |
| Stored interrupt entries | 56 | 56 | 0 |
| **Total code/data** | **3882** | **3676** | **-206** |

Messages use ordinal identifiers instead of passing a two-byte address at
each output site. The printer scans the pool to find a message, trading
execution speed for space. The last character carries an end marker in bit
7, eliminating separate terminator bytes. Text stays readable in
`src/v2/str8n-v2-text.json`; the build generates the encoded pool and IDs.
RAM-only self-edit result messages remain in the worker so they do not
depend on the ROM being changed.

A table replaces the command comparison chain. M and F share byte-list
parsing, staging, and preflight while retaining their distinct address
rules. C and F share the completion/error path. The line reader removes a
duplicate overflow check and unnecessary extra terminator write; bank
parsing rejects a missing digit before inspecting the suffix. Ring indices
wrap as bytes and are masked only when accessing the 64-byte queue.

The line reader shrank from 159 to 145 bytes, and the queue/cancellation
module from 160 to 156. These are modest savings: overflow rejection,
typeahead preservation, and cancellation while output is blocked remain.
The larger gains are in messages, their call sites, and dispatch.

## Console wording

`?` now lists commands compactly:

```text
B0-B3 D M F G L I C J0-J3 ?
```

Command syntax is unchanged:

| Command | Arguments |
| --- | --- |
| B / J | One bank digit, for example B1 or J3. |
| D | `D addr [end]` |
| M / F | `M addr bytes...` / `F addr bytes...` |
| G | `G addr` |
| L | No arguments; receive RAM S19. |
| I | `I start end`; receive complete-sector S19 after confirmation. |
| C | `C` or `C on bank addr delay`; hexadecimal fields, delay in tenths. |

Shortened wording includes `Bad command`, `Entry hhhh`, `STR8-N edit; reset`,
`Recovery`, and `replace; may erase`. Errors remain descriptive text rather
than numeric codes. Flash previews still identify the bank and affected
addresses/range; F still prints old/new bytes and whether erase is required.
Self-edits still finish entirely in RAM and hold for reset.

Refer to the [configuration guide](STR8N_V2_CONFIG_MILESTONE.md) for the
persistent format and hold rules, and the [flash guide](STR8N_V2_FLASH_MILESTONE.md)
for F/I operation. As corrected in alpha5, I preserves $EFF0-$EFFF only in
the resident bank; those addresses in other banks are normal payload data.

## Validation and artifacts

`make v2-check` builds with WDC02AS/WDCLN and runs all five execution suites.
Added checks execute the packed printer for every message, including page
crossings and stack/register preservation, and reject stale B/J suffixes
through the new dispatcher. Existing checks cover malformed edits, full
address guards, queue wrap/overflow, blocked-output cancellation, flash
mutation/failure, configuration integrity, and the measured startup window.

The normal E-F image and five test receipts are under `BUILD/v2-alpha6/`.
`build.json` now records resident code, text, and dispatch table sizes
separately so future growth is visible.

Install `str8n-v2-alpha6-e000-ffff.s19` through v1.35 I into a disposable
Bank 0-2, keeping v1.35 in Bank 3. This replaces both E and F sectors.
No board was flashed during this size pass. Host validation example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha6/str8n-v2-alpha6-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha6/validated-bank0.s19
```
