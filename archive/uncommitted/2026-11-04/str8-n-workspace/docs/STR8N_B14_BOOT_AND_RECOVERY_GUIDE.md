# STR8-N b14/b15 boot, recovery and configuration guide

**Unified source/build:** The 2512 FLASH and 2609 F-up work now share
[one STR8N-F codebase](../bootstrap-opaque/docs/UNIFIED_SYSTEM.md). Its common
CONFIG and tools replace separate active build routes; the dated paths in
this reference remain historical qualification evidence.

Current behavior and implementation status, including the b15 update on 2512.

This is the consolidated operator and technical reference for the
`2.0proto b14/b15` boot sector, SNBT boot records, recovery console, RAM CONFIG
and related RAM recovery tools. It describes the b14 baseline, the b15 update
installed on 2512 (generation `$8000000F`), and the separately built extended
CONFIG tool.
These components are separate from the published RC1 firmware and its manuals.
For the new component-by-component operator walkthrough, use
[Build the system from F alone](STR8N_B15_FROM_F_GUIDE.md): F up, journals,
MON A/B, configuration, opaque images and the other b15 features.
The RAM tools depend on matching prototype services; they do not run unchanged
on RC1 g0034 or WDCMONv2. CONFIG and the RAM read/restore service use entries
unchanged by b15. Tools that also check an exact F CRC need a matching build.

**b15 update:** Ctrl-C (`$03`) as the first input while `SEND BIN`
waits now cancels to recovery without writing or running the payload. After
the first non-Ctrl-C payload byte, `$03` remains literal binary data. This is
implemented in `2.0proto b15`, generation `$8000000F`, and installed on 2512.
The baseline b14 build and its receipts are preserved. See
[b15 offline qualification](../BUILD/pr04-b15-cancel-r3/b15-qualification.json)
and [builder](../prototypes/boot-record-v2/build_b15.py).
The b15 build passed 512 offline groups, including 40 dedicated cancellation
groups, on 65C02/65C816 emulation and both consoles. A second build reproduced
its payloads byte-for-byte. The receive/idle loop is unchanged from b14;
exact-F-CRC-bound b14 MON/recovery kits require rebuilding for use with b15.
The [2512 installation audit](../output/qualification/b15-2512-install-20261026/audited-results.json)
records the preserving upgrade, physical cancellation/load tests and owner-RAM
restoration.

## Contents

- [Implementation status](#implementation-status)
- [Boot-sector function and storage map](#boot-sector-function-and-storage-map)
- [Startup and boot selection](#startup-and-boot-selection)
- [Boot records and the journal](#boot-records-and-the-journal)
- [Recovery console and raw BIN loading](#recovery-console-and-raw-bin-loading)
- [RAM CONFIG](#ram-config)
- [Worked examples](#worked-examples)
- [Opaque installation and the recovery kit](#opaque-installation-and-the-recovery-kit)
- [Bank applications and the FLASH page example](#bank-applications-and-the-flash-page-example)
- [Other implemented improvements](#other-implemented-improvements)
- [Planned work](#planned-work)
- [Qualification and the 2512 hardware result](#qualification-and-the-2512-hardware-result)
- [Artifacts, source and rebuilding](#artifacts-source-and-rebuilding)

## Implementation status

**Implemented** means code and a built artifact exist. **Hardware tested**
describes the specific recorded board exercise; it does not extend every
model result to physical hardware. **Planned** means the feature is not in the
current CONFIG or F image.

| Feature | Implementation | Verification and deployment scope |
|---|---|---|
| Fixed F reset/bootstrap and recovery console | Implemented | b14 and b15 installed/tested on 2512 in separate trials |
| SNBT C/D journal: default target, enabled banks and entry pages | Implemented | CPU/NOR models; settings writes and reset persistence tested on 2512 |
| Boot countdown, S/A/B/0-3 selection and saved default | Implemented | Both CPU models; 2512 boot/recovery exercises |
| Raw `L` at `$0200`, three-second idle autorun | Implemented | Both CPU/console models; 2512 FT245 hardware transfer |
| Ctrl-C cancellation before the first BIN payload byte | Implemented in b15 | Both CPU models; verified on 2512 through USB in USB/BOTH modes |
| FT245/ACIA/BOTH console selection | Implemented | Both ports modeled; live ACIA electrical qualification remains pending |
| Extended command-based RAM CONFIG | Implemented | 20 offline groups and the 2512 enable/entry/default/restore trial |
| OIP1 opaque whole-sector installer | Implemented | Both CPU models; separate 2512 install/run/restore exercise |
| Combined RAM recovery kit for b14 F | Implemented | 162 offline groups; this exact combined app has no claimed live trial |
| MON A/B recovery with the separate b14 MON kit | Implemented | Separate restore kit used successfully on 2512 with b14 F |
| Commented opaque FLASH/maintenance page, with RAM/flash edits and Q to MON | Implemented as a separate b15 application | 69 offline groups; 2512 edit/restore trial passed, then B0:8 was reinstalled and left installed at the owner's request |
| FLASH busy-LED cleanup on return to its prompt | Implemented in the current FLASH image | 34 LED model groups, 69 regressions and live program/erase return paths; updated on 2512 |
| Named FLASH/IO/FILE/PROGRAM or CONFIG/MAINT/REPAIR application launcher | Planned; FLASH/IO/FILE/PROGRAM menu deferred by owner on October 27 | Multiple images can share storage now; a named directory/dispatcher has not been implemented |
| Numbered RAM CONFIG menu with draft edits and one Save | Planned | Design below; no menu CONFIG BIN has been built or loaded |
| 2609 WDCMONv2-to-b15 F-only step | Offline qualified, then installed through the RAM migrator | 44 offline groups; one 4096-byte F write; USB REC verified and stopped; ACIA remains unqualified |
| General journal repair, complete WDC-to-MON/journal conversion, cross-platform terminal | Not implemented as one operation | The F-only stage does not perform these operations |

The extended CONFIG is a temporary RAM application. Its hardware test ended
with the owner's RAM restored, so it is not a permanently resident command.

## Boot-sector function and storage map

F is the first-stage boot and recovery code in bank 3. It establishes CPU and
RAM service state, initializes the console, reads the saved boot record and
dispatches to a monitor, an opaque bank image or recovery. It also receives
temporary RAM tools when normal monitor services are unavailable.

F reads the configuration journal. The journal writer lives in MON/RAM tools,
and flash-busy operations execute from RAM. Normal CONFIG and opaque-image
operations do not replace F. This read-only policy is a software contract;
it is not a claim that the flash sector has hardware write protection.

Bank notation is `Bn:address`. Each bank maps a 32 KiB flash window at
`$8000-$FFFF`; the same CPU address can contain different bytes in each bank.

| Location | Purpose |
|---|---|
| B0/B1/B2:`$8000-$FFFF` | Normal locations for opaque images; installation replaces explicitly selected whole sectors |
| B3:`$A000-$AFFF` | MON A, including its image header |
| B3:`$B000-$BFFF` | MON B, including its image header |
| B3:`$C000-$CFFF` | SNBT configuration/wear journal sector C |
| B3:`$D000-$DFFF` | SNBT configuration/wear journal sector D |
| B3:`$F000-$FFFF` | Fixed F boot/recovery sector, including reserved hardware-vector space |
| RAM `$0200-$64FF` | Raw RAM-tool load window: 25,344 bytes |
| RAM `$6500-$77FF` | Reserved service/journal/staging workspace; outside raw L's writable window |
| RAM `$6700-$67FF` | Journal snapshot work frame within that reserved workspace |
| RAM `$6800-$77FF` | Opaque installer's 4 KiB staging buffer within that reserved workspace |

An opaque image has arbitrary owner-defined contents. The boot record stores
its bank and entry page, not the image itself. Selecting a bank does not check
the image's executable format, contents, CPU requirements or interrupt vectors.

## Startup and boot selection

**Implemented.** Startup initializes the runtime, waits for the USB/console
startup interval, drains stale receiver input, then displays the choices and
the fixed six-second countdown. The built b14 startup uses a nominal
two-second initial wait and approximately one-second drain at 8 MHz. The
visible message is `WAIT...`; older development notes use other wording and
timings.

A normal default-MON-B b15 startup includes:

```text
WAIT...
S=Recovery  A/B=Monitor  0-3=Bank
Boot : 6 5 4 3 2 1 0

STR8-N 2.0proto b15 B3 65C02
```

During the countdown, select a target with a single key; Enter is unnecessary.

| Key | Action |
|---|---|
| `S` | Enter fixed F recovery |
| `A` or `B` | Validate and launch that MON image |
| `0`, `1`, `2`, `3` | Launch the enabled bank at its saved entry |
| No selection before expiry | Use the saved default |

Lowercase letters are accepted. CR, LF and unrelated keys do not immediately
boot the default or restart the countdown. Make the selection after the
choices appear: the preceding drain intentionally discards stale input.
`J3` from a working monitor also restarts through this startup path.

A manual selection is for that handoff. Saving a different default requires
a configuration write, such as RAM CONFIG's `C target`.

MON selection requires a valid compatible slot image. A saved MON default
also uses the pinned generation in the boot record. An unavailable or invalid
requested image returns to recovery. Missing or ambiguous usable boot records
select recovery; opaque bank choices require a valid record and enable bit.

The record retains a timeout byte for compatibility. The current UI uses its
fixed six-second countdown and does not provide a timeout editor.

## Boot records and the journal

**Implemented.** C and D each contain sixteen page-aligned, 256-byte snapshot
slots. A committed snapshot contains boot policy, configuration and wear
history together. Sequence numbers identify the newest admitted snapshot.

### The 32-byte boot record

All offsets below are hexadecimal and relative to the start of a snapshot.
Multi-byte integers and stored CRCs are little-endian.

| Offset | Size | Field and meaning |
|---|---|---|
| `00-03` | 4 | ASCII signature `SNBT` |
| `04` | 1 | Format version `01` |
| `05` | 1 | Boot-record length `20` hex: 32 bytes |
| `06` | 1 | Flags; current accepted value is zero |
| `07` | 1 | ASCII default: `S`, `A`, `B`, `0`, `1`, `2` or `3` |
| `08-0B` | 4 | Monotonically increasing sequence number |
| `0C` | 1 | Preserved legacy timeout field; not the active b14 countdown setting |
| `0D` | 1 | Enabled-bank mask: bits 0-3 correspond to B0-B3 |
| `0E-11` | 4 | One entry-page value per bank: `08` means `$8000`, `0A` means `$A000` |
| `12-15` | 4 | Pinned generation for a saved MON A/B default |
| `16-1D` | 8 | Reserved fields, preserved by configuration edits |
| `1E-1F` | 2 | CRC16 of bytes `00-1D` |

The bank entry contract is `$8000,$9000,$A000,$B000,$C000,$D000,$E000`.
For B3, `$C000/$D000` are forbidden because they hold the journal. B3's
`$A000/$B000` values remain legal record entries but occupy MON slots; the
ordinary opaque installer protects those sectors. B0/B1/B2 are the usual
opaque-image banks. `$F000` and arbitrary byte-aligned entries are outside
the current boot contract.

Examples of logical records:

| Saved policy | Default | Bank mask | B0 entry | Result |
|---|---|---|---|---|
| Recovery by default | `S` | Any valid mask | Any valid page | Countdown expiry enters recovery |
| Opaque B0 at `$8000` | `0` | Bit 0 set | `08` | Countdown expiry switches to B0 and jumps to `$8000` |
| Opaque B0 at `$A000` | `0` | Bit 0 set | `0A` | Same bank, entry `$A000` |
| MON B by default | `B` | Any valid mask | Preserved | Launches compatible MON B with its saved generation |

A numeric default whose enable bit is clear is refused by the configuration
writer. Every stored entry page must meet the field rules, including entries
for banks that are disabled.

### The rest of a snapshot

| Offset | Contents |
|---|---|
| `20-3F` | System configuration area, including preserved legacy settings |
| `40-9F` | 32 saturating, 24-bit erase-attempt counters |
| `A0-A3` | Unknown-history mask |
| `A4-A7` | History/policy flags |
| `A8-FB` | Reserved extension space |
| `FC-FD` | CRC16 of bytes `00-FB` |
| `FE` | Reserved `FF` byte |
| `FF` | Commit byte; `00` is programmed last |

CRCs use CRC16/CCITT-FALSE. F checks the boot CRC, commit, field validity,
sequence ordering and conflicting equal-sequence boot records. It does not
require the full snapshot CRC. Before mutation, the guarded journal writer
also checks the full snapshot and conflicting same-sequence history. Thus F
being able to boot does not establish that a settings write is admissible.

The writer appends a sealed snapshot, reads it back and publishes its commit
byte last. It skips torn pages. During rollover it reserves the peer-sector
erase attempt durably before erasing, retains a committed source snapshot and
then appends in the peer. Reservation exhaustion, sequence exhaustion,
corruption or saturated required counters cause refusal.

Counters are conservative erase-attempt history, not an exact lifetime-wear
measurement. An interrupted attempt can be counted without a completed erase.
Blank initialization marks earlier history unknown. Identical bank/entry
requests skip a new B-command write. Current `C target` saves are separate
transactions and do not promise the same no-op optimization.

Restoring old settings means appending the original logical values again.
It must retain newer sequence and wear history; copying an old whole C/D
backup over the current journal is not the restoration procedure.

## Recovery console and raw BIN loading

**Implemented.** Press S during the startup countdown to reach:

```text
Recovery L A/B 0-3 C1/2/3 ?
REC>
```

Recovery commands are text followed by Enter. Lowercase and CR/LF/CRLF are
accepted.

| Command at `REC>` | Function |
|---|---|
| `?` | Show current recovery help |
| `L` | Receive raw BIN into RAM at `$0200`; start after three seconds idle |
| `A` or `B` | Validate and launch MON A/B |
| `0` through `3` | Reread the record and launch that enabled bank at its saved entry |
| `C1` | Select FT245/USB console for this runtime session |
| `C2` | Select ACIA console for this runtime session |
| `C3` | Select BOTH consoles for this runtime session |

`C1/C2/C3` here select a console. They do not save a boot default. The RAM
CONFIG command is `C target`, with a space, at the CONFIG prompt.

### Raw L behavior

1. Enter `L` and wait for `SEND BIN`.
2. Send the complete matching tool as raw binary, with no terminal text or
   S-record wrapping.
3. After the last byte, leave the link idle for three seconds. Execution
   starts at `$0200` automatically.

There is no first-byte deadline. Once reception starts, each received byte
restarts the idle timer. The first enabled console supplying data owns the
transfer, even if the other console typed L. Binary input is not echoed.
The loader normalizes an optional command CRLF's LF before announcing
`SEND BIN`.

In b15, the first input `$03` cancels to `REC>`.
This applies both to the ordinary ready wait and to a first byte caught by
the optional command-LF probe. Cancellation restores text-console state;
detected receive errors retain their refusal diagnostic. No Enter is needed
for Ctrl-C. A BIN whose first byte is `$03` therefore cannot load through
b15 L. Once the first payload byte is accepted, all later values, including
`$03`, CR and LF, are literal data and there is no mid-transfer cancel.
The original b14 loader also treated a leading `$03` as payload. The b15
change preserves the three-second idle autorun rule and adds no length/CRC
verification.

Raw L accepts at most 25,344 bytes, ending at `$64FF`. Overflow or a detected
serial receive error refuses execution. It carries no length, header or CRC:
a three-second gap can execute a truncated prefix, and undetected corruption
can execute corrupted bytes. CRC/readback checks in flash tools and journal
operations are separate from this unverified RAM transfer.

The loaded RAM span replaces whatever was there. Preserve owner RAM before
loading a tool and restore it afterward when required. Current F recovery
has no RAM escrow/readback command. Earlier RLP1 headers, `$2000` tool builds
and recovery `R`, `D`, `V` instructions describe older prototypes and must not
be used as b14 loading instructions.

Console text starts in BOTH mode after F reset. Binary reception remains
owned by its data source. The ACIA model uses the existing 19,200-baud timing
contract; physical ACIA electrical behavior has not been newly qualified.

## RAM CONFIG

For 2609's later b15 F+C/D+MON+VX1 checkpoint, use the separately prepared
[2609 b15 CONFIG package](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/receipt.md)
and [F-up procedure](STR8N_B15_FROM_F_GUIDE.md#matching-ram-config).
That 2,728-byte app passed 31 offline groups, then a separately authorized
[USB inspection on 2609](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/receipt.md)
using only ?, bare B, bare C, W and Q. Default S, disabled banks, all flash and
tracked wear were preserved; no saved-setting write occurred. The b14 artifact
and earlier 2512 trial below retain their original scope.

**Implemented and tested on 2512.** Use the extended
[RAM CONFIG BIN](../BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin).
It is 2,602 bytes at `$0200-$0C29`, entry `$0200`. It works through F without
MON A/B present. The generic historical b14 build still contains the older,
minimal CONFIG; use this separate extended artifact for bank editing.

From recovery:

```text
REC> C1
REC> L
SEND BIN
```

Send that BIN in binary mode. After the idle start, the prompt is:

```text
RAM CONFIG ? B C I W Q>
```

Each CONFIG command takes effect when its Enter-terminated line is accepted.
The implemented tool has no draft or later Save stage.

| Command | Effect |
|---|---|
| `?` | Display full help |
| `B` or `C` | Display the saved default, all enable states and entry addresses |
| `B bank entry` | Enable bank 0-3 and save a four-digit hex entry; preserve the default |
| `C target` | Save default S, A, B or an already-enabled bank 0-3 |
| `I` | Initialize only if both journal sectors are entirely blank |
| `W` | Display erase counts and unknown-history status |
| `Q` | Restart through F and boot the saved default after its countdown |

Use entries such as `8000` or `A000`, with no `$` or `0x` prefix. B/C changes
boot settings only; it neither installs an image nor verifies the target's
code. A/B defaults require a valid compatible MON and record its generation.

The public tool enables banks but has no disable command. It refuses invalid
entries, disabled-bank defaults, malformed lines and inadmissible journals.
`I` is blank-only initialization, not a damaged-journal repair or a reset-to-
factory-settings command. Normal configuration and initialization do not
set RTC time, acknowledge PF history or change trim.

## Worked examples

### Boot an already-installed opaque B0 image at `$8000`

Load CONFIG as above, then enter:

```text
B 0 8000
C 0
B
Q
```

The first line enables B0 and persists its entry in one snapshot. The second
saves default 0 in another snapshot. B displays the result. Q restarts F;
allowing the countdown to expire switches to B0 and jumps to `$8000`.
Press S after the startup choices appear to enter recovery instead.

The relevant display rows are:

```text
DEFAULT=0
B0 ON  ENTRY=8000
```

For a one-time launch from recovery, `0` followed by Enter uses B0's saved
entry without changing the saved default.

### Change B0's entry to `$A000`

For an image whose executable entry is already at B0:`$A000`:

```text
B 0 A000
C 0
B
```

The record stores page `0A`; it does not move or copy the image. Do not use
the numeric bank name as a MON slot name: `C B` selects MON B, whereas `C 0`
selects opaque bank 0.

### Restore the settings used before the 2512 trial

2512's captured original policy was default MON B, mask `0F`, with all four
entries at `$8000`. After the B0 `$A000`/default-0 exercise, CONFIG restored
that policy with:

```text
B 0 8000
C B
B
Q
```

The final display showed `DEFAULT=B` and every bank ON with `ENTRY=8000`.
The normal countdown then launched MON B. This restores those known original
values; it is not a generic undo command. Capture another board's original
values before changing them, especially because the public tool cannot
disable an originally disabled bank.

### Load maintenance when MON A/B are unavailable

Press S at the F countdown, use `C1` for USB if desired, then L and the matching
RAM tool BIN. F recovery and RAM CONFIG need no monitor image. The separate
MON restore kit or combined recovery kit can restore MON A/B; CONFIG itself
does not contain monitor images. Use a kit built for the current F image:
the linked b14 kit BINs have not been rebuilt for installed b15. Selecting absent A/B leaves recovery
available rather than manufacturing a monitor from boot metadata.

### Distinguish the three command contexts

| Context | Example | Meaning |
|---|---|---|
| Startup countdown | `S` without Enter | Enter recovery |
| Recovery `REC>` | `C1` then Enter | Select USB console |
| Recovery `REC>` | `0` then Enter | One-time launch of configured B0 |
| Recovery `REC>` | `L` then Enter | Receive and autorun a RAM BIN |
| RAM CONFIG | `B 0 8000` then Enter | Persist B0 enable and entry |
| RAM CONFIG | `C 0` then Enter | Persist default B0 |
| RAM CONFIG | `C B` then Enter | Persist default MON B |

## Opaque installation and the recovery kit

### OIP1 opaque-image installation

**Implemented.** The standalone 2,412-byte OIP1 RAM installer enters at
`$0200`; its b14 BIN loads through raw L. Its subsequent flash-transfer
protocol is separate and checked:

1. The host sends an `I` text command and waits for `SEND OIP1 HEADER`.
2. It sends the 20-byte OIP1 request header, including the canonical bank,
   sector, length, checksums and current target preimage CRC for a write.
3. For a write, it waits for `SEND 4096` and sends exactly one 4 KiB sector.
   A read returns `READ SECTOR+CRC`, the sector data and a CRC trailer.
4. The tool checks admission and payload/preimage CRC before mutation,
   reserves the erase attempt, writes and verifies the sector.

For example, installing B0:`$8000-$8FFF` requires one complete 4,096-byte
payload for bank 0, sector value `$80`. This is an OIP1 host operation; it is
not an arbitrary BIN sent at the installer menu. An image spanning multiple
sectors needs one admitted operation for each sector.

The ordinary read/write target set is B0/B1/B2 sectors 8-F and B3 sectors
8/9/E. It protects B3:A/B/C/D/F. Those B3 8/9/E locations may contain useful
existing firmware/data, so permission to address a sector does not mean it
is empty. Identical writes still require the current preimage CRC and skip
erase/wear when content is unchanged.

Interrupted opaque writes can leave the target sector torn. Read its current
contents before retrying. Framing, header/payload CRC, receive or partial-transfer failures
quarantine later input until reset, so delayed binary bytes cannot become
text maintenance commands. CRCs check integrity; they are not authenticity
or executable-code validation.

### Combined recovery kit

**Implemented; this combined BIN is qualified offline.**
[recovery-kit.bin](../BUILD/pr04-b14-recovery-kit-r3/payload/recovery-kit.bin)
is 11,985 bytes at `$0200-$30D0`. It shares one journal writer and embeds the
original b14 MON A/B images. It depends on matching F services.

Its prompt is `RAM KIT ? T I X Q> `. Commands take Enter:

| Command | Function |
|---|---|
| `?` | Full help |
| `T` | Restore embedded MON A/B, verify, commit each image last, then boot |
| `I` | Start the OIP1 host read/write protocol |
| `X` | Erase both monitors only after the `ERASE` confirmation |
| `Q` | Restart through F using the current boot record |

The app checks its own normalized CRC and the matching F CRC at entry and
before I/T/confirmed-X. These checks occur after raw execution starts and do
not turn F L into a verified or authenticated loader. T/X own MON sectors;
C/D mutations use the guarded writer, and ordinary I cannot write them.

The combined app is not a WDCMONv2 converter. The separately qualified MON
kit used for the physical 2512 restoration is a different artifact; its
hardware result does not qualify every combined-kit path on hardware.

## Other implemented improvements

| Improvement | Current behavior |
|---|---|
| Recovery independence | F loads RAM tools and dispatches enabled opaque banks with MON A/B absent |
| Startup input handling | Fixed drain of both receivers, then countdown polling; stale startup input is not a RAM-transfer protocol |
| Shared text handling | Echoed, lowercase-normalized commands; CR/LF/CRLF support; malformed-line rejection |
| Console ownership | FT245/ACIA/BOTH modes; first data source owns raw BIN reception |
| Flash preservation | Fixed protected sectors, full-snapshot admission, preimage checks, wear reservation and commit-last publication in the appropriate tools |
| No-op bank edits | Identical `B bank entry` requests make no new journal write |
| Recovery-kit consolidation | One shared writer saves 329 bytes versus the two separate tools |
| Reproducible artifacts | Independent builds reproduced b14 components, extended CONFIG and the combined kit byte-for-byte |

The b14 F space budget is:

| Item | Bytes |
|---|---:|
| Sector capacity | 4,096 |
| Body span, including internal gaps | 3,669 |
| Active code/data within that span | 3,572 |
| Reserved hardware-vector space | 32 |
| Contiguous free region `$FE55-$FFDF` | 395 |
| Reusable internal gaps | 97 |
| Total available space | 492 |

The active-code figure is part of the body span, not an additional allocation.
The b15 cancel update retains the same 395-byte contiguous reserve and
uses existing internal gaps; it has 81 internal spare bytes, 476 available
bytes in total. The b14 table above remains its historical baseline budget.
Each MON has a 3,830-byte body, 128-byte header and 138 free bytes. The original
writer is 983 bytes per independent MON link; RAM-tool copies can differ when
their dispatch/branch layout is extended. Shared PR04 service entry addresses
remain fixed within b14's prototype contract. They are not a promise of RC1
or future-version private-address compatibility.

## Planned work

### Menu-based RAM CONFIG

**Planned; not implemented.** A proposed interface is:

```text
RAM CONFIG
Saved default: B

1  View saved settings
2  Edit a bank (enable/disable and entry)
3  Choose default boot
S  Review and save pending changes
U  Discard pending changes
Q  Exit
```

Bank edits and default selection should remain in a RAM draft until Save.
Review should show saved and proposed values, then publish the complete draft
in one journal transaction. Disabling the current default must require a
valid replacement in the same draft. Identical saves should consume no page.
Quit with changes should offer Save/Discard/Cancel.

Use a separate read-only wear/history page and a clearly labeled blank-only
initialization action. Ordinary Exit should return to recovery; Restart into
the saved image should be a separate selection. The current command tool's
Q still restarts immediately through F.

### Other deferred or unsupported work

| Item | Status and required work |
|---|---|
| Public bank-disable command | Planned with the menu/draft editor; not present in the current CLI |
| Arbitrary entry addresses or `$F000` entry | Unsupported by the current record/F contract; needs an explicit format/consumer design |
| Editable startup timeout | Not implemented; stored legacy byte remains preserved |
| Damaged nonblank journal repair | Not implemented as a general recovery command; requires inspected preservation/migration policy |
| WDCMONv2 complete conversion including MON/journal | Not implemented as one operation; the 2609 b15 F-only stage is qualified offline and deliberately installs no other sector |
| b15 builds of exact-F-CRC-bound MON/recovery kits | Not built/qualified here; the linked b14 kit BINs retain their b14 F CRC checks |
| Windows/Linux Python serial terminal with BIN sending | Deferred investigation; no new cross-platform terminal was implemented here |
| Physical ACIA timing, broad NMI and electrical power-cut qualification | Pending; CPU/NOR and timing-model results are not those hardware tests |
| Published-release integration/full RC1 feature compatibility | Not completed by this prototype; auxiliary providers/debugger have separate private-interface requirements |

The broader v2.1 ABI/metadata and RTC event-journal proposals are separate
future work; they are not new F or RAM CONFIG services. See the
[ABI roadmap](STR8N_V2_1_ABI_METADATA_ROADMAP.md) and
[RTC event-journal proposal](RTC_EVENT_JOURNAL_PROPOSAL.md).

## Qualification and the 2512 hardware result

These result sets overlap in reused components. Their group totals should
not be added together as a new count of independent tests.

| Scope | Recorded result |
|---|---|
| b14 base components | 618 offline groups, both CPU models and console models, including raw-loader timing measurements |
| Extended CONFIG | 20 offline groups; all 26 admitted bank/entry pairs; 1,860 observed mutation prefixes; 24 selected interrupted-state retries |
| Combined recovery kit | 162 offline groups; 17,256 opaque mutation-prefix retries, including safe reservation refusals; 18 selected MON interruption prefixes |
| Exact captured-source CONFIG rehearsal | 65C02 and 65C816 emulation both predicted the same full-flash test/restoration postimages |
| Live CONFIG host checks | 15 buffered checks before the final board run |
| 2512 CONFIG exercise | Passed and audited; original logical settings and fresh owner RAM/ZP restored |
| 2512 b15 installation and loader tests | Passed and audited; Ctrl-C in USB/BOTH modes, normal CONFIG BIN execution/readback, original policy/opaque images/RAM preserved |

In the October 26 physical CONFIG trial:

1. Fresh repeated flash and RAM/ZP captures established original default B,
   enabled mask `0F` and four `$8000` entries.
2. A separately modeled, capture-bound bench helper temporarily disabled only
   B0 so the public tool could exercise an actual OFF-to-ON transition. That
   helper is not a public CONFIG disable command.
3. F raw L loaded the unchanged extended CONFIG. `B 0 A000` enabled B0 and
   changed its entry; `C 0` saved default 0.
4. Q restarted through F and S intercepted the countdown. Two independent
   full-flash reads matched the modeled saved postimage. No opaque code ran.
5. `B 0 8000` and `C B` restored the original logical policy. Two more full-
   flash reads matched the modeled restored postimage.
6. Fresh owner RAM `$0200-$64FF` was restored, compared twice through the RAM
   service and independently through MON. Owner ZP `$00-$DF` was preserved
   and verified. The final full-countdown boot selected MON B with BOTH
   consoles; pending flags were clear and the serial lease was released.

Journal sequence advanced from 930 to 936, retaining test/restoration history
and one additional B3:C erase attempt. F, MON A/B, opaque image sectors,
legacy settings, history flags and extension fields were preserved. No RTC
writes, physical reset or physical power-cut test occurred in that trial.
Initial sandbox/host prompt synchronization stops happened before settings
writes and remain in the retained receipts.

The earlier b14 installation receipt includes a physical-reset startup capture
and a raw FT245 load. A separate October 24 exercise installed, ran and
restored an opaque B0 probe with MON absent; original MON A/B were restored
afterward. Those are distinct operations from the October 26 CONFIG test.

Evidence:

- [b14 component qualification](../BUILD/pr04-b14-raw-r4/b14-qualification.json)
- [b14 installation hardware receipt](../output/qualification/pr04-b14-2512-install/test-results.json)
- [Extended CONFIG offline qualification](../BUILD/pr04-b14-ram-config-r1/ram-config-qualification.json)
- [2512 CONFIG audited result](../output/qualification/ram-config-2512-20261026-r3/audited-results.json)
- [Saved CONFIG display](../output/qualification/ram-config-2512-20261026-r3/CONFIG-saved.txt) and [restored display](../output/qualification/ram-config-2512-20261026-r3/CONFIG-restored.txt)
- [Earlier opaque install/run/restore receipt](../output/qualification/opaque-absent-2512-install-run-restore-r2/test-results.json)
- [Earlier separate MON restore receipt](../output/qualification/mon-restore-2512-through-F/test-results.json)
- [Combined recovery-kit offline qualification](../BUILD/pr04-b14-recovery-kit-r3/recovery-kit-offline-results.json)

These owner-local evidence/artifact paths are relative to this checkout.
Their presence does not mean private board captures belong in a public release.

### 2512 b15 installation, cancellation and normal BIN test

The owner-authorized b14-to-b15 update is complete. Fresh repeated flash and
RAM/ZP captures preceded a source-bound plan and 10 native transaction model
cases, 10 software-restart transaction cases and two post-install CPU profiles.
The success path restarted through F only after device verification; the
failure path remained halted. No physical RESET was used.

The board passed Ctrl-C at `SEND BIN` through FT245/USB in C1 mode after a
3.5-second first-byte wait, and in C3 BOTH mode with a CRLF command ending.
Both cancellations returned to recovery; independent MON readback confirmed
that cancellation changed no application RAM. A normal 2,602-byte extended
CONFIG BIN then loaded and executed. Its settings display succeeded, Q booted
b15 MON B, and an independent MON readback matched the executed image,
including its single known mutable display byte.

Two full-flash readbacks matched the modeled target. All B0/B1/B2 opaque
contents and unrelated B3 sectors were unchanged. Default B, enabled mask
`0F`, four `$8000` entry pages, legacy policy and history/extensions were
preserved. MON-generation metadata advanced from `$8000000E` to `$8000000F`.
Journal sequence advanced from 936 to 937 with one new reservation snapshot;
all prior journal pages remained intact. Exactly one erase attempt each for
B3:A, B3:F and B3:B was recorded, with no C/D erase.

Fresh owner RAM `$0200-$64FF` was restored, verified twice through the binary
RAM service and independently through MON. Owner ZP `$00-$DF` was preserved
and verified. The final full-countdown boot reached b15 MON B with BOTH
consoles. Pending flags were clear and the serial lease was released. No RTC
writes, opaque image execution or live ACIA input/electrical test was added.

Evidence: [audited installation result](../output/qualification/b15-2512-install-20261026/audited-results.json),
[hardware report](../output/qualification/b15-2512-install-20261026/test-results.json),
[exact-source CPU proof](../output/qualification/b15-2512-install-20261026/live-model-proof.json),
[USB cancellation](../output/qualification/b15-2512-install-20261026/Ctrl-C-USB-after-wait.json),
[BOTH/CRLF cancellation](../output/qualification/b15-2512-install-20261026/Ctrl-C-BOTH-CRLF.json).
The run directory retains its start-date name; its individual receipts record
the operation timestamps.

## Bank applications and the FLASH page example

### Applications can have names and their own screens

**Implemented storage and handoff:** A bank image can present its own page,
screen, menu and commands. The boot system only needs its bank and entry.
The FLASH example below demonstrates this with a `FLASH>` prompt and an
explicit return to `B3>`. A separate physical bank is not required for every
application: several images can occupy different sector ranges in one bank.

**Planned named dispatch:** Names such as `FLASH`, `IO`, `FILE`, `PROGRAM`,
`CONFIG`, `MAINT` and `REPAIR` would be logical application names. A launcher
would resolve a name to a bank and entry, then hand control to that image.
IO, FILE, PROGRAM and the proposed CONFIG/MAINT/REPAIR pages have not been
built by this example. Names do not change the board's physical bank count.

**Deferred by owner direction, October 27, 2026:** retain the idea of a menu
for FLASH, IO, FILE and PROGRAM, with FLASH mapped to B0:8 (entry `$8000`),
the other three pages marked as planned, and `Q` returning to `B3>` through
a validated MON. No launcher implementation or installation is underway.
Before future dispatch, verify that the intended FLASH image is present and
compatible; the initial 2512 trial restored B0, and the later leave-installed
setup is recorded below. The scope is
recorded in the [backlog](../TASKS.md#deferred-bank-menu-launcher-recorded-2026-10-27).

For example, this is a possible allocation, not an installed directory:

| Name | Storage | Entry | Status |
|---|---|---|---|
| FLASH | B0:8, `$8000-$8FFF` | B0:`$8000` | This example is built at this location |
| IO | B0:9-A, `$9000-$AFFF` | B0:`$9000` | Illustrative future application |
| FILE | B1:8-B, `$8000-$BFFF` | B1:`$8000` | Illustrative future application |
| PROGRAM | B2:8-E, `$8000-$EFFF` | B2:`$8000` | Illustrative future application |

The current SNBT record stores **one entry per bank**, plus one saved default
target. It has no image-name directory, lengths, image CRCs or per-image CPU
requirements. RAM CONFIG can change which image is that bank's saved entry.
From a running MON, `B0` followed by `G 9000` can instead make a one-time
handoff to an already installed image at B0:`$9000` without changing the saved
entry. The built image must match the entry and execution environment.

A natural next step is a small launcher image as the default boot, with a
menu of names. Its directory should carry name, bank, entry, allocated span,
integrity check and ABI/CPU requirements. This would also let FLASH protect
other registered images and give applications a common return-to-launcher
path. That dispatcher, directory format and return ABI remain planned. The
current SNBT format can stay unchanged: its saved entry starts the launcher,
and the launcher owns the directory of individual applications.

`B0:9-A` means sectors 9 and A in bank 0: an 8 KiB allocation. `B0:8` means
one 4 KiB sector at `$8000`. Physical banks are **0 through 3**; `B9:8` is
not a valid physical bank on this board.

### Built FLASH/maintenance example

The commented sources are [bank-monitor.asm](../prototypes/boot-record-v2/bank-monitor.asm)
and [bank-monitor-entry.asm](../prototypes/boot-record-v2/bank-monitor-entry.asm).
The [offline builder](../prototypes/boot-record-v2/build_bank_monitor.py)
produces two placements of the same application:

| Artifact | Placement | Size | RAM execution |
|---|---|---|---|
| [bank-monitor-8000.bin](../BUILD/b15-bank-monitor-led-r1/payload/bank-monitor-8000.bin) | B0:8, entry `$8000` | 4,096 bytes | `$0200-$0E83`; copying pads through `$0EFF` |
| [bank-monitor-9000.bin](../BUILD/b15-bank-monitor-led-r1/payload/bank-monitor-9000.bin) | B0:9-A, entry `$9000` | 8,192 bytes | Same RAM range; both source sectors protected |

The alternate 9-A variant deliberately reserves two sectors to demonstrate a
spanning image. The application currently fits in one. These are flash image
BINs, not raw `L` payloads: their first instructions expect to execute at
`$8000` or `$9000`. Install through an admitted opaque-sector installation
workflow, with fresh target backups and RAM escrow. Do not send these ROM
images to `REC> L`, which executes at `$0200`.

The initial build was offline. A subsequent owner-authorized trial installed
the **B0:8** variant on 2512, tested RAM/flash edits and Q, and restored the
original sectors, boot settings and fresh owner RAM/ZP. The owner then asked
for another installation to try personally: **FLASH is now left installed at
2512 B0:8**, with default MON B unchanged and a fresh original-B0 backup kept.
The B0:9-A variant remains model-tested only. See the two hardware operations
below. Installation over B0:8 replaces that sector's previous contents and
requires its own backup/restoration workflow.

Commands at the new application's prompt:

| Command | Function |
|---|---|
| `?` | Show the page's command help |
| `B0` through `B3` | Select the data bank for D/F/I; this does not leave the page |
| `D 9000` | Dump 16 bytes; allowed RAM `$2000-$64FF` or flash `$8000-$FFFF`, with the whole dump in range |
| `M 2000 41 42 03` | Edit 1-8 RAM bytes, only within `$2000-$64FF` |
| `F 9000 EA 60` | Edit 1-8 flash bytes, preserving every other byte in that sector |
| `I 9000` | Erase exactly one aligned 4 KiB sector |
| `Q` | Validate MON B, otherwise MON A, and enter `B3>`; if neither is valid, enter recovery |

All numbers are hexadecimal. F edits may cross a 256-byte page boundary but
cannot cross a 4 KiB sector boundary. Every edit is completely parsed before
RAM or flash changes. F and I display the target sector and require an exact
`YES` line (case-insensitive). Any other answer, including Ctrl-C, cancels.

For the `$8000` variant, the following edits **another** B0 sector, 9. It is
an example for a disposable, backed-up target, not a claim that the owner's
sector 9 is free:

```text
FLASH> B0
Data bank B0
FLASH> D 9000
... sixteen hexadecimal bytes ...
FLASH> M 2000 41 42 03
OK: RAM
FLASH> F 9000 EA 60
REWRITE SECTOR B0:9000; type YES> YES
OK: verified sector
FLASH> Q
... 2.0proto b15 ...
B3>
```

For the `$9000` variant, sectors 9 and A are protected as its own image; choose
a different disposable sector for flash exercises. Eligible targets are
B0/B1/B2:8-F and B3:8/9/E, excluding the application's own allocated source
span. B3:A/B monitors, C/D journal and F boot sector are refused. The tool
does not yet have a directory of other owner images: an explicitly selected
eligible target can contain another image and will be edited or erased.

To make an **already installed** `$8000` image the saved default, use extended
RAM CONFIG's `B 0 8000`, then `C 0`. For the alternate use `B 0 9000`, then
`C 0`. Save/entry changes do not install image bytes. Q from FLASH enters MON
directly rather than resetting into that default again; it never saves a
different default as a side effect.

### How the example works and its limits

The 62-byte ROM stub checks the published RAM ABI signature and copies the
3,204-byte application body to `$0200`, rounded to whole pages. The RAM body
then selects physical B3 before using any F services. It retains the source
bank separately from the selected data bank. This avoids fetching a ROM
continuation from the wrong overlay during a bank switch.

All flash mutation code executes from RAM. F editing stages a complete sector
at `$6800-$77FF`, modifies the requested bytes, then checks staging and target
preimage CRCs again after confirmation. The guarded journal engine reserves
one conservative erase attempt durably before the erase. Full erase check,
full byte comparison and final CRC verify the result. Identical content
consumes no erase or wear reservation. Invalid/conflicting journal history
or saturated wear counters cause refusal. The writer and mutation helpers
are reused from the qualified OIP1 implementation.

The example checks its immutable RAM code and exact installed b15 F CRC
before flash actions and Q. It is bound to the b15 F component with SHA-256
`1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8`.
CRC detects corruption; it is not an authenticity or security mechanism.
Q validates the selected MON image before setting its active page and calling
the RAM HOLD entry. This also works after cold opaque boot, when there is no
previous active MON to return to.

The page borrows `$0200-$0EFF`, stack, monitor ZP `$E0-$FF` and reserved
service/journal/staging workspace. M deliberately excludes the whole RAM
prefix below `$2000`. It does not automatically restore owner RAM on Q;
escrow and restore are the responsibility of the installation/test workflow.
IRQ remains disabled; 65C816 execution is emulation mode with D/DBR/PBR zero.
Physical ACIA, NMI and power-cut qualification remain pending.

Sector editing is not atomic. An interruption after erase can leave the
target sector torn; restoring all original unedited bytes then requires its
backup. Protected F/MON/journal and the source application remain recoverable.
Bulk BIN upload, assembler/editor integration, arbitrary I/O access, filesystem
services and a named application launcher are not implemented in this page.

Rebuild and run its offline model suite from the repository root, with the
existing frozen b15 build, WDC tools and Python model dependencies:

```text
python -B prototypes/boot-record-v2/build_bank_monitor.py --out BUILD/my-bank-monitor
python -B prototypes/boot-record-v2/test_bank_monitor.py --build BUILD/my-bank-monitor
python -B prototypes/boot-record-v2/test_bank_monitor_leds.py --build BUILD/my-bank-monitor
python -B prototypes/boot-record-v2/build_bank_monitor.py --out BUILD/my-bank-monitor-repro
python -B prototypes/boot-record-v2/qualify_bank_monitor.py --build BUILD/my-bank-monitor --repro BUILD/my-bank-monitor-repro
```

Use the generated BINs; S19 files are link intermediates before the builder
patches the application's code CRC. The
[build receipt](../BUILD/b15-bank-monitor-led-r1/bank-monitor-build.json) and
[CPU/NOR test receipt](../BUILD/b15-bank-monitor-led-r1/bank-monitor-tests.json)
record exact source hashes, placements and verification scope.
The [qualification receipt](../BUILD/b15-bank-monitor-led-r1/bank-monitor-qualification.json)
also checks source identity, reproducibility and unchanged inherited b15
firmware/tool payloads.
All 69 offline groups passed across 65C02 and 65C816 emulation, including both
placements, both console paths, all 26 eligible non-self targets, RAM/flash
editing, refusal cases, explicit MON return and representative erase/program
interruptions. One additional path within those 69 groups executes the local
CRC instructions without the model's CRC shortcut. Both image BINs reproduce
byte for byte. Those 69 groups are offline results; the following hardware
trial is recorded separately.

### 2512 FLASH install, edit, return and restore trial

**Hardware tested and restored, October 27, 2026.** Fresh repeated MON reads
captured all four flash banks and owner RAM/ZP before any flash change. Twenty
buffered host scope/framing checks and two exact-source CPU/NOR round-trip
models preceded installation. These models used the newly captured board
contents, not a generic erased-bank fixture.

The trial installed the 4 KiB FLASH example at B0:8 through the OIP1 installer,
verified its complete readback, then launched B0 from recovery at `$8000`.
At `FLASH>` the following passed:

- `M 2000 41 42 03 00 FF` and `D 2000` edited and read back five RAM bytes.
- `M 1FFF 55` and `F 8000 55` refused protected RAM and the executing image's
  own source sector.
- `F 9000 FF FF FF FF`, confirmed with `YES`, changed four bytes in the backed-up
  B0:9 sector. Full independent readback verified that the remaining 4,092 bytes
  were preserved. Repeating the same edit reported identical content and
  consumed no additional erase reservation.
- `Q` returned directly to b15 MON B at `B3>`. Independent MON readback also
  verified the RAM edit after leaving FLASH.

Two full-flash readbacks through the separate RAM service matched both CPU
models' edited postimage. OIP1 then restored the original B0:9 sector and the
original B0:8 image. Two further full-flash readbacks matched the modeled
restored state. B0/B1/B2 were byte-identical to the fresh capture; F and both
MON images were unchanged.

The original default B, enabled mask `0F`, four `$8000` entry pages, generation
pins, legacy policy and extension fields were preserved. No boot-setting
change was needed: B0 was already enabled at `$8000`. The journal advanced
from sequence 937 to 941, appending pages C500-C800. Each of B0:8 and B0:9
gained two actual erase-attempt reservations. All prior journal pages stayed
intact, other counters were unchanged and no C/D erase occurred. Restoration
preserves actual wear history rather than rolling counters back.

Fresh owner RAM `$0200-$64FF` was restored and verified twice through the
binary RAM service, then independently through MON after a complete
saved-default countdown. Owner ZP `$00-$DF` was preserved and independently
verified. Final state was b15 MON B, BOTH consoles, all restore-pending flags
clear and the serial lease released. No physical reset, power-cut test,
RTC write or live ACIA electrical test was performed.

Evidence: [audited hardware result](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/audited-results.json),
[hardware report](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/test-results.json),
[exact-source model proof](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/live-model-proof.json),
[RAM edit/readback](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/RAM-readback.txt),
[flash verification](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/flash-edit-YES.txt),
[Q to B3](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/FLASH-Q-to-B3.txt),
and [final default-B boot](../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/final-default-B-boot.txt).
The initial sandbox COM-port denial occurred before board traffic; the r2
run used direct serial access and completed the preserving trial.

### Current 2512 FLASH installation, left installed for the owner

After the preserving trial, the owner requested that FLASH remain installed
at B0:8. This separate October 27 operation captured current owner RAM/ZP and
all four flash banks twice. It retained the complete original 32 KiB B0 bank,
the overwritten 4 KiB sector and a backup manifest before programming.
The board was initially in MON A; capture used its validated entry without
changing the saved boot policy. Fourteen buffered host checks and both
source-bound CPU models passed before installation.

The first leave-installed image was `bank-monitor-8000.bin`, SHA-256
`900db634ce838aaf0cd85c53029377fe254ac4a4033d431a63d276da3f5902ec`.
Complete sector readback, live boot to `FLASH>`, help and Q back to `B3>`
passed. Two independent full-flash reads matched both models. Only B0:8 and
one appended wear record changed; B0:9, all other images, F and MON A/B are
unchanged. Journal sequence advanced from 941 to 942, with one B0:8 erase
reservation on page C900 and no C/D erase.

Owner RAM `$0200-$64FF` was restored and read back twice through the binary
service, then independently through MON. Owner ZP `$00-$DF` was preserved and
verified. Final state is **BOTH consoles, MON B at `B3>`**, with serial released
and all preservation-pending flags clear. Default B, enabled mask `0F`, all
four `$8000` entries, generation pins and the remaining policy are unchanged.
No RTC writes, physical reset, power-cut or live ACIA electrical test occurred.

To try the installed FLASH page, reconnect Tera Term to 2512's COM4:

1. At `B3>`, enter `J3` and press Enter.
2. During the startup countdown, press `0` to launch B0 at `$8000`.
3. At `FLASH>`, enter `?` for help. Enter `Q` to return to `B3>`.

From an existing `REC>` prompt, enter `0` and press Enter instead. The saved
default stays MON B. A FLASH launch copies its application into low RAM
`$0200-$0EFF`; Q returns to MON without restoring those borrowed bytes. The
fresh owner RAM escrow is retained alongside the original B0 backup.

Backups and evidence:

- [Complete original B0 bank, 32 KiB](../output/qualification/FLASH-2512-keep-20261027-r3/original-B0.bin)
- [Original B0:8 sector, 4 KiB](../output/qualification/FLASH-2512-keep-20261027-r3/original-B0-80.bin)
- [Backup manifest and hashes](../output/qualification/FLASH-2512-keep-20261027-r3/backup-manifest.json)
- [Start/return instructions](../output/qualification/FLASH-2512-keep-20261027-r3/START_HERE.txt)
- [Audited hardware result](../output/qualification/FLASH-2512-keep-20261027-r3/audited-results.json)
- [Exact-source CPU proof](../output/qualification/FLASH-2512-keep-20261027-r3/live-model-proof.json)

The earlier edit/restore trial remains a separate historical receipt. The
named FLASH/IO/FILE/PROGRAM launcher remains deferred.

### FLASH LED idle cleanup, installed October 27

The owner reported that `$F0` stayed lit after `I 9000` completed. This was
reproduced with the original image in the CPU/NOR model. The raw erase/program
worker sets the flash LEDs, while this RAM application's direct worker calls
bypass the ordinary MON finish routine. The FLASH menu now writes the normal
running pattern `$01` before every prompt. This clears the `$F0` busy bits on
success, refusal, cancellation and failure. Busy indication remains active
during actual NOR mutation.

The fix adds five bytes to the RAM application; its ROM allocation and copied
RAM window are unchanged. Both image variants reproduced byte for byte.
All 69 existing regression groups and 34 additional LED groups passed across
65C02/65C816 emulation and both console paths, including real mutation,
identical writes, already-erased sectors, cancellation, protected targets,
invalid journals and simulated erase failure.

Fresh hardware capture confirmed the owner's B0:9 erase, which advanced the
journal to sequence 943 after the previous installation. The old application's
known `$0200-$0EFF` RAM prefix was identified and restored from its verified
pre-application owner escrow; freshly captured RAM after that prefix and owner
ZP were preserved. Both source-bound CPU models passed before updating B0:8.

On 2512, the corrected image booted and performed `F 9000 00`, then `I 9000`.
Both actual mutations verified and returned through the new idle-write path.
B0:9 was returned to its captured all-`$FF` contents. Two full-flash readbacks
matched the models; settings, F/MON and all other opaque bytes were unchanged.
Owner RAM/ZP were restored, checked twice through the binary service and
independently through MON. Final state is BOTH-console MON B, serial released.
There was no independent optical LED measurement; the verified code writes
`$01` before the observed live prompts, and the LED bus values were checked
throughout the CPU/NOR models.

The current B0:8 image SHA-256 is
`3ec86d34bbcdbb4bef12074e263ffcd850e04f974981b1f7f237e4f77c941c79`.
Journal sequence advanced from 943 to 946: one B0:8 update reservation and two
B0:9 live-test reservations, appended at CB00-CD00. No C/D erase occurred.
The original B0 owner-image backup remains intact. Startup and Q commands
are unchanged, and the named application launcher remains deferred.

Evidence: [LED regression results](../BUILD/b15-bank-monitor-led-r1/bank-monitor-led-tests.json),
[old-image reproduction](../BUILD/b15-bank-monitor-led-r1/old-LED-regression.json),
[audited hardware update](../output/qualification/FLASH-LED-2512-20261027/audited-results.json),
[exact-source CPU proof](../output/qualification/FLASH-LED-2512-20261027/live-model-proof.json),
[live program return](../output/qualification/FLASH-LED-2512-20261027/program-returned-prompt.txt),
and [live erase return](../output/qualification/FLASH-LED-2512-20261027/erase-returned-prompt.txt).

## Artifacts, source and rebuilding

| Component | BIN | Primary source/builder |
|---|---|---|
| F sector, b14 baseline | [f-offline-component.bin](../BUILD/pr04-b14-raw-r4/payload/f-offline-component.bin) | [build_b14.py](../prototypes/boot-record-v2/build_b14.py), the versioned build chain and [boot logic](../prototypes/boot-record-v2/boot.inc) |
| F sector, installed b15 | [b15 F component](../BUILD/pr04-b15-cancel-r3/payload/f-offline-component.bin) | [build_b15.py](../prototypes/boot-record-v2/build_b15.py); adds first-byte Ctrl-C cancellation |
| Extended CONFIG | [ram-config-offline.bin](../BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin) | [ram-config-b14.asm](../prototypes/boot-record-v2/ram-config-b14.asm), [build_ram_config_b14.py](../prototypes/boot-record-v2/build_ram_config_b14.py) |
| Standalone opaque installer | [ram-installer-offline.bin](../BUILD/pr04-b14-raw-r4/payload/ram-installer-offline.bin) | [installer.inc](../prototypes/boot-record-v2/installer.inc), [installer_build_b14.py](../prototypes/boot-record-v2/installer_build_b14.py) |
| Combined kit | [recovery-kit.bin](../BUILD/pr04-b14-recovery-kit-r3/payload/recovery-kit.bin) | [build_recovery_kit.py](../prototypes/boot-record-v2/build_recovery_kit.py), [menu source](../prototypes/boot-record-v2/recovery-kit-menu.inc) |
| Separate MON restore kit | [mon-kit.bin](../BUILD/pr04-b14-mon-absent-r5/payload/mon-kit.bin) | [build_mon_absent.py](../prototypes/boot-record-v2/build_mon_absent.py) |

The F BIN is a component artifact, not an instruction to overwrite a board's
F sector. The current guide's CONFIG workflow changes RAM and boot settings;
it does not upgrade firmware. A board firmware migration needs its own
fresh capture and admitted preserving plan.

From the repository root, with Python, WDC assembler/linker and the existing
frozen b14/model dependencies available, reproduce extended CONFIG using
fresh output directories:

```text
python -B prototypes/boot-record-v2/build_ram_config_b14.py --out BUILD/my-b14-config
python -B prototypes/boot-record-v2/test_ram_config_b14.py --build BUILD/my-b14-config --cpu 65c02
python -B prototypes/boot-record-v2/test_ram_config_b14.py --build BUILD/my-b14-config --cpu 65c816-e
python -B prototypes/boot-record-v2/build_ram_config_b14.py --out BUILD/my-b14-config-repro
python -B prototypes/boot-record-v2/qualify_ram_config_b14.py --build BUILD/my-b14-config --repro BUILD/my-b14-config-repro
```

The builder defaults to frozen `BUILD/pr04-b14-raw-r4`, copies its matching
services and rebuilds only the RAM CONFIG app. These commands perform no
serial/board operation. They do not register a fresh hardware test.

For implementation archaeology, the
[prototype README](../prototypes/boot-record-v2/README.md) preserves the dated
build history. Earlier sections describe earlier protocols and capacities;
use this guide for the consolidated current b14 operation. Published RC1
operation remains in the [RC1 manual index](rc1/README.md).
