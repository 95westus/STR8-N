# Unified STR8-N operator manual — candidate4

Current compact profile, November 2, 2026. This is an unpublished candidate
above **STR8N-F 0.3.0 g00000001 / BASE1 / PR05**. F is exactly 4096 frozen
bytes. MON A/B are **STR8-N 0.1.0-dev g00000010**, using the approved
Traditional presentation. The same feature profile runs on W65C02SXB/65C02
and W65C816SXB/65C816 emulation, with optional matching EDU hardware.

This manual describes the extracted ZIP. Its Foundation instructions are in
`foundation/docs/USER_MANUAL.md`; the Python terminal is `terminal.py`.
See [developer tools](DEVELOPER_MANUAL.md), [terminal keys](SERIAL_CONSOLE.md)
and [qualification and remaining gates](UNIFIED_CANDIDATE_STATUS.md).

## Start and identify

At `REC>`, choose `A` or `B`. Both monitors have the same commands; the slot
identity differs. The saved default can select either monitor, recovery, or
an enabled opaque bank. MON `Q` returns to `REC>`.

Startup shows Foundation identity and purpose, then MON slot/generation,
board name, RAM, EDU, formatted SRAM capacities, local RTCC, tracked wear
and battery policy. `VERSION` (or `V`) adds CPU/ABI and valid MON A/B details.
`TIME` reads a fresh UTC sample with raw control/trim without repeating the
banner. `--*` denotes missing/unadmitted data; `*` qualifies unmeasured health
or prior wear. Tracked erase attempts do not establish physical flash health.
Saved values are board-specific; examples do not set a name, offset or trim.

`B0` through `B3` select the data bank and change the prompt to `Bx>`.
The monitor still runs in its A/B slot. Commands selecting a bank, including
`TABLE 2`, may return at `B2>`; this is normal. Use `B3` to select bank 3 again.

```text
REC> B
B3> VERSION
B3> APPS
B3> TIME
B3> R CLOCK
CLOCK> STATUS
CLOCK> Q
B3> Q
REC>
```

`?` is the installed monitor help. Main commands are VERSION/TIME, B0–B3,
D, M/!M, G, L/S19, M1–M3/W, APPS/APP, CLOCK, SRAM/WORK/EDU,
STORE/TABLE/RESTORE (S/T/R), BATCH and Q. MAINT/FLASH are REC BINs in this
profile; they are not resident named applications.

## Python terminal and RAM loading

From the extracted directory:

```text
python -m pip install -r requirements-console.txt
python terminal.py
```

Python 3.11+, Tk and pyserial 3.5 are required. Windows users may double-click
`Start-Terminal.cmd`. Select the correct port/baud and connect with F10 or the
button. The terminal does not connect, reset or flash on startup.

| Key | Action |
| --- | --- |
| F1 | Help |
| F2 | Choose a raw RAM BIN |
| F3 | Send chosen BIN at an observed SEND BIN |
| F4 | From REC>, send L and the chosen BIN |
| F5–F8 | Foundation MAP / CONFIG / OPAQUE / DEMO presets |
| F9 | Toggle a private host transcript |
| F10 / F11 / F12 | Connect/disconnect / clear display / Ctrl-C |
| Shift+F2 / Shift+F3 | Choose RAM S19 / send at the monitor RAM S19 prompt |

For full maintenance, F2 selects `rec/MAINT.bin`, then F4 at `REC>`. For
flash operations select `rec/FLASH.bin` instead. Both load and start at
**$0200**. Neither needs a stored MAINT/FLASH copy or SPI SRAM. F5's MAP is
the smaller Foundation inspection tool, not the full maintenance editor.

Raw recovery L accepts bytes for $0200–$64FF and runs after input idle. A raw
BIN has no declared length, checksum or independent readback in that protocol.
Wait for the expected tool prompt. Cancel SEND BIN with Ctrl-C **before the
first payload byte**. Once sending starts, finish the transfer; Ctrl-C would
be binary data. The console defers close/disconnect while sending.

To load RAM S19, enter `S19` in MON, wait for `SEND S19 (S0/S1/S9); Ctrl-C
cancels`, then Shift+F2/F3. Accepted RAM records do not autorun. Inspect the
result before `G address`. Dense flash S19 uses the FLASH tool's own protocol;
the RAM S19 shortcut does not send that format to flash.

RAM tools borrow application RAM and ZP. Their normal Q/QUIT does not restore
the overwritten application. Save work before loading another overlapping
tool. Preservation in lab qualification used separate host escrow/readback.
Never send AP/02 flash-sector images through raw RAM L.

## Dump, modify and execute

`D address [end]` dumps memory in the selected data bank. `M address bytes`
modifies admitted application RAM; `!M address bytes` explicitly forces ZP,
stack, other RAM/I/O, or admitted flash 1-to-0 byte programming. Each accepts
1–8 bytes. F and the C/D boot/wear journal remain protected. !M is a low-level
operation, not a sector editor or an erase override. `G address` transfers
control. Programs returning through public HOLD ($7E67) can return to MON.

`M1`, `M2`, `M3` give grid, ranges and wear; `W` also lists wear. An erased
sector is not permission to replace an owner image or reserved shared service.

## Installed tools and layout

| Region | Current use |
| --- | --- |
| B0:A/B | ASM g2, CPU-matched AP/02 image |
| B0:C/D | DBG g2 and paired SF/1 provider at D800–DFFF |
| B1:A | Shared MON flash-transfer workers |
| B1:B–D | Native SRAM/WORK services |
| B2:8–D | WB2 gE, PROGRAM g3, loader/storage/CLOCK services |
| B2:F | STATUS code at FA50–FFF9; preserve the whole allocation |
| B3:8 | RTC/I2C provider |
| B3:9 | RTC history code through 9BFF; board metadata at 9C00–9FFF |
| B3:A/B | MON A/B g10 |
| B3:C/D | Boot/wear journal, reserved |
| B3:E | Shared dispatcher, maps, apps and loaders |
| B3:F | Golden Foundation |

The compact full profile uses **92 KiB of sector allocations**, including
F and C/D, leaving nine fully erased sectors (36 KiB) on the cleaned reference
boards: B0:8/9/E/F, B1:8/9/E/F and B2:E. Generic user boards may contain owner
images there; the kit does not assume they are disposable.

ASM/DBG are installed with both their sectors, not just their AP/02 headers.
Choose CPU02 envelopes for 65C02 and CPU16 for 816 emulation. The executable
bodies are common; the CPU envelope/checksum fields differ. Native 816 mode
is outside this candidate. Current SRAM sizes/settings remain board-specific.

## MAINT.bin: full BANK MAINT editor

F2 choose `rec/MAINT.bin`; F4 from REC>. The prompt is `BM>` and the identity
is BANK MAINT 2.4 / REC 0200 r1. This is the full g1-based RAM maintenance
core, not MAINT-RO. It includes its own maps and requires frozen BASE1/PR05.

| Command | Function |
| --- | --- |
| VERSION; ? | Tool identity; menu |
| NAME [name\|CLEAR] | Query/name the board; changes require YES |
| M [1\|2\|3] | Grid / ranges / tracked wear |
| TABLE [bank\|first-last], T | Flash catalogue, including native images |
| E bank sector[-sector] | Erase admitted sectors; Y confirms |
| C src range dst start | Copy RAM/flash, with overlap handling; Y confirms |
| V src range dst start | Compare RAM/flash |
| R src range | Read up to 4096 bytes into the editor |
| D [offset[-end]] | Display editor bytes |
| P offset byte ... | Patch RAM editor bytes |
| F offset[-end] byte | Fill editor bytes |
| N length byte; K | New filled buffer; CRC16-CCITT-FALSE |
| W dst start | Write buffer and verify; Y confirms |
| BOOT [CONFIG command] | Inspect/set boot configuration |
| J bank; Q | Boot an enabled bank; restart Foundation |

Numbers are hexadecimal. src/dst is `R` (RAM) or bank 0–3. Sectors are 8–F;
editor offsets are 000–FFF. RAM copy workspace is $0200–$1FFF; the independent
4 KiB editor is $5000–$5FFF. Code/library ends at $4CDF; state and sector staging
also borrow high RAM. Raw writes protect B1:8–A, all B2 and all B3. Structured
NAME/BOOT writes use their own validated metadata/journal paths.

This RAM-only example changes the editor and then writes the borrowed RAM
workspace; it makes no flash or settings write:

```text
N 1000 FF
P 0 12 34 56
F 10-1F A5
D 0-1F
K
W R 1000
Y
V R 1000-100F R 1000
```

Q restarts Foundation with the saved boot policy. Choose S for REC>, or let
the default monitor boot. It does not change the default. The g1 REC package
has no later `EDU SAVE` or named `X` transfer command. Those commands from the
former resident g3 app are not advertised as available here.

## FLASH.bin: sector editing, byte writes and transfer

F2 choose `rec/FLASH.bin`; F4 from REC>. The menu is `FLASH/MAINT>`; VERSION
identifies FLASH g2. The core and dense-transfer library are included in the
RAM BIN ($0200–$4544 plus its runtime buffers). There is no resident FLASH copy.

```text
BANK 0
READ 9000
VIEW 000
EDIT 000 12 34
VIEW 000
WRITE
```

READ copies the containing 4096-byte sector and discards pending edits. VIEW
shows a 16-by-16 row/column page at offsets 000, 100, … F00. EDIT changes 1–8
buffer bytes only. WRITE asks YES before replacing the buffered target and
verifies readback/preimage; BANK does not retarget an already loaded buffer.
Choose an admitted target before confirming; the example is syntax, not a
scratch-sector allocation. Read again after a completed write.

`BYTE address byte` programs admitted 1-to-0 transitions after confirmation.
`ERASE address` erases its containing sector after confirmation. `I first last`
receives checked, dense ascending full-sector S19. Use the FLASH menu/host
instructions for that protocol, not the terminal RAM S19 shortcut. `HOST`
enters OIP1 whole-sector transfer; its Q returns to this tool. Main Q restarts
Foundation using the saved boot policy. Raw B3:C/D/F writes remain protected.
Erases require native durable wear reservations before chip erase.

## BOOT / CONFIG and opaque images

Use Foundation CONFIG (terminal F6), `BM> BOOT`, or `FLASH/MAINT> BOOT`.
Queries inspect; commands with settings arguments write immediately. These
examples are separate commands; do not type the explanatory comments:

```text
BOOT
BOOT B 0 8000
BOOT C 0
BOOT C B
```

`B bank entry` enables a bank and saves its entry. Entries are 8000–E000 in
1000 steps; B3 excludes C000/D000. `C 0` chooses enabled B0; `C B` chooses MON B
and binds its current generation. `C S` chooses recovery. First install and
verify a compatible opaque image; B/C only save policy. AP/02/RP/SR headers
are not raw opaque entry points. CLOCK/ASM/DBG use their loaders.

The FLASH BOOT panel also offers OFF/RUN/DELAY. BASE1's chooser is frozen at
three seconds: DELAY stores a legacy field and does not change that interval.
Do not initialize an existing journal. C/D rotation can replace old physical
rows while retaining current settings/counts; archive raw history and review
that scope. Saved MON defaults may need a separate C A/B append when MON
changes generation. Keep recovery selected during an incomplete installation.

The Foundation manual covers OPAQUE install/readback and the programmer-F
provisioner. An image has to obey its declared CPU/entry/return contract; merely
finding bytes or a WDC signature does not establish a bootable environment.

## CLOCK

`R CLOCK` is the resident full CLOCK 1.10-derived tool. HELP is its grammar.
TIME/R shows UTC/local time; STATUS/S shows flags, raw registers, control/trim
and identity. HISTORY/SHOW/STATS read retained outage evidence. VERSION/V
shows identity; Q returns to MON.

`SET yyyy-mm-dd hh:mm:ss` sets UTC after exact YES. `OFFSET +/-HH:MM` changes
the fixed local display offset (manual DST). `TRIM -127..+127` is confirmed;
clock output/alarm guards apply. `EUI` reads identity; `ACCEPT EUI` confirms
accepting a changed device. ACK/CLEAR and BATTERY administration have explicit
confirmations described by HELP. The health caveat remains on startup.

SET must archive latched power-fail evidence before RTCWKDAY clears it and
refuses enabled alarms. After a failed SET inspect STATUS before retrying.
TIME does not set the clock. A battery-warning stage advancing can append a
metadata record. Physical latched-event/changed-trim/battery cases are not
proved by earlier CPU-RAM fault injection; see the qualification summary.

## STORE / TABLE / RESTORE, PROGRAM and WORKSPACE

`MAINT` or `MAINT LOAD` enters/reloads `WORKBENCH>` storage services. This is
not the BANK MAINT editor. `SRAM` and `WORK` query storage. `EDU ON/OFF` chooses
the session wiring profile; it is not electrical identification of an add-on.
A previously saved EDU choice is still honored at startup, but changing that
persistent choice is not exposed by the new g1 REC MAINT BIN.

STORE/TABLE/RESTORE retain S/T/R aliases and AUTO selection. `P` explicitly
means PROGRAM; bank 0–3 explicitly means flash. The monitor/workbench TABLE
accepts **one bank or P**, e.g. `TABLE 2` or `TABLE P`, not a bank range.
Its SR/01 scan differs from the full native-image catalogue in BM> TABLE.
Explicit flash commands can change the selected Bx prompt.

```text
TABLE 0
TABLE P
AREA 0 8000 9FFF
STORE 0 AUTO 3000 3007 DEMO
RESTORE 0 DEMO L
STORE P AUTO 3000 3007 DEMO
RESTORE P DEMO L
RESTORE P DEMO
```

These are workflow syntax examples, not permission to overwrite an arena or
RAM source. Supply the actual source bytes, admit the flash arena/PROGRAM free
space and answer the prompted confirmation. `L` restores without execution;
omitting it may run the restored entry. Verify a copied destination before
retiring a source. There is no implicit delete-on-copy or atomic move.

PROGRAM is formatted named-record storage, not directly executable CPU RAM.
Load a record into CPU RAM to run it. There are eight directory slots; versions
and tombstones consume slots until explicit reclaim. WORKSPACE is the separate
application-managed SPI buffer/claim area, not extra CPU RAM or a PROGRAM file
area. Large Store/HOLD/BATCH, AUTO placement, CRC refusals and manager G/return
have dated qualifications. This kit does not format or change a partition.

`R SRAM` opens `SRAM>`; `R WORK` opens `WORK>`. They begin read-only. `!` opens
STORAGE controls; UNLOCK requires YES for session writes. S/W selects the
manager. The SRAM menu supports store/restore/run/delete/reclaim; WORK HELP
lists capacity, partition P, U upgrade, V repair and F format. These commands
can change data/layout; inspect their own menu and confirm an admitted scope.
Managed WORK functions require SS2; SS1 may require explicit U upgrade first.

A 64 KiB PROGRAM / 64 KiB WORKSPACE split gives 63,488 / 65,504 usable bytes.
It is a recommendation, not a forced default. The earlier cleanup retained
2604's SS2/16 KiB and 2512/2609's SS1/64 KiB layouts. A separately approved
November 2 standardization subsequently put all three on SS2/64 KiB PROGRAM
and 64 KiB WORKSPACE: native U on 2512/2609 and P 64 on 2604, without formatting.
Full before/after SRAM comparisons verified the exact management-cell changes,
unchanged PROGRAM directories and every payload byte; flash and owner RAM were
preserved. On 2604, $04000-$0FFFF changed ownership to PROGRAM: existing bytes
remain, but later STORE may allocate there. This does not authorize conversion
of another user's board. The local closeout is
`output/qualification/SS2-64K-standardization-complete-20261102.json`.
The candidate4 ZIP remains unchanged. Current PROGRAM directories are empty. Obsolete CLK/CLOCK/
NFCOPY records and retired flash copies are not preloaded by this candidate.

## APPS, BATCH, ASM and DBG

APPS shows native routes and installed AP/02 entries. `APP ASM`/`R ASM` and
`APP DBG`/`R DBG` launch CPU-matched tools from B0:A/B and C/D. ASM is a
65C02 cross-assembler on both CPUs. The 816 debugger qualifies the common
8-bit emulation subset, refuses reassigned/unsupported opcodes for S/N and
is not a native 816 debugger. See [DEVELOPER_MANUAL.md](DEVELOPER_MANUAL.md).

`BATCH VERSION;TIME` illustrates a returning command queue. Returning programs
must carry the supported return marker/contract. ASM/DBG and other interactive
tools are not returning BATCH jobs. A queue never supplies YES to a write
confirmation. Ctrl-C/ESC cancels where supported. A loaded large program can
borrow the workbench area; the accepted return path reloads its services.

## Prepare a reviewed installation; no automatic flashing

First reach published Foundation BASE1/PR05 using its manual/migrator. F.bin in
this ZIP is the unchanged published F, not a full-system programmer image.
Back up WDC firmware privately on the host. The full developer layout occupies
B0:A–D, so it cannot preserve a complete bootable WDC bank there. The retained
published Foundation migrator is not relabeled as the later Host/B0/Both
experimental migration; that full migration gate remains separate.

Run `python verify_candidate.py` after extraction. With all four fresh private
bank captures, prepare sectors locally:

```text
python tools/nf_compact_images.py --cpu 65c02 --current-b0 private/B0.bin --current-b1 private/B1.bin --current-b2 private/B2.bin --current-b3 private/B3.bin --out private/plan
```

Use `--cpu 65c816e` for W65C816SXB emulation. This prepares twenty active
component sectors, excluding F and C/D. B3:9 combines its 3072-byte history
code prefix with that board's exact final 1024 metadata bytes. B0 developer
envelopes follow the explicit CPU choice. All four captures and valid SNBT
are required; missing inputs, changed payloads or wrong F are refused.

`--retire-obsolete` additionally proposes clearing nine designated sectors.
Review each occupied preimage: on a generic board they may be useful owner
images, not obsolete data. The plan includes private backups, changed/identical
targets, exact native wear/journal forecast and old rows replaced by rotation.
Unchanged targets require no erase. No serial port is opened by preparation.

After approval, the matched Foundation OPAQUE tool/host protocol replaces
one reviewed sector at a time with native wear accounting. Its existing
`foundation/tools/nf_opaque.py --help` describes that live operation. Follow
the explicit plan; stop on failure rather than repeating a partly completed
erase. Re-capture if any image, boot setting or journal changed since planning.
Preserve owner RAM/ZP/cache/hooks separately before live qualification.

The preparer does not bind a different default generation, execute migration,
restore factory firmware or program a whole chip. Those are separate reviewed
operations. `tools/nf_factory_image.py` prepares board-matched WDC F-only/full-B3
restoration images without a port; real factory restoration removes Foundation
and remains a separate unqualified gate. No vendor firmware is distributed.

## Acceptance boundaries

The current compact bytes and REC tools passed on 2512/2604 (65C02) and 2609
(816 emulation). Developer g2 RAM/installed acceptance includes broader 65C02
and targeted emulation checks; positive source-write fixtures retain their
original board scopes. Candidate3 physical Shift-key and developer candidate2
extracted RAM acceptance are historical passes for those archives.

Candidate4 subsequently passed its own extracted-kit RAM acceptance on 2512,
including ASM/DBG, full REC MAINT/FLASH and guided terminal actions. The
MAINT sector editor/CRC and copy/compare checks used RAM; flash operations
were query, refusal or cancellation only. All flash banks and SPI metadata
remained exact, and owner RAM/ZP/cache/hooks were restored. The companion
`ACCEPTANCE-2512.json` records physical-key versus button coverage; the ZIP
remains unchanged. See `UNIFIED_CANDIDATE_STATUS.md`. Source-only rebuilding,
physical factory restoration, native816, physical changed-trim/latched-event
cases, and a persistent EDU-save/named-X REC front door remain separate gates.
Published Foundation downloads and historical candidates remain unchanged.
