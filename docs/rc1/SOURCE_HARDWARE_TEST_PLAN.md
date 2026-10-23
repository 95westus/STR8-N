# Source-store preserving installer and hardware test plan

The owner has separately authorized a limited MAINT/ASM installation and EDU
test on **board 2604 only**. The workbook's Appendix G records that trial's
actual outcome. Board 2609 and the remaining physical configuration matrix
remain future work. The experimental package retains
`installation_permitted=false`, `hardware_qualified=false` for general use;
the one-board runner additionally binds owner authorization, repeated hardware
capture, exact candidate and CPU-model proofs. RTC and soak campaigns stay stopped.

## Prepared artifacts

- `BUILD/rc1-maint-source-installer/installer-manifest.json`: sealed combined kit and exact
  source/target profiles. Both are generation 50; generation alone is never
  sufficient for admission.
- `BUILD/rc1-maint-source-installer/installer_plan.py`: offline prepare, verify and
  immediate-source restore. It has no execute command or serial import.
- `BUILD/rc1-maint-source-installer-tests/*-install/`: complete synthetic install
  plans, standalone RAM S19, ten 4096-byte transfer blocks, all four source
  and expected flash banks, repeated capture fixtures and RAM restore S19.
- `BUILD/rc1-maint-source-installer-tests/*-restore/`: modeled return to the exact
  admitted r9 firmware, with current owner settings and fresh wear reservation.
- `BUILD/rc1-maint-source-installer-tests/report.json`: linked-installer evidence for
  2604/65C02 and 2609/65C816 E=1, each with EDU OFF and ON.

The synthetic USB identities start with `MODEL-`; these fixtures are **not**
board backups. Never substitute them for a future repeated hardware capture.
Host scripts and sample source consume no additional firmware ROM.

## What the installer preserves

Admission binds every system sector in both exact profiles, including the
unchanged monitors, vectors and tables. In the source profile B1:9 must match
the fully erased release reference. An occupied or unrecognized B1:9 refuses;
there is no overwrite/force option. B2 is bound conservatively as a complete
system bank, so an unexpected tail there also refuses.

Only these eight firmware sectors change:

| Sector | Purpose |
| --- | --- |
| B1:`$9000–$9FFF` | Source extension and CRC |
| B1:`$E000–$EFFF` | Same-size editor hooks |
| B2:`$8000–$8FFF` | MAINT source/firmware range protection |
| B2:`$9000–$9FFF` | MAINT map/access display |
| B2:`$A000–$AFFF` | MAINT source/DEBUG identities and compact help |
| B2:`$B000–$BFFF` | Checked SRAM restore hook |
| B2:`$D000–$DFFF` | Storage adapter and utility seal |
| B3:`$E000–$EFFF` | Named ASM directory and seals |

The existing RAM transaction engine reserves erase attempts durably before
erasing. The plan records its exact staging/firmware/activation order.
That is **ten erases** and ten 4 KiB transfers,
plus a program-only reservation record in the retained journal. Both B3:C/D
journal sectors participate; wear counts increase rather than replaying an old
snapshot. The selected monitor, configuration bytes and generation stay the
same. The plan records exact hashes after every operation.

B0, existing saved source/program records, all nonowned B1 sectors, unaffected
firmware sectors, monitor A/B, B1:F opcode tables/vectors, and unrelated flash
bytes remain byte-exact. B3:`$9000–$9BFF` is bound as immutable RTC code;
B3:`$9C00–$9FFF` timezone history is preserved as owner data, including records
that differ from erased build defaults. No B0 payload is included in the update.
The installer uses application RAM; a verified RAM archive/restoration is a
separate required part of the live workflow. An interrupted update can
leave mixed shared components: this is not an atomic firmware swap.

## Admission work before any hardware installation

The combined candidate closes the original integration holds:

1. B1:9 and B1:A receive sealed header/CRC map recognition. MAINT protects the
   B0:8-D source arena and B1:9/A/E/F, in addition to existing B2/B3 protections.
   MAINT's named SRAM-to-B0 copy also refuses. Generic monitor S is append-only;
   expert low-level monitor F remains explicit. There is no source reclamation.
2. The candidate keeps private utility entry addresses fixed, using reclaimed
   help alignment space. Source and installer model evidence binds its hash.
3. For each further trial, obtain authorization and fresh board evidence. Check
   the device-operation records and exclusive serial lease; do not resume an
   owner-stopped soak or RTC campaign.

The current owner authorization covers the bounded 2604 trial only. It does
not authorize another board, public promotion, RTC sampling or a soak campaign.

## Board matrix and evidence sheet

| Physical board | CPU | Initial preference to preserve | Required combinations |
| --- | --- | --- | --- |
| 2604 | 65C02 | Capture actual setting; last qualified MON B | MON A/B × EDU OFF/ON |
| 2609 | 65C816 E=1 | Capture actual setting; last qualified MON A | MON A/B × EDU OFF/ON |

Record actual board/USB identity, firmware hashes, serial transcript, EDU
hardware presence, discovery descriptor, RAM limit, initial LED value, monitor
selection, settings, journal sequence and 32 wear counts for every trial.
EDU OFF is a configuration test; document whether the EDU is physically removed
or merely disabled. A physical bare-board claim requires the former. Keep the
816 in E=1, D/DBR/PBR zero before and after each program. No native-mode claim.

## Future installation sequence, separately authorized

1. Confirm the board is idle, its owner-stopped campaigns stay stopped, and
   there is no pending RAM restore/reset/worker. Record the explicit USB serial;
   discover the current port rather than trusting a stale COM number. Confirm
   reset assistance and programmer recovery availability before changing shared
   firmware sectors.
2. Capture all four 32 KiB flash banks **twice** and compare exact bytes. Archive
   all application RAM `$0200–$64FF` (EDU ON) or `$0200–$66FF` (EDU OFF), twice
   verified, plus its restore S19. Preserve optional-service state, LED state and
   owner data. Validate both monitor seals and exact admitted release sectors.
3. Offline, create a fresh board-specific plan with the admitted kit:

   ```text
   python -B BUILD/rc1-maint-source-installer/installer_plan.py prepare --capture <fresh-capture> --out <new-plan>
   python -B BUILD/rc1-maint-source-installer/installer_plan.py verify --plan <new-plan>
   ```

   These commands only build/verify files. They must refuse an unknown image,
   changed capture, torn journal, exhausted wear counter, missing repeated bank,
   missing RAM escrow, or non-erased B1:9. Inspect the exact ten-erase order
   and all-four-bank expected hashes. Recheck live flash matches the capture
   immediately before any separately authorized execution.
4. With the completed admission/live workflow, load only the verified RAM
   installer; send only its bound transfer blocks. Reserve wear first and keep
   all readback receipts. On any refusal, stop and retain the partial state.
   Do not run ASM while components may be mixed. Do not retry with old escrow
   or roll back journal/wear history.
5. Require installer completion, then press physical RESET when prompted by
   the verified RAM installer. Verify the boot, active monitor, both monitor
   seals, discovery, current journal and all four banks against the plan.
   Restore the complete original application RAM and reread it twice afterward.

## Future functional tests

For each row/combination in the matrix:

1. Take a fresh application-RAM archive for the active configuration. Changing
   EDU mode or launching ASM changes buffer ownership; do not reuse an archive
   with the wrong discovered ceiling. Do not change RTC time or initialize,
   format, resize or reclaim owner SRAM/WORK storage.
2. Read B0 in full. Identify **four whole erased sectors** within `$8000–$DFFF`
   for `CS1`, `CS2`, `E311`, `E312`, using fresh unique names if any already
   exist. Record the allocation. Never erase owner data to make space. If four
   sectors are unavailable, do not begin that flash exercise; report it as
   unrun or agree a smaller/new allocation with the owner. Allocate `CS1/CS2`
   to the first EDU-OFF write trial and `E311/E312` to the first EDU-ON write
   trial. This exercises flash writing in both configurations using four
   sectors total. The bare-SXB EDU-absent check can paste/assemble without
   saving, or load the EDU source after its EDU-ON save trial.
3. Run the relevant [workbook](SOURCE_DEVELOPMENT_WORKBOOK.md) end to end in
   those two initial write trials. In subsequent matrix combinations, LOAD,
   assemble, debug and execute the existing versions; do not repeat their
   new-name SAVE steps or describe those repeats as additional save trials.
   Capture paste,
   LIST, SAVE, ASM, S19, QUIT, BRK stops, S, C, HOLD, LOAD, numbered edit,
   new-name SAVE and changed executable bytes. Attempt the same flash name
   twice: expect `$50` and zero additional flash bytes programmed. Verify a
   missing source refuses without changing the live document. Verify dirty
   LOAD cancellation preserves it and `YES` replaces it.
4. Visually verify all eight CS sequences at the supplied four addresses. The
   owner has confirmed no hardware is attached to these windows. Record whether
   individual and paired strobes are visible; adjust the documented dwell
   constant and rebuild if needed. Do not interpret perceived brightness as
   a calibrated timing measurement.
5. With EDU ON, observe all 31 LED patterns in order, console `01–1F`, and entry
   LED restoration at the finished BRK. Repeat with Ctrl-C early, mid-sequence
   and near the end; cleanup must precede the final BRK. With EDU OFF, the EDU
   sample must print `E`, return, and perform no PIA access. The CS sample must
   work in either configuration. Capture logic-analyzer I/O traces if electrical
   confirmation is required; CPU-model traces alone are not that evidence.
6. In the initialized EDU configuration, repeat a source save/load using SRAM
   with an unused name. Verify same-name replacement, source integrity and
   write-protection restoration, preserving unrelated records. If SRAM is
   uninitialized, record this case as unrun; do not format it implicitly.
7. After a controlled reset, LOAD each new flash source and assemble identical
   executable bytes. Ordinary monitor R must refuse SF source as executable.
   Read all four flash banks; compare every byte outside the exact newly
   allocated B0 records and the separately expected firmware/journal changes.
   Source SAVE performs **zero sector erases**, so erase counts must not change
   during source-only trials.
8. Clear breakpoints/registrations via normal HOLD/X as appropriate. Restore
   and reread the correct RAM archive, original monitor preference and EDU
   configuration through the admitted workflows. Record any restoration writes
   and wear honestly. Leave the campaign stopped and the board idle.

Four source versions use four sectors per board, independent of monitor slot;
subsequent matrix trials may **read/reassemble** those names, but cannot resave
them. More new-name write trials require additional erased sectors. Plan the
finite arena across the whole campaign; do not promise all variants can append
four fresh records into the same six-sector arena.

## Restore and fault handling

The source test records may be retained as campaign-owned examples, with owner
agreement. Restoring r9 firmware deliberately preserves them in B0. A byte-exact
pretrial B0 restoration would require a separately admitted erase/reclaim
operation with new wear counts; it is not provided by this append-only prototype.

For an intact completed install, capture the current board twice and derive an
immediate-source restore from its original plan:

```text
python -B BUILD/rc1-maint-source-installer/installer_plan.py restore --original-plan <install-plan> --capture <new-capture> --out <restore-plan>
python -B BUILD/rc1-maint-source-installer/installer_plan.py verify --plan <restore-plan>
```

This restores only the admitted eight firmware sectors and retains newer owner
settings, B0 data and increasing wear. Wrong board/USB, mixed firmware or a torn
journal refuses. No hardware power cuts are part of this plan. If an accidental
interruption occurs, archive everything and use reviewed recovery/programmer
procedures from the private escrow. This kit does not guess or automatically
repair arbitrary partially programmed sectors.

Pass requires individual board/configuration receipts, exact preservation
comparisons and observed display/cancellation results. Until those exist, call
the result **offline tested**, not hardware qualified.
