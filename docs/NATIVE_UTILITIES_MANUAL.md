# STR8-N native utilities above Foundation

Development candidate: MON A/B g0000000A, services g6, WB2 g8, native apps g1
with RAM loader r7 and HOST prompt repair r8. Foundation remains **STR8N-F 0.3.0 g00000001 / BASE1 /
PR05**, exactly 4096 bytes. This candidate is separate from the published
Foundation and preview-1 downloads.

## Start and identify

At `REC>`, enter `B` for MON B, or `A` for the identical MON A. `VERSION` is
the full command; `V` remains an alias. `TIME` prints a fresh sample without
repeating the banner. Monitor `Q` returns to recovery.

```text
REC> B
B3> VERSION
B3> APPS
B3> R CLOCK
CLOCK> STATUS
CLOCK> VERSION
CLOCK> Q
B3> R FLASH
FLASH/MAINT> VERSION
FLASH/MAINT> Q
B3> MAINT
WORKBENCH> Q
```

`R CLOCK`, `R FLASH` and `R MAINT` are reserved native names, independent of
the selected data bank. `R MAINT` and `FLASH` open the shared board tool;
`MAINT` opens the storage/EDU workbench, where `BOOT` opens that board tool.
`APP name` launches a checked owner AP/02 flash image. `APPS` lists both native
tools and discovered AP/02 images; native tools use the `R` names above.

Two hardware profiles use the same source and command set: W65C02SXB/65C02
and W65C816SXB/emulation, optionally with their matching EDU. The current
native-utilities hardware acceptance is 2512/65C02/FT245. The corresponding
new 65C816 hardware paths remain to be checked; existing Foundation acceptance
is separate. FLASH/MAINT VERSION spells out the SXB CPU profile and Rev D EDU
wiring profile. A configured revision is not electronic identification of an
attached EDU. `--*` denotes unavailable/unverified status; tracked erase counts
cannot certify prior wear or flash/battery health.

## Install from the candidate ZIP

The `foundation/` directory is the unchanged published v0.3.0 operator kit,
including its Python terminal and WDC-loadable RAM migrator. Use its manual to
reach BASE1/PR05 first. Programmer-installed F with blank C/D needs the included
CONFIG/provisioning procedure. Do not reinitialize an existing journal.

Run `python verify_candidate.py` in the extracted candidate. Start the included
terminal with `python foundation/tools/nf_console.py`; F10 connects, F2 chooses
a BIN, F4 loads it at an observed REC>, F6 loads CONFIG and F7 loads OPAQUE.
The terminal's own F1 gives its complete function-key list. It does not connect
or flash automatically. Install `foundation/requirements-console.txt` if needed.

Review the B2/B3 allocation before replacing any occupied image. Keep a current
B3 capture for its F identity, C/D history and final 1 KB of sector9 metadata.
Optionally supply B2 too so the preparer identifies identical sectors:

```text
python tools/nf_native_images.py --current-b3 current-B3.bin --current-b2 current-B2.bin --out install-plan
```

This writes thirteen utility-sector files and a review JSON; it opens no port.
F and C/D are not image targets. Sector9 is assembled with the captured board's
metadata, not generic FF. Keep the board idle between capture, preparation and
replacement. Reprepare if its configuration, journal or RTC metadata changes.
Preserve owner RAM before loading a RAM tool when its contents matter.

Enter REC>, load the Foundation OPAQUE tool with F7, disconnect the terminal,
then use its qualified host client for each reviewed, changed target. Example:

```text
python foundation/tools/nf_opaque.py replace --port COM4 --bank 3 --sector A000 --image install-plan/B3-A000.bin --out private-step-A --request-prompt
```

Use the actual port and a new private output directory for every operation.
The client reads/verifies that target and the device reserves wear before an
erase. Identical images do not cause an erase. Never substitute the sector9
code-prefix file for the prepared complete sector. Do not program a generic
full-bank B3 image over a board's C/D or F.

After all reviewed components are installed, return from OPAQUE to REC>, enter
the desired A/B monitor, then R MAINT and BOOT to inspect saved settings. If
retaining default B after upgrading its generation, explicitly use `BOOT C B`;
use A for default A. Other defaults need no generation rebinding. This is an
optional native-tools candidate, not another Foundation migration or F update.

## CLOCK

This is the full b35-derived CLOCK 1.10 application, rather than the former
read-only page. Enter `R CLOCK`; its own `HELP` gives the complete grammar.

| Command | Function |
| --- | --- |
| TIME / R | UTC and local time with the saved fixed offset |
| STATUS / S | Running/calendar/backup/power-fail flags, raw registers, trim and identity |
| SET yyyy-mm-dd hh:mm:ss | Set UTC after exact YES confirmation |
| OFFSET +/-HH:MM | Save the local fixed offset; DST remains an operator choice |
| TRIM -127..+127 | Confirm a fine-trim change; output/alarm guards remain |
| EUI / ACCEPT EUI | Read identity; explicitly confirm accepting a changed device |
| HISTORY / SHOW n / STATS | Read retained power-fail evidence and interval estimates |
| ACK / CLEAR n / CLEAR ALL | Explicit confirmed history/acknowledgment operations |
| BATTERY | Show date/age policy; HELP describes replacement/date/limit changes |
| VERSION / V; Q | Show identity; return quietly to the active monitor |

SET retains b35's save-before-clear behavior for latched power-fail evidence
and refuses enabled alarms. A failed SET requires inspecting STATUS before
retrying. Confirmed SET, ACK, trim and policy commands change device/metadata
state; normal TIME does not set the clock. Existing battery-policy warning
stage latching can append a metadata record when the stage advances.

On 2512, STATUS, VERSION, calendar rejection and SET cancellation passed.
A successful SET/ACK/trim write under this new package has **not** been run;
the ongoing RTC/NTP clock and trim were deliberately retained.

## FLASH and the sector editor

```text
B3> R FLASH
FLASH/MAINT> BANK 0
FLASH/MAINT> READ 9000
FLASH/MAINT> VIEW 000
FLASH/MAINT> EDIT 000 12 34
FLASH/MAINT> VIEW 000
FLASH/MAINT> WRITE
REWRITE 4K B0:9000; type YES> NO
```

READ copies the containing 4096-byte sector into the RAM edit buffer and
discards pending buffer edits. VIEW accepts a page offset `000`, `100`, …
`F00` and prints a 16-by-16 hexadecimal row/column display. EDIT accepts one
to eight bytes at offsets `000`–`FFF`. EDIT alone changes RAM only. WRITE
rewrites the buffered target after YES and a preimage check; BANK does not
retarget an already loaded buffer. READ again after a completed write.

`BYTE 9000 FE` programs one byte with only 1-to-0 transitions, after YES.
`ERASE 9000` erases its containing sector after YES. Readback is verified;
erases require a durable wear reservation first. `B3:C/D/F` remain protected.
The tool runs in RAM, so it can update admitted flash without executing from
the busy chip. `HOST` enters the existing OIP1 whole-sector transfer interface;
its Q returns to the board-tool menu. A framing failure still requires reset.

BYTE, an edited sector WRITE, ERASE back to the original all-FF sector, and Q
passed on 2512/B0:9. NO/cancellation and protected-target refusals also passed.
Do not treat an erased sector on another board as automatically disposable.

## BOOT / CONFIG and opaque images

```text
FLASH/MAINT> BOOT                ; inspect saved settings
FLASH/MAINT> BOOT B 0 8000       ; enable B0, entry $8000
FLASH/MAINT> BOOT C 0            ; choose enabled B0 as default
FLASH/MAINT> BOOT C B            ; choose MON B, binding its current generation
FLASH/MAINT> BOOT OFF 0          ; disable B0 after selecting another default
FLASH/MAINT> BOOT DELAY 1E       ; hex 30 ticks, 0.1 seconds each
FLASH/MAINT> BOOT RUN 0          ; run the saved enabled B0 entry once
```

Semicolon comments above are documentation, not command input. B/C writes are
immediate, as in the standalone CONFIG tool. Settings carry the existing wear
snapshot; native C/D rotation retains the newest state and counts its own
erase. An older physical record can be compacted; retain raw history archives
when historical rows matter. Default-B generation binding was accepted live;
the new OFF/DELAY/RUN spellings still need their own positive trials.

Opaque images need no STR8-N format. Install them using the Foundation OPAQUE
tool/host client described in the included Foundation manual, then enable the
bank and save its default. Entries are sector boundaries `$8000`–`$E000`,
excluding B3:C/D; an image can provide a JMP stub at that boundary for another
internal entry address. The full system profile occupies B2/B3, so use admitted
B0/B1 space for owner environments. Native RP/01 storage headers are **not**
direct opaque boot entries: launch CLOCK/FLASH through their native loader.

## STORE / TABLE / RESTORE, EDU and PROGRAM

Full words and S/T/R aliases are supported. EDU selection is a session setting:

```text
B3> EDU ON
B3> SRAM
B3> WORK
B3> TABLE P
B3> RESTORE P NFCOPY
```

If SRAM reports disabled CB flags busy, explicitly use `SRAM PREP` and retry.
This acknowledges those flags; it is not a memory formatter. PROGRAM and
WORKSPACE are separate; these storage commands do not write WORKSPACE.
`EDU ON` selects the Rev D wiring, not proof that hardware is attached.

The accepted flash-to-PROGRAM workflow was:

```text
WORKBENCH> AREA 0 9000 9FFF
WORKBENCH> STORE 0 AUTO 3000 3007 NFCOPY
WORKBENCH> RESTORE 0 NFCOPY L
WORKBENCH> STORE P 9000 3000 3007 NFCOPY
WORKBENCH> TABLE P
WORKBENCH> RESTORE P NFCOPY L
WORKBENCH> RESTORE P NFCOPY
```

Store confirmations require human YES; a queue never supplies it. AUTO is
also supported for PROGRAM. The qualification chose explicit PROGRAM `$9000`
to retain obsolete payload bytes elsewhere. Flash names are scoped by bank;
`P` selects PROGRAM explicitly. After verifying/running the destination, the
temporary flash source was erased back to its original FF. Thereafter
`RESTORE NFCOPY` found and ran the PROGRAM copy automatically. Existing CLK
and CLOCK records remained intact. NFCOPY prints `P` then returns via public
HOLD. It remains on 2512 as a usable example.

Move currently means **copy, verify/run, then explicitly retire the source**.
There is no new one-command MOVE or bulk delete. Native reserved names do not
silently replace similarly named legacy PROGRAM records. Old b35 applications
using private addresses need adaptation; stored bytes alone do not establish
BASE1 compatibility.

## Memory and current limits

The full environment reserves 64 KiB: all B2 and B3, including F and the C/D
journal. B0/B1 remain owner space. This does not erase their current contents.
M1/W remain available; the map's unknown tag does not mean free space. The
allocation table in the acceptance document identifies the new RP modules.

The workbench borrows `$4800–$66FF`, with PROGRAM code at `$6B00–$77FF`.
Native CLOCK/FLASH overlays borrow `$2000–$5FFF` plus gateway/state/sector
scratch through `$77FF`. Save owner programs before explicitly loading tools.
Native Q restores monitor session and owner ZP; it does **not** restore the
owner RAM displaced by loading an app. The qualification host separately
restored its saved owner RAM after testing.

Workbench RESTORE destinations currently stop at `$47FF` to prevent executing
or returning into a self-overwritten loader. Larger legacy apps need the
independent load/handoff path; the native CLOCK loader supplies that path for
the named system app. BATCH currently covers returning workbench commands,
including VERSION/TIME, rather than every b35 app/STORE/RESTORE combination.
These remain explicit full-b35 shipping gaps. ASM/DBG are follow-on work.

## Restore factory firmware

Factory restoration is deliberate removal of Foundation, not a normal FLASH
override. Keep the exact CPU/board-matched WDC backup. The host preparer
`tools/nf_factory_image.py` creates a programmer image and review file without
opening a port. Restoring B3 replaces its F and C/D journal; archive current
boot/wear history first. A full-chip programmer erase also affects other banks
and their wear accounting, even if the file restores their bytes. Firmware
restoration does not reset RTC, SRAM, EEPROM or physical jumpers.

The kit includes no WDC vendor firmware. This factory-restoration route is
prepared for review, not qualified by a new factory flash on 2512. F remained
golden throughout the native-utilities work.

Example host preparation (no board access):

```text
python tools/nf_factory_image.py --current-flash current-128k.bin --wdc my-original-wdc-bank.bin --cpu 65c02 --out factory-review
```

Use `65c816e` and its matched WDC source for the W65C816SXB. Inspect the emitted
review before a separate programmer operation. A 4 KB WDC input fills B3:8-E
with FF in the prepared image; a 32 KB original bank restores that exact bank.
