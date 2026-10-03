# STR8-N 2.0a24c1 quick start

For **W65C02SXB and W65C816SXB**. One core image and one unified installer
serve both boards. The monitor runs in emulation mode on the 816.
No extra board hardware is needed.

## 1. Choose your starting point

**Stock WDCMON in B3:** follow installation below. **Already on a24c1:**
skip to page 2. **Already on alpha24 or another STR8-N version:** use the
matching update procedure; see `docs/STR8N_V2_FLASH_CONFIG.md` for alpha24.

Already on v2: skip installation and continue with monitor commands on page 2.
For reconnecting, use the operator manual's terminal-only instructions.

This is the current board-test candidate. Physical acceptance remains pending
for each CPU family. Verified stock migration and a working physical RESET
establish the beta 1 milestone; packaging does not establish qualification.

## 2. Prepare and launch the installer

For an extracted kit, use the supplied files. In a source checkout with the
WDC assembler/linker installed, build them using:

```powershell
make v2-config-wdcmon bank-maint-v2
```

Connect the board's USB console and identify its COM port. Close other
applications using that port. Keep a recovery copy of existing firmware,
note bank contents, and keep power stable during flash writes.

From the repository root or extracted release ZIP folder:

**Windows PowerShell:**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL-A24C1.ps1
```

**Linux terminal:** install Python 3 and pyserial (Debian/Ubuntu:
`sudo apt install python3 python3-serial`), then run:

```sh
sh ./INSTALL-A24C1.sh
```

Enter the serial device, such as `/dev/ttyUSB0`, on Linux. Your account needs
permission to access it. The Linux launcher uses the same RESET and board
confirmation steps. Offline tests pass, and the owner reported a successful
native Linux run on 2026-10-02.

The launcher lists detected ports and asks for the board port (`COM3` on
Windows, `/dev/ttyUSB0` on Linux). Enter `Q` to quit. It selects the installer, core BIN, and bank
maintenance file automatically. On Windows, script permission applies only to the launched PowerShell process.

Console colors: **cyan** = information; **yellow** = input, RESET and flash
activity; **green** = successful checks; **red** = failures, refusals or
cancellation. Follow the text; a verified-completion RESET request is yellow.
The bridge adds colors; raw transcripts and other terminals may be plain text.

**First RESET:** at `PHYSICAL RESET GATE`, press and release the physical
**RESET** button, wait two seconds, then press **Enter in the host terminal**.
At board confirmation, type **W65C02SXB** or **W65C816SXB** exactly in uppercase.
The bridge loads, reads back, and starts the RAM installer. Do not reset during
loading. Connection: **115200 baud, 8 data bits, no parity, 1 stop bit**.

## 3. Back up, install, then reset

- At `BANK>`, type **only `0`, `1`, `2`, or `NONE`**, then press Enter.
  Do not type `BACKUP BANK 0`. At `SECTORS 8-F>`, type a sector such as
  `F` or a range such as `8-F`, then press Enter. `8-F` saves the
  entire original bank; `F` saves the sector being replaced. The copy goes
  to the same sector addresses in the chosen bank.
- Use a free destination. Different occupied data is refused. An identical
  backup is reused. For an erased destination, confirm with `BACKUP B3`.
- Choosing `NONE` requires both `NO BACKUP` and `INSTALL WITHOUT BACKUP`.
  Preserve existing firmware; choose a backup range confirmed available on that board.
- At the core BIN transfer prompt, press **Ctrl-U**. Then type
  `INSTALL STR8-N 2.0A24C1` when requested.
- **Second RESET: only after the installer reports verified completion and
  waits for reset**, press and release the board's physical **RESET** button.
  Expect `STR8-N 2.0a24c1`, the correct CPU, and a responsive `B3>` prompt.

The installer replaces **B3:F only** and preserves the rest of B3. Do not reset,
press NMI, or remove power during a flash operation.

<!-- pagebreak -->

## 4. First steps at the monitor

Type commands at `B3>` and press Enter. All numbers below are hexadecimal.
The factory image holds at the monitor because no boot configuration is saved.

| Command | What it does |
| --- | --- |
| `?` | Show monitor commands |
| `D 2000 201F` | Display RAM bytes |
| `M 2000 01 02` | Edit two RAM bytes; use free RAM |
| `B1` / `B3` | Select the visible flash bank; remain in the monitor |
| `C` | Show saved boot settings; `No config` is normal initially |
| `L` | Receive an S19 text file into RAM |
| `G 2000` | Execute a loaded program at $2000 |

For a saved hold-at-monitor setting, use `C 0 3 V 0A` and confirm the
displayed write with `Y`. It disables autostart and saves in B3:F at
$FFD0-$FFDF. Wait for completion before resetting.

## 5. Load and use bank maintenance

In the bridge session started on page 1, enter `L`, wait for `S19`, and
press **Ctrl-D** to send the maintenance S19. Wait for `Entry 2000`, then
enter `G 2000`. The utility gives a `BM>` prompt.
With the terminal-only connection above, send the S19 using **Ctrl-U** instead.

If using another terminal, send `str8n-bank-maint-2000.s19` as a text file
after `L`. The utility needs an initialized v2 monitor, including on the 816.

| At BM> | What it does |
| --- | --- |
| `M` | Map the flash banks |
| `R 3 F` then `D FD0-FDF` | Read B3:F; view its config pocket in the buffer |
| `P FD0 01` / `K` | Edit a buffer byte / show buffer CRC |
| `W 1 A` | Write the buffer to B1:A; choose an available scratch sector |
| `C 1 A 1 B` | Copy B1:A to B1:B; replaces destination contents |
| `V 1 A 1 B` | Compare the two sectors |
| `E 1 A-B` | Erase B1:A through B1:B |
| `Q` / `?` | Return to the monitor / show all maintenance commands |

**R/P/D work in the buffer; W commits it.** R, N and S replace the previous
buffer. Use `C` at the monitor to save valid boot settings; raw buffer edits
do not rebuild configuration checksums.

Every erase, copy or buffer write shows its destination and asks for **Y**.
Touching **B3:F** also requires **B3F**. Protect your known firmware by choosing
scratch sectors carefully. After targeting the resident F sector, Q is blocked;
use an explicit `J bank` to boot known firmware.

## 6. Store the utility in B1, if space is available

At `BM>`, enter each line separately; confirm each W with Y:

```text
S 8
W 1 8
S 9
W 1 9
```

This archives the running utility in **B1:8-9**. A loader is still pending:
restore it to RAM $2000-$3FFF before execution. `J 1` does not launch this archive.

For board acceptance, interfaces and Mermaid maps/flows/charts, use the
[detailed technical guide](STR8N_V2_A24C1_TECHNICAL_GUIDE.md). The
[operator manual](STR8N_V2_A24C1_MANUAL.md) explains commands.
Leave autostart disabled until its target is proven.
