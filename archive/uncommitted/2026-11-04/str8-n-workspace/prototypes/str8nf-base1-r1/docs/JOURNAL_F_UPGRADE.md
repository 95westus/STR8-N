# Existing-journal F upgrade to frozen BASE1 / PR05

Source implementation: `migration-host/nf_upgrade.py`, separate NFU1 RAM
engine under `migrator/upgrade/`. Factory provisioning continues to refuse
existing-journal F upgrades; it never resets history to perform an upgrade.
Frozen BASE1 F 0.3.0 g00000001 and the factory NFM1 engine remain unchanged.
The new RAM variant was assembled once without CPU/flash models. The later
authorized [2512 hardware case](2512_BASE1_ACCEPTANCE.md) passed its known-b15
upgrade with exact preservation. Interruption and other-platform acceptance
remain pending. The 0.3.0-rc1 candidate now includes this command and prebuilt
engine. The [2609 extracted-ZIP test](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md)
passed the same existing-SNBT path on 65C816 emulation/FT245.

The accepted work order is existing-journal upgrade, BASE1 acceptance, then
WDC migration acceptance. The one-reservation/F-only 2512 trial was later
authorized and completed; additional writes/fault tests remain outside that
scope. Packaging adds no new hardware authorization.
Board 2205 remains excluded.

The board-specific [2512 acceptance plan](2512_UPGRADE_BASE1_TEST_PLAN.md)
defines fresh-capture gates, the archived D300 reference delta and independent
preservation checks. Archived captures marked `reference_only: true` may be
prepared/inspected, but the CLI and execution API refuse them before device
access. A fresh reviewed capture is required for any later authorized run.

## Supported transaction

The source must contain clean, committed SNBT history and either the exact
known project b15 F (SHA-256 below), or already matching BASE1 F. This is not
an arbitrary old-ROM/WDC upgrade route. Unknown F/raw-L contracts are refused.

```text
Known b15 F: 1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8
Target BASE1 F: 8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1
```

The planner selects a completely erased 256-byte page in C/D. It clones the
entire newest committed record, including unknown/reserved application fields,
saved boot policy, monitor-generation field and prior-history mask. It changes
only sequence (+1), the F erase-attempt reservation (+1), and the dependent
header/record CRCs. Every retained record and every other wear counter stays
unchanged. It never erases C or D or reserves an erase of either journal sector.

The NFU1 engine runs entirely from RAM and calls no old/new F or monitor code:

1. Verify its complete self-image/plan, all four source-bank FNV guards and the
   BF/B5 flash chip. Wait for the single Y confirmation; Ctrl-C here writes nothing.
2. Recheck self/source guards. Require the selected C/D page to be all FF.
   Program the staged reservation with commit byte FF, compare all 256 bytes,
   then program byte page+FF to 00 last and verify it.
3. Verify the complete B3 hash including that committed reservation. Print
   `JOURNAL: F reservation committed and full B3 verified`.
4. Only now accept the 4096-byte frozen F transfer. Verify its FNV and the
   complete current B3 preimage before issuing the single reserved F erase.
   Program/compare F, then verify all four final banks.
5. Halt for physical RESET. The host intercepts the BASE1 chooser with S,
   verifies its exact identity, independently reads all four final banks through
   matching READBACK and compares SHA-256. Restore and read back original
   owner RAM 0200-66FF and ZP 00-DF, then stop at REC>.

The F reservation remains committed if transfer, reset or power fails after
the append, even if no F erase ultimately occurred. It is a conservative
attempt reservation, not proof that an erase completed. It is never rolled
back to make counts appear lower. Before the commit, the old committed record
remains authoritative and F has not been erased. Actual interruption behavior
still needs hardware qualification.

Already matching BASE1 F produces an offline no-op plan without incrementing
anything or opening a device. Full journals, sequence/counter exhaustion,
unknown/torn/legacy/conflicting/regressing history and unsupported source F
are refused. Journal garbage collection and inspected damaged-history repair
remain separate work; this path does not erase history to obtain append space.

## Original capture and preparation

Use the existing private repeated-capture format accepted by nf_migrate:
`b0.bin` through `b3.bin`, corresponding `-repeat.bin` files, and original
`owner-ram.bin` / `owner-zp.bin` plus repeats. Banks must be 32768 bytes each;
RAM 25856 bytes, ZP 224 bytes. Each repeated pair must be separate identical
files. Original RAM must precede every helper upload; working helper RAM is
not a replacement for it.

`capture.json` must declare schema 1, the selected cpu/board_model,
`source_kind: "nf-recovery"`, `method: "independent-double-read"`,
`owner_original_before_helpers: true` and the exact `usb_serial` string.
Original capture timing is an operator declaration; the host verifies files,
not when they were captured. Live device source guards must still match all
four captured banks before mutation.

Preparation is offline and opens no port:

```text
python migration-host/nf_upgrade.py prepare --capture PRIVATE-ORIGINAL-CAPTURE --cpu 65c02 --out PRIVATE-UPGRADE-PLAN
python migration-host/nf_upgrade.py inspect --plan PRIVATE-UPGRADE-PLAN
```

The output binds the exact target F, all original captures, reservation frame,
complete final-bank images, sealed NFU1 engine and descending-copy raw-L wrapper.
Private plans contain owner data and must not enter Git/public kits.

## Execution from the complete operator kit

The source CLI has an `execute` subcommand taking `--plan`, `--port`, `--out`,
`--execute` and `--allow-unqualified`. Both explicit flags are required before
opening the USB port; the port must match the capture's USB serial. Use the
complete 0.3.0 operator kit, which includes the host, prebuilt engine and wrapper
dependency. Individual files copied into an older kit are insufficient.
Original capture remains a separate operator precondition; see rc1 errata.

The host saves durable phases before Y and before providing F bytes. Missing
reservation proof means no F payload is sent. No flash or RAM retry, automatic
reset or automatic replay is attempted after failure. If the RAM engine halts,
owner restoration remains pending; retain power, original captures and phase
logs for an inspected recovery procedure.

Raw L does not independently read back the relocation wrapper. NFU1 must pass
its self/source checks before Y. Hardware acceptance must cover this boundary,
append commit/power failures, F transfer/erase failures, reset into the exact
BASE1 image, independent bank readback and original-RAM restoration.

Saved defaults/images are preserved rather than converted to recovery defaults.
That does not prove old images are compatible with BASE1 private interfaces.
The live acceptance path must intercept S and finish at recovery; booting old
monitor/application images is a separate compatibility check. Do not assume a
preserved A/B default is a qualified BASE1 OS.
