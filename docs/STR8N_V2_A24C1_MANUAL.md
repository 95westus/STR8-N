# STR8-N 2.0a24c1 operator and technical manual

This manual covers the a24c1 firmware distributed as beta 1 on W65C02SXB and W65C816SXB.
The 816 monitor and applications using its services run in emulation mode.
Start with the [quick start](STR8N_V2_A24C1_QUICK_START.md) and use the
[detailed technical guide](STR8N_V2_A24C1_TECHNICAL_GUIDE.md) for Mermaid
diagrams, interfaces and board acceptance checks. See the
[maps and diagrams](STR8N_V2_A24C1_MAPS.md) for addresses and installation flow.

## Versions and prerequisites

**WARNING - power failure during flashing can be dangerous.** Loss of power
during flash erase/programming, installation or a configuration save can
corrupt firmware or boot vectors and leave the board unbootable. Recovery
may require an external flash programmer. STR8-N does not guarantee
power-loss recovery or automatic rollback. Keep power stable, retain a
recovery backup, and do not disconnect USB/power or press RESET/NMI until
the operation reports verified completion.

The firmware identifies itself as `2.0a24c1`; filenames use `a24c1`.
Bank maintenance has its own version, `1.0`. Release `v2.0b1` promotes these
exact tested artifacts; their internal version names are unchanged. See the
[beta notes](STR8N_V2_BETA1_RELEASE_NOTES.md).
The a24c2 RAM layout is a proposal and is not implemented in this image.
Alpha24 and a22 manuals describe older firmware. a24c1 stores configuration
in resident F at `$FFD0-$FFDF`.

The core needs no EDU board, RTC, SPI SRAM or crypto hardware. Use the FT245 USB console. The bridge defaults to 115200, 8-N-1.
Confirm the physical board label; an SXB tag alone does not identify the CPU.

## Installation and console colors

For stock WDCMONv2 in B3, run this from the repository root or extracted kit:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL-A24C1.ps1
```

On Linux, install Python 3 and pyserial, then use `sh ./INSTALL-A24C1.sh`.
Enter a device such as `/dev/ttyUSB0` with serial-access permission. For an
already installed monitor, use `sh ./INSTALL-A24C1.sh --terminal-only`.
The RESET, physical-board confirmation and transfer keys are the same.
Linux offline tests pass. The owner reported a successful native Linux run
on 2026-10-02.

Enter the board port. At the physical RESET gate, press and release RESET,
wait two seconds, then press Enter in the host terminal. Confirm the physical board
by typing `W65C02SXB` or `W65C816SXB` exactly in uppercase. The bridge loads,
reads back, and starts the RAM installer at `$2000`.

| Console color | Meaning |
| --- | --- |
| Cyan | Information, addresses, identity and progress |
| Yellow | Input or transfer prompts, RESET instructions, flash activity |
| Green | Successful checks, verification and file sends |
| Red | Refusal, invalid input, cancellation, halted state or failure |

Colors belong to the host bridge; another terminal may show plain text.
Read the text as well as the color. A success line asking for RESET appears
yellow because it requires action. Native PowerShell errors use the host's
error display. Raw transcripts retain the board bytes without color codes.

At `BANK>`, type only `0`, `1`, `2`, or `NONE`, then Enter. At `SECTORS 8-F>`,
type a single sector such as `F` or an ascending range such as `8-F`.
An erased backup destination requires `BACKUP B3`; an identical copy is
reused. Occupied different data is refused. `NONE` requires both `NO BACKUP`
and `INSTALL WITHOUT BACKUP`. Confirm the displayed plan before proceeding.

At the core transfer prompt, press Ctrl-U. Type `INSTALL STR8-N 2.0A24C1`
when requested. Only after `MIGRATION VERIFIED; PRESS PHYSICAL RESET`, press
RESET to boot a24c1. Do not reset, press NMI, or interrupt power during writes.
The stock installer replaces B3:F and preserves the rest of B3.

Already-installed STR8-N boards use the guarded updater described in the
[configuration guide](STR8N_V2_FLASH_CONFIG.md), rather than the stock installer.
COM ports and bank contents are session-specific; inspect the actual board.

For an already installed monitor on Windows, reconnect without resetting:

```powershell
$maint = './BUILD/bank-maint-v2/str8n-bank-maint-2000.s19'
./tools/wdcmonv2/start_wdcmonv2_ram.ps1 -Port COMx `
  -TerminalOnly -NoReset -TransferPath $maint
```

In the extracted Windows kit use `./start_wdcmonv2_ram.ps1` and
`./str8n-bank-maint-2000.s19` instead of repository paths. If scripts are
blocked, use process-only execution permission as described in the launcher.

## Monitor commands

Commands run at `B3>` followed by Enter. Numbers are hexadecimal.
The prompt shows the selected access bank; bank selection does not boot it.

| Command | Behavior |
| --- | --- |
| `?` | Show help |
| `B0` through `B3` | Select a flash bank for access |
| `D addr [end]` | Display a byte or inclusive range |
| `M addr bytes...` | Edit permitted RAM |
| `F addr bytes...` | Guarded raw flash edit in one sector; protected flash ranges are refused |
| `L` | Load S19 into application RAM; does not execute |
| `G addr` | Execute at the selected address |
| `I start end` | Install dense ascending S19 into aligned whole sectors; protected flash ranges are refused |
| `C` | Show resident boot configuration |
| `C enable bank target delay` | Save disabled/enabled autostart, bank, address or RESET-vector target, and delay |
| `J0` through `J3` | Boot a bank via its RESET vector |

The command line is limited to 40 characters. Ctrl-C cancels at supported
boundaries; it does not roll back a completed flash operation. G and J have
no return contract. Software J does not pulse the physical RESET pin.

## Configuration and startup

An erased or invalid factory configuration holds at the monitor. To save a
disabled-autostart setting, use `C 0 3 V 0A`, then confirm the preview with Y.
Delay is `$0A-$FF` tenths of a second. Enable autostart only after proving its
target, and test hold/cancellation using the technical guide.

C stages the full resident F sector in `$6900-$78FF`, changes the sixteen
bytes at `$78D0-$78DF`, and verifies the full sector after writing. Unchanged
settings need no programming or erase. A selected target bank does not move
the resident configuration. Raw F edits do not rebuild configuration checksums.

Failed core writes stay in RAM at `Flash fail; Y retry/reset`. A configuration
retry rewrites the complete staged sector and returns to the saving command
after verification. A raw self-edit restarts the monitor after a successful
retry. There is one persistent configuration copy; power-loss recovery is
not guaranteed. See the configuration guide for exact migration guards.

## Bank maintenance

In the installer's bridge session, enter L, wait for S19, press Ctrl-D to send
bank maintenance, then enter `G 2000`. It gives `BM>`. In a terminal-only
connection, use Ctrl-U instead. See the [maintenance guide](STR8N_BANK_MAINT_V2.md)
for its independent command set, buffer, protections and limitations.

## Application interface and validation

Application RAM is `$0200-$68FF`. ROM entry calls require the resident bank
visible; initialized RAM entries at `$7E64-$7E88` support calls with other
flash banks selected. Check the RA descriptor at `$7E60` first. IRQ must be
disabled and decimal clear; on 816 use E=1, DBR=0 and PBR=0. Services are
not native-mode or reentrant. The public include supplies exact symbols.

Host installer tests pass for backup ranges, refusal, no-backup confirmation,
full migration and recovery. The
[two-board record](STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md) establishes
owner-confirmed stock migration and captured physical RESET/core readbacks.
The [cold-start/configuration record](STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md)
records cold startup, configuration persistence, fixed-address autostart and
S hold on both CPU families. Broader qualification remains governed by the
technical guide acceptance checks.

## Source references

- [Core configuration and migration](STR8N_V2_FLASH_CONFIG.md)
- [Stock installer guide](STR8N_V2_CONFIG_WDCMON_INSTALL.md)
- [Public interface](../src/v2-config/str8n-v2-public.inc)
- [RAM definitions](../src/v2-config/str8n-v2-eq.inc)
- [Build identity](../BUILD/v2-a24c1/build.json)
