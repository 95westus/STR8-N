# STR8-N 2.0a21 RC1

STR8-N 2.0a21 RC1 is available for W65C02SXB board management with a connected,
enumerated USB FT245 host and stable 5 V board power. Board 2512 passed exact
Bank 3 F readback, physical RESET and hold cancellation, cold USB banner
capture, and configured guest handoff. Earlier alpha19 functional board tests
support this scoped RC; they were not repeated on alpha21.
The same firmware is intended for W65C02SXB or W65C816SXB with or without
the matching EDU; W65C816SXB and EDU operation still require board evidence.

This archive contains **only STR8-N firmware BIN/S19 images, project-authored
RAM flash update tools, two ASM-F2 `.a` carriers, the host bridge, this README,
the 816 getting-started guide, fillable and printable qualification checklist,
readback verifier, manifest, and the
STR8-N license**. It contains no WDCMONv2 firmware, stock-bank dump, HIMON,
ASM-F2 or R-YORS firmware, separately released guest application, frozen
source tree, or test probe.

## Files and intended use

| File | Use |
| --- | --- |
| `FIRMWARE/str8n-v2-alpha21-f000-ffff.bin` | Exact 4096-byte Bank 3 F top for the RAM migration installer or an external programmer at device offset `$1F000`. |
| `FIRMWARE/str8n-v2-alpha21-e000-ffff.bin` and `.s19` | Dense 8192-byte E-F image for an explicitly chosen bank and compatible flash path. |
| `FIRMWARE/str8n-v2-alpha21-8000-ffff.bin` and `.s19` | Dense 32768-byte full-bank image; installing it replaces the whole bank. |
| `FIRMWARE/str8n-v2-alpha21-b3-top-update-2000.s19` | Guarded RAM updater, loadable with STR8-N `L`, for an existing compatible STR8-N system. The board 2512 install used its earlier success-path build; this RC1 adjunct corrects the pre-erase cancel exit. |
| `APPLICATIONS/str8n-v2-alpha21-b3-top-update-2000.a` | ASM-F2 `ORG`/`DB` carrier for the matching guarded updater S19; pre-erase cancel enters v2 HOLD at `$F007`. |
| `APPLICATIONS/str8n-v2-bank3-id-2000.a` and matching S19 | Read-only Bank 3 header/RESET-vector report from RAM; restores the previous flash bank before returning to HIMON. |
| `APPLICATIONS/README.md` | Exact ASM-F2 loading steps, memory boundaries, and R-YORS compatibility limits. |
| `FIRMWARE/str8n-v2-rc1-wdcmonv2-install-2000.s19` | Standalone project-authored RAM installer for a stock WDCMONv2 board. It receives the separate alpha21 top BIN; it contains no WDCMONv2 firmware or embedded top BIN. This alpha21-specific migration path has host checks but no factory-board run. |
| `START-STR8N-V2-RC1.ps1` and `TOOLS/start_wdcmonv2_ram.ps1` | Windows host launcher and WDCMONv2 RAM bridge for the stock-board path. |

The `FIRMWARE/` BINs are raw byte images. `str8n-v2-alpha21-f000-ffff.bin`
is the file sent by Ctrl+U when the RAM installer requests `SEND STR8-N TOP BIN`.
The E-F and full-bank BINs are for an external programmer or a host workflow
that explicitly accepts raw BINs at those ranges. The STR8-N monitor `L`
command accepts **S19**, not raw BIN; use the supplied S19 for monitor loads.
The `.a` files are for the separate public R-YORS HIMON/ASM-F2 environment;
see `APPLICATIONS/README.md` before using them. They are project-authored
carriers, and this ZIP includes no R-YORS firmware or source.

## Stock WDCMONv2 board

For an incoming W65C816SXB/EDU, follow `GETTING-STARTED-816.md` first. It
starts with a read-only identity probe and ends with exact top-sector readback.
Record and sign the observations on `QUALIFICATION-CHECKLIST-816.md`.
The matching `QUALIFICATION-CHECKLIST-816.pdf` can be completed on screen or
printed. Its optional QCC (Questions, Comments, Concerns) page lists
`95west.us@gmail.com` for completed
records, questions, and concerns. Do not include private stock firmware or
full-flash backups with a returned record.

On Windows, extract the ZIP, connect the stock board to the host, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\START-STR8N-V2-RC1.ps1 -Port COM4
```

The actual COM port may differ. The launcher opens a timed physical RESET arm,
and defaults to expected board tag `SXB3` for the W65C816SXB. For a known
W65C02SXB stock board, pass `-ExpectedBoardTag SXB2`. Confirm the board's
reported identity before proceeding with any flash operation. The bridge
loads and byte-verifies the installer in RAM, then exposes its terminal. The
installer refuses a used, different Bank 0. With an erased Bank 0 it asks to
copy and verify the original complete Bank 3 there before touching Bank 3 F.
It then requests the packaged top BIN via Ctrl+U and requires a separate
`INSTALL STR8-N 2.0a21` confirmation. After verification it stays in RAM and
asks for **physical RESET**, which initializes alpha21's RAM state. Preserve
owner-local stock archives privately; the archive includes none.

This stock-board alpha21 migration tool has not been run on hardware. Its
S19 structure, guard order, and alpha21 BIN hash passed host checks. Use an
external programmer if recovery from a failed top-sector write is required.

## Operating scope

Keep host and board power stable. Do not unplug USB, remove power, press RESET,
or press NMI during an active transfer or flash write. Ordinary power-off
after completed work is within scope. No interruption-recovery claim is made:
an interrupted write or configuration change can leave an incomplete image
and require external reflashing; V2 has no automatic rollback.

ACIA receive/fallback, W65C816, EDU-specific behavior, and guest displays,
LED patterns, and sounds are outside this RC claim. The physical ACIA receive
issue remains open. `MANIFEST.json` records SHA-256 for each packaged file and
the exact board 2512 Bank 3 F identity.
