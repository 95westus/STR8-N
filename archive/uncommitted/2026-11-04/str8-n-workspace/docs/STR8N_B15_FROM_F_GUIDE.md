# STR8-N b15: build the system from F alone

The next [b16 journal direction](STR8N_B16_MESSAGE_JOURNAL_PLAN.md) uses a
persistent reservation from optional EDU SPI SRAM's WORK area, preserving the
formatted program area and the separate flash boot journal. It remains planned.

**Unified source/build:** The 2609 F-up work and 2512 FLASH work now share
[one STR8N-F codebase](../bootstrap-opaque/docs/UNIFIED_SYSTEM.md). Use its
common CONFIG/tool BINs and board profiles for ongoing development. The dated
board-specific paths below remain the exact evidence for those hardware steps.

This operator guide starts with **only the 4096-byte F bootstrap installed**.
The walkthrough then creates the journals, installs MON A/B, configures boot
settings, and installs opaque images using RAM tools, one component at a time.
Each tested piece becomes a chapter with its files, commands, expected output
and verification. Direct BIN programming and factory-WDC RAM migration are
alternative ways to reach the same F-only starting point.

For a user-facing tour before installation details, start with the
[F demonstration and installation routes](STR8N_B15_USER_DEMO_AND_INSTALL_ROUTES.md).
The 485-byte `b15-F-DEMO-RAM.bin` demonstrates F services without requiring the
journals, MONs or extension. It has now run over USB on 2609; all flash and
settings were preserved. The same document distinguishes the existing combined
C/D+MON installer from the proposed full-core/VX1 RAM and programmer images.

**Current checkpoint — October 27, 2026:** 2609 has b15 F, C/D journals,
VX1 E, ES1 EDU/SRAM B3:8 and matching MON A/B installed. `VERSION`, `CAPS` and the 224-byte INFO
record passed from both MONs over USB; each returned through `J3`/`S` to recovery.
Independent double reads of every bank before installation and after both MON
query checks confirmed the planned result. B0, unrelated sectors and saved
configuration were preserved during those installation checks. The later CONFIG
A/S exercise is now hardware-verified; F returned to `REC>` with restored S.
The port is closed. Tracked counts are A=51, B=54,
C=78, D=47, E=43 and F=30. ES1 installation recorded B3:8 26→27; all other
counts and unknown prior lifetime are retained. Latest journal is C800, seq1023,
default S and bank mask 00.
ACIA is **not board-tested**. Opaque-image installation has not yet been exercised
in this F-up walkthrough. Existing references are in the
[b14/b15 reference](STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md).

The matching `2609-CONFIG-RAM.bin` passed 31 offline groups and two byte-identical
builds, then ran on 2609 for USB inspection only. `?`, bare `B`, bare `C` and `W`
matched the qualified output; `Q` returned to recovery. Independent loaded-RAM
and complete flash checks passed. No saved setting or wear-history change occurred.

The MON-A-default / restore-S exercise ran from the ES1 seq1021 checkpoint:
C700/seq1022 saved A, then C800/seq1023 restored S.
It passed 25 offline groups, 602 interrupted-write prefixes and 730 retained
SRAM/no-SPI checks before the USB hardware run. Both saves returned OK and their
defaults booted on countdown expiry without an override key. Three complete SRAM
reads matched both original backups; all flash was read twice before and twice
after. All counts, including B3:8=27, and banks00 are retained. Both old prepared
plans are now consumed: use a fresh seq1023 admission for later writes.

The first **read-only RAM MAINT** is also prepared: `2609-MAINT-RO-RAM.bin`,
3,591 bytes, 33 offline groups and an identical rebuild. It supports map,
read-to-buffer/display, compare, CRC and Q with no linked writer. It has not
been uploaded; all hardware checkpoints and saved state above remain unchanged.

The optional [EDU/SRAM read-only first stage](STR8N_B15_EDU_SRAM_ONBOARDING.md)
now has a verified B3:8 provider installed by its matching guarded RAM installer.
All four BINs reproduce; 48 offline groups passed. Two original 131072-byte
SRAM backups, a fresh pre-install read and two reads through the installed
provider all match byte for byte, mode 40, SHA-256
`56cd2490028e7c6b4ee07fb26c87ea75d9d665f10c6406263c0c0f4000116a9e`.
The client code and all flash passed independent readbacks. Only B3:8 and its
C600 wear reservation changed. It returned to REC and stopped before saved
configuration changes. Named SRAM storage, WORK and saved EDU activation remain
later porting work; old counts/B0 are retained, with the one recorded B3:8 erase.

[2609 F-only hardware receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step03-F-only-install/receipt.md).
[2609 C/D journal hardware receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step05-journal-init-r3/receipt.md).
[2609 MON A/B hardware receipt and console log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step07-MON-install-r2/receipt.md).
[2609 VERSION/CAPS hardware receipt and console log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/receipt.md).
[2609 b15 RAM CONFIG preparation receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/receipt.md).
[2609 RAM CONFIG hardware inspection and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/receipt.md).
[2609 CONFIG save/restore preparation](../output/qualification/2609-b15-onboarding-20261027T212009Z/step12-CONFIG-exercise-ready/receipt.md).
[2609 F user demonstration](../output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-live/receipt.md).
[2609 RAM MAINT RO preparation](../output/qualification/2609-b15-onboarding-20261027T212009Z/step14-MAINT-RO-ready/receipt.md).
[2609 EDU/SRAM preparation](../output/qualification/2609-b15-onboarding-20261027T212009Z/step15-EDU-SRAM-ready/receipt.md).
[2609 RAM-only EDU/SRAM hardware backup and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step16-EDU-SRAM-preflight-live/receipt.md).
[2609 EDU/SRAM installation, preservation audit and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step17-EDU-SRAM-install/receipt.md).
[2609 refreshed CONFIG exercise from seq1021](../output/qualification/2609-b15-onboarding-20261027T212009Z/step18-CONFIG-exercise-seq1021-ready/receipt.md).
[2609 CONFIG A/S hardware receipt and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/receipt.md).
[STR8-N/F release scope and remaining gates](STR8N_F_RELEASE_PLAN.md).

## Walkthrough sequence

| Chapter | Starting state | Work and evidence |
|---|---|---|
| 1. F up | Only F installed | Reset to recovery; check console, Ctrl-C and a small RAM tool |
| 2. Journals | F plus RAM tools | Establish the C/D journal with saved configuration and tracked wear; verify admission and persistence |
| 3. MON A/B | F and valid journals | Install and verify matching MON images separately; test selection and return paths |
| 4. System configuration | F, journals and the selected tools | Set console, enabled banks, entries and boot default; verify saved state after reset |
| Optional EDU/SRAM | Core and matching tools admitted; S and banks disabled during inspection | RAM-only preflight, two retained-array backups, separately authorized B3:8 install, independent flash/SRAM verification; no format |
| 5. Opaque-image installer lesson | Known sector contents, valid journal and matching OIP1 RAM/host tools | Back up an admitted span; install/read back/launch/restore a probe; retain newer wear history; then install owner images |
| 6. b15 features and MAINT | The matching tools/components required by each feature | Worked recovery, raw loading, CONFIG, wear and MON; MAINT map/read/compare/CRC/buffer work before admitted flash edits |
| 7. B1 application selector | Verified language images and entries | OSI BASIC, fig-FORTH and two reserved slots; assign layout after sizes and entry requirements are checked |

On board 2609, B0 remains the original WDCMONV2 backup. B1 is the intended
selector image. No image placement or later component was installed by the
F-only operation.

## 1. F up

### Console qualification

Use USB/FT245 for this 2609 walkthrough. **ACIA code is model-tested only;
it is not assumed board-tested.** A BOTH-mode USB transcript does not qualify
the ACIA port, wiring, baud timing or receive behavior. Listing C2/C3 below
describes implemented commands, not ACIA hardware acceptance.

### Two ways to reach the same starting point

| Route | Input | Only flash destination |
|---|---|---|
| Direct F programming | `b15-F-4096.bin`, exactly 4096 bytes | B3:`$F000–$FFFF` |
| Factory WDC and RAM migrator | Project RAM S19 at `$2000–$3FFF`, entry `$3700`, followed by one 4096-byte transfer | B3:`$F000–$FFFF` |

Both routes use identical F bytes. No MON, journal, provider, language or
selector sector comes across. All other flash bytes are preserved by the
factory migration. On 2609 this includes the original WDC copy in B0.

For a complete 128 KiB chip image ordered B0/B1/B2/B3, B3:F starts at file
offset `$1F000`; a programmer's addressing convention must be checked before
using that offset. The F BIN is a flash image, not a RAM application to run at
`$0200`.

The factory RAM migrator normalizes original 65C816 native/emulation entry,
checks its loaded code and transfer tables, and checks all four source banks
before its one F erase. The tested WDC loader reads back the RAM image before
EXEC. It does not initialize C/D. The planned F erase is tracked in host
metadata until the later journal chapter.

Files used for the separately authorized F-only hardware step:

- [4096-byte F BIN](../output/qualification/2609-b15-onboarding-20261027T212009Z/step02-F-only-ready/b15-F-4096.bin)
- [Factory-WDC RAM migrator S19](../output/qualification/2609-b15-onboarding-20261027T212009Z/step02-F-only-ready/installer-model-only.s19)
- [Preparation and test receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step02-F-only-ready/receipt.md)

F SHA-256:
`1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8`.

There are 44 fresh offline groups: 22 installer/refusal groups and 22 F-up
groups. Each successful native/emulation migration checked 3,629 NOR mutation
prefixes for preservation of every non-F byte. A second build reproduced the
installer and transfer byte for byte. This is CPU/NOR and simulated-transport
evidence. The subsequent authorized 2609 hardware step used those exact bytes
and stopped at the first USB `REC>`. It does not extend the offline Ctrl-C
or RAM-app tests to this board, qualify ACIA, or install any later component.

### Expected F-only boot

After the separately performed F write and physical RESET, the expected
result is the startup chooser followed by **`REC>`**. No compatible MON or
SNBT journal has been installed in this chapter. Unavailable A/B or bank
selections return to recovery.

| Context | Input | Meaning |
|---|---|---|
| Startup chooser | `S` without Enter | Enter recovery |
| Recovery `REC>` | `?` then Enter | Help |
| Recovery `REC>` | `C1` / `C2` / `C3` then Enter | USB / ACIA / BOTH text consoles |
| Recovery `REC>` | `L` then Enter | Receive a raw RAM-tool BIN at `$0200` |
| `SEND BIN`, before the first payload byte | Ctrl-C | Cancel without writing or executing the tool |

Send the RAM-tool file as binary, without text conversion or added line
endings. The first-byte wait is indefinite. Once reception starts,
approximately three seconds of idle ends the transfer and runs `$0200`.
Ctrl-C after the first payload byte is literal data. Raw L has no framing
CRC, length or authentication; tools may check themselves after entry.

F installs its RAM console at the `RA` descriptor at `$7E60`. In F-only mode,
RAM tools return through **RESET `$7E64`**, which selects B3 and restarts F.
**HOLD `$7E67` resumes the active MON** and is not an F-only return path.
The new tests retained that distinction and verified an eight-byte RAM app
using the console and RESET on both starting routes. The b15 F bytes were not
modified.

## 2. Create the journals from F

### Wear-counter starting policy

For a factory WDC board with no trustworthy erase history, mark prior lifetime
wear **unknown** and count observed migration/maintenance erases. Do not seed
an invented flat number. Zero means no tracked erase yet, not an unused
sector; one means one tracked erase, not one lifetime erase. A factory F-only
conversion adds one tracked F erase. Later C/D initialization counts its own
actual erase attempts, and the unknown-history indication remains present.

For a board with verified owner-local history, retain every recorded count
and its lower-bound/unknown-lifetime meaning. On 2609 the saved F count is 29;
the authorized F-only operation retained the next count, 30, in the host
history after device verification. It did not initialize or modify C/D.

This is a separate later operation. The F-only stage works without changing
C/D. Untouched factory bytes in those sectors are not a blank journal.
The existing CONFIG `I` command is blank-only initialization; it does not
convert vendor code or repair a damaged journal.

### 2609 RAM initializer — hardware verified; stopped at REC

The new [RAM initializer](../prototypes/boot-record-v2/ram-journal-init-2609.asm)
is bound to 2609's device-verified F-only postimages and owner wear history.
It can convert the exact remaining vendor bytes in C/D; ordinary CONFIG `I`
cannot. Its [preparation receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step04-journal-init-ready/receipt.md)
contains the payload hash and 32 offline checks. The separately authorized
[hardware run](../output/qualification/2609-b15-onboarding-20261027T212009Z/step05-journal-init-r3/receipt.md)
completed initialization, additional device `V`, and independent double reads
of every flash bank. Both journal CRCs and commit bytes are valid. The final
F software restart reached `REC>`; no command followed it. **MON A/B were not
installed. Do not replay this original preimage-bound initializer on 2609 now.**

| Item | Before initialization | Verified after initialization |
|---|---:|---:|
| B3:C tracked erase count | 77 | 78 |
| B3:D tracked erase count | 46 | 47 |
| B3:F tracked erase count | 30 | 30 |
| Other 30 tracked counters | Preserved | Unchanged |
| Prior lifetime unknown mask | `FFFFFFFF` | `FFFFFFFF` |
| B0 WDCMONV2 backup | Preserved | Unchanged |

Both counts are reserved before D is erased. D is programmed and verified,
with its commit byte written last. The entire 4096-byte sector is verified
before C is erased. The D record already carries C's reserved count. C is
then erased, programmed, committed last and fully verified. The committed
snapshots use sequence 1014 in D and 1015 in C, recovery default `S`, no enabled
opaque banks, and b15 generation `8000000F`. The original 16-byte legacy
configuration body is retained unchanged for later configuration work.

The first journal erase has no earlier onboard SNBT record. This run retained
a durable host reservation and serial/progress log before confirmation. Both
erases were subsequently verified, and a new host wear-history file was
published; the previous file remains intact. For a future first initialization,
retain the same host reservation and log. If stopped early, reserved counts can
exceed completed erases. Reconcile that log and inspect changed sectors before
planning recovery. This original tool refuses changed preimages and does not
retry.

The initializer checks its own loaded bytes, the exact resident b15 RAM
routines, and all four banks before admitting a write. It repeats those
checks after confirmation. Each check prints progress. It uses USB only;
ACIA hardware is unqualified. F reads the SNBT boot-choice header, not the
legacy console byte in the body; returning to F keeps F's existing reset
console behavior.

**Initializer procedure for the first, correctly bound use:** the 2609 live
flow used `W`, `I`, `INIT C/D`, `V`, `Q`. The read-only preflight `V` option is
also available before `I`. This is a record of the procedure, not an instruction
to initialize 2609 again.

| Prompt/state | Input or file | Expected result |
|---|---|---|
| USB `REC>` | `C1` then Enter | Use USB for this runtime session |
| USB `REC>` | `L` then Enter | `SEND BIN` |
| `SEND BIN` | Send [2609-journal-init-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step04-journal-init-ready/2609-journal-init-RAM.bin) as binary | Load/entry `$0200`; about three seconds idle starts it |
| Initializer startup | Wait | RAM checks, `B0 OK` through `B3 OK`, then `RAM JINIT ? V W I Q>` |
| RAM menu | `W` then Enter | Display all imported counters and proposed reservations; no erase |
| RAM menu | `V` then Enter | Repeat read-only preflight; no erase |
| RAM menu, after owner authorization | `I` then Enter | Confirmation prompt; no erase yet |
| Confirmation | `INIT C/D` then Enter | Recheck inputs, then D erase/program/commit/verify, followed by C |
| After `C/D VERIFIED` | `V` then Enter | Verify exact C/D postimages |
| RAM menu | `Q` then Enter | Restart F and return to `REC>` |

This BIN is a RAM application, **not a 4096-byte sector image or an S19 text
file**. No MON or other flash image is included. Ctrl-C or a wrong confirmation
refuses initialization. A preflight or programming failure halts in RAM and
requires inspection. No command silently erases on load. This hardware run
captured the actual attempts, verified readback and a powered-on F software
restart. It did not perform a physical power-cycle test.

For independent verification, the live wrapper used a separately CPU-tested
[RAM readback service](../output/qualification/2609-b15-onboarding-20261027T212009Z/step05-readback-tools-r1/payload/readback-RAM.bin)
before and after initialization. It read each of the four banks twice, with
binary CRCs, and read its own loaded RAM prefix back. Its admitted binary
commands were `F` plus a bank byte 0–3, `M` for RAM readback, and `J` to restart
F. No flash writer exists in this service; no RAM-restoration command was used.
The [independent audit](../output/qualification/2609-b15-onboarding-20261027T212009Z/step05-journal-init-r3/audit.json)
binds those serial frames to the archived bank images and checks the entire TX
sequence, including the absence of commands after the final `REC>`.

### Could the journals use D/E instead?

The installed F fixes journal scanning at `$C000` through `$DFFF`; E remains
an ordinary opaque-image sector in this map. D/E is a possible future layout,
but requires a coordinated F rebuild plus updates to readers, writers,
protected-sector checks, bank-entry checks and documentation. Changing only
this initializer would leave F scanning the wrong pair and would conflict
with E's current role. This prepared initializer follows the installed C/D
contract and does not relocate any sector. The optional EDU/SPISRAM journal
idea is recorded separately in the
[future ABI/storage roadmap](STR8N_V2_1_ABI_METADATA_ROADMAP.md); retention,
startup access and absence/failure recovery need a defined contract first.

## 3. Install MON A and MON B from F

**Hardware checkpoint:** `2609-MON-AB-RAM.bin` has now run on 2609 from the
verified F+C/D state. MON A and B were installed, independently read back and
started over USB; both returned to recovery. Work stopped at the final `REC>`
before saved-configuration changes. The combined C/D+MON BIN remains offline
only. The two RAM installers passed **55 offline groups/checks** before this
separate hardware run, including both CPU models, MON entry/return,
corruption/failure/interruption cases and independent identical rebuilds.

The [full annotated console log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step07-MON-install-r2/console-log.txt)
names every uploaded file and captures all text replies. The
[hardware receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step07-MON-install-r2/receipt.md)
links exact readbacks, both MON banners, the final REC capture and the audit.
Neither original preimage-bound installer should be replayed on the current
F+C/D+MON board; both source states have changed.

Both use the exact qualified b15 MON A/B components, PR04 contract and generation
`8000000F`. MON is not required for F recovery or raw RAM-tool loading. These
are per-board, exact-preimage RAM applications; the BINs are not sector images
and must not be flashed at `$F000`, `$A000` or `$B000` directly. Source images,
wear history and the B0 backup remain verification inputs.

| Prepared RAM BIN | Required source | Journal work | MON work |
|---|---|---|---|
| [2609-MON-AB-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step06-MON-ready/2609-MON-AB-RAM.bin) | Archived, verified 2609 F+C/D starting checkpoint | Append full-CRC reservations at C100 and C200; no C/D erase | Erase/program/verify A, then B; hardware completed |
| [2609-CD-MON-AB-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step06-MON-ready/2609-CD-MON-AB-RAM.bin) | Archived 2609 F-only state, C/D still vendor bytes | Initialize D then C; append the same A/B reservations | Erase/program/verify A, then B |

The MON-only hardware run started with A=49, B=52, C=78, D=47 and F=30. Before
A erase it committed sequence 1016 at C100 with A=50. Before B erase it
committed sequence 1017 at C200 with B=53. Existing C000/D000 snapshots remain
byte-identical.
The two journal appends do not increment C/D erase counts. All other 30
counters, including C=78/D=47/F=30, retain their values and their unknown prior
lifetime meaning.

The combined route starts with the archived F-only history C=77/D=46/F=30. It
counts its D and C erases, then performs those same A/B reservations and writes.
Both routes produce identical final flash banks and counts: A=50, B=53, C=78,
D=47 and F=30, with the other counts preserved. The combined BIN **refuses the
later F+C/D and F+C/D+MON states** rather than erasing established history.
It must not be replayed there. A generic factory-board workflow must bind that
board's actual preimages and unknown/tracked wear, not copy 2609's history.

Only A/B and the required C/D journal bytes are in these transactions. B0–B2
and B3:8/9/E/F stay byte-identical. The B0 original WDC backup stays intact.
The final default remains `S` recovery, with no enabled opaque banks, unchanged
legacy configuration body and the unknown-history mask `FFFFFFFF`. Installing
MON does not select a new automatic boot target.

The live run used the following procedure; a future operation needs a fresh
plan bound to its actual starting state. Retain source reads and a durable host wear
reservation/attempt log. At USB `REC>`, use `C1` Enter, then `L` Enter, then send
the selected BIN unchanged in binary mode. After the three-second idle and
preflight checks, the prompt is `RAM MINSTALL ? V W I Q> `. `W` displays imported
and proposed counts; `V` checks the entire RAM program, resident b15 ABI and all
four source banks. Neither command erases flash.

`I` Enter requests confirmation: **`INSTALL MON`** Enter for MON-only or
**`INSTALL CD MON`** Enter for combined. Confirmation triggers another complete
preflight before any action. Each action prints its destination and progress;
its commit marker is written only after all other bytes match. MON commit
offset is 31; journal commit offset is 255. Entire actions are read back after
commit, then all four final banks are checked. `V` repeats that final check;
`Q` restarts F to `REC>`. A failure halts in RAM and requires inspection and a
new recovery plan; no automatic retry resets or guesses wear counts.

The [preparation receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step06-MON-ready/receipt.md)
contains both BIN hashes and qualification results. Successful CPU runs checked
8,156 MON-only and 8,460 combined NOR mutation prefixes per CPU for preservation
of protected bytes. Twelve MON-only and seventeen combined changed states booted
to recovery and refused blind replay. A simulated B erase failure retained a
valid committed A, and a reservation-write timeout stopped before any MON erase.
These are model results; no electrical power interruption was tested. The
[offline planner](../prototypes/boot-record-v2/prepare_mon_install_2609.py) has
no live execution path. An exact-F-bound b14 tool needs a matching b15 build;
shared entry addresses alone do not establish compatibility. ACIA remains
not board-tested; the separate MON-only hardware run qualified USB only.

The actual USB launch checks used `A` Enter and `B` Enter from recovery. Each
printed `STR8-N 2.0proto b15 B3 65C816`. Read-only `D 7D30 7D30` returned A0 for
MON A and B0 for MON B; these are B3 monitor pages, not a write to backup bank
B0. `D 7D00 7D02` returned `03 16 03` on each. `J3` Enter followed by `S`
returned each to F recovery. No saved-configuration writer was used. The RAM
readback service then read all four banks twice again, matching the exact
planned postimages, including the unchanged configuration and wear records.
A final service `J` restarted F to `REC>`; the audit verified no later TX.

### VERSION/CAPS extension hardware step

After the MON-only checkpoint, the
[minimal VERSION/capability candidate](STR8N_B15_VERSION_CAPS_CANDIDATE.md)
and matching MON hooks passed 52 offline groups/checks, then ran on 2609 by
separate owner authorization. The exact-source `2609-VERSION-CAPS-RAM.bin`
(15,480 bytes) embeds `version-caps-e000.bin`, `monitor-a0-version-caps.bin`
and `monitor-b0-version-caps.bin`, each 4096 bytes. F is unchanged; no permanent
RAM is added. The old provider/debugger paths remain disabled. The separate
`version-caps-query-RAM.bin` client remains model-tested only.

This is a one-time installer for the archived F+C/D+MON source state, not a
generic updater. First read all four banks twice with `readback-RAM.bin` and
match the bound source images. In F recovery, send `C1` Enter, then `L` Enter;
after `SEND BIN`, send the exact RAM BIN as raw bytes to `$0200`. At
`RAM MINSTALL ? V W I Q>`, `W` Enter displays imported and planned wear. Save
the host reservation before `I` Enter and the exact confirmation
`INSTALL VERSION` Enter. The actual console then verified:

```text
C300  journal reservation E, sequence 1018
E000  erase/program/verify VX1; commit last
C400  journal reservation A, sequence 1019
A000  erase/program/verify MON A; commit last
C500  journal reservation B, sequence 1020
B000  erase/program/verify MON B; commit last
ALL COMPONENTS VERIFIED; default S recovery; B0 and F preserved
```

The address descriptions above annotate the actual six-action order. `V` Enter
independently reported B0–B3 OK; `Q` Enter restarted F to `REC>`. E went
42→43, A 50→51 and B 53→54. C=78, D=47, F=30 and every other count were retained;
there was no C/D erase. C000/C100/C200/D000 stayed byte-identical.

From `REC>`, the exact MON A check used these keystrokes:

```text
C1<Enter>
A<Enter>
D 7D30 7D30<Enter>      ; A0 identifies the running MON page
D 7D00 7D02<Enter>      ; 03 16 03 identifies B3 / 65C816 / USB
VERSION<Enter>
CAPS<Enter>
D 6700 67DF<Enter>      ; read the 224-byte INFO record
J3<Enter>
S                      ; one key at the boot choices, no Enter
```

Repeat with `B` Enter in place of `A` Enter; the active page is then B0.
`VERSION` prints F and both MON release/generation/build identities and
`Running MON: A` or `B`. Both `CAPS` replies were exactly:

```text
VX1 INFO=01/224; legacy CAPS=01/17; CPU=16
```

Comments and `<Enter>` notation explain the keystrokes; do not transmit them.
Both output captures matched the qualified fixtures; both INFO records matched
the installed build identities. After both returns to recovery, the RAM readback
service read all four banks twice again and verified every expected byte,
including B0, unchanged configuration and all 32 counts. Its final `J` reached
`REC>`; the raw serial audit verified no later TX. Port and shared lease are idle.

Actual evidence: [full annotated console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/console-log.txt),
[MON A VERSION](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-A-VERSION.txt),
[MON A CAPS](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-A-CAPS.txt),
[MON B VERSION](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-B-VERSION.txt),
[MON B CAPS](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-B-CAPS.txt),
[audit](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/audit.json).

## 4–6. Configuration, opaque images and b15 features

### Matching RAM CONFIG

File: [2609-CONFIG-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/2609-CONFIG-RAM.bin),
**2,728 bytes**, load/entry `$0200`, end exclusive `$0CA8`. It links the exact
installed b15 F symbols and guarded journal engine. The previous extended b14
CONFIG BIN is not the admitted artifact for this step. The package contains
the CONFIG RAM app and evidence; it installs no flash sector or other component.

The [qualification](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/qualification.json)
records 31 offline groups, two identical builds and 1,864 interrupted-write
prefixes. Tests cover both CPUs and modeled USB/ACIA; this does not qualify
ACIA hardware. Captured 2609 banks were used for read-only inspection, default
S and disabled-bank checks, all 32 counts, MON A/B generation pinning and
disposable-model settings/rollover tests. Actual B0, journals, wear history,
default S and disabled banks remain unchanged. Preparation opened no serial port;
the separately authorized hardware inspection below confirms the same baseline.

CONFIG inspection belongs here, after verified journals/MON/VERSION and before
application installation. Final bank enables, entries and B1 default belong
after each application and selector have been installed and manually verified.

The inspection-only keystrokes, subsequently exercised on 2609 over USB, are:

```text
REC> C1<Enter>
REC> L<Enter>
SEND BIN
[send the exact 2609-CONFIG-RAM.bin as raw bytes; wait for idle autorun]
RAM CONFIG ? B C I W Q> ?<Enter>
RAM CONFIG ? B C I W Q> B<Enter>
RAM CONFIG ? B C I W Q> C<Enter>
RAM CONFIG ? B C I W Q> W<Enter>
RAM CONFIG ? B C I W Q> Q<Enter>
REC>
```

Prompts and bracketed instructions are explanatory; transmit only the commands
and BIN. Expected settings are `DEFAULT=S` and B0–B3 `OFF ENTRY=8000`.
`W` prints six-digit hexadecimal counts and `UNKNOWN HISTORY`.
[Simulated 65C816 USB capture](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/simulated-inspection-65c816-e-port1.txt)
and [help text](../output/qualification/2609-b15-onboarding-20261027T212009Z/step10-CONFIG-ready/CONFIG-help.txt)
are preparation evidence, not a new board console log.

**Stop before saved-setting writes:** bare `B`, bare `C` and `W` display state.
`B bank entry` and `C target` save immediately; even `C S` writes a new snapshot
when S is already selected. `I` is blank-only initialization and is refused on
2609's current journals. Do not use it to import or reset wear counts. There is
no draft/Save menu or general disable command. Recovery `C1` selects USB for
the current session; this CONFIG does not edit persistent console/RTC settings.

The app's exact b15 match is established by its build/admission hashes; it has
no on-device cryptographic F check. Raw L remains an unverified transfer.
The hardware inspection checked the executed app and current journal; it exercised
no settings writer. Saved-setting changes and application-bank enablement remain
later, separately directed steps.

**Hardware inspection passed:** the actual `?`, bare `B`, bare `C` and `W`
replies matched the qualified bytes. Both B/C displays reported `DEFAULT=S`,
B0–B3 `OFF ENTRY=8000`. W reported every current count and `UNKNOWN HISTORY`.
`Q` restarted F to `REC>`. Unchanged MON A then supplied read-only
`D 0200 0CA7`; the 2,728-byte RAM image matched the qualified BIN except its
expected private CONFIG_ROW display counter, 0→4. J3/S returned to recovery.

`readback-RAM.bin` read every bank twice before CONFIG and twice after inspection
and the RAM check. All 128 KiB were byte-identical, including every journal page;
sequence stayed 1020 at that inspection, default S, bank mask 00 and all 32
wear counts unchanged. The later ES1 install advances the current checkpoint
to seq1021 with only B3:8 incremented.
The original host history file was retained byte-for-byte. A final service `J`
reached `REC>`; the complete raw TX audit verified no later command and no saved
setting or flash-write command anywhere in the run. Port and lease are idle.

Actual console evidence: [requested CONFIG output](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/CONFIG-inspection-console.txt),
[? help](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/CONFIG-help.txt),
[bare B](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/CONFIG-B.txt),
[bare C](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/CONFIG-C.txt),
[W](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/CONFIG-W.txt),
[full annotated log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/console-log.txt),
[audit](../output/qualification/2609-b15-onboarding-20261027T212009Z/step11-CONFIG-inspection/audit.json).
Help's settings examples were printed only; they were not executed.

### CONFIG save/restore exercise: USB hardware verified

The [current seq1021 procedure and proof](../output/qualification/2609-b15-onboarding-20261027T212009Z/step18-CONFIG-exercise-seq1021-ready/receipt.md)
reuse the unchanged, hardware-inspected 2728-byte `2609-CONFIG-RAM.bin`.
That preparation was followed by the separately authorized
[hardware exercise](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/receipt.md).
Its [complete console log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/console-log.txt)
records both saved-setting commands and their verification.

| Stage | Executed CONFIG command | Journal result | Default | Bank mask |
|---|---|---|---|---|
| Starting ES1 checkpoint | Inspection only | C600 / seq1021 | S | 00 |
| Temporary MON default | `C A` Enter | Append C700 / seq1022, pin generation 8000000F | A | 00 |
| Restore recovery | `C S` Enter | Append C800 / seq1023 | S | 00 |

Both rows append without sector erase. All 32 counts, including B3:8=27, the
unknown mask FFFFFFFF, original B0, ES1 B3:8, VX1 E, MONs/F and retained SRAM
are preserved. The models use the actual 131072-byte SRAM backup and assert
no SPI access on observed CONFIG/reset/record-reader paths. Both CPUs and
modeled USB/ACIA passed; ACIA is still not physically qualified.

The live exercise first admitted the exact source using two full-bank reads and
a fresh 131072-byte SRAM read against both backups. Each CONFIG RAM upload was
independently verified with MON D/G before a save. `C A` returned OK; Q booted A
on countdown expiry without an A key. C700–C7FF matched the planned row, and the
active MON page was A0. J3/single S reached REC while A remained saved. After the
second verified RAM load, `C S` returned OK and Q reached REC without an S key.
Two complete post-exercise SRAM reads matched both original backups in mode40.
Two final full-bank reads matched exactly the two planned appends; every other
flash byte, all 32 counts and the unknown-history mask were retained. No erase
occurred. Final state is C800/seq1023, S, banks00; the port is closed at REC.

If interrupted, inspect the latest committed row and dirty pages; prepare only
the required restore and skip a torn page. Do not append C S when S is already
committed. This exercise is complete; neither its source plan nor C A/C S should
be replayed blindly. Preserve current history rather than restoring an old C/D image.
The receipt contains the exact commands, expected images and recovery limits.

#### Archived exercise from seq1020

The following old table/procedure is historical. C600 is already occupied by
the ES1 wear reservation. The later seq1021 plan has also been consumed; current
saved state is seq1023 and later work requires a fresh admission.

The [exercise receipt and operator procedure](../output/qualification/2609-b15-onboarding-20261027T212009Z/step12-CONFIG-exercise-ready/receipt.md)
reuse the exact, hardware-inspected **`2609-CONFIG-RAM.bin`**, 2,728 bytes.
No new CONFIG or firmware bytes were built. The source is the complete,
double-read 2609 bank set from the completed USB inspection.

| Stage | Prospective CONFIG save | Journal result | Default | Bank mask |
|---|---|---|---|---|
| Archived starting board | None | Latest C500 / sequence 1020 | S | 00 |
| Temporary monitor default | `C A` Enter | Append C600 / sequence 1021; pin MON A generation 8000000F | A | 00 |
| Restore recovery default | `C S` Enter | Append C700 / sequence 1022 | S | 00 |

The normal exercise appends two verified, commit-last rows and erases no sector.
All 32 tracked erase counts, unknown-lifetime mask, legacy settings and bank
entries remain unchanged in the modeled result. B0 and every non-journal sector
are preserved. Restoring S restores the boot policy through a **new append**;
it does not copy an older C/D image over newer sequence/wear history.

Before either prospective save, the modeled procedure checks the entire loaded
CONFIG image with MON A `D 0200 0CA7`, allowing only the expected CONFIG_ROW=4
display counter. MON `G 0200` re-enters that verified RAM copy without another
unverified raw transfer. This D/G path is newly exercised in models here; no
physical G-to-CONFIG or settings-write trial is claimed.

After saving A, `Q` must let the saved default boot MON A without an A keypress.
Read `D 7D30 7D30` to verify active page A0, then `D C600 C6FF` to independently
verify the exact seq1021 row, CRCs, commit and disabled banks. `J3` Enter / `S`
reaches recovery manually while the **saved** default stays A. Reload CONFIG,
inspect with bare C, use Q to return to saved MON A, and repeat the RAM D/G
check before the prospective `C S`. Its Q must reach REC automatically on
countdown expiry. A future hardware exercise must double-read all banks again
and match only the two planned journal appends before recording completion.

[23-group qualification](../output/qualification/2609-b15-onboarding-20261027T212009Z/step12-CONFIG-exercise-ready/qualification.json)
covers both CPUs and modeled USB/ACIA, exact save/restore postimages and automatic
boots, all 604 observed append-mutation prefixes, inspected torn-page restoration,
invalid MON refusal and unavailable-A recovery. A second preparation reproduced
every planned bank/row byte. These are offline results; ACIA/electrical power
loss remain unqualified. [Simulated USB walkthrough](../output/qualification/2609-b15-onboarding-20261027T212009Z/step12-CONFIG-exercise-ready/simulated-walkthrough-65c816-e-port1.txt).

Stop here before saved-setting writes. If interrupted during a later authorized
exercise, inspect the current committed journal and create a recovery plan;
do not replay the original preimage blindly. Select S manually to reach recovery
while A is saved. If S is already restored, do not append another C S. Preserve
the original host history; only a subsequently verified live exercise may add
a new host record at sequence 1022 with the same counts.

These chapters will use the tested earlier stages. Existing CONFIG commands
include `B`/`C` to display state, `B bank entry` to enable and set an entry,
`C target` to save a default, `W` for wear and `Q` to restart F. The public
CONFIG has no disable command. Installing an image and selecting its boot
entry are separate operations.

The required next application-installation lesson is the
[OIP1 opaque-image installer flow](STR8N_B15_USER_DEMO_AND_INSTALL_ROUTES.md#required-opaque-image-installer-lesson):
image manifest and explicit target selection, backup, matching b15 RAM/host
tool admission, wear reservation, install/readback, reviewed launch/return,
and restoration of the target bytes while retaining updated wear history.
No target is assigned or written by documenting this step. On 2609 preserve
B0 and installed VX1 E in addition to fixed F/MON/journal protections.

Before an enable/entry/default exercise, prepare a full policy restoration
path: the current CLI has no general bank-disable command. Restoring default
S alone does not clear a bank's enable bit. Keep banks disabled during the
disposable probe lesson unless a separately prepared restoration method exists.

Follow with the [MAINT options and demonstration](STR8N_B15_USER_DEMO_AND_INSTALL_ROUTES.md#maint-options-and-demonstration-order).
The read-only b15 candidate is now prepared and offline-tested. The fuller
old-system MAINT still needs additional porting for its write/edit/record paths.
Start with the candidate's map, reads, compare and CRC; it borrows buffer
`$5000–$5FFF` and contains no writer. RAM editing and application-sector writes/
erase remain later backed-up exercises, retaining all actual wear increments
and the protected B0/VX1/core. No live MAINT qualification is claimed yet.

Opaque images may span several 4096-byte sectors. The ordinary OIP1 writer
checks a header, payload and current preimage, reserves the erase and verifies
the result. This is separate from raw L, which only loads a RAM tool.

| Region | Current b15 role |
|---|---|
| B0/B1/B2:8–F | Ordinary opaque image/data targets; preserve the 2609 B0 backup |
| B3:8, 9, E | Ordinary opaque targets unless assigned to an optional service; installed E is VX1 and B3:8 is ES1 EDU/SRAM; preserve both |
| B3:A/B | Dedicated MON slots; protected by the ordinary opaque writer |
| B3:C/D | Dedicated journal sectors |
| B3:F | Fixed bootstrap/recovery |

The guide covers B3:8–E sector by sector, including the journal and MON setup
chapters. It does not treat the entire range as interchangeable image space.
On this 2609 checkpoint B3:E holds VX1; replacing E as opaque data removes
VERSION/CAPS availability. Preserve it while using this extension.
The optional [EDU/SRAM onboarding chapter](STR8N_B15_EDU_SRAM_ONBOARDING.md)
now has a hardware-verified read-only B3:8 provider and matching RAM clients.
It belongs after core/tool admission and before SRAM-backed application work.
Preserve B3:8 as a service-owned sector; B3:9 stays unchanged. Retained SRAM is
backed up and compared, never automatically formatted. C/D stay in flash.
Boot entries are `$8000–$E000` in `$1000` steps; B3 C/D entries are forbidden.
The boot record does not validate an opaque image's CPU, format or behavior.

The B1 selector, language placement and reserved slots remain a later chapter.
No addresses are assigned until the image sizes and entry/return contracts
have been checked.

## Optional starting route: original WDC backup

2609's B3 original WDCMONV2 was read twice and archived as BIN/S19. Two B0
reads matched it exactly; no new B0 programming was needed. Its SHA-256 is
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.
See the [backup receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step01-WDCMONV2-backup/receipt.md).

This backup/migration route is a way to reach F alone; it does not bring MON,
journals or other image sectors into the starting installation.

## Source and evidence

The [planner](../prototypes/boot-record-v2/wdc_b15_2609.py) exposes only offline
`prepare` and `verify`. Related source:
[RAM preflight](../prototypes/boot-record-v2/wdc-b15-guard.asm),
[installer tests](../prototypes/boot-record-v2/test_wdc_b15_2609.py),
[F-up tests](../prototypes/boot-record-v2/test_wdc_b15_F_only_boot.py),
[audit/packaging](../prototypes/boot-record-v2/qualify_wdc_b15_2609.py).

Private source/target bank images are verification escrow, not extra payloads.
The current plan has exactly one `transfer-00.bin`, equal to the F BIN. The
earlier five-sector preparation is marked superseded and is not used.

Interrupted F programming may require external recovery. Partial states
preserve B0 and refuse blind replay of the original preimage-bound plan; this
does not establish automatic power-loss recovery. The preparation/model work
accessed no board; the separate USB hardware step is documented above. No
post-REC commands or additional component installations were performed.
