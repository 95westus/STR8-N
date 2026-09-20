# STR8-N v2-alpha5 configuration and autostart

Historical milestone. The current [alpha6 size pass](STR8N_V2_COMPACT_MILESTONE.md)
retains these commands and configuration format, with shorter messages and
compact command-list help.

Completes the required command set: B, D, M, F, G, L, I, C, J, and ?.
No convenience commands, directory, journal, or HIMON dependency were added.
This build has not been installed or tested on physical hardware.

## Configuration command

`C` displays the current resident bank's configuration, or `No config` when
it is erased or invalid. To change it, provide all four hexadecimal fields:

```text
C on bank addr delay
```

| Field | Accepted value |
| --- | --- |
| on | 0 disables, 1 enables automatic execution. |
| bank | 0–3, selected when execution begins. |
| addr | Any address permitted by G: application RAM or $8000–$FFFF. |
| delay | $0A–$FF tenths of a second at nominal 8 MHz: approximately 1–25.5 seconds. |

Example: `C 1 2 9000 0A` enables execution at Bank 2, address $9000, after
the minimum hold window. `C 0 2 9000 0A` disables it while retaining those
other values. Each change shows the resident bank, all proposed settings,
and `Program` or `Erase/rewrite`, followed by `Y?`. Confirm with exactly Y
and Enter. Changes take effect on the next reset entry; C never launches
the configured program immediately.

C always edits the resident bank's $EFF0–$EFFF, independently of the B
selection. It computes the integrity bytes, preserves every neighboring
byte, and uses the shared F/I worker for programming, erase when required,
and full-sector verification. The previous selected bank is restored on
success, cancellation, and failure. Ctrl-C during mutation waits for the
active sector to finish. Flash failures can leave a partially changed sector;
there is no rollback.

## Reset and hold

Reset entry at $F000 initializes the monitor and checks its configuration.
Erased, invalid, unknown-format, or disabled settings leave the prompt ready.
For a valid enabled configuration, the monitor displays the settings and
`S/Ctrl-C hold`, then polls input throughout the configured delay.

S, lowercase s, or Ctrl-C cancels automatic execution for that boot. Keys
already queued while the banner was blocked are honored. Input overflow
also holds, since it may have discarded a stop key. Other input during the
window is consumed without shortening the wait. On expiry, the ordinary G
worker selects the configured bank and jumps to the address; the stack is
reset and IRQ remains disabled. The monitor does not inspect the target
program or load RAM before jumping.

Software prompt entry at $F003 always holds and preserves installed user
handler pointers. This provides a return to the monitor even when automatic
startup is enabled. J invokes a bank's reset vector, so J into this image
uses its autostart settings just as reset entry does.

The linked 65C02 idle path is checked for a minimum one-second window at
8 MHz, without skipping the delay loop. The software delay follows CPU
clock rate; incoming input and blocked output can extend it. Timing on the
physical boards and the 816 remains a hardware qualification item.

## Sixteen-byte format

The block is in the resident bank at $EFF0–$EFFF:

| Offset | Meaning |
| --- | --- |
| +0 | Format: 1. |
| +1 | Enable: 0 or 1. |
| +2 | Flash bank: 0–3. |
| +3/+4 | Execution address, little-endian. |
| +5 | Delay: $0A–$FF tenths. |
| +6–+13 | Reserved; must be zero. |
| +14 | First accumulated sum. |
| +15 | Second accumulated sum. |

Starting with `a = b = 0`, process bytes 0–13 in order: `a = (a + byte) &
255`, then `b = (b + a) & 255`. Store a at +14 and b at +15. These are
simple integrity checks, not authentication or protection against every
possible multi-byte corruption. Field validation is also required at boot.

F remains a raw editor and does not recompute these bytes. I preserves this
reservation only when installing into the resident bank. In other banks,
$EFF0–$EFFF are ordinary payload bytes and are installed exactly as supplied.
This corrects alpha4's preservation of those addresses in every bank.

## Size and validation

The final image occupies **3882 bytes**, including its **472-byte RAM
worker** and **56-byte interrupt image**, leaving **182 bytes** before
$FFE0. Adding configuration/autostart grew the image by only 396 bytes from
alpha4. Size reductions use the existing reserved zero page for scratch and
share newline and flash-mode output code. Application RAM remains
$0000–$00DF and $0200–$68FF; no application space was reclaimed for features.

The full $E0–$FF zero-page scratch area is now assigned. Configuration is
cached at $7D80–$7D8F within the reserved state page; public interrupt pointer
slots are unchanged. Internal scratch addresses changed and are not an
application ABI. Code size takes priority over execution speed.

`make v2-check` builds with WDC02AS/WDCLN and runs five suites: boot, monitor,
load, flash, and configuration. Added checks cover all resident-bank writes,
preserved neighbors, invalid settings, all 128 single-bit corruptions of a
configuration record, all 16 bank handoffs, queued/live stop keys, blocked
output, software reentry, cancellation/failure cleanup, and startup timing.
The earlier flash, install/boot/return, and v1.35 handoff checks remain.

Artifacts are under `BUILD/v2-alpha5/`, including
`str8n-v2-alpha5-e000-ffff.s19`, its `.bin`, `build.json`, and five test
receipts. A fresh image has erased configuration and therefore holds.

Install the E-F image into a disposable Bank 0–2 using v1.35 I, retaining
v1.35 in Bank 3. It replaces both E and F sectors. Host validation example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha5/str8n-v2-alpha5-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha5/validated-bank0.s19
```

Board tests remain required for flash timing, NMI during flash operations,
console flow control, and CPU-specific behavior. No hardware was flashed
during this development milestone.
