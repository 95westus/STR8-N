# STR8-N 1.35: Current Code Reference

## 1. Scope, evidence, and how to read this book

This book describes the STR8-N working tree captured for this edition. It covers the resident supervisor, its relocated worker, shared contracts, supported RAM utilities, host tooling, build rules, and tests. It contains no development chronology or release-by-release account. R-YORS, HIMON, ASM-F2, AP applications, and WDCMON firmware are external systems; only STR8-N's interfaces to them belong here.

The Makefile's `VERSION := v1.35`, release definitions, and `src/str8-version.inc` identify the current product. Product version 1.35, resident ABI version $01, record ABI version $02, worker ABI version $02, and RAM ABI version $12 are different identifiers. Do not infer one from another.

The explanatory chapters describe behavior and its consequences. **Source rationale** means a reason stated in a source comment or directly evident in the control flow. **Engineering inference** means an explanation inferred from that implementation, not a claim about the author's intentions. Unrecorded motivations remain unknown. The listings preserve technical comments, original line numbers, and code text; editorial filtering removes dated change-log comment lines and assembly branches outside the selected current build profiles. Shared utility listings contain the union of their supported profiles and retain their conditional directives. They are reading aids, not replacement assembler inputs.

The generated coverage appendix identifies each file, its hash, selected profiles, and omitted lines. The source directory and maintained tools are covered; duplicate superseded tool wrappers, old generated image carriers, build output copies, board transcripts, proposals, and project task history are excluded. Test fixtures retained as current test dependencies are inventoried without reproducing their old machine-code payloads. This is not a claim that every file in the repository is current executable firmware.

The source is authoritative for what this edition does. Existing linked maps and binaries supply layout cross-checks, but this documentation task does not rebuild or qualify firmware. No serial connection or flash operation is performed in producing the book.

## 2. System boundaries and execution model

STR8-N runs on the W65C02SXB/EDU with a banked SST39SF010A flash arrangement. The CPU sees RAM at $0000-$7EFF, memory-mapped I/O at $7F00-$7FFF, and one selected 32 KiB flash bank at $8000-$FFFF. Four physical banks provide 128 KiB of flash. Physical RESET selects Bank 3; its sector F contains STR8-N.

The protected resident layer supplies reset selection, guarded guest launch, a recovery console, dense flash installation, RAM load-and-execute, and a few stable callable services. It is not an operating system, filesystem, assembler, or general-purpose debugger. Payload identity and launchability are recorded in a four-row directory; payload execution and initialization remain the payload's responsibility.

The bank selector replaces the entire flash window, including the instruction currently at the next ROM address. Consequently, bank-dependent flash work and the final guest jump run from RAM. The resident copies its own worker before use; an install file does not supply executable worker bytes. **Source rationale:** the worker explicitly prohibits calling ROM while it changes banks. **Engineering inference:** this keeps execution independent of the payload being erased or selected.

Resident command surface:

| Command | Owner and result | Principal restriction |
|---|---|---|
| I | Resident transaction plus RAM worker; programs flash | Dense selected sector span; B3:F excluded |
| L | Resident parser and RAM copy; jumps to S9 | Destinations and entry $2000-$7AFF |
| C | Local HIMON cold entry | Compatible marker at fixed target required |
| W | Local HIMON warm entry | Compatible marker; RAM-preserving request |
| J0-J2 | Directory gate plus RAM worker | COMPLETE row and valid target RESET |
| J3 | RAM worker, local-bank exception | RESET validation; no COMPLETE-row gate |

## 3. Flash layout and configuration

The current worker constants and existing v1.35 map describe the following 4096-byte protected sector. Ends in this table are inclusive.

| CPU range | Bytes | Contents |
|---|---:|---|
| $F000-$FCF1 | 3314 | Resident code and data |
| $FCF2-$FD77 | 134 | Unused margin between resident and worker |
| $FD78-$FFAF | 568 | Stored worker, linked to execute at $0200 |
| $FFB0-$FFEF | 64 | Four bank-directory records |
| $FFF0-$FFF9 | 10 | Configuration pocket |
| $FFFA-$FFFF | 6 | NMI, RESET, IRQ/BRK vectors |

These are implementation addresses except for explicitly published ABI entries. The layout checker ties the worker include to its linker map and checks boundaries and available margin. An $FF byte inside a linked code region is not automatically allocatable space. Top-sector image generation fills unused space and combines the resident, relocated worker, metadata, configuration, and vectors.

`src/str8-config-eq.inc` assigns $FFF0 to the WORK locator, default $FF (none); $FFF1 to the protected top-backup locator, default $2F (Bank 2, sector F); and $FFF2 to AP/FNV discovery policy, default $FF (disabled). $FFF3-$FFF9 remain erased and unassigned. A valid application-sector locator packs bank 0-2 in the upper nibble and sector 8-F in the lower nibble. It does not describe a CPU address by itself.

The discovery encodings $A0-$A7 carry three permitted-bank bits. $FF and invalid signatures disable discovery. This is a contract consumed by cooperating software; merely declaring a byte does not implement an AP resolver in the resident. The STR8-iN/65 flags editor changes only this policy and deliberately does not allocate WORK or backup roles.

Configuration defaults describe a generated candidate. A live board can differ. Ordinary top update preserves the directory but installs candidate configuration, so a live policy such as $A6 is not automatically preserved. Inspect the candidate and the live bytes independently.

Role protection is not universal hardware protection. The resident I range policy permits Bank 0-2 sectors 8-F and does not consult the WORK/backup locators. A legal I operation can therefore overwrite a configured role sector such as B2:F. The maintenance tools implement their own role exclusions, and the current top-update driver explicitly selects B2:F. Do not infer a global write lock from a configuration label.

## 4. RAM ownership and phase restrictions

| Range | Owner and use | Consequence |
|---|---|---|
| $0090-$009C, $009E-$009F, $00A1-$00A2 | Installer state | Transient; not application storage during I |
| $00A0 | L has-data flag | Shared by phase, not a persistent variable |
| $00CD-$00D6 | Parser/directory/worker scratch | Calls are not reentrant |
| $0100-$01FF | Hardware stack | Reset and successful handoffs reset SP |
| $0200-$0226 | Public selector prefix | F010 overwrites these 39 bytes |
| $0200-$0437 | Complete resident worker | I/J overwrite the full worker extent |
| $0200-$09FF | Reserved worker tray | Other users require phase coordination |
| $0A00-$19FF | One 4 KiB staging sector | Not preserved across flash operations |
| $2000-$7AFF | Allowed L destination envelope | Loader does not allocate or relocate programs |
| $7B00-$7BFB | Decoded S-record data | Cannot be overwritten by L |
| $7C00-$7DBF | Foreground high-tool overlay | One owner at a time |
| $7DC0-$7DC7 | External AP-link scratch contract | Not general STR8-N scratch |
| $7DE7-$7DFF | Recovery state and handoff records | Some slots are operation-specific |
| $7E95-$7EA8 | Record request/result card | Shared mutable ABI state |
| $7EED-$7EEF, $7EF8-$7EFF | IVI signature and RAM vectors | Guest must initialize its interrupt policy |

The actual active worker is smaller than its tray. A selector-only call leaves the external helper area beginning at $0300 intact, while a complete worker copy does not. **Source rationale:** the prefix ends below $0300 specifically to avoid overwriting HIMON's RAM banked helper. RAM not named here is not automatically free in an integrated payload; other programs may own it.

The recovery capsule includes one-shot reset signature bytes at $7DE7-$7DE8, bank/mode/sector state, jump vector/status, and the published `BJ` bank-jump record at $7DFD-$7DFF. Not every operation refreshes every slot. Consumers must validate signatures and operation results instead of treating stale RAM as a fresh report.

## 5. Reset, selector, and local monitor entry

`START` jumps to `STR8_BOOT_START`. Boot disables maskable interrupts, clears decimal mode, and initializes SP to $FF. The selected EDU quiet-start path sets PIA CA2 low, configures LED outputs, publishes running state, and initializes IVI. The cold-console path delays before accessing the FT245R-facing VIA. It deliberately does not rewrite PCR while executing from flash during cold power-up.

The reset classifier reads the two-byte `RS` software-reset signature. Cooperating software writes SIG0 first and SIG1 last immediately before reset-vector entry. STR8-N clears SIG1 before printing. `RST S` therefore means a valid cooperating software marker was consumed; `RST H` means hardware or any unmarked entry. It is not a hardware-cause register and cannot distinguish every physical cause of reset.

After classification, a bounded RX flush discards up to 255 queued bytes. The banner and selector appear, followed by six live polling intervals. Current release defines suppress the dot-printing branch. Keys 0-2 request bank launch, C/W request cold/warm HIMON, and S stays in STR8-N. A timeout attempts warm HIMON. The fixed delay constants are calibrated for the board's stated 8 MHz timing; wall-clock time depends on actual clock and console readiness.

C/W validate the local HIMON identity and enter $C000. Warm entry writes the cooperating warm signature; cold entry requests normal initialization. Missing or incompatible identity falls back to the STR8-N command surface. Compatibility recognition is not cryptographic authentication or comprehensive payload verification.

The source's introductory comment still mentions attach pulses and selector dots, but the current enabled branch has the behavior described above. This is a comment/code discrepancy, not an alternative startup mode to assume in the current release.

## 6. Interrupt dispatch

Hardware NMI enters the resident stub at $F0CF; IRQ/BRK enters $F0E3 in the existing linked map. RESET enters $F000. IVI initialization invalidates its signature, installs reset/default RTI targets, and commits the signature after initialization. The NMI stub validates signature and a nonzero vector before dispatching; otherwise it returns with RTI.

The IRQ/BRK master examines the B bit in the saved processor status to choose BRK or IRQ RAM vectors. It preserves the registers it saves before the indirect handoff. These are interrupt entries, so an installed handler must honor interrupt stack semantics and eventually use the appropriate return discipline. They are not ordinary JSR callbacks.

SEI masks IRQ, not NMI. A top-sector stub cannot make flash erase/program safe against NMI, power loss, or reset while the flash window is unavailable. Default RTI behavior also does not acknowledge an arbitrary peripheral interrupt source. A guest enabling interrupts must install handlers and manage its hardware sources.

## 7. Console services and command parsing

The raw console operates through VIA control/data registers at $7FE0/$7FE1 and direction registers at $7FE2/$7FE3. It follows FT245R readiness and read/write strobes, including short instruction delays around signal changes. These sequences are hardware protocol code; rearranging apparently redundant writes or NOPs requires hardware evidence.

| Entry | Input/output contract | Limit |
|---|---|---|
| $F003 | Initialize console; A=$0C; X/Y/C preserved | Does not select Bank 3 |
| $F006 | C=1, A=$01, X=$3F; Y preserved | Feature discovery, not product version |
| $F013 | Wait for byte; A=byte, C=1; X/Y preserved | No timeout, echo, translation, or Ctrl-C interpretation |
| $F019 | Send A; A/X/Y preserved, C=1 | Blocking; no added line endings |
| $F03E | C indicates available byte; X/Y preserved | Non-consuming; A/other flags clobbered |

All these ROM calls require Bank 3 visible. The private text and activity wrappers add command semantics, CR/LF handling, case conversion, input limits, prompt printing, and LED indications. Public raw services do not change the LED display. Polling ready followed by blocking read assumes a single input owner: another consumer can remove the byte between calls.

The command loop discards invalid input without continually reprinting help. Bounded line input prevents an unlimited command from overwriting adjacent state. Compact messages use a high-bit-marked final character, and printing helpers exploit message placement. **Engineering inference:** these conventions conserve the fixed 4 KiB budget but make message layout part of executable correctness, not merely presentation.

## 8. Record parser: mechanism and limits

`STR8_RECORD_SERVICE_BODY` at public $F009 validates one S0, S1, or S9 record. Discovery bytes at $F00C-$F00F are $53 $52 $02 $03 (`SR`, version 2, buffer+console). Parsing never applies data to RAM or flash. Callers own destination policy, sequencing, rollback policy, and execution.

The caller supplies operation $01 at $7E95, format $01 at $7E96, source 0/1 at $7E97, and for buffer input an address at $7E99-$7E9A with an exact one-byte text length at $7E9B. Buffer text is one record without line ending; console records terminate with CR or LF. The buffer must not overlap the request/result card or decoded tray.

The count includes two address bytes, data, and checksum. The low byte of their sum plus count must be $FF. Hex decoding accepts valid hexadecimal characters and propagates a distinct failure status. Console Ctrl-C produces abort. The parser reports metadata/data/end kind, address, length, entry flag and entry address, and a pointer to $7B00.

Console S1 records can carry 252 bytes. Buffered S1 text is limited to 122 data bytes because the exact text length itself is an eight-bit quantity. The maximum decoded capacity and maximum buffered record size are therefore different.

Return A is status, carry set means success, X/Y are clobbered, and decimal mode is cleared. Interpret decoded fields only on success. Status codes are 00 success; 01 bad operation; 02 bad format; 03 bad source; 04 bad start; 05 bad type; 06 bad hex; 07 bad count; 08 bad checksum; 09 bad end; 0E abort. The named constants in `src/str8-record-eq.inc` define the complete card and statuses.

## 9. Directory identity and journal state machine

Each bank has a 16-byte record at $FFB0 + bank*16. Offsets are: +0 type; +1..+3 erased reserved bytes; +4..+8 five-character description; +9 seal $FE; +10..+11 entry; +12..+15 journal. Banks 0-2 use entry $FFFF; Bank 3 has a constrained entry in its payload area. Descriptions allow uppercase letters, digits, hyphen, underscore, and period.

The journal contains sixteen two-bit pairs. Unused is binary 11, STARTED is 10, COMPLETE is 00, and 01 is illegal. The scanner also validates ordering: the existence of a complete pair somewhere is not sufficient to accept a damaged journal. Legal progression respects flash's one-to-zero programming rule.

An open transaction leaves the row INCOMPLETE and prevents J0-J2 launch. Recovery completes the same open pair; a later transaction consumes another unused pair. A full journal requires guarded maintenance or a protected-sector refresh before another normal transaction. There is no wear counter or unbounded log.

`STR8_DIR_VALIDATE_BANK_A` checks structural identity and journal state. `STR8_DIR_WRITE_BYTES` bounds the request and preflights legal one-to-zero transitions. The RAM worker repeats transition preflight after selecting Bank 3. **Source rationale:** a resident-side check must not be trusted if it observed the wrong bank. Readback is part of success.

Identity is immutable under ordinary resident installation because the resident does not erase B3:F. Guarded RAM maintenance is the explicit exception for operations such as description rename, directory reclamation, and journal compaction.

## 10. Flash installer: preflight and stream policy

`STR8_CMD_INSTALL_PREVIEW` gathers bank, range, and applicable identity metadata, validates the directory, and presents a summary. `STR8_I_READ_RANGE` accepts a contiguous sector interval: 8-F in Banks 0-2 or 8-E in Bank 3. A sector is 4096 bytes. A partial install can start below the highest sectors; top alignment is not required.

The stream allows zero or one S0, nonempty S1 records that exactly fill the selected extent in ascending order, and S9 termination. First address must match the start; each subsequent address must match the next expected byte. Gaps, overlap, duplicate addresses, backward records, empty data, omitted erased padding, and out-of-range bytes fail. S2-S8 are unsupported.

For a full Bank 0-2 image, the supplied RESET vector must be non-erased and S9 must match it. Partial-image S9 may be $FFFF or an address in the selected extent. A first Bank-3 install needs an in-range entry; an established Bank-3 identity accepts $FFFF or that immutable entry. S9 is validation metadata here, not the guest J launch address.

An accepted partial installation can still be unbootable: if it leaves an erased vector sector untouched, J cannot invent a RESET vector. A COMPLETE row means the selected transaction completed under its rules, not that every possible payload behavior has been proven.

## 11. Flash installer: mutation, commit, and failure

After `WRITE? Y`, STR8-N copies/verifies the worker and records START and available first-enrollment metadata before announcing `S19`. This is the persistent transaction boundary. Cancelling the sender after the prompt does not restore the directory to its previous state.

Records fill the $0A00-$19FF staging tray. Each complete non-final sector is erased as needed, programmed, and verified while the stream continues. The final selected sector stays in RAM until valid termination and `COMMIT? Y`. Then the final sector is programmed and verified, a required first Bank-3 entry is written, and COMPLETE is written last.

**Source rationale:** START identifies interruption, final-sector holdback keeps the final commit separate, and COMPLETE-last prevents a bootable directory state from preceding verified installation. **Engineering inference:** this provides conservative launch gating rather than whole-image atomic rollback. Sectors already programmed remain changed if a later record fails.

After an interrupted install, recovery is restricted to the entire writable bank: $8000-$FFFF for Banks 0-2 or $8000-$EFFF for Bank 3. This avoids a narrow retry concealing uncertainty in sectors already touched.

Failure paths distinguish internal dense/order, entry, flash, trailing-input, directory, and worker failures while the compact UI may report a generic failure. Quenching continues parsing/discarding through a valid S9 or Ctrl-C; it does not reopen the command prompt between packets. **Source rationale:** pasted record tails must not become commands. Quenching neither rolls back RAM nor reverses persistent flash changes.

## 12. RAM loader: intentionally different policy

`STR8_CMD_LOAD_RAM` uses the same parser but accepts sparse and nonascending S1 records. Each whole record span must remain within $2000-$7AFF; the code checks the last byte, not only the start. A record crossing $7B00 fails even if its first byte is legal. At least one nonempty S1 must succeed, and S9 must lie in the same allowed envelope.

S9 in range does not prove the entry byte was actually loaded. Repeated addresses can overwrite earlier received data. These are consequences of the loader's compact policy, which is not an allocation or executable-integrity system.

On success, L disables IRQ, clears decimal mode, sets X/SP to $FF, and jumps indirectly to S9. Bank 3 remains selected. It prepares no return address; the RAM program must not RTS back to STR8-N. A/Y, unrelated RAM, interrupt targets, peripherals, and queued input can be inherited.

On failure, already copied records remain in RAM. The poisoned load cannot jump even if later records are valid. If needed, the loader drains through S9 or Ctrl-C before returning to its prompt. There is no load-only mode, rollback, arbitrary fallback address, or flash worker invocation. RAM tools normally exit by selecting Bank 3 as needed and entering $F000.

## 13. Worker implementation and flash primitives

`src/str8-worker.asm` links at $0200 and occupies 568 bytes. Its fixed selector service is at $0203; the prefix is 39 bytes. Modes are staged-sector program $05, protected record program $07, and bank jump $08. Unknown modes fail before changing banks or flash. These private modes are not a published general destructive API.

Staged-sector programming checks for an already erased destination, erases when necessary, skips programming staged $FF bytes, and verifies the entire sector. Byte writes check that a requested value can be reached using only one-to-zero transitions and skip equal bytes. Poll loops have bounded counters; a timeout or mismatch is a failure, not success inferred from command issuance.

The flash command sequence uses unlock addresses $D555 and $AAAA in the CPU window. Operation-specific routines preserve failure addresses in the recovery state or record result fields. The common returning tail reselects Bank 3, restores running LED state, restores the saved processor status, and publishes carry as the operation result.

The bank jump is the nonreturning exception. It selects the requested bank, rejects RESET below $8000 or equal to $FFFF, writes the validated `BJ` record, resets CPU software state, releases LEDs, and jumps. This is a software handoff, not an electrical reset. Peripherals and most RAM retain their contents.

## 14. Public bank selection and guest obligations

`$F010` requires a RAM caller and a RAM return address below $8000, with Bank 3 visible on entry. It copies/verifies only the selector prefix and tail-calls $0203. A is the bank number 0-3. Carry reports success; A/X/Y are clobbered. The selected bank remains visible on successful return.

The bank latch is read at $7FEC. Explicit bank patterns are $CC, $CE, $EC, and $EE under mask $EE. Other raw states are not valid bank numbers. Preserve unrelated hardware behavior when using the control register; do not assume reset pull-up state is an ordinary software-selected bank encoding.

`STR8_JUMP_BANK_PREP_A` and launch helpers perform resident-side gating before full-worker handoff. J0-J2 require COMPLETE directory records. J3 skips that row gate but still validates the RESET vector. A failed worker jump returns with Bank 3 restored; a successful jump does not return.

A guest must establish its own RAM, interrupt vectors, console/peripheral state, and execution assumptions. It must preserve the selection needed to fetch its own code. External code should use published ABI entries and generated contract constants, not private addresses merely visible in a map.

## 15. LEDs and hardware ownership

LEDs use PIA Port A at $7FA0 and are active high. Named states are $01 running; $21 no-host wait; $43 host/input wait; $07 RX activity; $0B TX activity; $F0 flash mutation; $00 released. The include also defines individual bit flags and $41 input-wait state.

The resident owns LEDs while managing its own interaction; raw public console calls leave them alone. Mutation publishes all-red status; successful guest handoff releases the display. A guest then owns its display policy. The host indication is derived from the control signal used by the code; it is not proof of a terminal program's identity or readiness to send a valid file.

The IRQ and LED probes are separate RAM programs with their own guards. A flash-worker probe is not a harmless display demo: its source and test contract must be consulted before board execution. This book generation does not execute probes.

## 16. Bank Maintenance and its three current forms

The maintained body is `tools/bank-maint/str8n-v1.23-bank-maint-2000.asm`, despite the filename. Current builds select standalone maintenance, a combined maintenance/top-updater menu, or STR8-iN/65 maintenance. Wrapper EQU definitions and Makefile flags select these forms. Their private mutation worker is distinct from the resident worker and has its own layout and call assumptions.

| Command | Operation | Important guard or exception |
|---|---|---|
| M | Inspect banks, sectors, AP envelopes, roles, and directory | Restores entry-bank state around staging |
| C | Copy full bank to Bank 0-2 and enroll | Empty destination row; verify payload before COMPLETE |
| D | Adopt existing payload without rewriting it | Empty row; RESET and applicable entry/signature checks |
| E | Erase selected permitted span | Exact target confirmation; B3:F and configured roles protected |
| R | Reclaim erased-bank row or compact full D3 journal | Erased-bank/full-journal proof and guarded top rewrite |
| N | Rename five-character description | COMPLETE validated row; preserve all other fields |
| P | Put a validated AP envelope | Erased target bytes; refuses role sectors |
| U | Combined-menu protected top update | Present in menu+top form |
| F | STR8-iN/65 discovery policy editor | Present in its form; changes $FFF2 only |
| Q / empty main line | Return to STR8-N | Direct reset entry, no RTS |

The AP source tray is $4000 in standalone maintenance and $7000 in the combined form, whose candidate occupies $4000-$4FFF. P accepts the bounded envelope described by the code and verifies its FNV information. A valid envelope is a format/integrity check, not a trust signature.

Copy is not atomic. If copy verifies but metadata entry is cancelled, the destination payload may exist without enrollment. D is the metadata-only adoption path for an empty row. It cannot repair an arbitrary nonempty record.

R for D0-D2 requires all eight sectors erased before clearing the row. R for an exhausted D3 journal retains identity and changes journal to one COMPLETE transaction ($FC,$FF,$FF,$FF), leaving fifteen pairs. N changes only description bytes. These top-sector mutations stage and back up B3:F, rewrite and verify it, then erase/verify scratch. Role sectors are not disposable scratch.

Ordinary safe failures and subprompt cancellation return to maintenance. Bank-3 erase is an exception: after erasing potential monitor code it returns directly to STR8-N. Scratch availability, power continuity, and exact confirmation remain operational requirements even though code preflights the operation.

## 17. Protected top update and directory refresh

The common driver is `tools/top-update/str8n-v1.23-top-update-2000.asm`. The standalone tool runs at $2000; its embedded menu form is placed at $3700. A host-generated exact 4096-byte candidate occupies $4000-$4FFF. The normal updater preserves the live directory; refresh installs an erased directory. Both install candidate configuration.

Preflight checks the resident doorway/signature and candidate checksum before active erase. The current driver uses Bank 2 sector F as the backup. It stages the live top, writes and verifies backup, then allows the separately confirmed active rewrite. Host SHA-256 checks identify the candidate; a small runtime checksum alone is not cryptographic authentication.

Before active erase, cancellation can return safely to the resident or embedding menu. After active erase, failure stays in the RAM retry/restore path. Calling erased resident code would be invalid. Direct console and flash access therefore remain local to the RAM driver.

Restore while the RAM tool remains alive is different from recovery after power loss. Losing RAM execution while B3:F is incomplete may require an external programmer. Directory refresh clears launch identities/journals; it does not automatically reconstruct them from payload contents.

## 18. Stock migration, archive, and host session control

The project-written WDCMON migration programs run in RAM under the external stock environment. The archive utility exports a selected complete bank with a receipt. Extraction validates captured data before creating a host binary. No WDCMON source or firmware is included as STR8-N implementation.

The installer accepts Bank 0 only if completely erased or byte-identical to the original Bank 3. If erased, it copies and verifies the original bank there. A used different Bank 0 is refused. Banks 1 and 2 are outside the ordinary preservation/copy path. Only after preservation is proven does it receive the canonical top image and change B3:F.

The displayed `ARCHIVE xxxxxxxx` FNV acknowledgement is an operator gate; typing it is not proof a valid host archive exists. The host extractor is responsible for producing and checking that file. The installer retains RAM recovery while alive, but protected-sector power-loss recovery can still require an external programmer.

PowerShell and Python launchers manage stock-monitor loading, port state, binary transfer, prompts, and capture. The higher-level migration entrypoints orchestrate those pieces. A serial reconnect or prompt match is transport evidence, not by itself proof of byte-for-byte flash correctness. Archive extraction and board readback checks address separate questions.

## 19. Build and image production

The Makefile calls WDC `wdc02as` and `wdcln`, PowerShell, and Python. External toolchain installation and licensing are outside this repository. The production resident defines enable V1 layout, installer staging and transaction code, cold-console startup, version 135, and quiet EDU initialization. A define named `DRY` does not mean the released installer is nonmutating: the transaction define is also enabled.

The worker links at $0200; the resident at $F000. Top-image construction imports their S19 payloads, relocates stored worker bytes, and places configuration and vectors. Layout validation checks actual symbol extents. Manifest generation records contracts and artifact identities; public-contract generation exports supported external constants.

RAM tool construction selects explicit variants, generates candidate includes, and validates S19 bounds and entry addresses. `.a` generation wraps a maintenance image for an external application environment; it is a generated carrier, not the maintained assembler body. The current carrier is inventoried by hash rather than printing encoded payload bytes again.

`make all` builds the configured artifact/check dependency graph. `make release-package` additionally builds the combined maintenance image, migration package, and probes, then creates and verifies allowlisted archives. Optional deeper opcode-model checks are separate targets. `make clean` is a build cleanup command, not a verification step; it was not run for this book.

Packaging scripts verify hashes and embedded candidate consistency, prepare release documentation, and generate link checks. Packaging can include documentation whose wording is stale; it cannot prove technical claims merely by copying them into an archive. Product code, generated artifact, and documentation identity must be checked separately.

## 20. Host utilities and checks

The file-by-file catalog following these chapters explains every included utility and provides its complete current listing. Broadly, the host tools have five responsibilities:

- Image conversion/composition: dense payload creation, entry/range validation, top-sector composition, and generated assembly includes.
- Layout/contract checks: fixed ABI addresses, worker extents, RAM ownership, supported load ranges, and permitted image records.
- Packaging: explicit contents, archive verification, public contract/manifest generation, and usable manual links.
- Board transport: capture, serial command sessions, stock-monitor launch, reconnect handling, archive extraction, and readback comparison.
- Behavioral tests: execute linked instructions against modeled CPU/flash/console state, check boundary policies, and inject failure conditions.

A filename beginning `test_` does not guarantee it performs only static inspection; read its entrypoint and dependencies. Conversely, a host check using a modeled flash array does not touch a physical board. The listings retain parameter defaults and execution entrypoints so these distinctions are reviewable.

## 21. Verification and present limitations

Host checks can establish image shape, checksums, layout consistency, and behavior within a modeled environment. They cannot reproduce every electrical timing, power interruption, FT245R, VIA, PIA, or flash-chip behavior. Differential tests use retained fixture data as a test oracle; this book explains their current purpose without narrating the older implementation.

The current v1.35 technical guide and packaged manifest report guarded update, reset, handoff, and readback evidence, while factory migration and the broader hardware matrix remain unqualified for v1.35. That is an existing qualification statement, not a board test performed during this documentation task.

Principal limitations are bounded ROM/RAM, blocking raw console calls, shared nonreentrant scratch, sixteen journal transactions per refresh cycle, no full-image rollback, no flash wear accounting, no payload authentication, and dependence on an external recovery route if the protected sector becomes unbootable. Existing guards reduce particular failure modes; they are not a general guarantee that arbitrary guest code or all interruptions are safe.

## 22. Source and documentation discrepancies to keep visible

The README headline and portions of its release wording identify 1.34, whereas Makefile and current source select 1.35. Some technical-guide subsection titles also retain a different product version. This edition follows executable selection and current contract constants.

The resident opening comment mentions unpolled attach pulses and selector dots that are suppressed or absent in the active startup path. The shared jump include describes copying the worker broadly; actual F010 copies only the 39-byte prefix. The complete worker is copied for I/J. ABI includes can retain version-like names independent of the product version; their constants and call semantics are the relevant contract.

No editorial rewrite of existing source comments or manuals is made by creating this book. Readers can inspect each exact source line and compare it with the interpretation. Addresses from existing build output are labeled as cross-checks rather than evidence that every artifact was freshly reproduced from this snapshot.

## 23. Practical reading paths

To understand startup, read chapters 2-7 and the resident labels START, STR8_BOOT_START, STR8_STARTUP_DELAY, STR8_IVY_INIT, and STR8_ENTER_HIMON_WARM. To integrate a caller, read chapters 4, 7, 8, and 14, then the ABI includes and generated public contract. To review flash integrity, read chapters 9-11, 13, and 17 with the directory and worker routines open.

To maintain the tooling, use chapters 16-20 and the file catalog. The generated symbol index locates named assembly labels/constants, Python functions/classes, PowerShell functions, and Makefile targets. It is a lexical navigation index, not a complete assembler cross-reference or proof of reachability. Local assembly labels are interpreted in their surrounding source context.

The listings and manifest make this edition a fixed snapshot. Regenerating refreshes listings and hashes; substantive code changes still require a human or agent to revise the explanatory chapters. A successful book build is a document check, not firmware qualification.
