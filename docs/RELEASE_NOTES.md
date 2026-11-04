# STR8N-F 0.3.0 — the 4KB foundation

> 4KB of firmware. One board. Up to four boot environments.

For WDC W65C02SXB (65C02) and W65C816SXB (65C816 emulation), with optional
matching W65C02EDU or W65C816EDU add-on boards. BASE1 does not require EDU.

Compatible, user-supplied images run one at a time, sharing the same CPU,
approximately 32KB RAM on supported boards, and peripherals.

STR8N-F supplies boot selection and recovery in **4096 bytes**, leaving
116 KiB of flash for owner images. Boot configuration and conservative
erase-attempt counts persist in the separate C/D journal. Rich OS status,
menus and device services belong to optional images.

F is **STR8N-F 0.3.0 g00000001 / BASE1 / PR05**. Its public ABI and exact
bytes remain frozen; no firmware rebuild accompanies this release.

## Downloads and use

- `STR8N-F-BOOT-4096.bin`: only B3:F000-FFFF. Under the standard linear
  128 KiB layout the offset is 1F000; confirm your programmer's mapping.
- `STR8N-F-BASE1-0.3.0.zip`: complete operator kit with five matching RAM
  tools, **Python Serial Console 0.1.0**, F-key transfers, verbose installation
  hosts, prebuilt engines, guides, manifests and hardware receipts.
- `STR8N-F-BASE1-0.3.0-source.zip`: corresponding source and build recipes.
- `SHA256SUMS.txt`: hashes for both ZIPs and the standalone F BIN.

The F BIN is not a whole-chip image. Installing F alone does not provision
occupied C/D. Follow [installation](INSTALLATION.md) for WDC migration,
programmer-installed-F provisioning or the supported existing-journal upgrade.
Back up original images, settings, history and owner RAM before helpers run.
Owner WDC firmware, private captures and per-board plans are not distributed.

The terminal needs Python 3.11+ with Tk and `pyserial==3.5`. See
[quick start](QUICK_START.md) and [terminal keys](SERIAL_CONSOLE.md).

## Evidence and boundaries

Reviewed 2512/65C02/FT245/Windows cases passed: reset/recovery, native terminal
keys/dialogs, Ctrl-C and BIN loading, CONFIG/opaque boot, WDC migration,
programmer-F provisioning and named chip-idle C/D recovery cases.
The unchanged rc1 operator kit's existing-SNBT upgrade also passed on
2609/65C816 emulation/FT245, retaining old records, images, boot settings and
owner RAM. See [status and receipts](RELEASE_STATUS.md).

This final package corrects docs/metadata/packaging and names the planned
optional monitor **Mona**. Firmware, terminal, migration hosts and engines
are unchanged from rc1. The final ZIP itself has not had another live trial;
the extracted WDC and programmer-F routes remain untested as package routes.
The manual original-capture precondition remains documented in
[rc1 findings](RC1_KNOWN_ISSUES.md). This is a scoped 0.3.0 release, not a
qualification of every board, adapter, layout or failure mode.

Normal recovery assumes F stays golden. Interrupted F installation,
electrical mid-pulse failures, native application-mode calls and ACIA physical
operation are not qualified. No hardware was accessed for final packaging.
No Mona image or expanded F ABI is included; see [Mona](MONA.md).

Frozen F SHA-256:
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
