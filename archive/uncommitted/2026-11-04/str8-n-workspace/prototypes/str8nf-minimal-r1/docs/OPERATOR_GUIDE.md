# Operator guide

Start with the [quick start](QUICK_START.md). The [unified source guide](UNIFIED_SYSTEM.md)
covers optional component development. Compatible boards use the same CONFIG RAM BIN.

## The boot choices

F is the bootstrap in B3:$F000–$FFFF. Its menu offers `S` for recovery, `A`/`B` for separately installed monitor slots and `0`–`3` for enabled user banks. A configured bank entry is a jump address; F does not interpret BASIC, Forth, a selector or another opaque program.

The menu depends on a valid saved C/D record for enabled banks and the default. Missing or invalid records lead to recovery. An absent MON slot cannot be selected successfully. The F-only recovery loader works without monitors, extensions or a journal.

`REC>` accepts `?`, `L`, `A`, `B`, `0`–`3` and `C1`/`C2`/`C3`. `C1` selects USB, `C2` ACIA and `C3` both consoles. This release's physical claim is USB; ACIA remains an open physical test item.

## Load a RAM tool

1. Reach `REC>` and enter `C1` followed by Enter for USB.
2. Enter `L` followed by Enter. Wait for `SEND BIN`.
3. Send the matching RAM **BIN** as raw binary starting with its first byte. Do not send an S-record or add terminal text/newlines to the file.
4. After the end-of-file idle interval, F starts the program at $0200.

The raw loader has no framing CRC or declared length. It accepts $0200–$64FF and uses a nominal three-second idle interval to end the transfer. Verify the local file's SHA-256 before sending. A leading Ctrl-C byte cancels while waiting for the first byte; after the first payload byte, all byte values are data. An interrupted transfer requires a reset and a new complete load.

The DEMO prints CPU and F capability information, calculates $1234+$0001 and echoes one key. It then restarts through F using the saved choice. Use default `S` when the desired stopping point is `REC>`.

## Inspect and save CONFIG

Load `STR8N-F-CONFIG-RAM.bin`. Its prompt is `RAM CONFIG ? B C I W Q>`.

| Command | Effect |
|---|---|
| `?` | Help |
| `B` or `C` | Inspect default, enabled banks and entries |
| `W` | Inspect erase counters and unknown-history indication |
| `B 1 9000` | Enable B1 and save its $9000 entry immediately |
| `C 1` | Save enabled B1 as default immediately |
| `C S` | Save recovery as default immediately |
| `C A` or `C B` | Save a separately installed valid monitor as default |
| `I` | Initialize only completely blank C/D; see installation boundaries |
| `Q` | Restart through F using the saved default |

Entries are $8000–$E000 in $1000 steps. B3:$C000 and $D000 are excluded because they contain the journal. F:$F000 is never an application entry. `B` with arguments changes saved configuration; it does not install or validate the application bytes. CONFIG has no bank-disable command in this release, so enable only a bank that is ready to boot.

For a reversible default exercise on an already provisioned board, first inspect the saved settings and ensure MON A is valid. `C A` saves A; `Q` starts it. Return to recovery, reload CONFIG, use `C S`, then `Q`. Each save appends a record and may eventually require journal rollover; retain the wear history. Do not run a demonstration save on a preservation-only inspection visit.

## Install an opaque image

Use the matching OPAQUE RAM tool and [OIP1 protocol](OPAQUE_PROTOCOL.md). Read and save each target sector before replacing it. The normal installer admits all sectors of B0–B2 and B3:8/9/E. It reserves B3:A/B for monitor slots, C/D for journals and F for the bootstrap. A provider in an otherwise allowed sector is still owner data: target selection must come from the actual board inventory.

Install every required sector and verify the complete application's image before enabling its boot entry. A bank may contain code, data, a menu, multiple applications or unused sectors; F does not infer which bytes belong together. Reset into recovery after an unsuccessful transfer and compare the sector with both the saved preimage and intended payload before deciding how to recover.

## Application contract

Applications own their application behavior and must match the board hardware. F's resident RAM service entries and reserved work areas are defined in [str8n-v2-public.inc](../src/include/str8n-v2-public.inc) and [str8n-v2-eq.inc](../src/include/str8n-v2-eq.inc). Calls require IRQ disabled and decimal mode clear; on 65C816 use emulation mode, D=0, DBR=0 and PBR=0. Bank-independent calls use the RAM facade after checking its signature. Calling F ROM routines requires B3 visible.

The operator kit supplies CONFIG, OPAQUE, DEMO, READBACK and optional BASE MONs.
BASE MON is a compact inspection/launch shell. Full-system M1 maps, WORK/EDU,
RTC status and richer interfaces are separate optional applications. Legacy
compatibility commands may report unavailable; their presence in old help does
not install the corresponding full-system provider. The source package retains
VX1/ES1/MAINT/FLASH development without making it part of F.
