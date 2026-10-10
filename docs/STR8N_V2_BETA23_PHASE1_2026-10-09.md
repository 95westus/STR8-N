# Beta23 phase 1: frozen candidate and backup-bound rehearsal

Phase 1 passed on October 9, 2026. Beta23 generation 32 is frozen locally;
boards 2512, 2205 and 2609 still run beta22 generation 31. Nothing was flashed.
This acceptance covers the freeze and offline upgrade rehearsal, not beta23
hardware qualification. Board 2604 remains excluded. STR8N-001 ACIA receive
on 2512/2205 remains deferred; the qualified console is USB.

## Frozen identity

Owner-local evidence: `output/qualification/beta23-phase1-2026-10-09`.
`frozen/build` retains all 495 build/input/model files; `frozen/source` retains
540 source/tool files from the exact working tree, including uncommitted and
untracked source. `freeze-receipt.json` records every SHA-256, Git base,
candidate audit, backup manifests, plans, model reports and installer hashes.
The complete frozen snapshot was independently rehashed after copying.
Clean-checkout reproduction and release packaging remain later gates.

| Receipt | SHA-256 |
|---|---|
| Freeze receipt | `bc98eda14a5c6959def40d6413cfa02d92c9a3de8ec241c9c3eb41b1974da4e2` |
| Build metadata | `cc487eb4d914772cc4149fc258b7a401d15897ce0302e90c85a939da52d370c2` |
| Bound candidate audit | `7f26f4cb166268e8a8a86331f1f221461b14e5d20e49a5a101f8176ac6e97bb3` |

The candidate audit passes all nine bound model receipts and sealed assets,
with unchanged CLOCK 1.6 and fixed recovery. This phase reran the reset-notice
and compact-display models and all 46 executed SPI ownership guard cases.
Reset notices pass both directions, cancellation, ordinary-return persistence,
cold activation and clearance. Compact local boot/date rollover, detailed
TIME/CLOCK/EUI, EDU OFF and modeled hardware/storage preservation pass.

## Fresh backups and exact installers

Read-only flash acquisition captured all four banks twice on each board;
each independent repeat matched, totaling 131,072 bytes per complete image.
The backup tool kept DTR/RTS inactive and sent only console/bank/dump commands.
Initial sandbox port opens failed before board access; elevated read-only
captures succeeded. Accepted backups are under `<board>/fresh/prior`.

| Board | Port | Saved EDU | Installer SHA-256 |
|---|---|---|---|
| 2512 | COM4 | OFF (`A5`) | `52b47a6a42aba9d2d1258d8fcb3bc11bb749fba1a40a437f60e80170ffa50e17` |
| 2205 | COM3 | ON (`00`) | `3d9071166225a0951ae5addbf074cbed1215a61a4936f87c478717d0337fd6c5` |
| 2609 | COM8 | ON (`00`) | `1a4083c536e086c6164876a3a3319d205af92c7a5c8c1e8249c2dba72b6c318d` |

`tools/prepare_v2_compact_boot_upgrade.py` refuses mismatched repeat backups,
non-beta22 source code/slots, changed CLOCK, and invalid candidate receipts.
It prepares eight sectors in this order:

```text
B3:C  B3:8  B3:9  B2:D  B2:C  B2:E  B3:B  B3:A
```

This updates metadata, the relinked provider/journal, sealed status/local
assets and B/A monitor slots. It is not a text-only patch. B3:9's identity and
offset tail is copied exactly. Complete B0/B1, CLOCK/MAINT/EDU/WORK and other
saved records, fixed recovery, saved EDU and untouched asset-sector bytes
are preserved. Metadata sequence advances once; each of the eight affected
sector wear counters advances once. No SRAM format or RTC/EEPROM write is
part of the installer.

For each board, `tools/test_v2_rtc_upgrade.py` executed the exact installer in
the emulator and compared every byte of all four final banks with the planned
images. Actual FNV opcodes were checked before accelerating long hash loops.
Erase order matched the plan; stale target-bank preimages and corrupt staged
payloads refused before any flash mutation. All three passed. Plans, payloads,
expected images, installers and model receipts remain under
`<board>/fresh/upgrade`, bound by the freeze receipt.

The tracked-file/history/release-ZIP backup-exclusion audit passed. Raw board
images and the frozen working snapshot remain ignored and owner-local.

## Next gate

Use this exact frozen build and these backup-bound installers for the separate
authorized hardware qualification run. Recheck current preimages before any
upload; changed preimages require fresh backups and a new bound rehearsal.
After successful upload, the halted installer requires physical main-board
RESET (2609 S2/RESB). Beta23 A/B starts, notices, interrupts, time/EUI, full
device preservation, interruption/recovery and the 48–72-hour soak remain
pending. Firmware/source changes invalidate this freeze and require affected
gates to be rerun. See the [RC plan](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md).
