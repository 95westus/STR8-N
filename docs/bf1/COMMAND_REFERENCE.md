> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# bf1 program and command reference — candidate

Current acceptance policy and tonight's prerelease scope: [accepted gates](../STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).

Target: **STR8-N 2.0bf1 generation 48 / FT245**, CLOCK 1.11, ASM 0.5.
This reference records audited syntax from the separate candidate
source; it is not an instruction to exercise write commands during the RTC
campaign. ACIA and crypto remain deferred. Hexadecimal addresses are CPU
bank-zero addresses unless an external address is explicitly named.

## Monitor context

| Command | Purpose and effect |
| --- | --- |
| `?` | Display monitor help |
| `VERSION` | Display version information |
| `TIME` | Display time information |
| `APPS` | List applications/utilities |
| `ASM` | Launch the ROM assembler; distinct from stored-program `R name` lookup |
| `B0` … `B3` | Select visible flash bank; affects later addresses |
| `D addr [end]` | Display memory; I/O reads are not ordinary RAM reads |
| `M addr bytes` | Modify allowed RAM; deliberate vector-pointer exceptions; protected ranges refuse |
| `F addr bytes` | Patch one selected flash sector after snapshot/preview/confirmation; persistent erase/program, not RAM fill |
| `G addr` | Execute RAM code; effects depend on that program |
| `L` | Load S-records into their specified destinations |
| `M [1 grid\|2 ranges\|3 wear]` | Monitor map/report form; distinguish from address-edit form |
| `I start end` | Installer operation; writes flash and requires its own validation |
| `W` | Wear information |
| `U A\|B` | Monitor-slot update operation; installation gate applies |
| `S bank flash start end [name]` | Store RAM program in flash; persistent write |
| `R [bank] name` | Find/load/run a named stored program |
| `R bank flash [L]` | Addressed stored-program operation; inspect its exact header/range |
| `T [bank\|first-last]` | Stored-program table |
| `J0` … `J3` | Select the named bank and follow its `$FFFC/$FFFD` reset vector; invalid/erased vectors refuse. In the complete bf1 layout, `J3` restarts bf1. These commands do not relocate the B3 bootstrap. |
| `C [0\|1 bank addr\|V delay]` | Configuration command; save can write journals |
| `P [A\|B]` | Preference command; changing it is a configuration write |
| `MAINT`, `SRAM`, `WORK`, `EDU` | Native utility aliases; `R` prefix optional |
| `BATCH cmd;cmd` | Supported bounded command sequence; 34 text bytes; Escape cancels |

The same letter can have several parser forms. Consult `?` and the relevant
source before automating a form. This guide does not expand ambiguous write
forms into recipes. The ongoing soak uses its own allowlisted preserving
operations and is not permission to run the entire command table live.

## CLOCK context

Enter with `R CLOCK`. The prompt is `CLOCK>`.

| Command | Meaning |
| --- | --- |
| `TIME` / `R` | Time display |
| `STATUS` / `S` | Flags, trim, identity and raw status |
| `EUI` | Device identity display |
| `HISTORY` | Stored power-fail history |
| `SHOW n` | Show selected history entry |
| `SET yyyy-mm-dd hh:mm:ss` | Set calendar using UTC convention; confirmed change |
| `OFFSET +/-HH:MM` | Fixed local display offset; confirmed setting change |
| `TRIM -127..+127` | Rate correction; confirmed device change |
| `ACK` | Acknowledge latched power-fail event; changes evidence |
| `ACCEPT EUI` | Accept identity; changes remembered binding |
| `CLEAR n` / `CLEAR ALL` | Delete history; persistent change |
| `BATTERY` | Battery-policy display; see persistence caveat below |
| `BATTERY REPLACED` / `BATTERY yyyy-mm-dd` | Record replacement date |
| `BATTERY LIMITS ww rr` | Warning/replacement limits, 01..99 30-day months, `ww < rr` |
| `HELP` / `?`, `Q` / `QUIT` | Help and return |

Keep all write forms unused during the campaign. CLOCK's detailed prompts and
confirmation paths remain authoritative; syntax recognition is not permission
to alter evidence. Battery status is inferred policy, not a battery-voltage
measurement. Boot/BATTERY may append a policy record when detecting a backward
date: QA35-006 demonstrated the expected uncertainty latch. Do not describe
every status entry path as universally free of persistent effects.

## ASM context

`number text` inserts/replaces a line; `number` deletes it. `NEW`, `PASTE`,
`LIST`, `ASM`, `DUMP`, `S19`, `QUIT`, and `?` operate on the current source and
output. See the [ASM guide](ASM_GUIDE.md) for buffer/origin rules. ASM owns much
of application RAM while loaded. An assembly success does not execute code.

## Native utility contexts

MAINT uses `BM>`. Its `NAME [1-8 characters | CLEAR]` setting requires `YES`.
SRAM uses `SRAM>` and advertises `S name start end entry`, `R/G/D name`,
`T C F Q`; those letters are SRAM-manager commands, not monitor commands.
WORK uses `WORK>` and advertises `?` capacity, `P 16/32/48/64` KiB,
`U` upgrade, `V` repair, `F` format, `HELP`, and `Q`. Upgrade, repair, format,
store and delete operations must be treated as writes. EDU uses `EDU>`;
changing its saved mode is reset-latched and can reserve/release optional
service RAM only after reset.

BATCH feeds supported prompt readers; utility responses therefore occur in
the active utility's context. Failure/unsupported input stops the sequence,
and Escape cancels. It does not supply a general conditional language. The
bf1 native/CLOCK hooks validate active A0 or B0, the BA capability and
matching UX/3/42 provider. CLOCK BATCH admission accepts exact `R CLOCK` /
`R 1 CLOCK` forms with a valid BT/1/1 header; wrong banks, arguments and
arbitrary applications remain refused. The legacy B9 marker is accepted only
for legacy B. Mixed component profiles do not enable bf1 handoff.

## PF and STATS interpretation

PF displays captured down/up information. STATS aggregates the records it
recognizes; it cannot reconstruct missing history or infer total uptime from
yearless stamps. The inherited duration formatting yields estimated days/hours/minutes
under a year anchor, with no seconds. Invalid/unanchored timestamps remain
unknown. A cleared latch or history record is lost evidence, not a shorter
outage. See [technical limitations](TECHNICAL_MANUAL.md).

## Source index

- [Monitor help, utility help and BATCH](../../release/candidates/batchfix-r1/source/xip/utilities.asm)
- [CLOCK commands](../../release/candidates/batchfix-r1/source/clock/clock.asm)
- [ASM commands](../../release/candidates/batchfix-r1/source/assembler/asm-app.asm)
- [PF worker](../../release/candidates/batchfix-r1/source/pf/pf.asm)
- [User guide](USER_GUIDE.md)

The same firmware supports 65C02 and 65C816 emulation-mode runtime. Native
816 applications/testing, ACIA and crypto remain deferred. The existing startup
CPU detector briefly enters native mode before restoring emulation; this
startup exception was explicitly accepted by the owner.
