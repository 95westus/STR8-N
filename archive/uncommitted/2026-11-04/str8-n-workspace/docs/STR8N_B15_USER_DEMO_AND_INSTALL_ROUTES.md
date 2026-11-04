# STR8-N b15: user demonstration and installation routes

Start by showing what the user can do with the 4096-byte F bootstrap. Then add
the durable settings, monitors, extension and application images in visible steps.
The staged tutorial and an optional combined installation should reach the same
documented system. Keep the demonstration separate from programming firmware.

## Demonstration 1: use F before installing the rest

`b15-F-DEMO-RAM.bin` is a **485-byte RAM application**, loaded at `$0200`.
It calls only F-supplied public services. It needs no C/D journal, MON A/B or E.
Eight model checks passed on 65C02 and 65C816 with those optional sectors absent
and with the existing 2609 contents; a second build reproduced the BIN exactly.

[Demo BIN](../output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-ready/b15-F-DEMO-RAM.bin) ·
[Model qualification](../output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-ready/qualification.json) ·
[2609 actual console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-live/F-demo-console.txt) ·
[Hardware receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step13-F-demo-live/receipt.md).

Use USB for the demonstrated route. ACIA remains model-tested, not board-qualified.

| User action | What the demonstration shows |
|---|---|
| Reset and let the saved S default expire, or press S after boot choices appear | F provides recovery independently of the monitors |
| `?` Enter at REC | Discover the available recovery commands |
| `C1` Enter | Select USB for the current session |
| `0` Enter with bank 0 disabled | The disabled bank is not launched; F returns to recovery |
| `L` Enter, wait for SEND BIN, then Ctrl-C before sending any payload | Cancel an unwanted load and remain in recovery |
| `L` Enter, then send the exact demo BIN as binary | Run the user's own small program in RAM without installing it in flash |
| Leave the link idle for three seconds after the BIN | F starts the RAM program at $0200 |
| Press one key at the demo's prompt | Test F's input service; the program reports the key byte |
| Program finishes | Return through F to the saved boot choice; S returns to REC |

Prompts are not typed. Ctrl-C cancels only before the first payload byte; once
payload reception begins, subsequent bytes are data. Raw L provides no transfer
length or CRC check. Use the exact file and a continuous binary transfer.

Actual 2609 program output included:

```text
STR8-N b15 F USER DEMO
This program runs in RAM using F only.
No journal, monitor or extension is required.
CPU code (02=65C02, 16=65C816): 16
F public capability flags: 17
RAM calculation, hex 1234 + 0001 = 1235
Press one key to test input> Received key byte, hex: 21
Program complete. Returning through F to the saved boot choice.
```

The demonstration driver supplied `!`, ASCII hex 21, at the key prompt. A user
can press any one key. The capability flags are F's legacy public API report;
the later VX1 VERSION/CAPS extension is a separate feature.

2609 retains its installed journals, monitors and VX1. The demo uses only F's
services; those sectors were not erased to demonstrate absence on hardware.
Independent MON readback checked the executed demo's RAM bytes and result data.
All four banks were read twice before and twice after. Every flash byte, B0,
all 32 wear counts, sequence 1020, default S and bank mask 00 stayed unchanged.
The demo ended at REC. The later CONFIG A/S exercise is now
[hardware-verified](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/receipt.md):
C700/seq1022 saved A, C800/seq1023 restored S; zero erases, banks00, counts/B0/SRAM retained.

## Demonstration 2: what each added component gives the user

| Add | Demonstrate | 2609 status |
|---|---|---|
| C/D journals and matching RAM CONFIG | Inspect saved boot policy and wear; save MON A temporarily, boot it, then restore S | USB hardware-verified: C700/seq1022 A, C800/seq1023 S; automatic boots passed; banks00 and wear/B0/SRAM retained |
| MON A and MON B | Select either monitor, display RAM, run a RAM program, and return through J3/S | Both USB start/return paths verified; exact command coverage is in each receipt |
| VX1 in E and matching MON hooks | VERSION, CAPS and independent F/MON build identities from both monitors | Hardware-verified over USB |
| Matching OIP1 opaque-image RAM installer | Back up a selected image span; install, read back, compare, launch and restore a probe | Required application-installation step; existing implementations/trials are references, not a newly admitted 2609 tool |
| Matching readback/export and FLASH maintenance tools | Archive bytes and hashes; inspect or deliberately edit selected application sectors | Separate tools with their own F/profile bindings; 2609 B0 and VX1 E require explicit preservation |
| Matching MAINT tool | First map/read/compare/CRC; later buffer editing and admitted application-sector writes | Read-only b15 RAM candidate prepared with 33 offline groups; no live 2609 MAINT upload. Write/edit stages remain future work. |
| OSI BASIC and fig-FORTH images | Run useful programs and switch between language environments | Placement, sizes and entry contracts still to be established |
| B1 application selector | Boot menu for OSI BASIC, fig-FORTH and two reserved slots | Planned; set B1 as default only after installation and manual tests |
| Debugger and further hardware tools | Additional development and peripheral exercises | Separate optional steps with their own qualification |

F reads boot policy and launches valid targets; RAM tools supply configuration
and installation operations. A temporary RAM tool need not occupy a flash sector.
The core demo should end before settings or flash writes; those are later lessons.

## Two installation experiences

### Staged tutorial

1. Back up original WDCMONV2 and preserve its B0 copy where applicable.
2. Install exactly F: either a 4096-byte programmer write or the factory-WDC
   RAM migrator. Demonstrate recovery and the small RAM program above.
3. Initialize C/D using the correct imported wear history; verify both journals.
4. Install and verify MON A/B; demonstrate selection and return to recovery.
5. Install VX1 E with the matching MON hooks; demonstrate VERSION/CAPS.
6. Admit the matching RAM toolset: CONFIG, **OIP1 opaque installer**, full
   readback/export and component recovery. Inspect CONFIG, then perform the
   separately directed A/default/S exercise. Keep application banks disabled.
7. Perform the **opaque-image installer lesson** below: prepare a small probe,
   back up its selected span, install, independently verify and launch it, then
   restore the previous bytes while retaining the newer wear/journal history.
8. Perform the **MAINT lesson** below: map/read/compare first, then RAM-buffer
   editing and CRC; flash edit/erase only on an explicitly backed-up target.
9. Install OSI BASIC and fig-FORTH through the same admitted OIP1 workflow.
   Verify each image's placement, entry and return/reset behavior. Demonstrate
   bank enable/entry only with a verified image and a prepared policy-restoration
   path; keep the saved default S during these tests.
10. Build and install the B1 selector with two reserved slots. Test all menu paths;
   only then save B1 as the default. Confirm reset persistence and S recovery.
11. Export the final inventory, images, configuration, wear record and console
    evidence. Optional diagnostics and development lessons follow.

This is the [existing F-up operator walkthrough](STR8N_B15_FROM_F_GUIDE.md).

## Required opaque-image installer lesson

OIP1 belongs **before the first application-image installation**. It can work
through matching F services with a valid journal even when MONs are unavailable;
the MONs in this tutorial supply additional inspection and return paths.
F raw L starts the RAM installer. The installer then receives the OIP1 host
protocol and image payload. Sending an opaque flash image directly to raw L
does not install it at its flash address.

1. **Describe the image.** Record filename/hash, name/version, CPU/ABI, bank,
   exact sector span, executable entry and return/reset behavior. SNBT currently
   stores one enabled entry per bank; it does not supply an image directory or
   validate opaque executable code. Check these properties before programming.
2. **Choose and archive the target.** Select an explicitly available span after
   inspecting the bank map. Do not assign a demonstration address implicitly.
   On 2609 preserve the whole B0 WDC backup, F, MON A/B, C/D, VX1 E and all
   unrelated images. Save the original target bytes and current CRC/hash.
3. **Admit the matching b15 installer and host transfer.** Verify the tool's F
   binding, current preimage and journal, payload integrity and target scope.
   Existing ordinary OIP1 protection refuses B3:A/B/C/D/F; B0-backup and installed
   VX1-E protection must also be enforced by the 2609 deployment profile. Do not
   assume the earlier b14/2512 artifacts provide those current-board protections.
4. **Install with progress.** Reserve each erase attempt in the journal before
   erasing, program the chosen sectors, and verify the bytes and final CRC/hash.
   Demonstrate an identical-content request as a no-erase/no-new-wear operation.
5. **Read back independently and launch deliberately.** Compare the entire
   image, then test its documented entry and return to MON/REC. Use a reviewed
   MON launch path if the lesson must keep all banks disabled. A raw RAM demo
   BIN is not automatically a relocatable flash probe; build the probe for its
   selected bank and entry.
6. **Restore and account.** Restore the captured target through the same guarded
   installer, verify it, and check all unrelated sectors. Restoring image bytes
   retains newer journal sequence and actual erase-attempt increments; it never
   resets wear counts or flashes an older whole-journal backup over them.
7. **Show the recovery boundary.** A torn opaque target may need reinstalling;
   inspect its current bytes before constructing a retry. Keep F recovery usable.
   Model interruption tests do not constitute an electrical power-cut trial.

This lesson is a required planned 2609 step. No opaque-image target was selected,
programmed or enabled by adding it to this flow. A matching installer, host
adapter and entry-specific probe still require preparation and qualification.

## MAINT options and demonstration order

MAINT is its own user-tool stage after the opaque-installer lesson and before
the application images. Prefer a matching RAM tool first; an optional installed
application can follow through OIP1. It does not enlarge F or imply that a flash
sector has been allocated for it.

**First read-only stage prepared:**
[2609-MAINT-RO-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step14-MAINT-RO-ready/2609-MAINT-RO-RAM.bin)
is **3,591 bytes**, raw L load/entry `$0200`, end exclusive `$1007`. It has
**no linked flash writer or CONFIG-save handler**. Its actual command set is:

```text
M [1|2|3]                   Grid / sector roles (default) / wear
R src first last            Read 1-4096 bytes into buffer $5000-$5FFF
D [offset [end]]            Display valid buffer bytes
K [src first last]          CRC16 of buffer or selected range
V src first last dst start  Compare ranges without copying
?                          Help
Q                          Restart F using the saved default
```

Addresses/offsets are four hexadecimal digits; source/destination is R for RAM
or flash bank 0–3. RAM reads are `$2000–$64FF`, flash reads `$8000–$FFFF`.
Read-to-buffer rejects a RAM source overlapping its own `$5000–$5FFF` buffer.
The borrowed buffer is disposable tool RAM, not a new permanent reservation.
Maps distinguish erased/programmed bytes and preservation roles; they do not
certify an opaque image or declare an unclassified sector free.

Startup checks immutable-code/F CRCs, the RA descriptor and copied RAM worker/
vector CRCs before private service calls. Snapshot counts require a full body
CRC and unambiguous same-sequence history. Invalid/unavailable journals display
unknown counts; the tool does not repair them. The existing F, MONs, VX1 and
all saved settings are unchanged.

The [33-group qualification](../output/qualification/2609-b15-onboarding-20261027T212009Z/step14-MAINT-RO-ready/qualification.json)
covers both CPUs, modeled USB/ACIA, startup guard failures, all current wear
values, erased scans, all-bank and 4 KiB reads, compare/CRC, malformed ranges,
45 refusal cases per port and preservation. The second WDC build is byte-identical.
This is **offline preparation only**, with no board upload or settings/flash write.
That MAINT preparation checkpoint was default S, bank mask 00 and sequence
1020. The later ES1 install now advances actual 2609 to sequence 1021 with
only B3:8 count incremented; the MAINT candidate remains not uploaded.
[Receipt and inspection sequence](../output/qualification/2609-b15-onboarding-20261027T212009Z/step14-MAINT-RO-ready/receipt.md) ·
[Simulated USB console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step14-MAINT-RO-ready/simulated-MAINT-65c816-e-port1.txt).

The fuller implementation in
[maintenance/maint.inc](../src/current/maintenance/maint.inc) already contains
map, copy/compare, buffer editing, CRC, write and erase operations. Its current
entry/layout/private service bindings belong to the older full system. It is
**not an admitted b15/2609 RAM BIN**. Its source-store/record/name operations
also depend on services that are not supplied by the present b15 VX1 extension.

Recommended matching-b15 options, reusing that work where appropriate:

| Option | User operation | Demonstration boundary |
|---|---|---|
| Status/map | Show bank/sector grid, used/erased ranges, image ownership and protections; wear and selected journal state | Read-only first; retarget the old map to the b15/B0-backup/VX1 layout |
| Read/display | Inspect RAM or flash; load a selected span into the 4 KiB edit buffer | No persistent write |
| Compare/CRC | Compare ranges; calculate buffer/image CRC; compare against a known manifest | No persistent write |
| Copy | Copy a span to RAM, or prepare a flash destination for review | RAM copy first; flash copy uses the guarded write path |
| Edit buffer | Patch bytes, fill a range, or create a filled buffer | Changes stay in RAM until an explicit verified write |
| Write/verify | Commit a reviewed buffer to an admitted application-sector destination; preserve bytes outside the requested edit | Backup/preimage checks, durable erase reservation, confirmation and full readback |
| Erase | Erase only an explicit aligned application-sector range | Separate confirmation, protection checks and wear accounting |
| Backup/export/restore | Use matching host transfer/readback tools to archive and restore bytes and manifests | Host integration is separate work; do not imply an onboard filesystem |
| Launch/return | Launch a verified application and return to MON or REC | Check its CPU/entry/return contract; keep the saved default S during lessons |
| Help | Show syntax, hexadecimal units, current target/protections and pending operation | Inspectable before mutation |

Start the MAINT demonstration with status, map, read, compare and CRC. Then load
a captured span into the RAM buffer, patch/fill it and show its changed CRC
without committing. Finally, if separately directed, use a disposable backed-up
application target for write/verify, identical-content no-op, erase and restoration.
Account for every actual erase; restoring old data does not restore old counters.

Normal b15 MAINT must preserve F, MON A/B, C/D, installed VX1 E, 2609's B0 WDC
backup, its own source image and all other declared image spans. The older MAINT
has dangerous/core-sector paths and older hardcoded layout assumptions; those
are not ordinary b15 user operations. Core updates, journal repair and component
reinstallation belong in their separately admitted recovery/install tools.

The smaller existing b15 FLASH example has actual commands `B0..B3`, `D`, `M`,
`F`, `I`, `Q` and `?`: select data bank, dump, edit RAM, edit flash, erase a sector,
return and help. Its recorded physical trial is on 2512, not a new MAINT trial
on 2609. See the [FLASH/maintenance reference](STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md#built-flashmaintenance-example).
NAME, stored-record transfer and broader FILE/IO actions remain separate
integration choices for b15; do not advertise them as active VX1 services.

## Other pieces needed for a complete user experience

| Piece | Where it belongs / current limitation |
|---|---|
| Image inventory and manifests | Before every install; show filenames, hashes, CPU/ABI, bank/span, entry and ownership. A resident named-image directory remains planned. |
| Backup, independent readback and export | Before mutation and at every checkpoint; include owner RAM when it matters, target images, configuration, wear and console evidence. |
| Enable/disable/entry/default CONFIG exercise | After a verified application exists. Current CLI has no general bank-disable command; prepare a guarded restoration path or the planned draft/Save editor before treating enable tests as reversible. |
| Journal status and capacity | Display selected sequence, validity, unknown-history flags and remaining append capacity; distinguish boot-policy restore from full image restore. A friendly status display still needs preparation. |
| Repair and component reinstall | Demonstrate recovery from missing MONs and interrupted targets with matching component tools; general damaged nonblank-journal repair is not implemented. |
| Settings review and save confirmation | Planned CONFIG menu/draft work. Current C/B settings commands take effect immediately; no Save/Discard screen exists. |
| Console qualification | USB is the demonstrated path. ACIA wiring, timing and receive behavior require their own physical tests. |
| RTC/NTP/calendar/trim/PF-history tools | Optional hardware-services chapter after core/tool admission. Use matching tools and record snapshots and actual changes; these are not commands supplied by F recovery. |
| EDU/SRAM | Optional [onboarding chapter](STR8N_B15_EDU_SRAM_ONBOARDING.md) after core/tool admission. B3:8 ES1 is installed/verified on 2609; a fresh pre-install array and two post-install reads match both original backups. Only B3:8 and C600 changed. Named storage/WORK/saved EDU mode remain later ports. |
| Debugger and program-development examples | Optional development chapter; qualify the required components and CPU mode independently. |
| Final acceptance and return to recovery | Verify installed bytes, versions, wear, all manual launches, saved-default persistence, the selector's reserved slots and the S recovery path. |

The user's first useful application should follow the complete opaque
install/readback/launch/restore lesson. Further peripheral and debugger demos
can then build on a known boot and recovery path.

## Optional full-core installation from F

The recommended combined artifact is a **RAM installer** loaded by F, with a
proposed name **`b15-CORE-INSTALL-RAM.bin`**. Its intended resident payload is:

| B3 sector | Contents after the proposed combined install |
|---|---|
| A | Matching MON A |
| B | Matching MON B |
| C/D | Valid configuration/wear journals |
| E | VX1 VERSION/CAPS provider |
| F | Existing 4096-byte bootstrap, preserved |

Default remains S, all application banks remain disabled, and B0–B2 plus B3:8/9
are preserved. The distribution kit must include **matching CONFIG, OIP1 opaque
installer/host adapter, MAINT, readback/export, recovery tools and the small demo**.
These are separate RAM/host files unless a measured combined-tool design is
explicitly built; they are not implied to occupy resident flash in the table.
Application images and debugger components require their own selected modules;
they are not silently included in the core install.
EDU/SRAM is also explicitly optional. The verified read-only ES1 module uses
B3:8 with B3:9 retained; include its matching RAM tools and backup procedure
only when selected. A future combined installer must reserve and account for
that extra sector erase and preserve existing retained SRAM. C/D are unchanged.

For an F-only starting point, import the correct wear provenance, durably reserve
the first C/D erase attempts on the host, establish valid journals, then reserve
each E/A/B erase in the journal before programming its component. Verify each
body and commit last, report progress by sector, independently read back all
banks, and return to REC. An existing valid journal needs a preserving update
route, not blank/factory initialization. A completed or interrupted source must
not be blindly replayed with an old exact-source installer.

**Existing precursor:**
[2609-CD-MON-AB-RAM.bin](../output/qualification/2609-b15-onboarding-20261027T212009Z/step06-MON-ready/2609-CD-MON-AB-RAM.bin)
is **19,327 bytes**, loads through F, and combines C/D plus the original b15 MON
A/B. Its 55-group preparation is archived in the
[installer receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step06-MON-ready/receipt.md).
It binds the archived 2609 F-only checkpoint and its wear counts. It is not a
generic factory installer, includes no VX1, and is not admitted on the current
2609 state. The separate MON-only installer was the route actually run.

**The new combined C/D+A/B+VX1 RAM installer is proposed, not built or tested.**
Its measured code and embedded payload must fit F's 25,344-byte load window.
Build and qualify it for the intended starting state before distributing it.

## Programmer BIN versus F-loaded RAM BIN

Both are useful distribution formats, but their addresses and contents differ.

| Artifact | Destination / execution | Scope |
|---|---|---|
| Existing `b15-F-4096.bin` | Program B3:F000–FFFF | Bootstrap only; used by the F-up route |
| Proposed `b15-CORE-INSTALL-RAM.bin` | Load/execute in RAM at $0200 through F L | Checks the board, installs C/D+A/B+E, preserves F and B0 |
| Proposed `b15-B3-AF-24576.bin` | External programmer, B3:A000–FFFF, exactly 24,576 bytes | MONs, journals, VX1 and F for a specified factory image |
| A complete chip image | External programmer, all four physical banks, 131,072 bytes | Requires an explicit full layout, B0-backup policy and all application contents |

A programmer image is not executable RAM-loader input. A factory journal image
cannot be copied over an existing owner's journals without losing newer history.
For new boards, identify earlier lifetime wear as unknown and record known erase
attempts; never seed them with 2609's private counts. A factory RAM migration
starts with the F-only migrator, then the combined core installer. Replacing F
is unnecessary during the second stage.

The next packaging work is the full-core RAM installer and a matching factory
programmer-image profile, each with a manifest, explicit address range, progress,
readback and operator instructions, plus the matching OIP1/toolset distribution.
Neither installation image was flashed by the demonstration.
